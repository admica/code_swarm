# llm.py

## Overview

Shared LLM client for Code Swarm.

(BEGIN AI Generated)
# Code Swarm Shared LLM Client Module

## Overview

This module provides a shared client for interacting with the Code Swarm Large Language Model (LLM) service, enabling seamless communication between the controller and LLM operations.

## Key Features and Functionality

*   **Service Management**: The `LLMService` class manages LLM operations, providing a centralized interface for clients to interact with the service.
*   **Client Interface**: The `LLMClient` class provides a client-side interface for users to send requests to the LLM service through the controller.
*   **Error Handling**: The `LLMError` class is raised when there's an error with LLM operations, ensuring robust error handling and providing informative error messages.

## Notable Implementation Details

*   **Modular Design**: The module is designed to be modular, allowing for easy extension or replacement of individual components.
*   **Metrics Tracking**: The `get_metrics` function provides a way to track and retrieve LLM usage metrics, enabling monitoring and analysis of service performance.

## Usage Guide

To use this module, simply import the required classes and functions, and follow the provided documentation on how to interact with the LLM service. This will enable you to take full advantage of the shared client's capabilities and integrate it seamlessly into your application or workflow.


## Classes

### `LLMError`

Raised when there's an error with LLM operations.

### `LLMStatus`

Status of the LLM service.

#### Methods

- `__init__()`

### `LLMService`

Service for managing LLM operations.

#### Methods

- `__init__()`: Initialize the LLM service.
- `get_metrics()`: Get LLM usage metrics.

### `LLMClient`

Client for interacting with LLM service through the controller.

#### Methods

- `__init__(agent_name)`

(END AI Generated)
