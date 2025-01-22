#!/usr/bin/env python3
"""Base agent implementation with common functionality for all agents."""

import os
import sys
import json
import logging
import asyncio
import aiohttp
import websockets
import configparser
from datetime import datetime
from typing import Optional, Dict, Any, List
from abc import ABC, abstractmethod
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from shared.agent_logger import AgentLogger

class BaseFileHandler(FileSystemEventHandler):
    """Base file handler for watching file changes."""

    def __init__(self, callback):
        """Initialize the handler with a callback function.
        
        Args:
            callback: Function to call with (event_type, file_path) when files change.
                     event_type will be one of: 'created', 'modified', 'deleted'
        """
        self.callback = callback
        self.watch_patterns = ('.py', '.lua')  # Default patterns to watch
        self._last_events = {}  # Track last event times to debounce

    def should_process_file(self, file_path: str) -> bool:
        """Check if a file should be processed based on its extension."""
        return any(file_path.endswith(ext) for ext in self.watch_patterns)

    def _debounce_event(self, event_path: str) -> bool:
        """Debounce events to prevent duplicates.
        Returns True if event should be processed."""
        now = datetime.now().timestamp()
        last_time = self._last_events.get(event_path, 0)
        
        # Ignore events that are too close together (within 100ms)
        if now - last_time < 0.1:
            return False
            
        self._last_events[event_path] = now
        return True

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

