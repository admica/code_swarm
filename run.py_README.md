# run.py

## Overview

Launcher script for Code Swarm - manages both backend and frontend services.

(BEGIN AI Generated)
# Code Swarm Launcher Module

## Overview

This module serves as a launcher script for Code Swarm, responsible for managing both backend and frontend services. It provides a centralized interface to start, stop, and monitor these services.

## Key Features and Functionality

*   Manages the lifecycle of backend and frontend services through the `ServiceManager` class.
*   Provides a main entry point (`main`) for launching the services.
*   Includes functions for checking port availability (`_is_port_in_use` and `_wait_for_port`), starting and stopping services (`start_backend`, `start_frontend`, and `stop_services`).
*   Verifies dependencies are installed using the `check_dependencies` function.
*   Handles shutdown signals with the `signal_handler` function.
*   Terminates a process and its children with the `terminate_process_tree` function.

## Notable Implementation Details

The module follows best practices for modular design, encapsulating service management logic within the `ServiceManager` class. The use of signal handling (`signal_handler`) ensures the script remains responsive during shutdown processes. Additionally, the `_wait_for_port` function provides a mechanism to wait for port availability before starting services, reducing the likelihood of port conflicts.

By leveraging this launcher module, users can easily manage their Code Swarm services and ensure a stable application environment.


## Classes

### `ServiceManager`

Manages the backend and frontend services.

#### Methods

- `__init__()`
- `_is_port_in_use(port)`: Check if a port is in use.
- `_wait_for_port(port, timeout)`: Wait for a port to become available.
- `start_backend()`: Start the backend service.
- `start_frontend()`: Start the frontend service.
- `stop_services()`: Stop all services.
- `check_dependencies()`: Check if all required dependencies are installed.

(END AI Generated)
