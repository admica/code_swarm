# agent_code_mon_readme.py

## Overview

Agent that automatically generates and maintains README files for Python and Lua modules.

(BEGIN AI Generated)
README Overview:

**Automatic README Generator for Python and Lua Modules**

Generate and maintain accurate README files for your Python and Lua modules with this automated agent.

**Key Features:**

* Automatically analyzes code to extract documentation and structure
* Generates high-quality README files based on extracted information
* Handles file modification events to ensure READMEs are updated in real-time

**Functionality:**

* Analyzes code using the CodeAnalyzer class to extract key information
* Uses the ReadmeGenerator class to create a structured README file
* Notifies PyFileHandler to handle file modification events
* Identifies and ignores files based on predefined patterns

**Notable Implementation Details:**

* Utilizes AST (Abstract Syntax Tree) analysis for accurate code extraction
* Employs Python's standard library for file handling and event processing
* Supports both Python and Lua modules, with customizable configuration options

**Getting Started:**

1. Install the module using pip: `pip install automatic-readme-generator`
2. Configure the module to your project by setting environment variables or editing the configuration file.
3. Start the queue processor using `start` command.

This agent simplifies the process of maintaining README files for Python and Lua modules, ensuring consistency and accuracy across projects.


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
