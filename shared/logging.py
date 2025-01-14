#!/usr/bin/env python3
"""Shared logging utilities for Code Swarm."""

import os
import json
import logging
from typing import Optional, Dict, Any
from datetime import datetime
from pathlib import Path

class AgentLogger:
    """Logging wrapper for Code Swarm agents."""

    _instances = {}

    def __new__(cls, agent_name: str):
        """Create or return existing logger instance for the agent.

        Args:
            agent_name: Name of the agent

        Returns:
            AgentLogger instance (new or existing)
        """
        if agent_name not in cls._instances:
            instance = super().__new__(cls)
            cls._instances[agent_name] = instance
            instance._initialized = False
        return cls._instances[agent_name]

    def __init__(self, agent_name: str):
        """Initialize logger for an agent.

        Args:
            agent_name: Name of the agent
        """
        # Skip if already initialized
        if getattr(self, '_initialized', False):
            return

        self.agent_name = agent_name
        self.logger = logging.getLogger(f'agent_{agent_name}')
        self.logger.setLevel(logging.INFO)

        # Remove any existing handlers
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)

        # Create logs directory if it doesn't exist
        log_dir = Path('logs')
        log_dir.mkdir(exist_ok=True)

        # File handler
        log_file = log_dir / f'agent_code_mon_{agent_name}.log'
        fh = logging.FileHandler(log_file)
        fh.setLevel(logging.INFO)

        # Console handler
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)

        # Formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        fh.setFormatter(formatter)
        ch.setFormatter(formatter)

        # Add handlers
        self.logger.addHandler(fh)
        self.logger.addHandler(ch)

        self.log_file = log_file
        self._initialized = True

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

    async def log_activity(self, action: str, file_path: str) -> None:
        """Log a high-visibility activity message.

        Args:
            action: The action being performed (e.g., 'analyzing', 'generating')
            file_path: The file being acted upon
        """
        message = f"Agent {self.agent_name} is {action} {file_path}"
        self.info(message, category='activity', file=file_path)

    def exception(self, message: str, category: str = 'general', **kwargs):
        """Log an exception with traceback."""
        self.logger.exception(f" [{category}] {message}", extra=kwargs) 