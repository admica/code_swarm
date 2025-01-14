#!./venv/bin/python3
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
import json
from datetime import datetime
from shared.base_agent import BaseAgent
import websockets

# Set up logging
logger = AgentLogger('code_mon_deps')

# Constants
UPDATE_DELAY = 3.0  # seconds
DEFAULT_MAX_DEPTH = 8
REQUIRE_PATTERNS = [
    r'''(?:require|dofile|loadfile)\s*[\(\["']([^"\'\)]+)["'\)\]]''',  # Simple requires
    r'''(?:require|dofile|loadfile)\s*\(?([^"\'\)]+\.\.[\s\n]*[^"\'\)]+)\)?''',  # Concatenated
    r'''(?:require|dofile|loadfile)\s*\(\s*([^"\'\)]+)\s*\)'''  # Complex expressions
]

class DependencyAnalyzer(BaseAgent):
    """Analyzes source code dependencies."""

    def __init__(self, root_path: str):
        """Initialize the analyzer.

        Args:
            root_path: The root directory to analyze
        """
        super().__init__('code_mon_deps')
        self.root_path = root_path
        self.logger = AgentLogger('code_mon_deps')
        self.llm_client = LLMClient('code_mon_deps')
        self._cache: Dict[str, List[str]] = {}
        self._dependents: Dict[str, Set[str]] = {}  # Track which files depend on each file
        self.config = config_manager.get_agent_config('code_mon_deps')

        # Load configuration with defaults
        self.skip_patterns = self.config.get('ignore_patterns', 'venv/*,__pycache__/*,.git/*').split(',')
        self.group_by_directory = self.config.get('group_by_directory', True)
        self.diagram_direction = self.config.get('diagram_direction', 'TB')  # Default to top-bottom
        self.enable_ai_analysis = self.config.get('enable_ai_analysis', True)

        # Analysis tuning parameters
        self.min_coupling_threshold = self.config.get('min_coupling_threshold', 9)  # Minimum number of dependencies to flag
        self.std_dev_multiplier = self.config.get('std_dev_multiplier', 2.1)  # How many standard deviations above mean to flag
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
            return ':::python'  # Using ::: for class assignment
        elif file_path.lower().endswith('.lua'):
            return ':::lua'  # Using ::: for class assignment
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

