#!/usr/bin/env python3
# PATH: ./agent_code_mon_deps.py
"""
Agent that analyzes Python and Lua file dependencies and generates Mermaid diagrams.

This agent monitors source files, analyzes their dependencies, and generates
visual representations of the dependency structure using Mermaid diagrams.
Supports both Python imports and Lua requires.
"""
import sys
import os
import logging
import ast
import asyncio
import time
from pathlib import Path
from typing import Dict, List, Set, Optional, Tuple, Any
import importlib.util
import re
from shared import LLMClient, config_manager, AgentLogger
from shared.file_monitor import FileMonitor
import fnmatch

# Set up logging
logger = AgentLogger('code_mon_deps')

# Constants
UPDATE_DELAY = 3.0  # seconds
DEFAULT_MAX_DEPTH = 5
REQUIRE_PATTERNS = [
    r'''(?:require|dofile|loadfile)\s*[\(\["']([^"\'\)]+)["'\)\]]''',  # Simple requires
    r'''(?:require|dofile|loadfile)\s*\(?([^"\'\)]+\.\.[\s\n]*[^"\'\)]+)\)?''',  # Concatenated
    r'''(?:require|dofile|loadfile)\s*\(\s*([^"\'\)]+)\s*\)'''  # Complex expressions
]

class DependencyAnalyzer:
    """Analyzes source code dependencies."""

    def __init__(self, root_path: str):
        """Initialize the analyzer.
        
        Args:
            root_path: The root directory to analyze
        """
        self.root_path = root_path
        self.logger = AgentLogger('code_mon_deps')
        self.llm_client = LLMClient('code_mon_deps')
        self._cache: Dict[str, List[str]] = {}
        self._dependents: Dict[str, Set[str]] = {}  # Track which files depend on each file
        self.config = config_manager.get_agent_config('code_mon_deps')
        
        # Load configuration with defaults
        self.skip_patterns = self.config.get('ignore_patterns', 'venv/*,__pycache__/*,.git/*').split(',')
        self.group_by_directory = self.config.get('group_by_directory', True)
        self.diagram_direction = self.config.get('diagram_direction', 'LR')
        self.enable_ai_analysis = self.config.get('enable_ai_analysis', True)
        
        # Analysis tuning parameters
        self.min_coupling_threshold = self.config.get('min_coupling_threshold', 8)  # Minimum number of dependencies to flag
        self.std_dev_multiplier = self.config.get('std_dev_multiplier', 2.0)  # How many standard deviations above mean to flag
        self.max_depth = self.config.get('max_depth', DEFAULT_MAX_DEPTH)  # Maximum depth for recursive dependency analysis
        
        # Cache and update behavior
        self.cache_enabled = self.config.get('cache_enabled', True)  # Whether to use caching
        self.partial_invalidation = self.config.get('partial_invalidation', True)  # Whether to use partial cache invalidation

    def clear_cache(self) -> None:
        """Clear all caches."""
        self._cache.clear()
        self._dependents.clear()

    def invalidate_file(self, file_path: str) -> None:
        """Invalidate a file and anything that depends on it (recursively)."""
        self.logger.debug(f"Invalidating cache for {file_path}")
        
        # Keep track of all files we need to invalidate
        to_invalidate = set()
        to_process = {file_path}
        
        # Find all files that depend on this one (recursively)
        while to_process:
            current = to_process.pop()
            if current not in to_invalidate:
                to_invalidate.add(current)
                # Add all files that depend on this one
                dependents = self._dependents.get(current, set())
                to_process.update(dependents)
        
        # Remove all affected files from cache
        for invalid_file in to_invalidate:
            self._cache.pop(invalid_file, None)
            self._dependents.pop(invalid_file, None)
        
        self.logger.debug(f"Invalidated {len(to_invalidate)} files")

    def should_skip_file(self, file_path: str) -> bool:
        """Check if a file should be skipped based on patterns."""
        rel_path = os.path.relpath(file_path, self.root_path)
        return any(
            fnmatch.fnmatch(rel_path, pattern.strip())
            for pattern in self.skip_patterns
            if pattern.strip()
        )

    def get_all_source_files(self) -> List[str]:
        """Get all source files in the project."""
        source_files = []
        for root, _, files in os.walk(self.root_path):
            for file in files:
                if not file.lower().endswith(('.py', '.lua')):
                    continue
                file_path = os.path.join(root, file)
                if not self.should_skip_file(file_path):
                    source_files.append(file_path)
                else:
                    self.logger.debug(f"Skipping file due to pattern match: {file_path}")
        return source_files

    def get_module_name(self, file_path: str) -> str:
        """Get module name from file path.
        
        Args:
            file_path: Absolute path to file
            
        Returns:
            Module name
        """
        rel_path = os.path.relpath(file_path, self.root_path)
        module_name = os.path.splitext(rel_path)[0].replace(os.sep, '.')
        return module_name

    def _get_node_style(self, file_path: str) -> str:
        """Get Mermaid node style based on file type."""
        if file_path.lower().endswith('.py'):
            return ':::python'
        elif file_path.lower().endswith('.lua'):
            return ':::lua'
        return ''

    def analyze_python_imports(self, file_path: str) -> List[str]:
        """Analyze Python imports in a file.
        
        Args:
            file_path: Path to Python file
            
        Returns:
            List of absolute paths to imported files
        """
        imports = []
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Match import statements
            import_patterns = [
                r'^import\s+([\w.]+)',  # import foo.bar
                r'^from\s+([\w.]+)\s+import',  # from foo.bar import
                r'^\s+import\s+([\w.]+)',  # indented import
                r'^\s+from\s+([\w.]+)\s+import'  # indented from import
            ]

            for pattern in import_patterns:
                for match in re.finditer(pattern, content, re.MULTILINE):
                    module_path = match.group(1)
                    # Convert module path to file path
                    file_path_parts = module_path.split('.')
                    potential_paths = [
                        os.path.join(self.root_path, *file_path_parts) + '.py',
                        os.path.join(self.root_path, *file_path_parts, '__init__.py')
                    ]
                    for potential_path in potential_paths:
                        if os.path.exists(potential_path):
                            imports.append(potential_path)
                            break

        except Exception as e:
            self.logger.error(f"Error analyzing Python imports in {file_path}: {str(e)}")

        return imports

    def analyze_lua_requires(self, file_path: str) -> List[str]:
        """Analyze Lua requires in a file.
        
        Args:
            file_path: Path to Lua file
            
        Returns:
            List of absolute paths to required files
        """
        requires = []
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Match require statements
            # Handle both require('module') and require "module"
            require_patterns = [
                r'require\s*\(\s*[\'"]([^\'"\)]+)[\'"]\s*\)',  # require('module')
                r'require\s*[\'"]([^\'"\)]+)[\'"]',  # require "module"
                r'require\s*\[\[([^\]]+)\]\]'  # require [[module]]
            ]

            for pattern in require_patterns:
                for match in re.finditer(pattern, content):
                    module_path = match.group(1)
                    # Convert module path to file path
                    file_path_parts = module_path.replace('.', os.sep).split(os.sep)
                    potential_paths = [
                        os.path.join(self.root_path, *file_path_parts) + '.lua',
                        os.path.join(self.root_path, *file_path_parts, 'init.lua')
                    ]
                    for potential_path in potential_paths:
                        if os.path.exists(potential_path):
                            requires.append(potential_path)
                            break

        except Exception as e:
            self.logger.error(f"Error analyzing Lua requires in {file_path}: {str(e)}")

        return requires

    def analyze_file(self, file_path: str) -> List[str]:
        """Analyze dependencies in a file with caching."""
        rel_path = os.path.relpath(file_path, self.root_path)
        
        if file_path in self._cache:
            self.logger.debug(f"Cache hit for {rel_path}")
            return self._cache[file_path]

        self.logger.debug(f"Cache miss for {rel_path}, analyzing file")
        if file_path.lower().endswith('.py'):
            self.logger.debug(f"Analyzing Python imports in {rel_path}")
            deps = self.analyze_python_imports(file_path)
        elif file_path.lower().endswith('.lua'):
            self.logger.debug(f"Analyzing Lua requires in {rel_path}")
            deps = self.analyze_lua_requires(file_path)
        else:
            self.logger.debug(f"Skipping unsupported file type: {rel_path}")
            deps = []

        # Clean up old dependencies before updating
        if file_path in self._dependents:
            old_deps = self._dependents.pop(file_path)
            self.logger.debug(f"Cleared {len(old_deps)} old dependencies for {rel_path}")
        
        # Update cache and track new dependents
        self._cache[file_path] = deps
        for dep in deps:
            if dep not in self._dependents:
                self._dependents[dep] = set()
            self._dependents[dep].add(file_path)
            self.logger.debug(f"Added {rel_path} as dependent of {os.path.relpath(dep, self.root_path)}")

        return deps

    def analyze_project(self) -> Dict[str, List[str]]:
        """Analyze all dependencies in the project."""
        self.logger.info("Starting project-wide dependency analysis")
        dependencies = {}
        source_files = self.get_all_source_files()
        self.logger.info(f"Found {len(source_files)} source files to analyze")
        
        for file_path in source_files:
            rel_path = os.path.relpath(file_path, self.root_path)
            if file_path not in self._cache:
                self.logger.info(f"Analyzing dependencies in {rel_path}")
                deps = self.analyze_file(file_path)
                self.logger.info(f"Found {len(deps)} dependencies for {rel_path}")
                if deps:
                    self.logger.debug(f"Dependencies for {rel_path}: {[os.path.relpath(d, self.root_path) for d in deps]}")
            else:
                self.logger.debug(f"Using cached dependencies for {rel_path}")
                deps = self._cache[file_path]
            dependencies[file_path] = deps
        
        self.logger.info(f"Completed analysis of {len(dependencies)} files")
        return dependencies

