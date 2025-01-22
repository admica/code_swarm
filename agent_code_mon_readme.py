#!/usr/bin/env python3
"""
README Documentation Agent - Monitors Python/Lua files and generates/updates README documentation
using LLM analysis.
"""

import os
import sys
import json
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Set, Tuple
from dataclasses import dataclass, field
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import fnmatch
import signal
from queue import Queue
from threading import Lock
import aiohttp
import websockets
import configparser

from shared.base_agent import BaseAgent, BaseFileHandler

@dataclass
class FileCache:
    """Cache for file content and metadata."""
    content: str                   # Full file content
    last_modified: float          # File's mtime
    last_analyzed: float          # When we last processed it
    sections: Dict[str, str] = field(default_factory=dict)  # Cached section analysis
    
    def content_changed(self, new_content: str) -> bool:
        """Check if content has meaningfully changed."""
        return self.content != new_content
    
    def update(self, new_content: str, new_mtime: float) -> bool:
        """Update cache with new content. Returns True if content changed."""
        changed = self.content_changed(new_content)
        self.content = new_content
        self.last_modified = new_mtime
        if changed:
            self.last_analyzed = 0  # Reset analysis time if content changed
        return changed

class ReadmeFileHandler(BaseFileHandler):
    """Custom file handler for README agent."""
    
    def __init__(self, agent):
        self.agent = agent
        super().__init__(self.agent._sync_handle_change)
        
    def on_created(self, event):
        """Handle file creation events."""
        if event.is_directory:
            return
        if not self.should_process_file(event.src_path):
            return
        if self._debounce_event(event.src_path):
            self.callback('created', event.src_path)

    def on_modified(self, event):
        """Handle file modification events."""
        if event.is_directory:
            return
        if not self.should_process_file(event.src_path):
            return
        if self._debounce_event(event.src_path):
            self.callback('modified', event.src_path)

    def on_deleted(self, event):
        """Handle file deletion events."""
        if event.is_directory:
            return
        if not self.should_process_file(event.src_path):
            return
        if self._debounce_event(event.src_path):
            self.callback('deleted', event.src_path)
            if event.src_path in self._last_events:
                del self._last_events[event.src_path]

