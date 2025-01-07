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
        self.callback = callback
        
    def on_modified(self, event):
        if event.is_directory:
            return
        if not event.src_path.endswith('.py'):
            return
        self.callback(event.src_path)

class BaseAgent(ABC):
    """Base agent class implementing common functionality."""
    
    def __init__(self, name: str, config_path: str = 'config.ini'):
        self.name = name
        self.config = self._load_config(config_path)
        self.controller_url = self.config.get('controller_url', 'http://localhost:8000')
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self.observer: Optional[Observer] = None
        self.current_task: Optional[str] = None
        self.last_activity = datetime.now()
        self.running = False
        self.monitor_path: Optional[str] = None
        self.health_check_interval = 30  # seconds
        self.logger = AgentLogger(self.name)

    def _load_config(self, config_path: str) -> Dict[str, str]:
        """Load configuration from file."""
        if not os.path.exists(config_path):
            return {}
            
        config = configparser.ConfigParser()
        config.read(config_path)
        
        if self.name not in config:
            return {}
            
        return dict(config[self.name])

    async def connect(self):
        """Connect to the controller via WebSocket."""
        ws_url = f"ws://localhost:8000/ws"
        try:
            self.ws = await websockets.connect(ws_url)
            await self.ws.send(json.dumps({
                "type": "agent_connect",
                "data": {
                    "name": self.name,
                    "status": self.get_status()
                }
            }))
            self.logger.info("Connected to controller")
            return True
        except Exception as e:
            self.logger.error(f"Failed to connect to controller: {e}")
            return False

    async def disconnect(self):
        """Disconnect from the controller."""
        if self.ws:
            try:
                await self.ws.close()
            except Exception as e:
                self.logger.error(f"Error closing WebSocket connection: {e}")
            self.ws = None

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
            "websocket_connected": self.ws is not None and not self.ws.closed
        }

    async def report_status(self):
        """Report current status to controller."""
        if not self.ws:
            return
        
        try:
            await self.ws.send(json.dumps({
                "type": "agent_status",
                "data": self.get_status()
            }))
        except Exception as e:
            self.logger.error(f"Error reporting status: {e}")
            await self.reconnect()

    async def reconnect(self):
        """Attempt to reconnect to the controller."""
        await self.disconnect()
        for attempt in range(5):  # 5 retry attempts
            self.logger.info(f"Reconnection attempt {attempt + 1}")
            if await self.connect():
                return True
            await asyncio.sleep(2 ** attempt)  # Exponential backoff
        return False

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
        if self.ws:
            try:
                await self.ws.send(json.dumps({
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

    def start_monitoring(self, path: str):
        """Start monitoring a directory for changes."""
        if self.observer:
            self.observer.stop()
            self.observer = None

        try:
            path = os.path.abspath(path)
            if not os.path.exists(path):
                os.makedirs(path)
            elif not os.path.isdir(path):
                raise NotADirectoryError(f"Not a directory: {path}")

            self.monitor_path = path
            self.observer = Observer()
            self.observer.schedule(
                BaseFileHandler(self.handle_file_change),
                path,
                recursive=True
            )
            self.observer.start()
            self.running = True
            self.logger.info(f"Started monitoring: {path}")
            return True
        except Exception as e:
            self.logger.error(f"Error starting monitoring: {e}")
            return False

    def stop_monitoring(self):
        """Stop monitoring directory."""
        if self.observer:
            self.observer.stop()
            self.observer = None
        self.running = False
        self.monitor_path = None
        self.logger.info("Stopped monitoring")

    async def run(self):
        """Main agent run loop."""
        try:
            if not await self.connect():
                return

            # Start health check loop
            asyncio.create_task(self._health_check_loop())

            while True:
                try:
                    if not self.ws:
                        if not await self.reconnect():
                            break
                    
                    # Handle WebSocket messages
                    message = await self.ws.recv()
                    data = json.loads(message)
                    
                    if data["type"] == "stop":
                        break
                    elif data["type"] == "path_update":
                        new_path = data["data"]["path"]
                        self.start_monitoring(new_path)
                    
                    # Update last activity
                    self.last_activity = datetime.now()
                    
                except websockets.exceptions.ConnectionClosed:
                    if not await self.reconnect():
                        break
                except Exception as e:
                    self.logger.error(f"Error in run loop: {e}")
                    await asyncio.sleep(1)

        finally:
            self.stop_monitoring()
            await self.disconnect()

    async def _health_check_loop(self):
        """Periodic health check and status report."""
        while self.running:
            await self.report_status()
            await asyncio.sleep(self.health_check_interval)

    @abstractmethod
    def handle_file_change(self, file_path: str):
        """Handle file change event. Must be implemented by subclasses."""
        pass

    @abstractmethod
    async def process_file(self, file_path: str):
        """Process a file. Must be implemented by subclasses."""
        pass 

    async def log_activity(self, action: str, file_path: str) -> None:
        """Log a high-visibility activity message.
        
        Args:
            action: The action being performed (e.g., 'analyzing', 'generating')
            file_path: The file being acted upon
        """
        rel_path = os.path.relpath(file_path, self.workspace_root) if hasattr(self, 'workspace_root') else file_path
        message = f"Agent {self.name} is {action} {rel_path}"
        await self.log('info', message, category='activity', file=rel_path)

    def check_dependencies(self) -> bool:
        # This method is not implemented in the original code block, so it's left unchanged
        pass 