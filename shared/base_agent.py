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
        success = True
        
        # Connect to logs endpoint
        try:
            self.ws_logs = await websockets.connect(f"ws://localhost:8000/ws/logs")
            self.logger.info("Connected to log stream")
        except Exception as e:
            self.logger.error(f"Failed to connect to log stream: {e}")
            success = False

        # Connect to agent endpoint
        try:
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
                    self.reconnect_attempts = 0  # Reset counter on successful connection
                else:
                    self.logger.error(f"Unexpected response during handshake: {data}")
                    success = False
            except asyncio.TimeoutError:
                self.logger.error("Timeout waiting for connection confirmation")
                success = False
            except Exception as e:
                self.logger.error(f"Error during handshake: {e}")
                success = False
                
        except Exception as e:
            self.logger.error(f"Failed to connect to agent message stream: {e}")
            success = False

        if not success:
            await self.disconnect()
            
        return success

    async def disconnect(self):
        """Disconnect from the controller."""
        if self.ws_logs:
            try:
                if not getattr(self.ws_logs, 'closed', False):
                    await self.ws_logs.close()
            except Exception as e:
                self.logger.error(f"Error closing log WebSocket connection: {e}")
            self.ws_logs = None

        if self.ws_agent:
            try:
                if not getattr(self.ws_agent, 'closed', False):
                    await self.ws_agent.close()
            except Exception as e:
                self.logger.error(f"Error closing agent WebSocket connection: {e}")
            self.ws_agent = None

    async def reconnect(self):
        """Attempt to reconnect to the controller."""
        self.reconnect_attempts += 1
        if self.reconnect_attempts > self.max_reconnect_attempts:
            self.logger.error("Max reconnection attempts reached")
            return False

        await self.disconnect()
        delay = self.reconnect_delay * (2 ** (self.reconnect_attempts - 1))  # Exponential backoff
        self.logger.info(f"Attempting reconnection in {delay} seconds (attempt {self.reconnect_attempts})")
        await asyncio.sleep(delay)
        
        return await self.connect()

    async def ensure_connection(self):
        """Ensure WebSocket connections are active."""
        if not self.ws_agent or getattr(self.ws_agent, 'closed', True):
            return await self.reconnect()
        return True

    async def send_activity(self, action: str, file_path: str, details: dict = None):
        """Send an activity message through the agent WebSocket."""
        if not await self.ensure_connection():
            return

        try:
            message = {
                "type": "agent_activity",
                "timestamp": datetime.now().isoformat(),
                "agent": self.name,
                "data": {
                    "action": action,
                    "file_path": file_path,
                    "details": details or {}
                }
            }
            await self.ws_agent.send(json.dumps(message))
            self.last_activity = datetime.now()
        except Exception as e:
            self.logger.error(f"Failed to send activity message: {e}")
            await self.reconnect()

    async def send_status(self):
        """Send current status through the agent WebSocket."""
        if not await self.ensure_connection():
            return

        try:
            message = {
                "type": "agent_status",
                "timestamp": datetime.now().isoformat(),
                "agent": self.name,
                "data": self.get_status()
            }
            await self.ws_agent.send(json.dumps(message))
        except Exception as e:
            self.logger.error(f"Failed to send status message: {e}")
            await self.reconnect()

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

    async def run(self):
        """Main agent run loop."""
        try:
            if not await self.connect():
                return

            # Start health check loop
            health_check_task = asyncio.create_task(self._health_check_loop())

            while self.running:
                try:
                    if not self.ws_agent:
                        if not await self.reconnect():
                            break
                    
                    # Handle WebSocket messages
                    message = await self.ws_agent.recv()
                    data = json.loads(message)
                    await self.handle_controller_message(data)
                    
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
            if 'health_check_task' in locals():
                health_check_task.cancel()

    async def _health_check_loop(self):
        """Periodic health check and status report."""
        while self.running:
            await self.send_status()
            await asyncio.sleep(self.health_check_interval)

    async def log_activity(self, action: str, file_path: str, details: dict = None):
        """Log activity and send it through both logging and agent websocket."""
        # Log through regular logging system
        await self.log('info', f"{action}: {file_path}", category='activity')
        
        # Send through agent websocket
        await self.send_activity(action, file_path, details)

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
            await self.reconnect()

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

    async def send_agent_message(self, msg_type: str, data: dict) -> None:
        """Send a typed message to controller.
        
        Args:
            msg_type: The type of message (e.g., 'agent_activity', 'ai_analysis')
            data: The message data matching the type's schema
        """
        if not self.ws_agent:
            self.logger.warning(f"Cannot send agent message, no websocket connection: {msg_type}")
            return
        
        try:
            message = {
                "type": msg_type,
                "timestamp": datetime.now().isoformat(),
                "agent": self.name,
                "data": data
            }
            
            self.logger.debug(f"Sending agent message: {msg_type}")
            await self.ws_agent.send(json.dumps(message))
            self.logger.debug(f"Successfully sent agent message: {msg_type}")
        except Exception as e:
            self.logger.error(f"Error sending agent message: {e}")
            await self.reconnect() 