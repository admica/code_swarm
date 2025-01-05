# code_swarm
AI Agents that assist with programming tasks

![logo](logo.png)

# Python Code Monitor Agent

A Git-aware Python file monitoring agent that automatically analyzes code changes and maintains per-file changelogs. This tool helps track code evolution by monitoring Python files in a directory, analyzing changes, and maintaining detailed changelog files for each monitored file.

## Features

* 🔍 Real-time monitoring of Python files in a directory and its subdirectories
* 📊 Multiple analysis metrics:
** Syntax correctness
** Style consistency with other project files
** Code complexity based on changes
** PEP standards compliance using Pylint
* 🤖 Optional AI-powered change analysis using Ollama
* 📝 Automatic changelog generation for each Python file
* 🔄 Git integration for tracking changes
* ⚙️ Configurable via config.ini
