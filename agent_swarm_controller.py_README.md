# agent_swarm_controller.py

## Overview

Swarm Controller - Manages code_swarm agents and provides API endpoints

(BEGIN AI Generated)
# Swarm Controller Module Overview

The Swarm Controller module is a Python-based framework designed to manage code_swarm agents and provide API endpoints for monitoring and controlling the swarm.

## Purpose

The primary purpose of this module is to act as a central hub for managing code_swarm agents, tracking metrics, and providing status updates. It handles LLM requests with queueing and metrics tracking, ensuring efficient and reliable operation of the swarm.

## Key Features and Functionality

*   Manages code_swarm agents through various API endpoints
*   Tracks metrics for LLM requests using `LLMMetrics`
*   Provides real-time status information about the LLM service using `LLMStatus`
*   Supports queueing and prioritization of LLM requests using `LLMService`
*   Offers a range of control functions, including starting, stopping, and monitoring agents
*   Allows users to record and retrieve metrics for LLM requests

## Notable Implementation Details

*   Utilizes a configuration file (`config`) to store settings and metadata
*   Employs a skip list configuration mechanism for efficient agent management
*   Incorporates logging functionality through the `read_agent_logs` function


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

(END AI Generated)
