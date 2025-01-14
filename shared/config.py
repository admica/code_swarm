#!/usr/bin/env python3
"""Shared configuration management for Code Swarm."""

import os
import logging
import configparser
from typing import Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

class ConfigurationError(Exception):
    """Raised when there's an error with configuration."""
    pass

class SharedConfigManager:
    """Singleton configuration manager for Code Swarm."""

    _instance = None
    _config = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SharedConfigManager, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if self._config is None:
            self._config = configparser.ConfigParser()
            self.config_path = 'config.ini'
            self.load_config()

    def load_config(self) -> None:
        """Load configuration from file."""
        if not os.path.exists(self.config_path):
            logger.warning(f"Config file not found at {self.config_path}. Creating default configuration.")
            self.create_default_config()

        try:
            self._config.read(self.config_path)
            self.validate_config()
        except configparser.Error as e:
            raise ConfigurationError(f"Error reading config file: {e}")

    def create_default_config(self) -> None:
        """Create default configuration file."""
        self._config['swarm_controller'] = {
            'host': '0.0.0.0',
            'port': '8000',
            'monitor_path': '/tmp',
            'skip_list': 'node_modules/,venv/,.git/,__pycache__/'
        }

        self._config['ollama'] = {
            'model': 'llama3.2',
            'endpoint': 'http://localhost:11434'
        }

        # Default agent configurations
        for agent in ['changelog', 'readme', 'deps']:
            self._config[f'agent_{agent}'] = {
                'enabled': 'true',
                'ollama_model': 'llama3.2',
                'controller_url': 'http://localhost:8000/api',
                'watch_patterns': '*.py',
                'ignore_patterns': '__pycache__/*,.*'
            }

        self.save_config()

    def save_config(self) -> None:
        """Save current configuration to file."""
        try:
            with open(self.config_path, 'w') as f:
                self._config.write(f)
        except Exception as e:
            raise ConfigurationError(f"Error saving config: {e}")

    def validate_config(self) -> None:
        """Validate configuration values."""
        required_sections = ['swarm_controller', 'ollama']
        for section in required_sections:
            if section not in self._config:
                raise ConfigurationError(f"Missing required section: {section}")

        # Validate swarm_controller section
        controller = self._config['swarm_controller']
        if 'port' in controller and not controller['port'].isdigit():
            raise ConfigurationError("Controller port must be a number")

        # Validate paths
        monitor_path = controller.get('monitor_path')
        if monitor_path and not os.path.exists(monitor_path):
            logger.warning(f"Monitor path does not exist: {monitor_path}")

    def get_controller_config(self) -> Dict[str, Any]:
        """Get controller configuration."""
        return dict(self._config['swarm_controller'])

    def get_agent_config(self, agent_name: str) -> Dict[str, Any]:
        """Get configuration for a specific agent."""
        section = f'agent_{agent_name}'
        if section not in self._config:
            raise ConfigurationError(f"No configuration found for agent: {agent_name}")
        return dict(self._config[section])

    def get_ollama_config(self) -> Dict[str, str]:
        """Get Ollama configuration."""
        return dict(self._config['ollama'])

    def update_section(self, section: str, values: Dict[str, Any]) -> None:
        """Update a configuration section."""
        if section not in self._config:
            self._config.add_section(section)

        for key, value in values.items():
            self._config[section][key] = str(value)

        self.save_config()

    def get_value(self, section: str, key: str, default: Any = None) -> Optional[str]:
        """Get a specific configuration value."""
        try:
            return self._config[section][key]
        except (configparser.NoSectionError, configparser.NoOptionError):
            return default

    def set_value(self, section: str, key: str, value: Any) -> None:
        """Set a specific configuration value."""
        if section not in self._config:
            self._config.add_section(section)

        self._config[section][key] = str(value)
        self.save_config()

# Global instance
config_manager = SharedConfigManager() 