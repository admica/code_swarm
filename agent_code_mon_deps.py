#!/usr/bin/env python3
# PATH: ./agent_code_mon_deps.py
"""
Agent that analyzes Python file dependencies and generates Mermaid diagrams.
"""
import sys
import time
import os
import logging
import ast
import configparser
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from pathlib import Path
from typing import Dict, List, Set, Optional, Tuple
import importlib.util
import re
import requests

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('agent_code_mon_deps.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('agent_code_mon_deps')

class ConfigManager:
    """Manages configuration for the dependency graph agent."""

    def __init__(self, config_path: str = 'config.ini'):
        self.config = configparser.ConfigParser()
        self.config_path = config_path
        self.load_config()

    def load_config(self) -> None:
        """Load configuration from config.ini file."""
        if not os.path.exists(self.config_path):
            logger.warning(f"Config file not found at {self.config_path}. Creating default configuration.")
            self.create_default_config()

        try:
            self.config.read(self.config_path)
        except configparser.Error as e:
            logger.error(f"Error reading config file: {e}")
            raise

    def create_default_config(self) -> None:
        """Create default configuration file."""
        self.config['agent_code_mon_deps'] = {
            'watch_patterns': '*.py',
            'ignore_patterns': '__pycache__/*,.*,test_*',
            'max_depth': '5',  # Maximum directory depth to search
            'group_by_directory': 'true',
            'include_external_deps': 'false',
            'diagram_direction': 'TD',  # TB (top-bottom), LR (left-right), etc.
            'ollama_model': 'llama3.2',
            'controller_url': 'http://localhost:8000',
            'enable_ai_analysis': 'true'
        }

        with open(self.config_path, 'w') as f:
            self.config.write(f)

    def get_config(self) -> Dict[str, str]:
        """Get configuration dictionary."""
        if 'agent_code_mon_deps' not in self.config:
            logger.warning("Configuration section missing, creating default")
            self.create_default_config()
        return self.config['agent_code_mon_deps']

class DependencyAnalyzer:
    """Analyzes Python code dependencies."""

    def __init__(self, root_path: str, config: Dict[str, str]):
        """Initialize the analyzer with root path and configuration."""
        self.root_path = os.path.abspath(root_path)
        self.config = config
        self.max_depth = int(config.get('max_depth', '5'))
        self.group_by_directory = config.get('group_by_directory', 'true').lower() == 'true'
        self.include_external_deps = config.get('include_external_deps', 'false').lower() == 'true'
        self.diagram_direction = config.get('diagram_direction', 'TD')
        self.enable_ai_analysis = config.get('enable_ai_analysis', 'true').lower() == 'true'
        self.controller_url = config.get('controller_url', 'http://localhost:8000')
        self.ollama_model = config.get('ollama_model', 'llama3.2')

        # Cache for analyzed files
        self.file_cache: Dict[str, Dict] = {}

    def get_module_name(self, file_path: str) -> str:
        """Convert file path to module name."""
        rel_path = os.path.relpath(file_path, self.root_path)
        module_name = os.path.splitext(rel_path)[0].replace(os.sep, '.')
        return module_name

    def get_all_python_files(self) -> List[str]:
        """Get all Python files in the project."""
        python_files = []
        for root, _, files in os.walk(self.root_path):
            depth = root[len(self.root_path):].count(os.sep)
            if depth > self.max_depth:
                continue

            for file in files:
                if file.endswith('.py') and not any(
                    pattern in file for pattern in self.config['ignore_patterns'].split(',')
                ):
                    python_files.append(os.path.join(root, file))
        return python_files

    def analyze_imports(self, node: ast.AST, file_path: str) -> Dict[str, Set[str]]:
        """Analyze import statements in AST.

        Returns:
            Dict with 'modules' and 'names' containing imported items
        """
        imports = {'modules': set(), 'names': set()}
        module_dir = os.path.dirname(file_path)

        def resolve_relative_import(level: int, module: Optional[str]) -> Optional[str]:
            """Resolve a relative import to an absolute path."""
            try:
                current_path = Path(module_dir)
                for _ in range(level - 1):
                    if current_path.parent == current_path:  # At root
                        return None
                    current_path = current_path.parent

                if module:
                    module_path = current_path / module.replace('.', os.sep)
                else:
                    module_path = current_path

                if os.path.exists(f"{module_path}.py"):
                    return str(module_path.relative_to(self.root_path)).replace(os.sep, '.')
                elif os.path.isdir(module_path) and os.path.exists(module_path / '__init__.py'):
                    return str(module_path.relative_to(self.root_path)).replace(os.sep, '.')

                return None
            except (ValueError, RuntimeError):
                return None

        for node in ast.walk(node):
            if isinstance(node, ast.Import):
                for name in node.names:
                    if '.' in name.name:
                        # Split module.attribute style imports
                        module, attr = name.name.split('.', 1)
                        imports['modules'].add(module)
                        imports['names'].add(name.name)
                    else:
                        imports['modules'].add(name.name)
                        if name.asname:
                            imports['names'].add(name.asname)
                        else:
                            imports['names'].add(name.name)

            elif isinstance(node, ast.ImportFrom):
                if node.level > 0:  # Relative import
                    resolved = resolve_relative_import(node.level, node.module)
                    if resolved:
                        imports['modules'].add(resolved)
                        for name in node.names:
                            full_name = f"{resolved}.{name.name}"
                            imports['names'].add(name.asname or name.name)
                            imports['names'].add(full_name)
                else:
                    if node.module:
                        imports['modules'].add(node.module)
                        for name in node.names:
                            full_name = f"{node.module}.{name.name}"
                            imports['names'].add(name.asname or name.name)
                            imports['names'].add(full_name)

        return imports

    def analyze_class_usage(self, node: ast.AST) -> Set[str]:
        """Analyze class usage in AST including inheritance and composition."""
        class_uses = set()

        for node in ast.walk(node):
            # Direct class usage
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                class_uses.add(node.id)

            # Attribute access (e.g., module.Class)
            elif isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Load):
                # Get the full attribute chain (e.g., 'module.submodule.Class')
                parts = []
                current = node
                while isinstance(current, ast.Attribute):
                    parts.append(current.attr)
                    current = current.value
                if isinstance(current, ast.Name):
                    parts.append(current.id)
                class_uses.add('.'.join(reversed(parts)))

            # Class inheritance
            elif isinstance(node, ast.ClassDef):
                for base in node.bases:
                    if isinstance(base, ast.Name):
                        class_uses.add(base.id)
                    elif isinstance(base, ast.Attribute):
                        parts = []
                        current = base
                        while isinstance(current, ast.Attribute):
                            parts.append(current.attr)
                            current = current.value
                        if isinstance(current, ast.Name):
                            parts.append(current.id)
                        class_uses.add('.'.join(reversed(parts)))

            # Type annotations
            elif isinstance(node, ast.AnnAssign) and node.annotation:
                if isinstance(node.annotation, ast.Name):
                    class_uses.add(node.annotation.id)
                elif isinstance(node.annotation, ast.Attribute):
                    parts = []
                    current = node.annotation
                    while isinstance(current, ast.Attribute):
                        parts.append(current.attr)
                        current = current.value
                    if isinstance(current, ast.Name):
                        parts.append(current.id)
                    class_uses.add('.'.join(reversed(parts)))

        return class_uses

    def analyze_file(self, file_path: str) -> Dict:
        """Analyze a Python file for dependencies."""
        try:
            with open(file_path, 'r') as f:
                content = f.read()

            tree = ast.parse(content)

            # Get defined classes and functions
            defined_classes = {
                node.name
                for node in ast.walk(tree)
                if isinstance(node, ast.ClassDef)
            }

            defined_functions = {
                node.name
                for node in ast.walk(tree)
                if isinstance(node, ast.FunctionDef)
            }

            # Get imports and class usage
            imports = self.analyze_imports(tree, file_path)
            class_uses = self.analyze_class_usage(tree)

            return {
                'path': file_path,
                'module': self.get_module_name(file_path),
                'imports': imports,
                'defined_classes': defined_classes,
                'defined_functions': defined_functions,
                'class_uses': class_uses
            }
        except Exception as e:
            logger.error(f"Error analyzing {file_path}: {e}")
            return {
                'path': file_path,
                'module': self.get_module_name(file_path),
                'imports': set(),
                'defined_classes': set(),
                'defined_functions': set(),
                'class_uses': set()
            }

    def analyze_project(self) -> Dict[str, List[str]]:
        """Analyze all Python files in the project."""
        dependencies = {}
        python_files = self.get_all_python_files()

        # First pass: analyze all files
        for file_path in python_files:
            self.file_cache[file_path] = self.analyze_file(file_path)

        # Second pass: resolve dependencies
        for file_path, info in self.file_cache.items():
            deps = set()

            # Check imports - we need exact matches now
            imports = info.get('imports', {})
            for other_path, other_info in self.file_cache.items():
                if other_path != file_path:  # Don't count self-dependencies
                    other_module = other_info['module']
                    # Check if the module is directly imported
                    if other_module in imports.get('modules', set()):
                        deps.add(other_path)
                    # Check if any specific names from the module are used
                    used_names = imports.get('names', set())
                    defined_items = other_info['defined_classes'].union(other_info['defined_functions'])
                    if any(name in defined_items for name in used_names):
                        deps.add(other_path)

            # Check class usage - match only with defined classes
            for class_name in info.get('class_uses', set()):
                for other_path, other_info in self.file_cache.items():
                    if other_path != file_path:  # Don't count self-dependencies
                        if class_name in other_info['defined_classes']:
                            # Verify it's not just a similar name
                            module_prefix = other_info['module'].split('.')[-1]
                            if (f"{module_prefix}.{class_name}" in info.get('imports', {}).get('names', set()) or
                                any(imp.endswith(module_prefix) for imp in info.get('imports', {}).get('modules', set()))):
                                deps.add(other_path)

            dependencies[file_path] = sorted(list(deps))

            logger.debug(f"Dependencies for {file_path}:")
            logger.debug(f"  Imports: {imports}")
            logger.debug(f"  Class uses: {info.get('class_uses', set())}")
            logger.debug(f"  Resolved deps: {deps}")

        return dependencies

    def generate_mermaid(self, dependencies: Dict[str, List[str]]) -> str:
        """Generate Mermaid diagram from dependencies."""
        if self.group_by_directory:
            return self._generate_grouped_mermaid(dependencies)
        return self._generate_flat_mermaid(dependencies)

    def _generate_flat_mermaid(self, dependencies: Dict[str, List[str]]) -> str:
        """Generate flat Mermaid diagram."""
        mermaid = f"graph {self.diagram_direction}\n"

        # Add nodes
        for file_path in dependencies.keys():
            node_id = self.get_module_name(file_path).replace('.', '_')
            node_label = os.path.basename(file_path)
            mermaid += f"    {node_id}[{node_label}]\n"

        # Add relationships
        for file_path, deps in dependencies.items():
            source_id = self.get_module_name(file_path).replace('.', '_')
            for dep in deps:
                target_id = self.get_module_name(dep).replace('.', '_')
                mermaid += f"    {source_id} --> {target_id}\n"

        return mermaid

    def _generate_grouped_mermaid(self, dependencies: Dict[str, List[str]]) -> str:
        """Generate Mermaid diagram with directory grouping."""
        mermaid = f"graph {self.diagram_direction}\n"

        # Track directories
        directories = set()
        for file_path in dependencies.keys():
            rel_path = os.path.relpath(file_path, self.root_path)
            dir_path = os.path.dirname(rel_path)
            if dir_path:
                directories.add(dir_path)

        # Add subgraphs for directories
        for directory in sorted(directories):
            dir_id = directory.replace(os.sep, '_')
            mermaid += f"    subgraph {dir_id}[{directory}]\n"

            # Add nodes for files in this directory
            for file_path in dependencies.keys():
                rel_path = os.path.relpath(file_path, self.root_path)
                if os.path.dirname(rel_path) == directory:
                    node_id = self.get_module_name(file_path).replace('.', '_')
                    node_label = os.path.basename(file_path)
                    mermaid += f"        {node_id}[{node_label}]\n"

            mermaid += "    end\n"

        # Add nodes for files in root
        for file_path in dependencies.keys():
            rel_path = os.path.relpath(file_path, self.root_path)
            if not os.path.dirname(rel_path):
                node_id = self.get_module_name(file_path).replace('.', '_')
                node_label = os.path.basename(file_path)
                mermaid += f"    {node_id}[{node_label}]\n"

        # Add relationships
        for file_path, deps in dependencies.items():
            source_id = self.get_module_name(file_path).replace('.', '_')
            for dep in deps:
                target_id = self.get_module_name(dep).replace('.', '_')
                mermaid += f"    {source_id} --> {target_id}\n"

        return mermaid

    def get_ai_insights(self, dependencies: Dict[str, List[str]]) -> Optional[str]:
        """Get AI insights about the project's dependency structure.
        
        Args:
            dependencies: Dictionary of file dependencies
            
        Returns:
            AI analysis text or None if disabled or service unavailable
        """
        if not self.enable_ai_analysis:
            return None

        try:
            # First check if controller is available
            try:
                requests.get(f"{self.controller_url}/llm/health", timeout=1)
            except requests.exceptions.RequestException:
                logger.warning("Controller service not available, skipping AI analysis")
                return None

            # Build a structural analysis of the dependency graph
            analysis = {
                "total_files": len(dependencies),
                "files_with_deps": len([f for f in dependencies.values() if f]),
                "max_deps": max((len(deps) for deps in dependencies.values()), default=0),
                "circular_deps": [],
                "highly_coupled": []
            }

            # Find circular dependencies
            for file_path, deps in dependencies.items():
                for dep in deps:
                    if file_path in dependencies.get(dep, []):
                        pair = tuple(sorted([
                            os.path.relpath(file_path, self.root_path),
                            os.path.relpath(dep, self.root_path)
                        ]))
                        if pair not in analysis["circular_deps"]:
                            analysis["circular_deps"].append(pair)

            # Find highly coupled files (many dependencies)
            threshold = analysis["max_deps"] * 0.7  # 70% of max as threshold
            for file_path, deps in dependencies.items():
                if len(deps) >= threshold:
                    analysis["highly_coupled"].append({
                        "file": os.path.relpath(file_path, self.root_path),
                        "dep_count": len(deps)
                    })

            # Create the prompt
            prompt = f"""Analyze this Python project's dependency structure:

Project Statistics:
- Total Python files: {analysis['total_files']}
- Files with dependencies: {analysis['files_with_deps']}
- Maximum dependencies for a single file: {analysis['max_deps']}

{f'''Circular Dependencies Found:
{chr(10).join(f"- {a} <-> {b}" for a, b in analysis['circular_deps'])}''' if analysis['circular_deps'] else 'No circular dependencies found.'}

{f'''Highly Coupled Files:
{chr(10).join(f"- {f['file']} ({f['dep_count']} dependencies)" for f in analysis['highly_coupled'])}''' if analysis['highly_coupled'] else 'No highly coupled files found.'}

Please provide:
1. An assessment of the project's modularity
2. Potential issues or anti-patterns in the dependency structure
3. Specific recommendations for improvement
Keep the response under 200 words."""

            response = requests.post(
                f"{self.controller_url}/llm/deps/analyze",
                json={
                    "prompt": prompt,
                    "model": self.ollama_model,
                    "agent": "deps"
                },
                timeout=30
            )

            if response.status_code == 404:
                logger.warning("Controller LLM endpoint not found, skipping AI analysis")
                return None

            response.raise_for_status()
            result = response.json()
            
            if result.get('error'):
                logger.warning(f"LLM error: {result['error']}")
                return None
                
            return result.get('response')
            
        except requests.exceptions.RequestException as e:
            logger.warning(f"Controller service error: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error in AI analysis: {e}")
            return None

