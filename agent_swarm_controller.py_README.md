# agent_swarm_controller.py

## Overview

Swarm Controller - Manages code_swarm agents and provides API endpoints

(BEGIN AI Generated)
# Swarm Controller Module Overview

The Swarm Controller is a Python module designed to manage code_swarm agents and provide API endpoints for controlling and monitoring their behavior.

## Purpose

The primary purpose of this module is to serve as a centralized hub for managing code_swarm agents, tracking metrics, and providing status updates. It utilizes the LLM (Large Language Model) service to process requests from the swarm agents and provides features such as agent management, logging, and metrics tracking.

## Key Features and Functionality

*   **Agent Management**: The module allows users to start, stop, and monitor individual agents.
*   **Metrics Tracking**: It tracks key performance indicators (KPIs) for the LLM service, including request latency and throughput.
*   **API Endpoints**: Provides a set of RESTful API endpoints for interacting with the swarm controller.

## Notable Implementation Details

*   The module uses a dictionary-based data structure to store agent information and configuration settings.
*   It leverages the `skiplist` data structure to efficiently manage access control lists (ACLs) for monitoring paths.


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

(END AI Generated)
