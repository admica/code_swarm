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
- WebSocket for real-time updates
- Ollama integration for AI features
- Centralized path monitoring

#### Python Agents

1. **CHANGELOG Agent** (agent_code_mon_changelog.py)
   - Monitors file changes
   - Analyzes code modifications
   - Maintains detailed changelogs
   - Git-aware (optional)

2. **README Agent** (agent_code_mon_readme.py)
   - Generates module documentation
   - Updates READMEs automatically
   - Maintains API documentation
   - AI-powered summaries

3. **Dependency Graph Agent** (agent_code_mon_deps.py)
   - Maps project dependencies
   - Creates visual graphs
   - Tracks module relationships
   - Updates in real-time

### Frontend

A Next.js web application that provides:
- Real-time agent status monitoring
- Centralized path management
- Live updates via WebSocket
- Dark-themed, responsive interface

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

2. Install backend dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Install frontend dependencies:
   ```bash
   cd frontend
   npm install
   cd ..
   ```

4. Start the backend server:
   ```bash
   python agent_swarm_controller.py
   ```

5. In a new terminal, start the frontend:
   ```bash
   cd frontend
   npm run dev
   ```

6. Open http://localhost:3000 in your browser

## Configuration

### Backend Configuration (config.ini)
- Monitor path settings
- Agent-specific configurations
- Ollama settings
- Server options

### Frontend Configuration
- API endpoint: http://localhost:8000/api
- WebSocket: ws://localhost:8000/ws
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

2. WebSocket Connection
   - Ensure backend is running
   - Check port availability
   - Monitor connection status

3. Path Monitoring
   - Use absolute paths
   - Verify directory permissions
   - Check agent logs

## License

This project is licensed under the GNU General Public License v3.0 (GPLv3)
