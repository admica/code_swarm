# agent_code_mon_deps.py

## Overview

Agent that analyzes Python and Lua file dependencies and generates Mermaid diagrams.

This agent monitors source files, analyzes their dependencies, and generates
visual representations of the dependency structure using Mermaid diagrams.
Supports both Python imports and Lua requires.

(BEGIN AI Generated)
# Agent Overview

This module is a Python agent designed to analyze file dependencies and generate visual representations using Mermaid diagrams.

## Purpose
The agent monitors source files, analyzes their dependencies, and generates visual representations of the dependency structure using Mermaid diagrams. It supports both Python imports and Lua requires.

## Key Features and Functionality

* Analyzes Python and Lua file dependencies
* Generates Mermaid diagrams to visualize dependency structures
* Supports recursive invalidation of dependent files
* Notifies when a file changes, allowing for real-time updates
* Caches analysis results for improved performance

## Implementation Details

* Utilizes caching to improve performance and reduce unnecessary analysis
* Employs a hierarchical approach to analyzing dependencies, ensuring accurate visualizations
* Includes support for both Python imports and Lua requires, making it suitable for diverse projects

## Usage
To use this agent, simply run the `start` function to begin monitoring your project's source files. The `generate_mermaid` function can be used to generate a Mermaid diagram from the analyzed dependencies.

### Example Use Case:
```python
from agent import DependencyVisualizer

# Create an instance of the dependency visualizer
visualizer = DependencyVisualizer()

# Start monitoring the project
visualizer.start()

# Generate a Mermaid diagram from dependencies
mermaid_diagram = visualizer.generate_mermaid()
```
This agent is designed to provide a clear and concise overview of your project's dependencies, making it easier to understand and maintain complex codebases.


## Classes

### `DependencyAnalyzer`

Analyzes source code dependencies.

#### Methods

- `__init__(root_path)`: Initialize the analyzer.
- `clear_cache()`: Clear all caches.
- `invalidate_file(file_path)`: Invalidate a file and anything that depends on it (recursively).
- `should_skip_file(file_path)`: Check if a file should be skipped based on patterns.
- `get_all_source_files()`: Get all source files in the project.
- `get_module_name(file_path)`: Get module name from file path.
- `_get_node_style(file_path)`: Get Mermaid node style based on file type.
- `analyze_python_imports(file_path)`: Analyze Python imports in a file.
- `analyze_lua_requires(file_path)`: Analyze Lua requires in a file.
- `analyze_file(file_path)`: Analyze dependencies in a file with caching.
- `analyze_project()`: Analyze all dependencies in the project.

### `DependencyMonitor`

Monitors source files for dependency changes.

#### Methods

- `__init__(path)`: Initialize the monitor.
- `handle_file_change(file_path)`: Handle file change event.
- `start(path)`: Start monitoring.
- `stop()`: Stop monitoring and clean up resources.

### `DependencyVisualizer`

Generates and maintains dependency visualizations.

#### Methods

- `__init__(analyzer)`: Initialize the visualizer.
- `generate_mermaid(dependencies)`: Generate Mermaid diagram from dependencies.
- `_generate_flat_mermaid(dependencies)`: Generate flat Mermaid diagram.
- `_generate_grouped_mermaid(dependencies)`: Generate Mermaid diagram with directory grouping.

(END AI Generated)