class DependencyMonitor:
    """Monitors source files for dependency changes."""

    def __init__(self, path: str):
        """Initialize the monitor.
        
        Args:
            path: The root directory to monitor.
        """
        self.analyzer = DependencyAnalyzer(path)
        self.visualizer = DependencyVisualizer(self.analyzer)
        self.file_monitor = FileMonitor('code_mon_deps', self.handle_file_change)
        self.queue = asyncio.Queue()
        self._task: Optional[asyncio.Task] = None
        
        # Load configuration
        self.config = config_manager.get_agent_config('code_mon_deps')
        self._update_delay = self.config.get('update_delay', UPDATE_DELAY)
        self._batch_window = self.config.get('batch_window', 1.0)  # Time window to batch changes
        self._max_queue_size = self.config.get('max_queue_size', 100)  # Maximum number of pending changes
        
        self._last_update = 0
        self._cache_lock = asyncio.Lock()
        logger.info("Dependency monitor initialized with update delay: %s", self._update_delay)

    def handle_file_change(self, file_path: str) -> None:
        """Handle file change event."""
        try:
            file_lower = file_path.lower()
            if not file_lower.endswith(('.py', '.lua')):
                return
                
            logger.info(f"Detected modification to {file_path}")
            asyncio.create_task(self.queue.put(file_path))
        except Exception as e:
            logger.error(f"Error handling file change for {file_path}: {str(e)}", exc_info=True)

    async def start_processing(self):
        """Start processing the file queue."""
        while True:
            try:
                file_path = await self.queue.get()
                
                # Apply debouncing
                now = time.time()
                if now - self._last_update < self._update_delay:
                    await asyncio.sleep(self._update_delay)
                self._last_update = now
                
                try:
                    # Use lock to protect cache and visualization operations
                    async with self._cache_lock:
                        if os.path.exists(file_path):
                            self.analyzer.invalidate_file(file_path)  # Only invalidate affected files
                            await self.visualizer.update_visualization()
                except Exception as e:
                    logger.error(f"Error updating visualization for {file_path}: {str(e)}", exc_info=True)
                finally:
                    self.queue.task_done()
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in queue processor: {str(e)}", exc_info=True)
                await asyncio.sleep(1)

    def start(self, path: str):
        """Start monitoring."""
        if not self._task or self._task.done():
            self._task = asyncio.create_task(self.start_processing())
        self.file_monitor.start(path)

    def stop(self):
        """Stop monitoring and clean up resources."""
        if self._task:
            self._task.cancel()
        self.file_monitor.stop()
        self.analyzer.clear_cache()
        # Ensure queue is empty
        while not self.queue.empty():
            try:
                self.queue.get_nowait()
            except asyncio.QueueEmpty:
                break

