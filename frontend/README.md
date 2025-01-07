# Code Swarm Frontend

A modern web interface for monitoring and managing AI-powered programming agents.

## Overview

This frontend application provides a real-time dashboard for visualizing and interacting with Code Swarm's Python agents:

- **Changelog Agent**: Monitor file changes and view automated code analysis
- **README Agent**: Track documentation updates and AI-generated summaries
- **Dependency Agent**: Visualize project dependencies through interactive graphs

## Tech Stack

- **Framework**: Next.js 14 with App Router
- **Language**: TypeScript
- **Styling**: Tailwind CSS for utility-first styling
- **Data Fetching**: Axios for API requests
- **Real-time Updates**: WebSocket for live agent status

## Project Structure

```
src/
├── app/              # Next.js app router pages
├── components/       # React components
│   ├── agents/      # Agent monitoring components
│   └── MonitorPathSelector.tsx  # Path selection component
├── types/           # TypeScript types
│   └── agents/      # Agent-related types
└── lib/             # Utilities and helpers
    ├── api.ts       # API client
    └── websocket.ts # WebSocket client
```

## Features

- Real-time agent status monitoring
- Centralized path management
- Live status updates via WebSocket
- Dark-themed interface
- Responsive layout

## Development Setup

### Prerequisites
1. Node.js 18 or higher
2. Backend server (Swarm Controller) running on port 8000
3. Ollama service running (for AI features)

### Configuration
The application expects the following services to be available:
- REST API: `http://localhost:8000/api`
- WebSocket: `ws://localhost:8000/ws`
- Ollama: `http://localhost:11434` (for AI features)

### Running the Application

1. Install dependencies:
   ```bash
   npm install
   ```

2. Run development server:
   ```bash
   npm run dev
   ```

3. Build for production:
   ```bash
   npm run build
   ```

### Development Workflow

1. Start the backend server first:
   ```bash
   cd ..  # Go to project root
   python agent_swarm_controller.py
   ```

2. Start the frontend development server:
   ```bash
   cd frontend
   npm run dev
   ```

3. Access the application at `http://localhost:3000`

## Troubleshooting

### Common Issues

1. WebSocket Connection Failures
   - Ensure the backend server is running
   - Check if port 8000 is available
   - The frontend will automatically attempt to reconnect

2. Agent Start/Stop Issues
   - Verify the monitor path exists and has correct permissions
   - Check the backend logs for detailed error messages
   - Ensure Ollama is running if using AI features

3. Path Permission Issues
   - The monitor path must be readable and writable
   - The backend will create the directory if it doesn't exist
   - Use absolute paths to avoid confusion

### Debugging

- Check the browser console for frontend errors
- Monitor the WebSocket connection status in the Network tab
- Review the backend logs for agent-specific issues

## API Integration

The frontend communicates with the backend through:
- REST API endpoints for agent control and configuration
- WebSocket connection for real-time status updates
- Automatic reconnection handling
- Error handling and user feedback

## Contributing

1. Fork the repository
2. Create your feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

GPL3]
