#!/usr/bin/env python3
"""Template for a Code Swarm agent."""

import os
import sys
import asyncio
import signal
from pathlib import Path
from typing import Dict, Any

from shared.base_agent import BaseAgent
from shared.file_monitor import FileMonitor

class AgentTemplate(BaseAgent):
    """Template agent implementing core agent functionality."""

    def __init__(self, monitor_path: str):
        """Initialize the agent.

        Args:
            monitor_path: Path to monitor for file changes
        """
        # Initialize base agent with name
        super().__init__("template")  # Change "template" to your agent's name

        # Store monitor path
        self.monitor_path = Path(monitor_path)

        # Initialize file monitor
        self.file_monitor = FileMonitor(
            self.name,
            self.handle_file_change
        )

        # Setup signal handlers
        self._setup_signal_handlers()

    def _setup_signal_handlers(self):
        """Setup handlers for graceful shutdown."""
        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        print(f"\nReceived signal {signum}")
        if self.running:
            print("Initiating graceful shutdown...")
            asyncio.create_task(self.stop())

    async def handle_file_change(self, file_path: str) -> None:
        """Handle file system changes.

        Args:
            file_path: Path to the changed file
        """
        if not self.running:
            return

        try:
            # Log the file change detection
            await self.log_activity(
                action="file_changed",
                file_path=str(file_path)
            )

            # Send message about file change
            await self.send_agent_message(
                "file_change",
                {
                    "file": str(file_path),
                    "status": "detected"
                }
            )

        except Exception as e:
            if self.running:  # Only log if still running
                await self.log(
                    'error',
                    'file_handler',
                    f"Error handling file change: {e}",
                    file=str(file_path)
                )

    def get_status(self) -> Dict[str, Any]:
        """Get current agent status."""
        status = super().get_status()
        status.update({
            "monitor_status": self.file_monitor.get_status() if self.file_monitor else None,
            "monitor_path": str(self.monitor_path)
        })
        return status

    async def start(self) -> None:
        """Start the agent."""
        try:
            # Connect to controller
            if not await self.connect():
                self.logger.error("Failed to connect to controller")
                return

            # Start file monitoring
            if not self.file_monitor.start(str(self.monitor_path)):
                self.logger.error("Failed to start file monitor")
                await self.disconnect()
                return

            self.running = True

            # Send startup message
            await self.send_agent_message(
                "lifecycle",
                {
                    "status": "started",
                    "monitor_path": str(self.monitor_path)
                }
            )

            # Run the main agent loop
            await super().run()

        except Exception as e:
            self.logger.error(f"Error starting agent: {e}")
            self.running = False
            await self.stop()

    async def stop(self) -> None:
        """Stop the agent."""
        if not self.running:
            return

        self.running = False

        try:
            # Send shutdown message
            await self.send_agent_message(
                "lifecycle",
                {
                    "status": "stopping",
                    "monitor_path": str(self.monitor_path)
                }
            )

            # Stop file monitoring
            if self.file_monitor:
                self.file_monitor.stop()

            # Disconnect from controller
            await self.disconnect()

        except Exception as e:
            self.logger.error(f"Error during shutdown: {e}")

def main():
    """Main entry point."""
    if len(sys.argv) != 2:
        print("Usage: agent_template.py <monitor_path>")
        sys.exit(1)

    monitor_path = sys.argv[1]
    agent = AgentTemplate(monitor_path)

    try:
        asyncio.run(agent.start())
    except KeyboardInterrupt:
        print("\nShutting down...")
        asyncio.run(agent.stop())
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
