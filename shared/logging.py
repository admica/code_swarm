#!/usr/bin/env python3
"""Shared logging utilities for Code Swarm."""

import os
import json
import logging
import asyncio
from typing import Optional, Dict, Any
from datetime import datetime
from pathlib import Path
import websockets

class WebSocketHandler(logging.Handler):
    """Logging handler that sends logs via WebSocket."""
    
    def __init__(self, agent_name: str, websocket: Optional[websockets.WebSocketClientProtocol] = None):
        super().__init__()
        self.agent_name = agent_name
        self.websocket = websocket
        self.queue = asyncio.Queue()
        self.task: Optional[asyncio.Task] = None
    
    def set_websocket(self, websocket: websockets.WebSocketClientProtocol):
        """Update the WebSocket connection."""
        self.websocket = websocket
        if not self.task or self.task.done():
            self.task = asyncio.create_task(self._process_queue())
    
    def emit(self, record: logging.LogRecord):
        """Emit a log record."""
        try:
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "agent": self.agent_name,
                "level": record.levelname.lower(),
                "message": self.format(record),
                "category": record.name,
                "data": {
                    "function": record.funcName,
                    "line": record.lineno,
                    "thread": record.threadName
                }
            }
            
            # Add to queue for async processing
            asyncio.create_task(self.queue.put(log_entry))
            
        except Exception as e:
            print(f"Error in WebSocket logging: {e}")
    
    async def _process_queue(self):
        """Process queued log messages."""
        while True:
            try:
                if not self.websocket:
                    await asyncio.sleep(1)
                    continue
                
                log_entry = await self.queue.get()
                try:
                    await self.websocket.send(json.dumps({
                        "type": "agent_log",
                        "data": log_entry
                    }))
                except websockets.exceptions.WebSocketError:
                    # Put the message back in the queue
                    await self.queue.put(log_entry)
                    await asyncio.sleep(1)
                finally:
                    self.queue.task_done()
            
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Error processing log queue: {e}")
                await asyncio.sleep(1)

class StructuredFileHandler(logging.FileHandler):
    """File handler that writes structured JSON logs."""
    
    def emit(self, record: logging.LogRecord):
        """Emit a log record."""
        try:
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "level": record.levelname.lower(),
                "message": self.format(record),
                "category": record.name,
                "function": record.funcName,
                "line": record.lineno,
                "thread": record.threadName
            }
            
            self.stream.write(json.dumps(log_entry) + '\n')
            self.flush()
            
        except Exception as e:
            print(f"Error in structured file logging: {e}")

class AgentLogger:
    """Logger for Code Swarm agents."""
    
    def __init__(self, agent_name: str, log_dir: str = 'logs'):
        self.agent_name = agent_name
        self.log_dir = log_dir
        self.logger = logging.getLogger(f'agent_{agent_name}')
        self.logger.setLevel(logging.INFO)
        self.ws_handler: Optional[WebSocketHandler] = None
        self._setup_logging()
    
    def _setup_logging(self):
        """Set up logging handlers."""
        # Create log directory if it doesn't exist
        os.makedirs(self.log_dir, exist_ok=True)
        
        # Clear existing handlers
        self.logger.handlers = []
        
        # Add structured file handler
        file_handler = StructuredFileHandler(
            os.path.join(self.log_dir, f'{self.agent_name}.log')
        )
        file_handler.setLevel(logging.INFO)
        self.logger.addHandler(file_handler)
        
        # Add console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)
        
        # Create WebSocket handler (will be connected later)
        self.ws_handler = WebSocketHandler(self.agent_name)
        self.ws_handler.setLevel(logging.INFO)
        self.logger.addHandler(self.ws_handler)
    
    def set_websocket(self, websocket: websockets.WebSocketClientProtocol):
        """Update the WebSocket connection for logging."""
        if self.ws_handler:
            self.ws_handler.set_websocket(websocket)
    
    def log(self, level: str, message: str, category: str = 'general', **kwargs):
        """Log a message with additional context."""
        log_func = getattr(self.logger, level.lower(), self.logger.info)
        
        # Add context to the message
        context = f" [{category}]" if category else ""
        if kwargs:
            context += f" {json.dumps(kwargs)}"
        
        log_func(f"{context} {message}")
    
    def info(self, message: str, category: str = 'general', **kwargs):
        """Log an info message."""
        self.log('info', message, category, **kwargs)
    
    def warning(self, message: str, category: str = 'general', **kwargs):
        """Log a warning message."""
        self.log('warning', message, category, **kwargs)
    
    def error(self, message: str, category: str = 'general', **kwargs):
        """Log an error message."""
        self.log('error', message, category, **kwargs)
    
    def debug(self, message: str, category: str = 'general', **kwargs):
        """Log a debug message."""
        self.log('debug', message, category, **kwargs)
    
    async def flush_logs(self):
        """Ensure all logs are processed before shutdown."""
        if self.ws_handler:
            await self.ws_handler.queue.join()
    
    def close(self):
        """Close all handlers."""
        for handler in self.logger.handlers:
            handler.close()
        self.logger.handlers = [] 