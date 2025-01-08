# agent_logger.py

## Overview

Shared logging utilities for Code Swarm agents.

(BEGIN AI Generated)
# Shared Logging Utilities for Code Swarm Agents

This module provides a centralized logging system for Code Swarm agents, enabling consistent and structured log output across the agent.

## Overview

The `AgentLogger` class serves as a wrapper for logging messages from Code Swarm agents, providing a standardized way to track events, errors, and debug information. The logger supports various log levels (info, warning, error, debug) and exception handling.

## Key Features and Functionality

*   **Centralized Logging**: Log messages are stored in a single location, making it easier to monitor and analyze agent activity.
*   **Customizable Log Levels**: Agents can adjust the log level to control the amount of information output.
*   **Exception Handling**: The logger catches exceptions and logs them with their corresponding error message.

## Notable Implementation Details

*   The `__new__` method ensures that only one instance of the logger is created for each agent, preventing multiple instances from being created.
*   Log messages are formatted with a timestamp and log level prefix to maintain consistency and readability.


## Classes

### `AgentLogger`

Logging wrapper for Code Swarm agents.

#### Methods

- `__new__(cls, agent_name)`: Create or return existing logger instance for the agent.
- `__init__(agent_name)`: Initialize logger for an agent.
- `log(level, message, category)`: Log a message with additional context.
- `info(message, category)`: Log an info message.
- `warning(message, category)`: Log a warning message.
- `error(message, category)`: Log an error message.
- `debug(message, category)`: Log a debug message.
- `exception(message, category)`: Log an exception with traceback.

(END AI Generated)
