#!./venv/bin/python3
"""Dependency monitoring agent for analyzing Python and Lua file dependencies."""

import os
import re
import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, List, Set, Optional
from shared.base_agent import BaseAgent
from shared.file_monitor import FileMonitor
import websockets
from shared import config_manager, LLMClient
import fnmatch

logger = logging.getLogger('code_mon_deps')

class DependencyAgent(BaseAgent):
    """Agent that monitors and analyzes file dependencies."""

    def __init__(self, path: str):
        super().__init__('code_mon_deps')
        self.root_path = path
        self.graph_path = os.path.join(path, 'dependency_graph.md')
        
        # Add LLM client
        self.llm_client = LLMClient('code_mon_deps')
        
        # Pass the async handler directly - FileMonitor will now handle it properly
        self.file_monitor = FileMonitor('code_mon_deps', self.handle_file_change)
        
        # Load configurations
        self.config = config_manager.get_agent_config('code_mon_deps')
        controller_config = config_manager.get_controller_config()
        
        # Get ignore patterns from both configs
        default_patterns = ['venv/*', '__pycache__/*', '.git/*', 'venv_linux/*']
        agent_patterns = self.config.get('ignore_patterns', '').split(',')
        controller_patterns = controller_config.get('skip_list', '').split(',')
        
        # Combine and clean patterns
        self.ignore_patterns = []
        for patterns in [agent_patterns, controller_patterns, default_patterns]:
            self.ignore_patterns.extend([p.strip() for p in patterns if p.strip()])
            
        logger.info(f"Loaded ignore patterns: {self.ignore_patterns}")
        
        # Dependencies cache
        self._dependencies: Dict[str, List[str]] = {}
        self._cache_lock = asyncio.Lock()
        
        # File processing queue
        self.queue = asyncio.Queue()
        self._processing_task: Optional[asyncio.Task] = None
        
        # Connection state
        self._connection_confirmed = False
        self._connection_lock = asyncio.Lock()
        
        # Import patterns
        self.python_patterns = [
            r'^import\s+([\w.]+)',
            r'^from\s+([\w.]+)\s+import',
            r'^\s+import\s+([\w.]+)',
            r'^\s+from\s+([\w.]+)\s+import'
        ]
        self.lua_patterns = [
            r'require\s*\(\s*[\'"]([^\'"\)]+)[\'"]\s*\)',
            r'require\s*[\'"]([^\'"\)]+)[\'"]',
            r'require\s*\[\[([^\]]+)\]\]'
        ]

    def should_ignore_path(self, file_path: str) -> bool:
        """Check if a file should be ignored based on config patterns."""
        rel_path = os.path.relpath(file_path, self.root_path)
        for pattern in self.ignore_patterns:
            if pattern.strip() and fnmatch.fnmatch(rel_path, pattern.strip()):
                logger.debug(f"Ignoring {rel_path} (matches pattern {pattern})")
                return True
        return False

    async def connect(self) -> bool:
        """Establish connection with proper handshake."""
        async with self._connection_lock:
            try:
                # Connect to agent endpoint
                self.ws_agent = await websockets.connect("ws://localhost:8000/ws/agent")
                logger.info("WebSocket connection established")
                
                # Send initial connect message
                connect_message = {
                    "type": "agent_connect",
                    "timestamp": datetime.now().isoformat(),
                    "agent": self.name,
                    "data": {
                        "status": self.get_status()
                    }
                }
                await self.ws_agent.send(json.dumps(connect_message))
                logger.info("Sent initial connect message")
                
                # Wait for confirmation
                try:
                    response = await asyncio.wait_for(
                        self.ws_agent.recv(),
                        timeout=5.0
                    )
                    data = json.loads(response)
                    
                    if data.get('type') == 'connection_confirmed':
                        self._connection_confirmed = True
                        logger.info("Connection confirmed by controller")
                        
                        # Only connect to logs after agent connection is confirmed
                        try:
                            self.ws_logs = await websockets.connect("ws://localhost:8000/ws/logs")
                            logger.info("Connected to log stream")
                            return True
                        except Exception as e:
                            logger.error(f"Failed to connect to log stream: {e}")
                            await self.disconnect()
                            return False
                    else:
                        logger.error(f"Unexpected response: {data}")
                        await self.disconnect()
                        return False
                        
                except asyncio.TimeoutError:
                    logger.error("Timeout waiting for connection confirmation")
                    await self.disconnect()
                    return False
                    
            except Exception as e:
                logger.error(f"Connection failed: {e}")
                await self.disconnect()
                return False

    async def disconnect(self) -> None:
        """Clean disconnect from all connections."""
        async with self._connection_lock:
            self._connection_confirmed = False
            
            if self.ws_agent:
                try:
                    await self.ws_agent.close()
                except Exception as e:
                    logger.error(f"Error closing agent connection: {e}")
                finally:
                    self.ws_agent = None
            
            if self.ws_logs:
                try:
                    await self.ws_logs.close()
                except Exception as e:
                    logger.error(f"Error closing logs connection: {e}")
                finally:
                    self.ws_logs = None

    async def ensure_connection(self) -> bool:
        """Ensure we have an active connection."""
        if not self.ws_agent or not self._connection_confirmed:
            return await self.connect()
        return True

    async def scan_directory(self) -> None:
        """Scan directory for Python and Lua files."""
        logger.info("Starting directory scan")
        await self.send_activity(
            action="scanning_directory",
            file_path=self.root_path
        )
        
        files_found = 0
        files_ignored = 0
        
        for root, _, files in os.walk(self.root_path):
            for file in files:
                if file.lower().endswith(('.py', '.lua')):
                    file_path = os.path.join(root, file)
                    # Skip the dependency graph file itself and ignored paths
                    if file_path == self.graph_path:
                        continue
                    if self.should_ignore_path(file_path):
                        files_ignored += 1
                        continue
                    files_found += 1
                    await self.queue.put(file_path)
        
        logger.info(f"Directory scan complete: {files_found} files queued, {files_ignored} files ignored")

    def analyze_file(self, file_path: str) -> List[str]:
        """Analyze file dependencies."""
        if not os.path.exists(file_path):
            logger.debug(f"File does not exist: {file_path}")
            return []
            
        if not os.path.isfile(file_path):
            logger.debug(f"Not a file: {file_path}")
            return []

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                try:
                    content = f.read()
                except UnicodeDecodeError:
                    logger.debug(f"Unable to read {file_path} as UTF-8, trying with system encoding")
                    # Try again with system encoding
                    with open(file_path, 'r') as f2:
                        content = f2.read()

            if file_path.lower().endswith('.py'):
                try:
                    deps = [dep for dep in self._analyze_python(content, file_path) 
                           if not self.should_ignore_path(dep)]
                    logger.debug(f"Found {len(deps)} Python dependencies for {file_path}")
                    return deps
                except Exception as e:
                    logger.error(f"Error analyzing Python imports in {file_path}: {e}")
                    return []
            elif file_path.lower().endswith('.lua'):
                try:
                    deps = [dep for dep in self._analyze_lua(content, file_path)
                           if not self.should_ignore_path(dep)]
                    logger.debug(f"Found {len(deps)} Lua dependencies for {file_path}")
                    return deps
                except Exception as e:
                    logger.error(f"Error analyzing Lua requires in {file_path}: {e}")
                    return []
            return []
            
        except Exception as e:
            logger.error(f"Error reading {file_path}: {e}")
            return []

    def _analyze_python(self, content: str, file_path: str) -> List[str]:
        """Analyze Python imports."""
        imports = []
        current_dir = os.path.dirname(file_path)
        
        # Updated patterns to capture relative imports
        patterns = [
            # Standard imports
            r'^import\s+([\w.]+)',
            r'^from\s+([\w.]+)\s+import',
            # Indented imports
            r'^\s+import\s+([\w.]+)',
            r'^\s+from\s+([\w.]+)\s+import',
            # Relative imports
            r'^from\s*(\.+)([\w.]*)\s+import',
            r'^\s+from\s*(\.+)([\w.]*)\s+import'
        ]
        
        for pattern in patterns:
            for match in re.finditer(pattern, content, re.MULTILINE):
                if len(match.groups()) == 1:
                    # Standard import
                    module_path = match.group(1)
                    file_path_parts = module_path.split('.')
                    potential_paths = [
                        os.path.join(self.root_path, *file_path_parts) + '.py',
                        os.path.join(self.root_path, *file_path_parts, '__init__.py')
                    ]
                elif len(match.groups()) == 2:
                    # Relative import
                    dots, module_path = match.groups()
                    level = len(dots)  # Number of dots for relative import
                    
                    # Start from current directory and go up based on dot count
                    target_dir = current_dir
                    for _ in range(level):
                        target_dir = os.path.dirname(target_dir)
                    
                    if module_path:
                        module_parts = module_path.split('.')
                        target_dir = os.path.join(target_dir, *module_parts[:-1]) if len(module_parts) > 1 else target_dir
                        potential_paths = [
                            os.path.join(target_dir, module_parts[-1] + '.py'),
                            os.path.join(target_dir, module_parts[-1], '__init__.py')
                        ]
                    else:
                        # Just dots with no module path (e.g., "from .. import x")
                        potential_paths = [os.path.join(target_dir, '__init__.py')]
                else:
                    continue
                
                # Filter out paths outside project root
                potential_paths = [p for p in potential_paths 
                                 if p.startswith(self.root_path) and 
                                 not self.should_ignore_path(p)]
                
                # Add first existing path
                for path in potential_paths:
                    if os.path.exists(path) and path != file_path:  # Avoid self-references
                        imports.append(path)
                        break
        
        return list(set(imports))  # Remove duplicates

    def _analyze_lua(self, content: str, file_path: str) -> List[str]:
        """Analyze Lua requires."""
        requires = []
        for pattern in self.lua_patterns:
            for match in re.finditer(pattern, content):
                module_path = match.group(1)
                file_path_parts = module_path.replace('.', os.sep).split(os.sep)
                potential_paths = [
                    os.path.join(self.root_path, *file_path_parts) + '.lua',
                    os.path.join(self.root_path, *file_path_parts, 'init.lua')
                ]
                for path in potential_paths:
                    if os.path.exists(path):
                        requires.append(path)
                        break
        return requires

    def generate_mermaid(self) -> str:
        """Generate Mermaid diagram from current dependencies."""
        # Start with flowchart definition
        mermaid = [
            "%%{init: {'flowchart': {'nodeSpacing': 50, 'rankSpacing': 50, 'htmlLabels': true}} }%%",
            "flowchart TD",
        ]
        
        # Add enhanced style definitions
        mermaid.extend([
            "    %% Node styles",
            "    classDef python fill:#2b5b84,stroke:#1a365d,color:#fff,stroke-width:2px",
            "    classDef lua fill:#000080,stroke:#000066,color:#fff,stroke-width:2px",
            "    classDef heavy_deps fill:#8b0000,stroke:#580000,color:#fff,stroke-width:3px",
            "    classDef light_deps fill:#006400,stroke:#004100,color:#fff,stroke-width:1px",
            "    classDef cluster fill:#2d2d2d,stroke:#404040,color:#fff",
        ])

        def create_short_label(file_path: str) -> str:
            """Create a very short label for the node."""
            name = os.path.basename(file_path)
            name = re.sub(r'\.(py|lua)$', '', name)
            if len(name) > 12:
                name = f"{name[:6]}~{name[-3:]}"
            return name

        # Calculate dependency levels (distance from root)
        def calculate_level(file_path: str, visited=None) -> int:
            """Calculate the dependency level (0 = leaf, higher = more dependencies)."""
            if visited is None:
                visited = set()
            if file_path in visited:
                return 0
            visited.add(file_path)
            
            dependents = [f for f, deps in self._dependencies.items() if file_path in deps]
            if not dependents:
                return 0
            return 1 + max(calculate_level(dep, visited.copy()) for dep in dependents)

        # Calculate levels for all files
        levels = {f: calculate_level(f) for f in self._dependencies.keys()}
        max_level = max(levels.values()) if levels else 0

        # Group files by level
        level_groups = [[] for _ in range(max_level + 1)]
        for file_path, level in levels.items():
            level_groups[level].append(file_path)

        # Sort files within each level by number of dependencies
        for level in level_groups:
            level.sort(key=lambda f: len(self._dependencies.get(f, [])), reverse=True)

        # Add nodes level by level
        added_nodes = set()
        for level, level_files in enumerate(level_groups):
            if not level_files:
                continue

            # Create a subgraph for this level
            mermaid.append(f"    subgraph level_{level}[Level {level}]")
            mermaid.append("        direction TB")
            
            # Add nodes at this level
            for file_path in level_files:
                node_id = os.path.relpath(file_path, self.root_path).replace(os.sep, '_')
                file_name = create_short_label(file_path)
                
                deps_count = len(self._dependencies.get(file_path, []))
                if deps_count > 5:
                    style = ":::heavy_deps"
                elif deps_count == 0:
                    style = ":::light_deps"
                else:
                    style = ":::python" if file_path.endswith('.py') else ":::lua"
                
                mermaid.append(f"        {node_id}[{file_name}]{style}")
                added_nodes.add(file_path)
            
            mermaid.append("    end")

        # Add edges with explicit ordering to minimize crossings
        mermaid.append("")
        mermaid.append("    %% Dependencies")
        
        # Sort edges to prioritize vertical connections
        edges = []
        for source_file, deps in self._dependencies.items():
            if not deps:
                continue
            
            source = os.path.relpath(source_file, self.root_path).replace(os.sep, '_')
            source_level = levels[source_file]
            
            for dep in deps:
                target = os.path.relpath(dep, self.root_path).replace(os.sep, '_')
                target_level = levels[dep]
                # Calculate vertical distance for sorting
                level_diff = abs(source_level - target_level)
                edges.append((source, target, level_diff))
        
        # Sort edges by level difference (prioritize vertical connections)
        edges.sort(key=lambda x: (-x[2], x[0], x[1]))
        
        # Add edges in order
        for source, target, _ in edges:
            # Use thicker arrows for direct dependencies
            if target in self._dependencies.get(source.replace('_', os.sep), []):
                mermaid.append(f"    {source} ==> {target}")
            else:
                mermaid.append(f"    {source} --> {target}")
        
        return "\n".join(mermaid)

    def _create_dependency_clusters(self) -> List[Set[str]]:
        """Create clusters of related files based on their dependencies."""
        # Build adjacency matrix
        files = list(self._dependencies.keys())
        file_to_idx = {f: i for i, f in enumerate(files)}
        
        # Create undirected graph of dependencies
        graph = {f: set() for f in files}
        for file_path, deps in self._dependencies.items():
            for dep in deps:
                if dep in graph:
                    graph[file_path].add(dep)
                    graph[dep].add(file_path)
        
        # Find clusters using a simple clustering algorithm
        clusters: List[Set[str]] = []
        visited = set()
        
        def dfs(file_path: str, current_cluster: Set[str]):
            """Depth-first search to find connected components."""
            if file_path in visited:
                return
            visited.add(file_path)
            current_cluster.add(file_path)
            
            # Add strongly connected files to same cluster
            for neighbor in graph[file_path]:
                if neighbor not in visited:
                    dfs(neighbor, current_cluster)
        
        # Create initial clusters based on connected components
        for file_path in files:
            if file_path not in visited:
                current_cluster = set()
                dfs(file_path, current_cluster)
                if current_cluster:
                    clusters.append(current_cluster)
        
        # Split large clusters
        MAX_CLUSTER_SIZE = 8
        final_clusters = []
        for cluster in clusters:
            if len(cluster) > MAX_CLUSTER_SIZE:
                # Split based on dependency count
                sorted_files = sorted(cluster, 
                                   key=lambda f: len(self._dependencies.get(f, [])),
                                   reverse=True)
                
                # Create smaller clusters
                for i in range(0, len(sorted_files), MAX_CLUSTER_SIZE):
                    final_clusters.append(set(sorted_files[i:i + MAX_CLUSTER_SIZE]))
            else:
                final_clusters.append(cluster)
        
        return final_clusters

    async def get_ai_validation(self, dependencies: Dict[str, List[str]]) -> Optional[str]:
        """Get AI validation and analysis of the dependency structure."""
        try:
            # Create a summary of the dependency structure
            summary = []
            for file_path, deps in dependencies.items():
                rel_path = os.path.relpath(file_path, self.root_path)
                dep_paths = [os.path.relpath(d, self.root_path) for d in deps]
                summary.append(f"- {rel_path} depends on: {', '.join(dep_paths) if dep_paths else 'no dependencies'}")

            prompt = f"""Analyze this Python/Lua project's dependency structure:

Dependencies:
{chr(10).join(summary)}

Please provide:
1. Validation of the dependency structure (identify any potential issues)
2. Analysis of modularity and coupling
3. Suggestions for improving the dependency organization
4. Any potential circular dependencies or problematic patterns

Keep the response focused and actionable."""

            result = await self.llm_client.generate(
                prompt=prompt,
                max_tokens=1000,
                temperature=0.7
            )

            if result and result.get('response'):
                # Clean up the response
                ai_response = result['response'].strip()
                ai_response = ai_response.replace('(BEGIN AI Generated)', '')
                ai_response = ai_response.replace('(END AI Generated)', '')
                ai_response = ai_response.strip()
                return f"\n## AI Analysis\n\n(BEGIN AI Generated)\n{ai_response}\n(END AI Generated)\n"

            return None

        except Exception as e:
            logger.error(f"Error getting AI validation: {e}")
            return None

    async def update_graph_file(self) -> None:
        """Update the dependency graph markdown file."""
        try:
            # Generate Mermaid diagram
            try:
                mermaid = self.generate_mermaid()
            except Exception as e:
                logger.error(f"Error generating Mermaid diagram: {e}")
                return

            # Get AI validation
            try:
                ai_analysis = await self.get_ai_validation(self._dependencies)
            except Exception as e:
                logger.error(f"Error getting AI analysis: {e}")
                ai_analysis = None

            # Prepare content
            content = [
                "# Project Dependency Graph\n",
                "## Visualization\n",
                "```mermaid",
                mermaid,
                "```\n",
            ]

            # Add AI analysis if available
            if ai_analysis:
                content.append(ai_analysis)

            content.append("\n## Detailed Dependencies\n")
            
            # Add detailed dependencies
            try:
                for file_path, deps in self._dependencies.items():
                    try:
                        rel_path = os.path.relpath(file_path, self.root_path)
                        content.append(f"### {rel_path}\n")
                        if deps:
                            content.append("Depends on:")
                            for dep in deps:
                                try:
                                    dep_rel_path = os.path.relpath(dep, self.root_path)
                                    content.append(f"- {dep_rel_path}")
                                except ValueError as e:
                                    logger.error(f"Error getting relative path for {dep}: {e}")
                                    continue
                        else:
                            content.append("No dependencies")
                        content.append("")  # Empty line
                    except Exception as e:
                        logger.error(f"Error processing dependencies for {file_path}: {e}")
                        continue
            except Exception as e:
                logger.error(f"Error processing dependencies list: {e}")
            
            # Write to file
            try:
                with open(self.graph_path, 'w', encoding='utf-8') as f:
                    f.write('\n'.join(content))
            except Exception as e:
                logger.error(f"Error writing to graph file: {e}")
                return
                
            # Send visualization update
            if self.ws_agent:
                try:
                    update_data = {
                        "type": "visualization_update",
                        "timestamp": datetime.now().isoformat(),
                        "data": {
                            "diagram": mermaid,
                            "analysis": ai_analysis if ai_analysis else None,
                            "stats": {
                                "total_files": len(self._dependencies),
                                "total_dependencies": sum(len(deps) for deps in self._dependencies.values())
                            }
                        }
                    }
                    await self.ws_agent.send(json.dumps(update_data))
                except Exception as e:
                    logger.error(f"Error sending visualization update: {e}")
            else:
                logger.debug("No websocket connection available for visualization update")
            
        except Exception as e:
            logger.error(f"Error updating graph file: {e}", exc_info=True)

    async def handle_file_change(self, file_path: str) -> None:
        """Handle file change events."""
        try:
            if not file_path.lower().endswith(('.py', '.lua')):
                return
                
            # Skip the dependency graph file itself and ignored paths
            if file_path == self.graph_path or self.should_ignore_path(file_path):
                return

            logger.info(f"Detected change in {file_path}")
            
            # Send file modified activity
            await self.send_activity(
                action="file_modified",
                file_path=file_path
            )
            
            # Queue for processing
            await self.queue.put(file_path)
            
        except Exception as e:
            logger.error(f"Error handling file change: {e}", exc_info=True)

    async def process_files(self):
        """Process queued files."""
        while True:
            try:
                file_path = await self.queue.get()
                logger.info(f"Processing {file_path}")
                
                try:
                    # Send analysis start message
                    await self.send_activity(
                        action="analyzing_dependencies",
                        file_path=file_path
                    )
                    
                    # Analyze dependencies
                    async with self._cache_lock:
                        if os.path.exists(file_path):
                            self._dependencies[file_path] = self.analyze_file(file_path)
                        else:
                            # File was deleted
                            self._dependencies.pop(file_path, None)
                        
                        # Update the graph file
                        await self.update_graph_file()
                    
                    # Send analysis complete message
                    await self.send_activity(
                        action="analysis_complete",
                        file_path=file_path,
                        details={
                            "dependencies": len(self._dependencies.get(file_path, [])),
                            "dependents": sum(1 for deps in self._dependencies.values() if file_path in deps)
                        }
                    )
                    
                except Exception as e:
                    logger.error(f"Error processing {file_path}: {e}", exc_info=True)
                    
                finally:
                    self.queue.task_done()
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in processing loop: {e}", exc_info=True)
                await asyncio.sleep(1)

    async def start(self, path: str):
        """Start the agent."""
        if not self.running:
            self.running = True
            
        # Establish initial connection
        if not await self.connect():
            logger.error("Failed to establish initial connection")
            self.running = False
            return
            
        # Start file processing
        if not self._processing_task or self._processing_task.done():
            self._processing_task = asyncio.create_task(self.process_files())
            
        # Check for existing graph file
        if not os.path.exists(self.graph_path):
            logger.info("No dependency graph found, scanning directory")
            await self.scan_directory()
        else:
            logger.info("Found existing dependency graph")
            
        # Start file monitoring
        self.file_monitor.start(path)
        
        # Process messages until stopped
        try:
            while self.running:
                try:
                    if not self.ws_agent:
                        if not await self.ensure_connection():
                            await asyncio.sleep(1)
                            continue
                            
                    message = await self.ws_agent.recv()
                    data = json.loads(message)
                    
                    if data.get('type') == 'ping':
                        await self.ws_agent.send(json.dumps({
                            "type": "pong",
                            "timestamp": datetime.now().isoformat(),
                            "agent": self.name
                        }))
                        
                except websockets.exceptions.ConnectionClosed:
                    logger.error("WebSocket connection closed")
                    self._connection_confirmed = False
                    await asyncio.sleep(1)
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    await asyncio.sleep(1)
                    
        finally:
            await self.stop()

    async def stop(self):
        """Stop the agent."""
        self.running = False
        
        if self._processing_task:
            self._processing_task.cancel()
            
        self.file_monitor.stop()
        self._dependencies.clear()

async def main(path: str):
    """Main entry point."""
    try:
        agent = DependencyAgent(path)
        await agent.start(path)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
    finally:
        if agent:
            await agent.stop()

if __name__ == '__main__':
    import sys
    if len(sys.argv) != 2:
        print("Usage: python agent_code_mon_deps.py <path>")
        sys.exit(1)
    asyncio.run(main(sys.argv[1])) 
