# Code Swarm Backend Documentation

## Overview

The Code Swarm backend consists of two main components:
1. A central controller (FastAPI server)
2. A set of autonomous Python agents

## Swarm Controller

The Swarm Controller (`agent_swarm_controller.py`) is a FastAPI application that:
- Manages and monitors the agent processes
- Provides REST API endpoints
- Handles WebSocket connections for real-time updates
- Integrates with Ollama for AI features

### Configuration

The controller uses `config.ini` for configuration:

```ini
[swarm_controller]
monitor_path = /path/to/monitor
host = 0.0.0.0
port = 8000

[ollama]
model = llama3.2
endpoint = http://localhost:11434
```

### API Endpoints

#### Agent Management

- `GET /api/agents`
  - Get status of all agents
  - Response: `Record<string, AgentState>`

- `POST /api/agents/{agent_name}/start`
  - Start a specific agent
  - Query params: `path` (optional)
  - Response: `AgentState`

- `POST /api/agents/{agent_name}/stop`
  - Stop a specific agent
  - Response: `AgentState`

- `GET /api/agents/{agent_name}/status`
  - Get status of specific agent
  - Response: `AgentState`

- `GET /api/agents/{agent_name}/logs`
  - Get agent logs
  - Query params: `lines` (default: 100)
  - Response: `string[]`

#### Configuration

- `POST /api/config/monitor-path`
  - Set global monitor path
  - Query params: `path`
  - Response: `{ success: string } | { error: string }`

- `GET /api/info`
  - Get controller information
  - Response: `ControllerInfo`

#### LLM Integration

- `GET /api/llm/status`
  - Get Ollama service status
  - Response: `LLMStatus`

- `POST /api/llm/readme/generate`
  - Generate README content
  - Body: `LLMRequest`
  - Response: `LLMResponse`

- `POST /api/llm/changelog/generate`
  - Generate changelog content
  - Body: `LLMRequest`
  - Response: `LLMResponse`

- `POST /api/llm/deps/analyze`
  - Analyze dependencies
  - Body: `LLMRequest`
  - Response: `LLMResponse`

### WebSocket

The WebSocket endpoint at `/ws` provides real-time updates for:
- Agent status changes
- New changelog entries
- README updates
- Dependency graph changes

Message format:
```typescript
interface WebSocketMessage {
  type: 'agent_update' | 'changelog' | 'readme' | 'dependency';
  data: AgentState | ChangelogEntry | ReadmeUpdate | DependencyGraph;
}
```

## Agents

### Changelog Agent

The Changelog Agent (`agent_code_mon_changelog.py`):
- Monitors Python files for changes
- Analyzes code modifications
- Generates detailed changelogs
- Optionally uses Git for change detection
- Integrates with Ollama for AI-powered analysis

Configuration:
```ini
[changelog_agent]
enabled_features = syntax,style,complexity
ollama_model = llama3.2
```

### README Agent

The README Agent (`agent_code_mon_readme.py`):
- Monitors Python files
- Generates and updates README files
- Extracts documentation from code
- Uses Ollama for summaries and descriptions

Configuration:
```ini
[readme_agent]
template_path = templates/readme.md
ollama_model = llama3.2
```

### Dependency Agent

The Dependency Agent (`agent_code_mon_deps.py`):
- Maps project dependencies
- Creates Mermaid.js diagrams
- Tracks module relationships
- Updates in real-time

Configuration:
```ini
[deps_agent]
max_depth = 3
include_external = false
```

## Data Types

### AgentState
```typescript
interface AgentState {
  name: string;
  pid: number | null;
  running: boolean;
  monitor_path: string | null;
  last_error: string | null;
}
```

### LLMRequest
```typescript
interface LLMRequest {
  prompt: string;
  model: string;
  agent: string;
  max_tokens?: number;
  temperature?: number;
}
```

### LLMResponse
```typescript
interface LLMResponse {
  response?: string;
  error?: string;
  processing_time: number;
  queue_time: number;
  timestamp: string;
}
```

## Development

### Running the Backend

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Start Ollama (optional):
   ```bash
   ollama serve
   ```

3. Start the controller:
   ```bash
   python agent_swarm_controller.py
   ```

### Logs

- Controller: `swarm_controller.log`
- Agents:
  - `agent_code_mon_changelog.log`
  - `agent_code_mon_readme.log`
  - `agent_code_mon_deps.log`

### Error Handling

The controller handles several types of errors:
1. Agent process failures
2. Path permission issues
3. LLM service unavailability
4. WebSocket connection issues

Each error is:
- Logged appropriately
- Broadcasted to connected clients
- Handled with automatic recovery when possible 

## License

This project is licensed under the GNU General Public License v3.0 (GPLv3).