class BaseAgent(ABC):
    """Base agent class implementing common functionality."""

    def __init__(self, name: str, config_path: str = 'config.ini'):
        self.name = name
        self.config = self._load_config(config_path)
        self.controller_url = self.config.get('controller_url', 'http://localhost:8000')
        self.ws_logs: Optional[websockets.WebSocketClientProtocol] = None
        self.ws_agent: Optional[websockets.WebSocketClientProtocol] = None
        self.observer: Optional[Observer] = None
        self.current_task: Optional[str] = None
        self.last_activity = datetime.now()
        self.running = False
        self.monitor_path: Optional[str] = None
        self.health_check_interval = 30  # seconds
        self.logger = AgentLogger(self.name)
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 5
        self.reconnect_delay = 2  # seconds
        self._connection_lock = asyncio.Lock()  # Add connection lock
        self._is_connecting = False  # Add connection state flag

    def _load_config(self, config_path: str) -> Dict[str, str]:
        """Load configuration from file."""
        if not os.path.exists(config_path):
            return {}

        config = configparser.ConfigParser()
        config.read(config_path)

        if self.name not in config:
            return {}

        return dict(config[self.name])

    async def connect(self) -> bool:
        """Establish permanent connections to the controller.
        If either connection fails, the agent will not start."""
        try:
            # Connect to logs endpoint
            self.ws_logs = await websockets.connect(f"ws://localhost:8000/ws/logs")
            self.logger.info("Connected to log stream")

            # Connect to agent endpoint
            self.ws_agent = await websockets.connect(f"ws://localhost:8000/ws/agent")

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

    async def disconnect(self):
        """Clean shutdown of connections."""
        if self.ws_logs:
            try:
                await self.ws_logs.close()
            except Exception as e:
                self.logger.error(f"Error closing log connection: {e}")
            finally:
                self.ws_logs = None

        if self.ws_agent:
            try:
                await self.ws_agent.close()
            except Exception as e:
                self.logger.error(f"Error closing agent connection: {e}")
            finally:
                self.ws_agent = None

    async def send_agent_message(self, msg_type: str, data: dict) -> None:
        """Send a typed message to controller."""
        if not self.ws_agent:
            self.logger.error(f"Cannot send message, no connection: {msg_type}")
            self.running = False  # Fatal error - trigger shutdown
            return

        try:
            message = {
                "type": msg_type,
                "timestamp": datetime.now().isoformat(),
                "agent": self.name,
                "data": data
            }
            await self.ws_agent.send(json.dumps(message))
            self.last_activity = datetime.now()
        except Exception as e:
            self.logger.error(f"Failed to send message: {e}")
            self.running = False  # Fatal error - trigger shutdown

    async def run(self):
        """Main agent run loop."""
        try:
            # Establish connections
            if not await self.connect():
                self.logger.error("Failed to establish connections")
                return

            self.running = True
            
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
                    break  # Fatal error - exit loop
                except Exception as e:
                    self.logger.error(f"Error in message loop: {e}")
                    break  # Fatal error - exit loop

        finally:
            self.running = False
            self.stop_monitoring()
            await self.disconnect()
            if 'health_check_task' in locals():
                health_check_task.cancel()

    async def _health_check_loop(self):
        """Periodic health check and status report."""
        while self.running:
            try:
                await self.send_agent_message("agent_status", self.get_status())
            except Exception as e:
                self.logger.error(f"Health check failed: {e}")
                break  # Fatal error - exit loop
            await asyncio.sleep(self.health_check_interval)

    async def handle_controller_message(self, message: dict):
        """Handle messages received from the controller."""
        try:
            msg_type = message.get('type')
            if msg_type == 'stop':
                self.running = False
            elif msg_type == 'path_update':
                new_path = message.get('data', {}).get('path')
                if new_path:
                    self.start_monitoring(new_path)
            # Add more message type handlers as needed
        except Exception as e:
            self.logger.error(f"Error handling controller message: {e}")

    async def log_activity(self, action: str, file_path: str, details: dict = None):
        """Log activity and send it through both logging and agent websocket."""
        # Log through regular logging system
        await self.log('info', f"{action}: {file_path}", category='activity')

        # Send through agent websocket
        await self.send_agent_message("agent_activity", {
            "action": action,
            "file_path": file_path,
            "details": details or {}
        })

    def get_status(self) -> Dict[str, Any]:
        """Get current agent status."""
        return {
            "name": self.name,
            "running": self.running,
            "current_task": self.current_task,
            "last_activity": self.last_activity.isoformat(),
            "monitor_path": self.monitor_path,
            "health": self.check_health()
        }

    def check_health(self) -> Dict[str, Any]:
        """Check agent health status."""
        return {
            "status": "healthy" if self.running else "stopped",
            "last_activity_age": (datetime.now() - self.last_activity).total_seconds(),
            "websocket_connected": self.ws_agent is not None and not getattr(self.ws_agent, 'closed', True)
        }

    async def report_status(self):
        """Report current status to controller."""
        if not self.ws_agent:
            return

        try:
            await self.ws_agent.send(json.dumps({
                "type": "agent_status",
                "data": self.get_status()
            }))
        except Exception as e:
            self.logger.error(f"Error reporting status: {e}")

    async def log(self, level: str, category: str, message: str, **kwargs):
        """Send structured log message to controller."""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "agent": self.name,
            "level": level,
            "category": category,
            "message": message,
            "data": kwargs
        }

        # Log locally using AgentLogger
        await self.logger.log(level, message, category=category, **kwargs)

        # Send to controller
        if self.ws_logs:
            try:
                await self.ws_logs.send(json.dumps({
                    "type": "agent_log",
                    "data": log_entry
                }))
            except Exception as e:
                self.logger.error(f"Error sending log to controller: {e}")

    async def get_llm_analysis(self, prompt: str) -> Optional[Dict[str, Any]]:
        """Get LLM analysis using controller's LLM service."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.controller_url}/api/llm/generate",
                    json={
                        "prompt": prompt,
                        "agent": self.name,
                        "model": self.config.get('ollama_model', 'llama3.2')
                    }
                ) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        self.logger.error(f"LLM request failed: {response.status}")
                        return None
        except Exception as e:
            self.logger.error(f"Error getting LLM analysis: {e}")
            return None

    def _handle_file_change(self, event_type: str, file_path: str):
        """Handle file change events from the file handler.
        
        Args:
            event_type: Type of event ('created', 'modified', or 'deleted')
            file_path: Path to the file that changed
        """
        try:
            self.log_activity(f"File {event_type}: {file_path}")
            self.handle_file_change(event_type, file_path)
        except Exception as e:
            self.log_error(f"Error handling file change: {str(e)}")

    @abstractmethod
    def handle_file_change(self, event_type: str, file_path: str):
        """Handle a file change event. Must be implemented by subclasses.
        
        Args:
            event_type: Type of event ('created', 'modified', or 'deleted')
            file_path: Path to the file that changed
        """
        pass

    def start_monitoring(self, path: str):
        """Start monitoring a directory for file changes."""
        try:
            if hasattr(self, '_observer') and self._observer is not None:
                self.stop_monitoring()

            self._observer = Observer()
            self._event_handler = BaseFileHandler(self._handle_file_change)
            self._observer.schedule(self._event_handler, path, recursive=True)
            self._observer.start()
            self.log_activity(f"Started monitoring directory: {path}")
        except Exception as e:
            self.log_error(f"Error starting file monitoring: {str(e)}")

    def stop_monitoring(self):
        """Stop monitoring for file changes."""
        try:
            if hasattr(self, '_observer') and self._observer is not None:
                self._observer.stop()
                self._observer.join()
                self._observer = None
                self.log_activity("Stopped file monitoring")
        except Exception as e:
            self.log_error(f"Error stopping file monitoring: {str(e)}") 