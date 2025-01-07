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
    
    def __init__(self, agent_name: str):
        """Initialize logger for an agent.
        
        Args:
            agent_name: Name of the agent
        """
        self.agent_name = agent_name
        self.logger = logging.getLogger(f'agent_{agent_name}')
        self.logger.setLevel(logging.INFO)
        
        # Create logs directory if it doesn't exist
        log_dir = Path('logs')
        log_dir.mkdir(exist_ok=True)
        
        # File handler
        log_file = log_dir / f'{agent_name}.log'
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