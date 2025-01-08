# agent_code_mon_readme.py

## Overview

Agent that automatically generates and maintains README files for Python and Lua modules.

(BEGIN AI Generated)
# README Generator Module

Automatically generates and maintains README files for Python and Lua modules.

## Overview

This module provides a suite of classes and functions to analyze code, extract documentation, and generate readable README files. It supports Python and Lua modules, allowing developers to easily create high-quality documentation for their projects.

## Key Features and Functionality

* Analyzes code to extract key information and docstrings
* Generates documentation in the format of a README file
* Supports both Python and Lua modules
* Notifies users when code changes are detected, ensuring documentation stays up-to-date
* Handles file modification events to ensure documentation is updated on every change

## Notable Implementation Details

* Utilizes the Abstract Syntax Tree (AST) for Python code analysis
* Leverages regular expressions for efficient pattern matching and filtering
* Employs a queue processing system to handle multiple files simultaneously, ensuring optimal performance.

## Usage

To start using this module, simply import the classes and functions that suit your needs. The `start` method initiates the README generation process, while the `stop` method terminates it.


## Classes

### `CodeAnalyzer`

Analyzes code to extract documentation and structure.

#### Methods

- `__init__()`: Initialize the analyzer with LLM client.
- `extract_docstring(node)`: Extract docstring from an AST node.
- `analyze_code(content)`: Analyze code and extract key information.

### `ReadmeGenerator`

Generates README.md files for modules.

#### Methods

- `__init__()`: Initialize the generator with a code analyzer.
- `generate_class_section(classes)`: Generate documentation for classes.

### `PyFileHandler`

Handles file modification events.

#### Methods

- `__init__()`: Initialize with a README generator.
- `should_ignore(file_path)`: Check if a file should be ignored based on patterns.
- `process_existing_files(path)`: Process all existing code files in the directory that don't have READMEs.
- `on_modified(event)`: Handle file modification events.
- `start()`: Start the queue processor.
- `stop()`: Stop the queue processor.

(END AI Generated)