class DependencyVisualizer:
    """Generates and maintains dependency visualizations."""

    def __init__(self, analyzer: DependencyAnalyzer):
        self.analyzer = analyzer

    def update_visualization(self) -> None:
        """Update dependency visualization files."""
        try:
            # Analyze project dependencies
            dependencies = self.analyzer.analyze_project()

            # Generate Mermaid diagram
            mermaid = self.analyzer.generate_mermaid(dependencies)

            # Get AI insights
            ai_insights = self.analyzer.get_ai_insights(dependencies)

            # Create visualization file
            vis_path = os.path.join(self.analyzer.root_path, 'dependency_graph.md')
            with open(vis_path, 'w') as f:
                f.write("# Project Dependency Graph\n\n")
                
                if ai_insights:
                    f.write("## AI Analysis\n\n")
                    f.write(ai_insights)
                    f.write("\n\n")
                
                f.write("## Visualization\n\n")
                f.write("```mermaid\n")
                f.write(mermaid)
                f.write("\n```\n\n")

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

            logger.info(f"Updated dependency visualization at {vis_path}")

        except Exception as e:
            logger.error(f"Error updating visualization: {e}")

class PyFileHandler(FileSystemEventHandler):
    """Handles Python file modification events."""

    def __init__(self, visualizer: DependencyVisualizer):
        self.visualizer = visualizer
        logger.info("File handler initialized")

    def on_modified(self, event) -> None:
        """Handle file modification events."""
        if event.is_directory:
            return

        if not event.src_path.endswith('.py'):
            return

        logger.info(f"Detected modification to {event.src_path}")
        self.visualizer.update_visualization()

def main(path: str) -> None:
    """Main function to run the dependency graph agent."""
    try:
        config_manager = ConfigManager()
        config = config_manager.get_config()

        analyzer = DependencyAnalyzer(path, config)
        visualizer = DependencyVisualizer(analyzer)
        event_handler = PyFileHandler(visualizer)

        # Generate initial visualization
        visualizer.update_visualization()

        observer = Observer()
        observer.schedule(event_handler, path, recursive=True)
        observer.start()

        logger.info(f"Started monitoring directory: {path}")

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Received shutdown signal")
            observer.stop()
        observer.join()

    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        logger.error("Please provide the directory path to monitor")
        sys.exit(1)

    path = sys.argv[1]
    main(path)
