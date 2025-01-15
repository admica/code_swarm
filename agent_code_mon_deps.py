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
from shared import config_manager
import fnmatch

logger = logging.getLogger('code_mon_deps')

class DependencyAgent(BaseAgent):
    """Agent that monitors and analyzes file dependencies."""

    def __init__(self, path: str):
        super().__init__('code_mon_deps')
        self.root_path = path
        self.graph_path = os.path.join(path, 'dependency_graph.md')
        
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
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            if file_path.lower().endswith('.py'):
                return [dep for dep in self._analyze_python(content, file_path) 
                       if not self.should_ignore_path(dep)]
            elif file_path.lower().endswith('.lua'):
                return [dep for dep in self._analyze_lua(content, file_path)
                       if not self.should_ignore_path(dep)]
            return []
            
        except Exception as e:
            logger.error(f"Error analyzing {file_path}: {e}")
            return []

    def _analyze_python(self, content: str, file_path: str) -> List[str]:
        """Analyze Python imports."""
        imports = []
        for pattern in self.python_patterns:
            for match in re.finditer(pattern, content, re.MULTILINE):
                module_path = match.group(1)
                file_path_parts = module_path.split('.')
                potential_paths = [
                    os.path.join(self.root_path, *file_path_parts) + '.py',
                    os.path.join(self.root_path, *file_path_parts, '__init__.py')
                ]
                for path in potential_paths:
                    if os.path.exists(path):
                        imports.append(path)
                        break
        return imports

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
        # Add metadata section for layout control
        mermaid = [
            "---",
            "config:",
            "    layout: elk",
            "    elk:",
            "        algorithm: layered",
            "        nodePlacementStrategy: BRANDES_KOEPF",
            "        hierarchyHandling: INCLUDE_CHILDREN",
            "        spacing: 40",
            "        feedbackEdges: true",
            "        aspectRatio: 0.5",  # Favor vertical growth
            "---",
            "flowchart TD",
            "    %% Use TD (top-down) direction",
        ]
        
        # Add enhanced style definitions
        mermaid.extend([
            "    %% Node styles",
            "    classDef python fill:#2b5b84,stroke:#1a365d,color:#fff,stroke-width:2px;",
            "    classDef lua fill:#000080,stroke:#000066,color:#fff,stroke-width:2px;",
            "    classDef heavy_deps fill:#8b0000,stroke:#580000,color:#fff,stroke-width:3px;",
            "    classDef light_deps fill:#006400,stroke:#004100,color:#fff,stroke-width:1px;",
            "    classDef cluster fill:#2d2d2d,stroke:#404040,color:#fff;",
            "",
            "    %% Link styles",
            "    linkStyle default stroke:#666,stroke-width:1px;",
        ])

        def create_short_label(file_path: str) -> str:
            """Create a very short label for the node."""
            name = os.path.basename(file_path)
            name = re.sub(r'\.(py|lua)$', '', name)
            # More aggressive shortening
            if len(name) > 12:
                # Keep first 6 and last 3 chars
                name = f"{name[:6]}~{name[-3:]}"
            return name

        # Analyze dependency relationships to create clusters
        dependency_clusters = self._create_dependency_clusters()
        
        # Track nodes that have been added
        added_nodes = set()
        
        # Add nodes in clusters to control layout
        for cluster_idx, cluster in enumerate(dependency_clusters):
            cluster_name = f"cluster_{cluster_idx}"
            # Use orientation hint in subgraph
            mermaid.append(f"    subgraph {cluster_name}[Cluster {cluster_idx + 1}]")
            mermaid.append("        direction: TB")
            
            # Sort files by their dependency relationships for better layering
            cluster_files = sorted(cluster, 
                                 key=lambda f: (
                                     len(self._dependencies.get(f, [])),  # Primary: number of outgoing deps
                                     -sum(1 for deps in self._dependencies.values() if f in deps)  # Secondary: incoming deps
                                 ),
                                 reverse=True)
            
            # Add rank hints for better vertical alignment
            current_rank = []
            current_deps = -1
            
            for file_path in cluster_files:
                if file_path in added_nodes:
                    continue
                    
                node_id = os.path.relpath(file_path, self.root_path).replace(os.sep, '_')
                file_name = create_short_label(file_path)
                
                # Determine node style
                deps_count = len(self._dependencies.get(file_path, []))
                
                # Start new rank group if dependency count changes
                if deps_count != current_deps:
                    if current_rank:
                        # Add rank grouping for previous nodes
                        mermaid.append(f"        {{rank=same {' '.join(current_rank)}}}")
                        current_rank = []
                    current_deps = deps_count
                
                if deps_count > 5:
                    style = ":::heavy_deps"
                elif deps_count == 0:
                    style = ":::light_deps"
                else:
                    style = ":::python" if file_path.endswith('.py') else ":::lua"
                
                mermaid.append(f"        {node_id}[{file_name}]{style}")
                current_rank.append(node_id)
                added_nodes.add(file_path)
            
            # Add final rank group if any nodes remain
            if current_rank:
                mermaid.append(f"        {{rank=same {' '.join(current_rank)}}}")
            
            mermaid.append("    end")
            mermaid.append(f"    style {cluster_name} fill:#2d2d2d,stroke:#404040,color:#fff")
        
        # Add any remaining nodes that weren't in clusters
        remaining_files = set(self._dependencies.keys()) - added_nodes
        if remaining_files:
            mermaid.append("")
            mermaid.append("    %% Unclustered files")
            for file_path in remaining_files:
                node_id = os.path.relpath(file_path, self.root_path).replace(os.sep, '_')
                file_name = create_short_label(file_path)
                style = ":::python" if file_path.endswith('.py') else ":::lua"
                mermaid.append(f"    {node_id}[{file_name}]{style}")
        
        # Add relationships with explicit ordering to minimize crossings
        mermaid.append("")
        mermaid.append("    %% Dependencies")
        
        # Sort dependencies to minimize crossings
        edges = []
        for file_path, deps in self._dependencies.items():
            if not deps:
                continue
            
            source = os.path.relpath(file_path, self.root_path).replace(os.sep, '_')
            for dep in deps:
                target = os.path.relpath(dep, self.root_path).replace(os.sep, '_')
                # Calculate edge weight based on node positions
                weight = len(self._dependencies.get(dep, [])) * 100 + len(deps)
                edges.append((source, target, weight))
        
        # Sort edges by weight to prioritize important connections
        edges.sort(key=lambda x: x[2], reverse=True)
        
        # Add edges with consistent ordering
        for source, target, _ in edges:
            if target in self._dependencies.get(source, []):
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

    async def update_graph_file(self) -> None:
        """Update the dependency graph markdown file."""
        try:
            mermaid = self.generate_mermaid()
            
            content = [
                "# Project Dependency Graph\n",
                "## Visualization\n",
                "```mermaid",
                mermaid,
                "```\n",
                "## Dependencies\n"
            ]
            
            # Add detailed dependencies
            for file_path, deps in self._dependencies.items():
                rel_path = os.path.relpath(file_path, self.root_path)
                content.append(f"### {rel_path}\n")
                if deps:
                    content.append("Depends on:")
                    for dep in deps:
                        dep_rel_path = os.path.relpath(dep, self.root_path)
                        content.append(f"- {dep_rel_path}")
                else:
                    content.append("No dependencies")
                content.append("")  # Empty line
            
            # Write to file
            with open(self.graph_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(content))
                
            # Send visualization update
            await self.ws_agent.send(json.dumps({
                "type": "visualization_update",
                "timestamp": datetime.now().isoformat(),
                "data": {
                    "diagram": mermaid,
                    "stats": {
                        "total_files": len(self._dependencies),
                        "total_dependencies": sum(len(deps) for deps in self._dependencies.values())
                    }
                }
            }))
            
        except Exception as e:
            logger.error(f"Error updating graph file: {e}")

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