class DependencyVisualizer:
    """Generates and maintains dependency visualizations."""

    def __init__(self, analyzer: DependencyAnalyzer):
        """Initialize the visualizer.
        
        Args:
            analyzer: The dependency analyzer to use
        """
        self.analyzer = analyzer
        self.logger = AgentLogger('code_mon_deps')

    def generate_mermaid(self, dependencies: Dict[str, List[str]]) -> str:
        """Generate Mermaid diagram from dependencies.
        
        Args:
            dependencies: Dictionary mapping files to their dependencies
            
        Returns:
            Mermaid diagram markup
        """
        if self.analyzer.group_by_directory:
            return self._generate_grouped_mermaid(dependencies)
        return self._generate_flat_mermaid(dependencies)

    def _generate_flat_mermaid(self, dependencies: Dict[str, List[str]]) -> str:
        """Generate flat Mermaid diagram."""
        mermaid = f"graph {self.analyzer.diagram_direction}\n"
        
        # Add style definitions
        mermaid += "    classDef python fill:#2b5b84,stroke:#1a365d,color:#fff\n"
        mermaid += "    classDef lua fill:#000080,stroke:#000066,color:#fff\n"

        # Add nodes
        for file_path in dependencies.keys():
            node_id = self.analyzer.get_module_name(file_path).replace('.', '_')
            node_label = os.path.basename(file_path)
            style = self.analyzer._get_node_style(file_path)
            mermaid += f"    {node_id}[{node_label}] {style}\n"

        # Add relationships
        for file_path, deps in dependencies.items():
            source_id = self.analyzer.get_module_name(file_path).replace('.', '_')
            for dep in deps:
                target_id = self.analyzer.get_module_name(dep).replace('.', '_')
                mermaid += f"    {source_id} --> {target_id}\n"

        return mermaid

    def _generate_grouped_mermaid(self, dependencies: Dict[str, List[str]]) -> str:
        """Generate Mermaid diagram with directory grouping."""
        mermaid = f"graph {self.analyzer.diagram_direction}\n"
        
        # Add style definitions
        mermaid += "    classDef python fill:#2b5b84,stroke:#1a365d,color:#fff\n"
        mermaid += "    classDef lua fill:#000080,stroke:#000066,color:#fff\n"

        # Track directories
        directories = set()
        for file_path in dependencies.keys():
            rel_path = os.path.relpath(file_path, self.analyzer.root_path)
            dir_path = os.path.dirname(rel_path)
            if dir_path:
                directories.add(dir_path)

        # Add subgraphs for directories
        for directory in sorted(directories):
            dir_id = directory.replace(os.sep, '_')
            mermaid += f"    subgraph {dir_id}[{directory}]\n"

            # Add nodes for files in this directory
            for file_path in dependencies.keys():
                rel_path = os.path.relpath(file_path, self.analyzer.root_path)
                if os.path.dirname(rel_path) == directory:
                    node_id = self.analyzer.get_module_name(file_path).replace('.', '_')
                    node_label = os.path.basename(file_path)
                    style = self.analyzer._get_node_style(file_path)
                    mermaid += f"        {node_id}[{node_label}] {style}\n"

            mermaid += "    end\n"

        # Add nodes for files in root
        for file_path in dependencies.keys():
            rel_path = os.path.relpath(file_path, self.analyzer.root_path)
            if not os.path.dirname(rel_path):
                node_id = self.analyzer.get_module_name(file_path).replace('.', '_')
                node_label = os.path.basename(file_path)
                style = self.analyzer._get_node_style(file_path)
                mermaid += f"    {node_id}[{node_label}] {style}\n"

        # Add relationships
        for file_path, deps in dependencies.items():
            source_id = self.analyzer.get_module_name(file_path).replace('.', '_')
            for dep in deps:
                target_id = self.analyzer.get_module_name(dep).replace('.', '_')
                mermaid += f"    {source_id} --> {target_id}\n"

        return mermaid

    async def get_ai_insights(self, dependencies: Dict[str, List[str]]) -> Optional[str]:
        """Get AI insights about the dependency structure."""
        if not self.analyzer.enable_ai_analysis:
            return None

        try:
            deps_counts = [len(deps) for deps in dependencies.values()]
            avg_deps = sum(deps_counts) / len(dependencies) if dependencies else 0
            
            analysis = {
                "total_files": len(dependencies),
                "files_with_deps": len([f for f in dependencies.values() if f]),
                "max_deps": max((len(deps) for deps in dependencies.values()), default=0),
                "avg_deps": round(avg_deps, 2),
                "circular_deps": [],
                "highly_coupled": []
            }

            # Find circular dependencies
            for file_path, deps in dependencies.items():
                for dep in deps:
                    if file_path in dependencies.get(dep, []):
                        pair = tuple(sorted([
                            os.path.relpath(file_path, self.analyzer.root_path),
                            os.path.relpath(dep, self.analyzer.root_path)
                        ]))
                        if pair not in analysis["circular_deps"]:
                            analysis["circular_deps"].append(pair)

            # Use configured thresholds for coupling analysis
            if deps_counts:
                std_dev = (sum((x - avg_deps) ** 2 for x in deps_counts) / len(deps_counts)) ** 0.5
                threshold = avg_deps + (self.analyzer.std_dev_multiplier * std_dev)
                threshold = max(threshold, self.analyzer.min_coupling_threshold)
                
                for file_path, deps in dependencies.items():
                    if len(deps) >= threshold:
                        analysis["highly_coupled"].append({
                            "file": os.path.relpath(file_path, self.analyzer.root_path),
                            "dep_count": len(deps)
                        })

            # Create the prompt
            prompt = f"""Analyze this project's dependency structure:

Project Statistics:
- Total source files: {analysis['total_files']}
- Files with dependencies: {analysis['files_with_deps']}
- Average dependencies per file: {analysis['avg_deps']}
- Maximum dependencies for a single file: {analysis['max_deps']}

{f'''Circular Dependencies Found:
{chr(10).join(f"- {a} <-> {b}" for a, b in analysis['circular_deps'])}''' if analysis['circular_deps'] else 'No circular dependencies found.'}

{f'''Files with Notably High Coupling:
{chr(10).join(f"- {f['file']} ({f['dep_count']} dependencies)" for f in analysis['highly_coupled'])}''' if analysis['highly_coupled'] else 'No files with unusually high coupling found.'}

Please provide:
1. A balanced assessment of the project's modularity
2. Note any potential areas for improvement, but consider that some coupling is normal and necessary
3. If suggesting improvements, focus on significant patterns rather than isolated cases
Keep the response under 220 words and maintain a constructive tone."""

            result = await self.analyzer.llm_client.generate(
                prompt=prompt,
                max_tokens=1100,
                temperature=0.6
            )

            return result.get('response') if result else None

        except Exception as e:
            self.logger.error(f"Unexpected error in AI analysis: {e}")
            return None

    async def update_visualization(self) -> None:
        """Update dependency visualization files."""
        try:
            self.logger.info("Starting dependency visualization update")
            
            # Analyze project dependencies
            self.logger.info("Analyzing project dependencies...")
            dependencies = self.analyzer.analyze_project()
            self.logger.info(f"Found dependencies for {len(dependencies)} files")

            # Generate Mermaid diagram
            self.logger.info("Generating Mermaid diagram...")
            mermaid = self.generate_mermaid(dependencies)
            self.logger.debug("Mermaid diagram generated successfully")

            # Get AI insights if enabled
            ai_insights = None
            if self.analyzer.enable_ai_analysis:
                self.logger.info("Requesting AI analysis of dependencies...")
                ai_insights = await self.get_ai_insights(dependencies)
                if ai_insights:
                    self.logger.info("AI analysis received successfully")
                else:
                    self.logger.warning("AI analysis not available")

            # Create visualization file
            vis_path = os.path.join(self.analyzer.root_path, 'dependency_graph.md')
            self.logger.info(f"Writing visualization to {vis_path}")
            
            with open(vis_path, 'w') as f:
                f.write("# Project Dependency Graph\n\n")
                
                f.write("## Visualization\n\n")
                f.write("```mermaid\n")
                f.write(mermaid)
                f.write("\n```\n\n")

                if ai_insights:
                    f.write("## AI Analysis\n\n")
                    f.write(ai_insights)
                    f.write("\n\n")
                
                # Add dependency details
                f.write("## Detailed Dependencies\n\n")
                for file_path, deps in dependencies.items():
                    rel_path = os.path.relpath(file_path, self.analyzer.root_path)
                    f.write(f"### {rel_path}\n\n")
                    if deps:
                        f.write("Depends on:\n")
                        for dep in deps:
                            dep_rel_path = os.path.relpath(dep, self.analyzer.root_path)
                            f.write(f"- {dep_rel_path}\n")
                    else:
                        f.write("No dependencies\n")
                    f.write("\n")

            self.logger.info(f"Successfully updated dependency visualization at {vis_path}")

        except Exception as e:
            self.logger.error(f"Error updating visualization: {str(e)}", exc_info=True)
            raise

