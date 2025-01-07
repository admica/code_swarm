# file_monitor.py

## Overview

Shared file monitoring utilities for Code Swarm.

(BEGIN AI Generated)
README
================

File Monitoring Utilities for Code Swarm
-----------------------------------------

This module provides a flexible file monitoring system for Code Swarm, allowing you to track changes in specific directories and files.

### Purpose

The primary purpose of this module is to monitor files and directories for changes, enabling Code Swarm to respond to updates in real-time. This module uses pattern matching to identify relevant files and provides an efficient way to scan directories and handle file system events.

### Key Features and Functionality

*   **File Pattern Matching**: The `should_monitor_file` function checks if a file should be monitored based on predefined patterns.
*   **Directory Scanning**: The `scan_directory` function scans the monitored directory for matching files, enabling you to track changes in real-time.
*   **File System Event Handling**: The `handle_file_change` function handles file system change events, ensuring that your Code Swarm application remains up-to-date with the latest changes.

### Notable Implementation Details

The module is designed to be highly customizable, allowing you to tailor the monitoring behavior to suit your specific needs. It also includes a simple and efficient implementation of the file monitoring system, making it suitable for use in a variety of applications.

To get started with this module, refer to the [Installation](#installation) section below.


## Classes

### `FileMonitor`

File monitoring system with pattern matching and change detection.

#### Methods

- `__init__(agent_name, callback)`
- `should_monitor_file(file_path)`: Check if a file should be monitored based on patterns.
- `scan_directory()`: Scan the monitored directory for matching files.
- `handle_file_change(event)`: Handle file system change events.
- `start(path)`: Start monitoring a directory.
- `stop()`: Stop monitoring.
- `is_running()`: Check if monitoring is active.
- `get_status()`: Get current monitoring status.

(END AI Generated)
