# code_swarm
AI Agents that assist with programming tasks

![logo](logo.png)

## Python Code Monitor Agents

### CHANGELOG Agent (agent_code_mon_changelog.py)

A Git-aware Python file monitoring agent that automatically analyzes code changes and maintains per-file changelogs. This tool helps track code evolution by monitoring Python files in a directory, analyzing changes, and maintaining detailed changelog files for each monitored file.

🔍 Real-time monitoring of Python files in a directory and its subdirectories
📊 Multiple analysis metrics:
  - Syntax correctness
  - Style consistency with other project files
  - Code complexity based on changes
  - PEP standards compliance using Pylint
🤖 Optional AI-powered change analysis using Ollama
📝 Automatic changelog generation for each Python file
🔄 Git integration for tracking changes
⚙️ Configurable via config.ini

### README Agent (agent_code_mon_readme.py)

An intelligent documentation agent that automatically generates and maintains README files for Python modules. It analyzes Python files in real-time and creates comprehensive, up-to-date documentation that stays consistent with your code.

📝 Automatic README generation for each Python file
🔍 Extracts and organizes:
  - Module overview and purpose
  - Function documentation
  - Class and method descriptions
  - Dependencies
🤖 Optional AI-powered summaries using Ollama
🔄 Maintains documentation consistency across updates
⚙️ Configurable via config.ini

### Each agent will:

- Monitor your Python files for changes
- Generate/update documentation files automatically
- Provide analysis and insights about your code
- Create separate documentation files:
  - filename.py_CHANGELOG.md for change history
  - filename.py_README.md for module documentation

### AI Integration

Both agents can optionally use Ollama for AI-powered analysis:

Install Ollama from ollama.ai
Run the Ollama service
The agents will automatically use it if available

### Requirements

Python 3.6+
Git repository
Required Python packages (see requirements.txt)
Ollama (optional, for AI analysis)
