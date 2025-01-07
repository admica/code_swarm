# agent_code_mon_readme.py

## Overview

Agent that automatically generates and maintains README files for Python and Lua modules.

(BEGIN AI Generated)
# README Generator Module

Automatically generates and maintains README files for Python and Lua modules.

## Overview

This module is designed to simplify the process of creating and maintainingREADME files for Python and Lua modules. It analyzes code, extracts documentation, and generates a clear, concise README section for classes, functions, and modules.

## Key Features and Functionality

* Analyzes Python and Lua code to extract key information
* Generates documentation for classes, functions, and modules
* Automatically creates README files based on extracted documentation
* Handles file modification events to ensure READMEs stay up-to-date
* Supports multiple file patterns and ignores unwanted files

## Notable Implementation Details

* Utilizes CodeAnalyzer to analyze code and extract documentation
* Employs ReadmeGenerator to generate readable and concise README sections
* Leverages PyFileHandler to monitor file modification events
* Integrates with a queue processor to efficiently process existing files and new updates

By utilizing this module, developers can streamline their README generation process, reduce manual effort, and focus on writing high-quality code.


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
