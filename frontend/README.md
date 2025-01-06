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
- **Styling**: 
  - Tailwind CSS for utility-first styling
  - shadcn/ui for component primitives
- **Data Fetching**: 
  - SWR for real-time data and caching
  - Axios for API requests
- **Visualization**:
  - Mermaid.js for dependency graphs
  - React components for real-time monitoring

## Project Structure

```
src/
├── app/              # Next.js app router pages
├── components/       # React components
│   ├── agents/      # Agent monitoring components
│   ├── changelog/   # Changelog visualization
│   ├── readme/      # README display components
│   ├── dependencies/# Dependency graph components
│   └── ui/          # Reusable UI components
├── types/           # TypeScript types
│   ├── agents/      # Agent-related types
│   └── api/         # API response types
└── lib/             # Utilities and helpers
```

## Features

- Real-time agent status monitoring
- Live code change visualization
- Interactive dependency graphs
- Documentation updates tracking
- Dark mode support
- Responsive design

## Development

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

## API Integration

The frontend communicates with Python agents through a REST API, featuring:
- WebSocket connections for real-time updates
- Endpoint-specific data fetching with SWR
- Automatic error handling and retries

## Contributing

1. Fork the repository
2. Create your feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

[Add your license here]
