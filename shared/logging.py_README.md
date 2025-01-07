# logging.py

## Overview

Shared logging utilities for Code Swarm.

(BEGIN AI Generated)
# Code Swarm Shared Logging Utilities

This module provides a set of shared logging utilities for Code Swarm, enabling agents to log messages with varying levels of severity.

## Overview

The purpose of this module is to provide a standardized way of logging events in Code Swarm, allowing for better error tracking and debugging capabilities. The module offers a flexible logging system with customizable log levels (info, warning, error, debug).

## Key Features and Functionality

- **AgentLogger Class**: A logging wrapper specifically designed for Code Swarm agents.
- **log() Function**: Logs a message with additional context, allowing for more informative logs.
- **Info, Warning, Error, Debug Functions**: Offer different log levels for various use cases.

## Notable Implementation Details

- The module uses a centralized logging system to ensure consistency across all Code Swarm agents.
- The `log()` function allows for easy customization of the logging format and severity level.

By utilizing this shared logging utilities module, Code Swarm agents can streamline their logging process, improve error detection, and enhance overall debugging capabilities.


## Classes

### `AgentLogger`

Logging wrapper for Code Swarm agents.

#### Methods

- `__init__(agent_name)`: Initialize logger for an agent.
- `log(level, message, category)`: Log a message with additional context.
- `info(message, category)`: Log an info message.
- `warning(message, category)`: Log a warning message.
- `error(message, category)`: Log an error message.
- `debug(message, category)`: Log a debug message.

(END AI Generated)
