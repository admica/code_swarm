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

- `GET /api/llm/metrics`
  - Get LLM usage metrics
  - Response: `LLMMetrics`

- `GET /api/llm/health`
  - Quick health check for LLM service
  - Response: `{ status: string, response_time: number }`

- `POST /api/llm/generate`
  - Generic endpoint for LLM content generation
  - Body: `LLMRequest`
  - Response: `LLMResponse`

- `POST /api/config/ai-markers`
  - Set AI content markers
  - Query params: `begin`, `end`
  - Response: `{ success: boolean }`

- `GET /api/config/ai-markers`
  - Get AI content markers
  - Response: `{ begin: string, end: string }`

### WebSocket

The WebSocket endpoint at `/ws/logs` provides real-time log streaming:
- Streams logs from all agents and controller
- Handles file rotation and deletion
- Automatic reconnection
- Efficient memory usage
- Real-time log tailing

Message format:
```typescript
interface WebSocketMessage {
  type: 'agent_update' | 'changelog' | 'readme' | 'dependency' | 'log';
  data: AgentState | ChangelogEntry | ReadmeUpdate | DependencyGraph | string;
}
```

### LLM Service Features

The LLM service includes:
- Request queueing and prioritization
- Automatic retries with exponential backoff
- Detailed metrics tracking
- Health monitoring
- Configurable timeouts
- Memory-efficient streaming

Metrics tracked:
- Total requests
- Success/failure rates
- Processing times
- Queue times
- Per-agent usage

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
   - Automatic process cleanup
   - State recovery
   - Error logging
2. Path permission issues
   - Detailed error messages
   - Permission validation
   - Automatic directory creation
3. LLM service issues
   - Automatic retries
   - Fallback options
   - Health monitoring
4. WebSocket connection issues
   - Automatic reconnection
   - Connection state tracking
   - Resource cleanup

Each error is:
- Logged with full context
- Reported through appropriate channels
- Handled with recovery strategies
- Monitored for patterns

## License

This project is licensed under the GNU General Public License v3.0 (GPLv3).
