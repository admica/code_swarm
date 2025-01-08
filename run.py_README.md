# run.py

## Overview

Launcher script for Code Swarm - manages both backend and frontend services.

(BEGIN AI Generated)
# Code Swarm Launcher Module README

**Overview**
------------

This module serves as a launcher script for Code Swarm, managing both backend and frontend services. It provides a centralized interface to start, stop, and monitor services, ensuring seamless operation of the Code Swarm ecosystem.

**Key Features and Functionality**
---------------------------------

*   **Service Management**: The `ServiceManager` class oversees the lifecycle of backend and frontend services.
*   **Port Management**: The `_is_port_in_use`, `_wait_for_port`, and `_kill_process_on_port` functions ensure that ports are properly utilized and cleaned up.
*   **Dependency Checking**: The `check_dependencies` function verifies that all required dependencies are installed before launching services.
*   **Signal Handling**: The `signal_handler` function handles shutdown signals, ensuring a clean termination of services.

**Notable Implementation Details**
---------------------------------

*   The module utilizes a service manager to orchestrate the launch and management of backend and frontend services.
*   Port management is handled through a combination of port checking and cleanup mechanisms to prevent conflicts and ensure resource efficiency.
*   Dependency checks are performed using external package managers, allowing for flexible configuration and update handling.

# Usage
------------

To use this module, simply run the `main` function, which will launch the services and manage their lifecycle. The module can be extended or modified as needed to accommodate specific requirements of your Code Swarm setup.

**Example Use Cases**
--------------------

*   Launching services with dependencies: `python launcher.py`
*   Stopping services: `python launcher.py stop_services`

For more information, please refer to the accompanying documentation and codebase.


## Classes

### `ServiceManager`

Manages the backend and frontend services.

#### Methods

- `__init__()`
- `_is_port_in_use(port)`: Check if a port is in use.
- `_wait_for_port(port, timeout)`: Wait for a port to become available.
- `_kill_process_on_port(port)`: Kill any process running on the specified port.
- `_cleanup_ports()`: Clean up any processes running on required ports.
- `start_backend()`: Start the backend service.
- `start_frontend()`: Start the frontend service.
- `stop_services()`: Stop all services and cleanup processes.
- `check_dependencies()`: Check if all required dependencies are installed.

(END AI Generated)
