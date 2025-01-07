# config.py

## Overview

Shared configuration management for Code Swarm.

(BEGIN AI Generated)
# Code Swarm Configuration Manager

This module provides a centralized configuration management system for Code Swarm, ensuring consistency and reliability across different components.

## Overview

The `SharedConfigManager` class is a singleton instance that manages and stores configuration data for Code Swarm. It offers various methods to load, save, validate, and retrieve specific configurations, including controller, agent, Ollama, and general settings.

## Key Features and Functionality

*   **Configuration Management**: Load, save, and update configuration files.
*   **Validation**: Check configuration values for correctness and consistency.
*   **Section Updates**: Modify specific sections of the configuration file.
*   **Value Retrieval**: Access individual configuration values by name or key.

## Notable Implementation Details

*   The `SharedConfigManager` class is designed as a singleton, ensuring only one instance exists throughout the application's lifecycle.
*   Configuration files are loaded and saved using a flexible file format that supports multiple sections and keys.

## Usage Guidelines

To utilize this module effectively:

1.  Create an instance of `SharedConfigManager`.
2.  Use methods like `load_config`, `create_default_config`, `save_config`, and others to manage your configuration data.
3.  Validate your configurations using the `validate_config` method before proceeding with application setup or execution.

By integrating this module into your Code Swarm project, you can maintain a well-organized and efficient configuration management system that supports seamless scalability and reliability.


## Classes

### `ConfigurationError`

Raised when there's an error with configuration.

### `SharedConfigManager`

Singleton configuration manager for Code Swarm.

#### Methods

- `__new__(cls)`
- `__init__()`
- `load_config()`: Load configuration from file.
- `create_default_config()`: Create default configuration file.
- `save_config()`: Save current configuration to file.
- `validate_config()`: Validate configuration values.
- `get_controller_config()`: Get controller configuration.
- `get_agent_config(agent_name)`: Get configuration for a specific agent.
- `get_ollama_config()`: Get Ollama configuration.
- `update_section(section, values)`: Update a configuration section.
- `get_value(section, key, default)`: Get a specific configuration value.
- `set_value(section, key, value)`: Set a specific configuration value.

(END AI Generated)
