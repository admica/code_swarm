# agent_swarm_controller.py

## Overview

Swarm Controller - Manages code_swarm agents and provides API endpoints

(BEGIN AI Generated)
# Swarm Controller Module Overview

The Swarm Controller is a Python module designed to manage code_swarm agents and provide API endpoints for monitoring and controlling the agents.

## Purpose

The primary purpose of this module is to act as an intermediary between the code_swarm agent cluster and external clients, providing a centralized interface for managing agent status, sending requests, and tracking metrics.

## Key Features and Functionality

*   Manages and monitors code_swarm agents through API endpoints
*   Tracks LLM (Large Language Model) request metrics and provides current metrics via API
*   Handles LLM requests with queueing and metrics tracking
*   Provides APIs for starting, stopping, and checking the status of individual agents
*   Offers functionality to start or stop all agents

## Notable Implementation Details

*   The module includes a `main` function that serves as the entry point for the swarm controller.
*   It leverages a skip list configuration for efficient path management and provides APIs for setting and validating monitoring paths.
*   The module tracks agent messages through WebSocket connections, enabling real-time communication between agents and external clients.

## Usage

To utilize this module, simply import it into your Python application and access its API endpoints to interact with the swarm controller.


## Classes

### `AgentStatus`

#### Methods

- `dict()`

### `LLMRequest`

### `LLMResponse`

### `LLMMetrics`

Tracks metrics for LLM requests.

#### Methods

- `__init__()`
- `record_request(agent, success, processing_time, queue_time)`: Record metrics for a request.
- `get_metrics()`: Get current metrics.

### `LLMStatus`

Status information about the LLM service.

### `LLMService`

Handles LLM requests with queueing and metrics tracking.

#### Methods

- `__init__()`
- `get_metrics()`: Get current LLM metrics.

### `ControllerInfo`

Information about the controller configuration and status.

### `SwarmController`

Controls and monitors code_swarm agents.

#### Methods

- `__init__()`
- `_save_config()`: Save current configuration to config.
- `update_skip_list(skip_list)`: Update the skip list configuration.
- `should_skip_path(path)`: Check if a path should be skipped based on the skip list.
- `set_monitor_path(path)`: Set and validate the monitoring path.
- `start_agent(agent_name, path)`: Start a specific agent.
- `stop_agent(agent_name)`: Stop a specific agent.
- `get_agent_status(agent_name)`: Get the status of a specific agent.
- `get_all_statuses()`: Get status of all agents.
- `start_all(path)`: Start all agents.
- `stop_all()`: Stop all agents.
- `read_agent_logs(agent_name, lines)`: Read recent log entries for an agent.

### `SkipListUpdate`

### `AgentMessageManager`

Manages WebSocket connections for agent messages and frontend clients.

#### Methods

- `__init__()`
- `get_connection_status()`: Get current connection status.

(END AI Generated)