class DependencyMonitor(BaseAgent):
    """Monitors source files for dependency changes."""

    def __init__(self, path: str):
        """Initialize the monitor.

        Args:
            path: The root directory to monitor.
        """
        super().__init__('code_mon_deps')
        self.analyzer = DependencyAnalyzer(path)
        self.visualizer = DependencyVisualizer(self.analyzer)
        self.file_monitor = FileMonitor('code_mon_deps', self.handle_file_change)
        self.queue = asyncio.Queue()
        self._task: Optional[asyncio.Task] = None
        self._message_task: Optional[asyncio.Task] = None

        # Connection state management
        self._connection_confirmed = False
        self._connection_lock = asyncio.Lock()
        self._message_queue = asyncio.Queue()

        # Load configuration
        self.config = config_manager.get_agent_config('code_mon_deps')
        self._update_delay = self.config.get('update_delay', UPDATE_DELAY)
        self._batch_window = self.config.get('batch_window', 2.0)
        self._max_queue_size = self.config.get('max_queue_size', 100)
        self._max_ws_retries = 3

        self._last_update = 0
        self._cache_lock = asyncio.Lock()
        logger.info("Dependency monitor initialized with update delay: %s", self._update_delay)

    async def _process_messages(self):
        """Process incoming messages from the controller."""
        while self.running:
            try:
                if not self.ws_agent:
                    await asyncio.sleep(1)
                    continue

                message = await self.ws_agent.recv()
                data = json.loads(message)

                if data.get('type') == 'connection_confirmed':
                    self._connection_confirmed = True
                    logger.info("Connection confirmed by controller")
                elif data.get('type') == 'ping':
                    # Respond to ping with pong
                    await self.ws_agent.send(json.dumps({
                        "type": "pong",
                        "timestamp": datetime.now().isoformat(),
                        "agent": self.name
                    }))
                else:
                    # Queue other messages for processing
                    await self._message_queue.put(data)
                    logger.debug(f"Queued message for processing: {data.get('type')}")

            except websockets.exceptions.ConnectionClosed:
                logger.error("WebSocket connection closed")
                self._connection_confirmed = False
                await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"Error processing message: {e}")
                await asyncio.sleep(1)

    async def connect(self):
        """Establish connection with proper handshake."""
        async with self._connection_lock:
            try:
                # First ensure we're disconnected
                await self.disconnect()

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

                # Wait for confirmation with timeout
                try:
                    deadline = time.time() + 5.0
                    while time.time() < deadline and not self._connection_confirmed:
                        try:
                            response = await asyncio.wait_for(
                                self.ws_agent.recv(), 
                                timeout=max(0.1, deadline - time.time())
                            )
                            data = json.loads(response)

                            if data.get('type') == 'connection_confirmed':
                                self._connection_confirmed = True
                                logger.info("Connection confirmed by controller")
                                break
                            else:
                                # Queue any other messages received during connection
                                await self._message_queue.put(data)
                        except asyncio.TimeoutError:
                            break

                    if not self._connection_confirmed:
                        logger.error("Connection confirmation not received")
                        await self.disconnect()
                        return False

                    # Only connect to logs after agent connection is confirmed
                    try:
                        self.ws_logs = await websockets.connect("ws://localhost:8000/ws/logs")
                        logger.info("Connected to log stream")
                    except Exception as e:
                        logger.error(f"Failed to connect to log stream: {e}")
                        await self.disconnect()
                        return False

                    return True

                except Exception as e:
                    logger.error(f"Error during handshake: {e}")
                    await self.disconnect()
                    return False

            except Exception as e:
                logger.error(f"Connection failed: {e}")
                await self.disconnect()
                return False

    async def disconnect(self):
        """Clean disconnect from all connections."""
        async with self._connection_lock:
            self._connection_confirmed = False

            if self.ws_agent:
                try:
                    await self.ws_agent.send(json.dumps({
                        "type": "agent_disconnect",
                        "timestamp": datetime.now().isoformat(),
                        "agent": self.name
                    }))
                except Exception as e:
                    logger.warning(f"Failed to send disconnect message: {e}")

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

            # Clear message queue
            while not self._message_queue.empty():
                try:
                    self._message_queue.get_nowait()
                except asyncio.QueueEmpty:
                    break

    async def ensure_connection(self):
        """Check connection state and reconnect if necessary."""
        if not self.ws_agent or not self._connection_confirmed:
            return await self.connect()
        return True

    async def handle_file_change(self, file_path: str) -> None:
        """Handle file change event."""
        try:
            file_lower = file_path.lower()
            if not file_lower.endswith(('.py', '.lua')):
                return

            logger.info(f"Detected modification to {file_path}")

            # Ensure connection before sending
            if not await self.ensure_connection():
                logger.error("Failed to ensure WebSocket connection")
                return

            # Send activity message
            logger.info("Sending file_modified activity for %s", file_path)
            await self.send_activity(
                action="file_modified",
                file_path=file_path
            )
            logger.info("Queueing file for processing: %s", file_path)
            await self.queue.put(file_path)
        except Exception as e:
            logger.error(f"Error handling file change for {file_path}: {str(e)}", exc_info=True)

    async def start(self, path: str):
        """Start monitoring."""
        logger.info("Starting dependency monitor for path: %s", path)

        if not self.running:
            self.running = True
            logger.info("Agent running state set to True")

        # Start message processing
        if not self._message_task or self._message_task.done():
            self._message_task = asyncio.create_task(self._process_messages())
            logger.info("Message processing task started")

        # Establish initial connection
        if not await self.connect():
            logger.error("Failed to establish initial connection")
            self.running = False
            if self._message_task:
                self._message_task.cancel()
            return

        logger.info("Initial connection established")

        if not self._task or self._task.done():
            self._task = asyncio.create_task(self.start_processing())
            logger.info("File processing task started")

        # Start file monitoring
        try:
            self.file_monitor.start(path)
            logger.info("File monitor started for path: %s", path)
        except Exception as e:
            logger.error("Failed to start file monitor: %s", e)
            self.running = False
            if self._message_task:
                self._message_task.cancel()
            if self._task:
                self._task.cancel()
            return

        logger.info("All tasks started, entering main loop")

        # Create tasks for both the run loop and our processing
        tasks = [
            asyncio.create_task(self.run()),
            self._message_task,
            self._task
        ]

        try:
            # Wait for any task to complete or fail
            done, pending = await asyncio.wait(
                tasks,
                return_when=asyncio.FIRST_COMPLETED
            )

            # If any task completed, log it and stop everything
            for task in done:
                try:
                    result = await task
                    logger.error("Task completed unexpectedly: %s", result)
                except Exception as e:
                    logger.error("Task failed with error: %s", e)

            # Cancel remaining tasks
            for task in pending:
                task.cancel()

            await self.stop()

        except Exception as e:
            logger.error("Error in main loop: %s", e)
            await self.stop()

    async def stop(self):
        """Stop monitoring and clean up resources."""
        self.running = False

        # Cancel tasks
        if self._task:
            self._task.cancel()
        if self._message_task:
            self._message_task.cancel()

        # Stop file monitoring
        self.file_monitor.stop()
        self.analyzer.clear_cache()

        # Clear queues
        while not self.queue.empty():
            try:
                self.queue.get_nowait()
            except asyncio.QueueEmpty:
                break

        while not self._message_queue.empty():
            try:
                self._message_queue.get_nowait()
            except asyncio.QueueEmpty:
                break

        # Disconnect WebSockets
        await self.disconnect()

    async def start_processing(self):
        """Start processing the file queue."""
        logger.info("Starting file processing loop")
        while True:
            try:
                logger.debug("Waiting for file in queue...")
                file_path = await self.queue.get()
                logger.info("Processing file: %s", file_path)

                # Apply debouncing
                now = time.time()
                if now - self._last_update < self._update_delay:
                    await asyncio.sleep(self._update_delay)
                self._last_update = now

                try:
                    # Use lock to protect cache and visualization operations
                    async with self._cache_lock:
                        if os.path.exists(file_path):
                            # Ensure WebSocket connection before sending messages
                            if not await self.ensure_connection():
                                logger.error("Failed to ensure WebSocket connection")
                                continue

                            logger.info("Starting dependency analysis for %s", file_path)
                            # Send analysis start message with retry
                            retry_count = 0
                            while retry_count < self._max_ws_retries:
                                try:
                                    await self.send_activity(
                                        action="analyzing_dependencies",
                                        file_path=file_path
                                    )
                                    break
                                except Exception as e:
                                    retry_count += 1
                                    if retry_count >= self._max_ws_retries:
                                        logger.error(f"Failed to send start message after {retry_count} attempts: {e}")
                                        break
                                    logger.warning(f"Failed to send start message (attempt {retry_count}): {e}")
                                    await asyncio.sleep(1 * retry_count)

                            self.analyzer.invalidate_file(file_path)
                            logger.info("Updating visualization")
                            await self.visualizer.update_visualization()

                            # Send analysis complete message with retry
                            logger.info("Analysis complete, sending results")
                            retry_count = 0
                            while retry_count < self._max_ws_retries:
                                try:
                                    await self.send_activity(
                                        action="analysis_complete",
                                        file_path=file_path,
                                        details={
                                            "dependencies": len(self.analyzer._cache.get(file_path, [])),
                                            "dependents": len(self.analyzer._dependents.get(file_path, set()))
                                        }
                                    )
                                    break
                                except Exception as e:
                                    retry_count += 1
                                    if retry_count >= self._max_ws_retries:
                                        logger.error(f"Failed to send complete message after {retry_count} attempts: {e}")
                                        break
                                    logger.warning(f"Failed to send complete message (attempt {retry_count}): {e}")
                                    await asyncio.sleep(1 * retry_count)

                except Exception as e:
                    logger.error(f"Error updating visualization for {file_path}: {str(e)}", exc_info=True)
                finally:
                    self.queue.task_done()
                    logger.info("Finished processing %s", file_path)

            except asyncio.CancelledError:
                logger.info("File processing loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in queue processor: {str(e)}", exc_info=True)
                await asyncio.sleep(1)

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
        mermaid = ["graph " + self.analyzer.diagram_direction]

        # Add style definitions
        mermaid.append("    classDef python fill:#2b5b84,stroke:#1a365d,color:#fff;")
        mermaid.append("    classDef lua fill:#000080,stroke:#000066,color:#fff;")

        # Add nodes
        for file_path in dependencies.keys():
            node_id = self.analyzer.get_module_name(file_path).replace('.', '_')
            node_label = os.path.basename(file_path)
            style = self.analyzer._get_node_style(file_path)
            mermaid.append(f"    {node_id}[{node_label}]{style}")

        # Add relationships
        for file_path, deps in dependencies.items():
            source_id = self.analyzer.get_module_name(file_path).replace('.', '_')
            for dep in deps:
                target_id = self.analyzer.get_module_name(dep).replace('.', '_')
                mermaid.append(f"    {source_id} --> {target_id}")

        return "\n".join(mermaid)

    def _generate_grouped_mermaid(self, dependencies: Dict[str, List[str]]) -> str:
        """Generate Mermaid diagram with directory grouping."""
        mermaid = ["graph " + self.analyzer.diagram_direction]

        # Add style definitions
        mermaid.append("    classDef python fill:#2b5b84,stroke:#1a365d,color:#fff;")
        mermaid.append("    classDef lua fill:#000080,stroke:#000066,color:#fff;")

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
            mermaid.append(f"    subgraph {dir_id}[{directory}]")

            # Add nodes for files in this directory
            for file_path in dependencies.keys():
                rel_path = os.path.relpath(file_path, self.analyzer.root_path)
                if os.path.dirname(rel_path) == directory:
                    node_id = self.analyzer.get_module_name(file_path).replace('.', '_')
                    node_label = os.path.basename(file_path)
                    style = self.analyzer._get_node_style(file_path)
                    mermaid.append(f"        {node_id}[{node_label}]{style}")

            mermaid.append("    end")

        # Add nodes for files in root
        for file_path in dependencies.keys():
            rel_path = os.path.relpath(file_path, self.analyzer.root_path)
            if not os.path.dirname(rel_path):
                node_id = self.analyzer.get_module_name(file_path).replace('.', '_')
                node_label = os.path.basename(file_path)
                style = self.analyzer._get_node_style(file_path)
                mermaid.append(f"    {node_id}[{node_label}]{style}")

        # Add relationships
        for file_path, deps in dependencies.items():
            source_id = self.analyzer.get_module_name(file_path).replace('.', '_')
            for dep in deps:
                target_id = self.analyzer.get_module_name(dep).replace('.', '_')
                mermaid.append(f"    {source_id} --> {target_id}")

        return "\n".join(mermaid)

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

            # Send AI analysis start message
            await self.analyzer.send_activity(
                action="starting_ai_analysis",
                file_path="project_dependencies",
                details={
                    "total_files": analysis["total_files"],
                    "files_with_deps": analysis["files_with_deps"]
                }
            )

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
COUPLING LEVELS:
- LOW: 0-5 dependencies (typical for utility modules)
- MODERATE: 6-8 dependencies (common for core modules)
- HIGH: 9-11 dependencies (investigate if necessary)
- EXCESSIVE: 12+ dependencies (should be refactored)
PROJECT STATISTICS:
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
2. Note any potential areas/ideas for significant improvement
3. If suggesting improvements, focus on significant patterns rather than isolated cases
Keep the response under 290 words and maintain a positive constructive tone."""

            result = await self.analyzer.llm_client.generate(
                prompt=prompt,
                max_tokens=1320,
                temperature=0.6
            )

            if result and result.get('response'):
                # Send AI analysis complete message
                await self.analyzer.send_activity(
                    action="ai_analysis_complete",
                    file_path="project_dependencies",
                    details={
                        "analysis": result['response'],
                        "metrics": analysis
                    }
                )
                return result['response']

            return None

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
        monitor.running = True  # Set running state before starting

        # Generate initial visualization before starting monitor
        vis_path = os.path.join(path, 'dependency_graph.md')
        if not os.path.exists(vis_path):
            logger.info("No existing dependency graph found. Generating initial visualization...")
            try:
                await monitor.visualizer.update_visualization()
                logger.info("Initial dependency graph generated successfully")
            except Exception as e:
                logger.error(f"Failed to generate initial visualization: {e}", exc_info=True)
                raise
        else:
            logger.info(f"Found existing dependency graph at {vis_path}")

        # Start monitoring and keep running
        await monitor.start(path)  # This will start both file monitoring and the BaseAgent run loop

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