class ReadmeAgent(BaseAgent):
    """Agent for monitoring code files and maintaining README documentation."""

    def __init__(self, name: str = "agent_code_mon_readme", config_path: str = "config.ini"):
        """Initialize the README agent."""
        super().__init__(name, config_path)
        
        # File processing state
        self.file_cache: Dict[str, FileCache] = {}
        self.pending_files: Set[str] = set()
        self.monitor_path = None  # Track monitored path
        
        # Event queue for thread safety
        self._event_queue = Queue()
        self._queue_lock = Lock()
        
        # Load full config to access template values
        full_config = configparser.ConfigParser()
        full_config.read(config_path)
        template_config = dict(full_config['agent_template']) if 'agent_template' in full_config else {}
        
        # Configuration with template fallbacks
        self.controller_url = self.config.get('controller_url', template_config.get('controller_url', 'http://localhost:8000'))
        self.watch_patterns = self.config.get('watch_patterns', template_config.get('watch_patterns', '*.py,*.lua')).split(',')
        self.ignore_patterns = self.config.get('ignore_patterns', template_config.get('ignore_patterns', '__pycache__/*,.*,venv/*,venv_linux/*,node_modules/*,.git/*')).split(',')
        self.debounce_delay = float(self.config.get('debounce_delay', template_config.get('debounce_delay', '2.0')))
        
        # Agent-specific configuration (no template fallbacks)
        self.batch_window = float(self.config.get('batch_window', 2.0))
        self.max_queue_size = int(self.config.get('max_queue_size', 50))
        self.llm_timeout = int(self.config.get('llm_timeout', 180))
        self.llm_retries = int(self.config.get('llm_retries', 3))
        self.cache_enabled = self.config.get('cache_enabled', 'true').lower() == 'true'
        
        # LLM configuration (with template fallback for model)
        self.llm_model = self.config.get('llm_model', template_config.get('ollama_model', 'llama3.2'))
        self.llm_max_tokens = int(self.config.get('llm_max_tokens', 2048))
        self.llm_temperature = float(self.config.get('llm_temperature', 0.7))
        
        # README configuration with template fallbacks
        self.readme_sections = self.config.get('readme_sections', 'overview,installation,usage,api,examples').split(',')
        self.ai_start_marker = self.config.get('ai_start_marker', template_config.get('ai_marker_begin', '<!-- AI-GENERATED CONTENT START -->'))
        self.ai_end_marker = self.config.get('ai_end_marker', template_config.get('ai_marker_end', '<!-- AI-GENERATED CONTENT END -->'))
        
        # Batch processing state
        self._batch_task = None
        self._event_processor = None
        self._shutdown = False
        self._event_handler = None
        self._observer = None

    def get_status(self) -> Dict[str, Any]:
        """Get current agent status."""
        status = super().get_status()
        status.update({
            "agent_type": "readme",  # Identify agent type
            "capabilities": ["llm", "file_monitor"],  # Declare capabilities
            "monitor_status": {
                "running": self.running,
                "path": self.monitor_path,
                "monitored_files": len(self.file_cache),
                "watch_patterns": self.watch_patterns,
                "ignore_patterns": self.ignore_patterns,
                "pending_changes": len(self.pending_files)
            },
            "readme_status": {
                "queue_size": len(self.pending_files),
                "cache": self._get_cache_stats(),
                "sections": self.readme_sections,
                "last_generation": max((f.last_analyzed for f in self.file_cache.values()), default=0)
            }
        })
        return status

    def _get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        now = datetime.now().timestamp()
        return {
            'total_files': len(self.file_cache),
            'pending_analysis': sum(1 for f in self.file_cache.values() if f.last_analyzed == 0),
            'recently_analyzed': sum(1 for f in self.file_cache.values() if 0 < now - f.last_analyzed <= 3600),
            'average_file_size': sum(len(f.content) for f in self.file_cache.values()) // max(len(self.file_cache), 1)
        }

    async def get_llm_analysis(self, prompt: str) -> Optional[Dict[str, Any]]:
        """Get LLM analysis using controller's LLM service."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.controller_url}/api/llm/generate",
                    json={
                        "prompt": prompt,
                        "agent": self.name,
                        "model": self.llm_model,
                        "max_tokens": self.llm_max_tokens,
                        "temperature": self.llm_temperature
                    }
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        return result
                    else:
                        error_content = await response.text()
                        self.logger.error(f"LLM request failed: {response.status} - {error_content}")
                        return None
        except Exception as e:
            self.logger.error(f"Error getting LLM analysis: {e}")
            return None

    def start_monitoring(self, path: str):
        """Start monitoring a directory for file changes."""
        try:
            if self._observer:
                self.stop_monitoring()

            # Store the monitored path
            self.monitor_path = os.path.abspath(path)
            
            # Create directory if it doesn't exist
            if not os.path.exists(self.monitor_path):
                os.makedirs(self.monitor_path)
            elif not os.path.isdir(self.monitor_path):
                raise NotADirectoryError(f"Not a directory: {self.monitor_path}")

            # Set up the observer with our custom handler
            self._observer = Observer()
            self._event_handler = ReadmeFileHandler(self)
            self._observer.schedule(
                self._event_handler,
                self.monitor_path,
                recursive=True
            )
            self._observer.start()
            self.running = True
            
            # Log success
            self.logger.info(f"Started monitoring: {self.monitor_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error starting monitoring: {e}")
            return False

    def stop_monitoring(self):
        """Stop monitoring for file changes."""
        if self._observer:
            self._observer.stop()
            self._observer.join()
            self._observer = None
            self.monitor_path = None
            self.running = False
            self.logger.info("Stopped monitoring")

    def _sync_handle_change(self, event_type: str, file_path: str):
        """Thread-safe handler for file changes."""
        if self.running and not self._shutdown:
            with self._queue_lock:
                self._event_queue.put((event_type, file_path))

    async def _process_event_queue(self):
        """Process events from the queue in the async context."""
        while self.running and not self._shutdown:
            try:
                # Process all available events
                while not self._event_queue.empty():
                    with self._queue_lock:
                        event_type, file_path = self._event_queue.get_nowait()
                    await self.handle_file_change(event_type, file_path)
                
                # Wait before checking again
                await asyncio.sleep(0.1)
            except Exception as e:
                self.logger.error(f"Error processing event queue: {e}")

    async def handle_file_change(self, event_type: str, file_path: str) -> None:
        """Handle file change events."""
        if not self.running or self._shutdown:
            return

        # For deletions, remove from cache and skip processing
        if event_type == 'deleted':
            if file_path in self.file_cache:
                del self.file_cache[file_path]
            return

        if not os.path.exists(file_path) or not os.path.isfile(file_path):
            return

        # Skip if file is in ignore patterns
        for pattern in self.ignore_patterns:
            if fnmatch.fnmatch(file_path, pattern):
                return

        # Only process files that match the watch patterns
        if not any(fnmatch.fnmatch(file_path, pattern) for pattern in self.watch_patterns):
            return

        # Log the change
        await self.log_activity(
            action=f"file_{event_type}",
            file_path=file_path,
            details={"status": "queued"}
        )

        self.pending_files.add(file_path)
        
        # Start batch processing if not already running
        if not self._batch_task or self._batch_task.done():
            self._batch_task = asyncio.create_task(self._process_batch())

    async def _process_batch(self) -> None:
        """Process batched file changes."""
        while self.running and not self._shutdown:
            if not self.pending_files:
                break

            # Wait for batch window to collect changes
            await asyncio.sleep(self.batch_window)
            
            # Process files in batch
            files_to_process = list(self.pending_files)[:self.max_queue_size]
            self.pending_files.difference_update(files_to_process)

            for file_path in files_to_process:
                try:
                    await self._process_file(file_path)
                except Exception as e:
                    await self.log('error', 'file_processing', f"Error processing {file_path}: {e}")

    async def _process_file(self, file_path: str) -> None:
        """Process a single file change."""
        try:
            # Get file stats and content
            stats = os.stat(file_path)
            with open(file_path, 'r', encoding='utf-8') as f:
                new_content = f.read()

            # Check cache if enabled
            if self.cache_enabled:
                cached = self.file_cache.get(file_path)
                if cached:
                    if not cached.update(new_content, stats.st_mtime):
                        await self.log_activity(
                            action="file_skipped",
                            file_path=file_path,
                            details={
                                "reason": "no_content_changes",
                                "last_analyzed": datetime.fromtimestamp(cached.last_analyzed).isoformat()
                            }
                        )
                        return
                else:
                    # New file, create cache entry
                    self.file_cache[file_path] = FileCache(
                        content=new_content,
                        last_modified=stats.st_mtime,
                        last_analyzed=0  # Never analyzed
                    )

            # Generate/update README
            await self._update_readme(file_path, new_content)
            
            # Update last analyzed time
            if file_path in self.file_cache:
                self.file_cache[file_path].last_analyzed = datetime.now().timestamp()
            
        except Exception as e:
            await self.log('error', 'file_processing', f"Error processing {file_path}: {e}")

    async def _update_readme(self, file_path: str, content: str) -> None:
        """Update README documentation based on file changes."""
        try:
            # Generate README path by appending _README.md to the input file path
            readme_path = f"{file_path}_README.md"
            
            # Generate documentation using LLM
            prompt = self._generate_readme_prompt(file_path, content)
            
            await self.log_activity(
                action="llm_request",
                file_path=file_path,
                details={"status": "started"}
            )
            
            for attempt in range(self.llm_retries):
                try:
                    response = await asyncio.wait_for(
                        self.get_llm_analysis(prompt),
                        timeout=self.llm_timeout
                    )
                    if response and response.get('response'):
                        break
                except asyncio.TimeoutError:
                    if attempt == self.llm_retries - 1:
                        raise
                    await asyncio.sleep(1)
                    continue

            if not response or not response.get('response'):
                await self.log('error', 'readme_generation', f"Failed to generate README content for {file_path}")
                return

            # Update README file
            await self._write_readme(readme_path, response['response'])
            
            await self.log_activity(
                action="readme_updated",
                file_path=readme_path,
                details={
                    "source_file": file_path,
                    "status": "completed"
                }
            )

        except Exception as e:
            await self.log('error', 'readme_generation', f"Error updating README for {file_path}: {e}")

    def _generate_readme_prompt(self, file_path: str, content: str) -> str:
        """Generate prompt for README documentation."""
        return f"""Analyze the following code file and generate documentation for a README.md file.