async def main(path: str) -> None:
    """Main function to run the dependency graph agent.
    
    Args:
        path: The root directory to monitor
    """
    try:
        # Initialize monitor
        monitor = DependencyMonitor(path)
        
        # Generate initial visualization before starting monitor
        vis_path = os.path.join(path, 'dependency_graph.md')
        if not os.path.exists(vis_path):
            logger.info("No existing dependency graph found. Generating initial visualization...")
            try:
                # Create event loop if needed (for subprocess case)
                loop = asyncio.get_event_loop()
                if loop.is_closed():
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                # Generate initial visualization
                await monitor.visualizer.update_visualization()
                logger.info("Initial dependency graph generated successfully")
            except Exception as e:
                logger.error(f"Failed to generate initial visualization: {e}", exc_info=True)
                raise
        else:
            logger.info(f"Found existing dependency graph at {vis_path}")
        
        # Start monitoring
        monitor.start(path)
        
        try:
            # Keep running until interrupted
            while True:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            logger.info("Dependency monitor shutting down...")
            monitor.stop()
            raise
            
    except Exception as e:
        logger.error(f"Error in dependency monitor: {str(e)}", exc_info=True)
        raise

if __name__ == '__main__':
    import sys
    if len(sys.argv) != 2:
        print("Usage: python agent_code_mon_deps.py <path>")
        sys.exit(1)
    try:
        asyncio.run(main(sys.argv[1]))
    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
