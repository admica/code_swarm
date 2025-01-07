# agent_code_mon_deps.py

## Overview

Agent that analyzes Python file dependencies and generates Mermaid diagrams.

(BEGIN AI Generated)
# Module Overview

This Python module provides a comprehensive tool for analyzing Python file dependencies and generating visualizations using Mermaid diagrams.

## Purpose

The primary purpose of this module is to help developers understand their project's dependency structure by automatically analyzing Python files, identifying import statements, class usage, and other relevant information. The generated Mermaid diagrams provide a clear visual representation of the dependencies, making it easier to navigate and maintain complex projects.

## Key Features and Functionality

* Analyzes Python file dependencies using Abstract Syntax Trees (AST)
* Generates Mermaid diagrams for dependency visualizations
* Supports directory grouping and flat diagrams
* Handles relative import resolution
* Monitors project files for changes and updates the visualization accordingly

## Notable Implementation Details

* Utilizes the `ast` module to analyze Python ASTs
* Leverages the `mermaid` library for generating Mermaid diagrams
* Implements a simple event-driven system for monitoring file changes and updating visualizations

## Usage

To use this module, simply import the necessary classes and functions, then call the desired methods to analyze your project's dependencies. The module provides a simple command-line interface (CLI) for starting and stopping monitoring.

Example usage:
```python
from dependency_analyzer import DependencyAnalyzer

analyzer = DependencyAnalyzer()
analyzer.analyze_project()  # Analyze all Python files in the project
analyzer.generate_mermaid()  # Generate Mermaid diagram from dependencies
```
This module is designed to simplify the process of understanding and maintaining complex Python projects.


## Classes

### `DependencyAnalyzer`

Analyzes Python file dependencies.

#### Methods

- `__init__(root_path)`: Initialize the analyzer with root path and configuration.
- `get_module_name(file_path)`: Convert file path to module name.
- `get_all_python_files()`: Get all Python files in the project.
- `analyze_imports(node, file_path)`: Analyze import statements in AST.
- `analyze_class_usage(node)`: Analyze class usage in AST including inheritance and composition.
- `analyze_file(file_path)`: Analyze a Python file for dependencies.
- `analyze_project()`: Analyze all Python files in the project.
- `generate_mermaid(dependencies)`: Generate Mermaid diagram from dependencies.
- `_generate_flat_mermaid(dependencies)`: Generate flat Mermaid diagram.
- `_generate_grouped_mermaid(dependencies)`: Generate Mermaid diagram with directory grouping.

### `DependencyVisualizer`

Generates and maintains dependency visualizations.

#### Methods

- `__init__(analyzer)`

### `DependencyMonitor`

Monitors Python files for dependency changes.

#### Methods

- `__init__(path)`
- `handle_file_change(file_path)`: Handle file change event.
- `start(path)`: Start monitoring.
- `stop()`: Stop monitoring.

(END AI Generated)
