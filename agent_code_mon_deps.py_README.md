# agent_code_mon_deps.py

## Overview

Agent that analyzes Python and Lua file dependencies and generates Mermaid diagrams.

This agent monitors source files, analyzes their dependencies, and generates
visual representations of the dependency structure using Mermaid diagrams.
Supports both Python imports and Lua requires.

(BEGIN AI Generated)
# Dependency Analyzer Module

Overview
--------

This Python module is an agent that analyzes dependencies between source files in a project and generates visual representations using Mermaid diagrams. It supports both Python imports and Lua requires, allowing developers to visualize their code's dependency structure.

Key Features and Functionality
-----------------------------

* Analyzes Python and Lua file dependencies for visualization
* Generates Mermaid diagrams to represent dependency structures
* Supports recursive invalidation of files and their dependencies
* Provides caching for improved performance

Notable Implementation Details
-------------------------------

* The module is designed with modularity, featuring separate classes for dependency analysis (`DependencyAnalyzer`), monitoring (`DependencyMonitor`), and visualization (`DependencyVisualizer`)
* Caching is implemented to improve performance by storing analyzed data locally
* Mermaid diagrams are generated using the `_generate_flat_mermaid` and `_generate_grouped_mermaid` functions

Usage
-----

To utilize this module, you can call various functions depending on your needs, such as `analyze_project`, `generate_mermaid`, or `invalidate_file`. The module also includes utility functions like `clear_cache` and `should_skip_file`.

Example Usage
-------------

```python
# Import the dependency analyzer module
from dependency_analyzer import DependencyAnalyzer

# Create an instance of the dependency analyzer
analyzer = DependencyAnalyzer()

# Analyze all dependencies in the project
dependencies = analyzer.analyze_project()

# Generate a Mermaid diagram from the analyzed dependencies
diagram = analyzer.generate_mermaid(dependencies)
```

Note: This is just a starting point, and the actual usage will depend on your specific requirements and project structure.


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

### `DependencyVisualizer`

Generates and maintains dependency visualizations.

#### Methods

- `__init__(analyzer)`: Initialize the visualizer.
- `generate_mermaid(dependencies)`: Generate Mermaid diagram from dependencies.
- `_generate_flat_mermaid(dependencies)`: Generate flat Mermaid diagram.
- `_generate_grouped_mermaid(dependencies)`: Generate Mermaid diagram with directory grouping.

(END AI Generated)
