# Code Swarm Frontend

A modern web interface for monitoring and managing AI-powered programming agents.

## Overview

This frontend application provides a real-time dashboard for visualizing and interacting with Code Swarm's Python agents:

- **Changelog Agent**: Monitor file changes and view automated code analysis
- **README Agent**: Track documentation updates and AI-generated summaries
- **Dependency Agent**: Visualize project dependencies through interactive graphs

## Tech Stack

- **Framework**: Next.js 15.1.3 with App Router
- **Language**: TypeScript
- **UI Components**: shadcn/ui with Radix UI primitives
- **Styling**: Tailwind CSS with dark mode support
- **Data Fetching**: Axios for API requests
- **Real-time Updates**: WebSocket for live agent status
- **State Management**: React hooks and context

## Component System

The application uses shadcn/ui, a collection of reusable components built on Radix UI:
- Customizable through `components.json`
- Accessible and responsive components
- Dark mode support out of the box
- Integration with Tailwind CSS for styling

## Project Structure

```
src/
├── app/              # Next.js app router pages
├── components/       # React components
│   ├── agents/      # Agent monitoring components
│   ├── LLMMonitoring.tsx  # LLM metrics and status
│   ├── SkipListManager.tsx  # Skip list configuration
│   ├── AIMarkerConfig.tsx  # AI marker settings
│   └── MonitorPathSelector.tsx  # Path selection component
├── types/           # TypeScript types
│   └── agents/      # Agent-related types
└── lib/             # Utilities and helpers
    ├── api.ts       # API client
    └── websocket.ts # WebSocket client
```

## Features

### Core Features
- Real-time agent status monitoring
- Live status updates via WebSocket
- Centralized path management
- Dark-themed responsive interface

### Advanced Features
- **LLM Monitoring Dashboard**
  - Real-time metrics and status
  - Success rate visualization
  - Processing time analytics
  - Available models display
  - Health monitoring

- **Configuration Management**
  - Skip list pattern management
  - AI marker configuration
  - Monitor path selection
  - Agent-specific settings

- **Real-time Updates**
  - WebSocket-based log streaming
  - Automatic reconnection with backoff
  - Live agent status updates
  - Error handling and recovery

## Development Setup

### Prerequisites
1. Node.js 20.11.0 or higher (required for Next.js 15)
2. Backend server (Swarm Controller) running on port 8000
3. Ollama service running on port 11434 (for AI features)
4. Git for version control
5. npm or yarn package manager

### Environment Setup
1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd code_swarm/frontend
   ```

2. Install dependencies:
   ```bash
   npm install
   # or
   yarn install
   ```

3. Configure environment variables:
   - Copy `.env.example` to `.env.local`
   - Adjust API endpoints if needed

### Development Workflow

1. Start the backend services:
   ```bash
   # Start Ollama (required for AI features)
   ollama serve

   # In another terminal, start the backend
   cd code_swarm
   python agent_swarm_controller.py
   ```

2. Start the frontend development server:
   ```bash
   cd frontend
   npm run dev
   # or
   yarn dev
   ```

3. Access the application:
   - Main dashboard: `http://localhost:3000`
   - LLM monitoring: `http://localhost:3000/llm`
   - Settings: `http://localhost:3000/settings`

### Building for Production

1. Create production build:
   ```bash
   npm run build
   # or
   yarn build
   ```

2. Start production server:
   ```bash
   npm run start
   # or
   yarn start
   ```

### Code Quality

1. Run linting:
   ```bash
   npm run lint
   # or
   yarn lint
   ```

2. Type checking:
   ```bash
   npm run type-check
   # or
   yarn type-check
   ```

## API Integration

The frontend communicates with the backend through:
- REST API endpoints for agent control and configuration
- WebSocket connection for real-time status updates
- Automatic reconnection handling
- Error handling and user feedback

### Configuration
The application expects the following services to be available:
- REST API: `http://localhost:8000/api`
- WebSocket: `ws://localhost:8000/ws/logs`
- Ollama: `http://localhost:11434` (for AI features)

## Troubleshooting

### Common Issues

1. WebSocket Connection Failures
   - Ensure the backend server is running on port 8000
   - Check if the port is not blocked by firewall
   - The frontend will automatically attempt to reconnect with exponential backoff
   - Check browser console for detailed connection errors
   - Verify the WebSocket endpoint is correct (`ws://localhost:8000/ws/logs`)

2. LLM Service Issues
   - Verify Ollama is running on port 11434
   - Check if the correct model is installed (`ollama pull llama3.2`)
   - Monitor the LLM dashboard for service health
   - Check backend logs for LLM-related errors
   - Ensure sufficient system resources for model inference

3. Agent Management Issues
   - Verify the monitor path exists and has correct permissions
   - Check the backend logs for detailed error messages
   - Ensure Ollama is running if using AI features
   - Verify skip list patterns are correctly formatted
   - Check AI markers configuration if README updates fail

4. UI Component Issues
   - Clear browser cache if styles are not updating
   - Verify Tailwind CSS classes are properly configured
   - Check for shadcn/ui component version compatibility
   - Ensure dark mode is properly configured in layout
   - Monitor browser console for component errors

### Performance Optimization

1. LLM Monitoring
   - Adjust polling intervals in LLMMonitoring component
   - Configure appropriate batch sizes for requests
   - Monitor WebSocket connection health
   - Optimize LLM prompt lengths and complexity

2. Real-time Updates
   - Configure WebSocket reconnection parameters
   - Adjust log buffer sizes if memory usage is high
   - Implement log rotation if needed
   - Monitor network traffic for bottlenecks

### Debugging Tools

1. Frontend Debugging
   - Use React Developer Tools for component inspection
   - Check browser console for detailed error messages
   - Monitor Network tab for API/WebSocket issues
   - Use Performance tab for identifying bottlenecks

2. Backend Integration
   - Monitor backend logs for API errors
   - Check WebSocket connection status
   - Verify API endpoint responses
   - Test LLM service connectivity

3. Development Tools
   - Use TypeScript compiler for type checking
   - Run ESLint for code quality issues
   - Monitor build output for optimization opportunities
   - Use React profiler for performance analysis

## License

This project is licensed under the GNU General Public License v3.0 (GPLv3)