Focus on these sections: {', '.join(self.readme_sections)}

File: {file_path}

Content:
{content}

Please provide clear, concise documentation that explains the purpose, functionality, and usage of this code.
Include relevant examples where appropriate.
"""

    async def _write_readme(self, readme_path: str, content: str) -> None:
        """Write content to README file with AI markers."""
        try:
            existing_content = ''
            if os.path.exists(readme_path):
                with open(readme_path, 'r', encoding='utf-8') as f:
                    existing_content = f.read()

            # Extract non-AI content
            start_idx = existing_content.find(self.ai_start_marker)
            end_idx = existing_content.find(self.ai_end_marker)
            
            if start_idx == -1 or end_idx == -1:
                # No existing AI content, append new content
                final_content = f"{existing_content}\n\n{self.ai_start_marker}\n{content}\n{self.ai_end_marker}"
            else:
                # Replace existing AI content
                before = existing_content[:start_idx]
                after = existing_content[end_idx + len(self.ai_end_marker):]
                final_content = f"{before}{self.ai_start_marker}\n{content}\n{self.ai_end_marker}{after}"

            # Write updated content
            with open(readme_path, 'w', encoding='utf-8') as f:
                f.write(final_content)

        except Exception as e:
            await self.log('error', 'readme_write', f"Error writing README {readme_path}: {e}")

    async def stop(self) -> None:
        """Stop the agent."""
        self._shutdown = True
        
        try:
            # Stop batch processing
            if self._batch_task:
                self._batch_task.cancel()
                try:
                    await self._batch_task
                except asyncio.CancelledError:
                    pass

            # Stop monitoring and disconnect (handled by base agent)
            await super().stop()

        except Exception as e:
            self.logger.error(f"Error during shutdown: {e}")

    async def handle_controller_message(self, message: dict):
        """Handle messages received from the controller."""
        try:
            msg_type = message.get('type')
            if msg_type == 'readme_config':
                # Handle README-specific configuration updates
                config = message.get('data', {})
                if 'sections' in config:
                    self.readme_sections = config['sections']
                if 'cache_enabled' in config:
                    self.cache_enabled = config['cache_enabled']
                await self.log_activity(
                    action="config_updated",
                    file_path="",
                    details={"config": config}
                )
            elif msg_type == 'cache_invalidate':
                # Handle cache invalidation requests
                patterns = message.get('data', {}).get('patterns', ['*'])
                invalidated = 0
                for file_path in list(self.file_cache.keys()):
                    for pattern in patterns:
                        if fnmatch.fnmatch(file_path, pattern):
                            self.file_cache[file_path].last_analyzed = 0
                            invalidated += 1
                            break
                await self.log_activity(
                    action="cache_invalidated",
                    file_path="",
                    details={"patterns": patterns, "count": invalidated}
                )
            else:
                # Handle base messages
                await super().handle_controller_message(message)
        except Exception as e:
            self.logger.error(f"Error handling controller message: {e}")

    async def run(self):
        """Main agent run loop."""
        try:
            # Establish connections
            if not await self.connect():
                self.logger.error("Failed to establish connections")
                return

            self.running = True
            
            # Start event queue processor
            self._event_processor = asyncio.create_task(self._process_event_queue())
            
            # Start health check loop
            health_check_task = asyncio.create_task(self._health_check_loop())

            # Main message handling loop
            while self.running:
                try:
                    message = await self.ws_agent.recv()
                    data = json.loads(message)
                    await self.handle_controller_message(data)
                    self.last_activity = datetime.now()
                except websockets.exceptions.ConnectionClosed:
                    self.logger.error("Lost connection to controller")
                    break
                except Exception as e:
                    self.logger.error(f"Error in message loop: {e}")
                    break

        finally:
            self.running = False
            self.stop_monitoring()
            await self.disconnect()
            if 'health_check_task' in locals():
                health_check_task.cancel()
            if self._event_processor:
                self._event_processor.cancel()

    async def log_activity(self, action: str, file_path: str, details: dict = None) -> None:
        """Log activity and send it through both logging and agent websocket."""
        # Log through regular logging system
        self.logger.info(f"{action}: {file_path}", category='activity')

        # Send through agent websocket
        await self.send_agent_message("agent_activity", {
            "action": action,
            "file_path": file_path,
            "details": details or {}
        })

    async def connect(self) -> bool:
        """Establish permanent connections to the controller."""
        try:
            # Connect to logs endpoint
            self.ws_logs = await websockets.connect(f"ws://localhost:8000/ws/logs")
            self.logger.info("Connected to log stream")

            # Connect to agent endpoint
            self.ws_agent = await websockets.connect(f"ws://localhost:8000/ws/agent")

            # Send initial connect message with capabilities
            connect_message = {
                "type": "agent_connect",
                "timestamp": datetime.now().isoformat(),
                "agent": self.name,
                "data": {
                    "status": self.get_status(),
                    "capabilities": ["llm", "file_monitor"],
                    "agent_type": "readme"
                }
            }
            await self.ws_agent.send(json.dumps(connect_message))

            # Wait for confirmation
            try:
                response = await asyncio.wait_for(self.ws_agent.recv(), timeout=5.0)
                data = json.loads(response)
                if data.get('type') == 'connection_confirmed':
                    self.logger.info("Connected to agent message stream")
                    return True
                else:
                    self.logger.error(f"Unexpected response during handshake: {data}")
                    return False
            except asyncio.TimeoutError:
                self.logger.error("Timeout waiting for connection confirmation")
                return False

        except Exception as e:
            self.logger.error(f"Failed to establish connections: {e}")
            await self.disconnect()
            return False

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Usage: agent_code_mon_readme.py <monitor_path>")
        sys.exit(1)
        
    monitor_path = sys.argv[1]
    agent = ReadmeAgent()
    
    # Set up signal handlers for graceful shutdown
    def handle_shutdown(signum, frame):
        print("\nShutting down gracefully...")
        agent._shutdown = True
        if agent._observer:
            agent.stop_monitoring()
        sys.exit(0)
        
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)
    
    # Start the agent
    try:
        if not agent.start_monitoring(monitor_path):
            print("Failed to start monitoring")
            sys.exit(1)
        asyncio.run(agent.run())
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        agent.stop_monitoring() 