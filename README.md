# Code Swarm

AI Agents that assist with programming tasks, with a modern web interface for monitoring and control.

![logo](logo.png)

## Overview

Code Swarm is a suite of AI-powered programming assistants that help maintain and document your Python codebase. It consists of:

1. A set of specialized Python agents for different tasks
2. A central controller that manages the agents
3. A modern web interface for monitoring and control

## Components

### Backend

#### Swarm Controller

The central server that manages all agents and provides API endpoints. Features:
- RESTful API for agent control
- WebSocket for real-time logging
- Advanced LLM integration with:
  - Request queueing
  - Automatic retries
  - Health monitoring
  - Usage metrics
- Centralized path monitoring
- Robust error handling

#### Python Agents

1. **CHANGELOG Agent** (agent_code_mon_changelog.py)
   - Monitors file changes
   - Analyzes code modifications
   - Maintains detailed changelogs
   - Git-aware (optional)
   - AI-powered analysis

2. **README Agent** (agent_code_mon_readme.py)
   - Generates module documentation
   - Updates READMEs automatically
   - Maintains API documentation
   - AI-powered summaries
   - Configurable AI markers

3. **Dependency Graph Agent** (agent_code_mon_deps.py)
   - Maps project dependencies
   - Creates visual graphs
   - Tracks module relationships
   - Updates in real-time
   - AI-powered insights

### Frontend

A Next.js web application that provides:
- Real-time agent status monitoring
- Live log streaming
- LLM metrics dashboard
- Path management interface
- Dark-themed, responsive design

## Requirements

### Backend
- Python 3.6+
- Git (optional)
- Required Python packages (see requirements.txt)
- Ollama (optional, for AI features)

### Frontend
- Node.js 18+
- npm or yarn
- Modern web browser

## Quick Start

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/code_swarm.git
   cd code_swarm
   ```

2. Run the setup script to install all dependencies:
   ```bash
   python setup.py
   ```

3. Start the application:
   ```bash
   python run.py
   ```

4. Open http://localhost:3000 in your browser

The application will automatically:
- Start the backend server on port 8000
- Start the frontend development server on port 3000
- Set up WebSocket connections for real-time logging
- Initialize all required services

To stop the application, press Ctrl+C in the terminal where run.py is running.

## Configuration

### Backend Configuration (config.ini)
- Monitor path settings
- Agent-specific configurations
- Ollama settings
  - Model selection
  - Retry configuration
  - Queue settings
- Server options
- AI content markers

### Frontend Configuration
- API endpoint: http://localhost:8000/api
- WebSocket: ws://localhost:8000/ws/logs
- Ollama endpoint: http://localhost:11434

## Development

See individual README files in:
- [Frontend Documentation](frontend/README.md)
- [Backend Documentation](docs/backend.md)

## Troubleshooting

### Common Issues

1. Agent Start/Stop Issues
   - Check file permissions
   - Verify Ollama is running (if using AI)
   - Review agent logs
   - Check process cleanup

2. WebSocket Connection
   - Ensure backend is running
   - Check port availability
   - Monitor connection status
   - Check log streaming

3. Path Monitoring
   - Use absolute paths
   - Verify directory permissions
   - Check agent logs
   - Monitor file events

4. LLM Service
   - Check Ollama status
   - Monitor queue metrics
   - Review error logs
   - Check retry patterns

## License

This project is licensed under the GNU General Public License v3.0 (GPLv3)
