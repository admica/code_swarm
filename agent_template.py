#!/usr/bin/env python3
"""Test agent for monitoring file changes and communicating with swarm controller."""

import os
import asyncio
import logging
from datetime import datetime
from typing import Optional, Dict, List
from shared.base_agent import BaseAgent
from shared.file_monitor import FileMonitor
from shared import config_manager
import fnmatch

# Set up logging
logger = logging.getLogger('agent_test')

class TestAgent(BaseAgent):
    """Simple test agent that monitors file changes."""

    def __init__(self, path: str):
        """Initialize the test agent.

        Args:
            path: Directory path to monitor
        """
        super().__init__('test')
        self.root_path = path
        self.file_monitor = None
        self.running = False
        
        # Load configurations
        self.config = config_manager.get_agent_config('test')
        controller_config = config_manager.get_controller_config()
        
        # Get watch patterns
        self.watch_patterns = self.config.get('watch_patterns', '*.py,*.lua').split(',')
        self.watch_patterns = [p.strip() for p in self.watch_patterns if p.strip()]
        logger.info(f"Loaded watch patterns: {self.watch_patterns}")
        
        # Get ignore patterns from both configs
        default_patterns = ['venv/*', '__pycache__/*', '.git/*', 'venv_linux/*']
        agent_patterns = self.config.get('ignore_patterns', '').split(',')
        controller_patterns = controller_config.get('skip_list', '').split(',')
        
        # Combine and clean patterns
        self.ignore_patterns = []
        for patterns in [agent_patterns, controller_patterns, default_patterns]:
            self.ignore_patterns.extend([p.strip() for p in patterns if p.strip()])
            
        logger.info(f"Loaded ignore patterns: {self.ignore_patterns}")
        
        # Debounce settings
        self.debounce_delay = float(self.config.get('debounce_delay', '2.0'))
        self.last_change_time = datetime.now()
        self._change_lock = asyncio.Lock()
        
        # Queue for processing changes
        self.queue = asyncio.Queue()
        self._processing_task: Optional[asyncio.Task] = None

    def should_watch_file(self, file_path: str) -> bool:
        """Check if a file should be watched based on patterns."""
        return any(fnmatch.fnmatch(file_path, pattern) for pattern in self.watch_patterns)

    def should_ignore_path(self, file_path: str) -> bool:
        """Check if a file should be ignored based on patterns."""
        rel_path = os.path.relpath(file_path, self.root_path)
        for pattern in self.ignore_patterns:
            if pattern.strip() and fnmatch.fnmatch(rel_path, pattern.strip()):
                logger.debug(f"Ignoring {rel_path} (matches pattern {pattern})")
                return True
        return False

    def get_status(self) -> Dict:
        """Get current agent status."""
        return {
            'status': 'running' if self.running else 'stopped',
            'root_path': self.root_path,
            'queue_size': self.queue.qsize() if hasattr(self, 'queue') else 0,
            'monitor_active': self.file_monitor is not None and self.file_monitor.is_running(),
            'processor_active': self._processing_task is not None and not self._processing_task.done() if self._processing_task else False,
            'ignore_patterns': self.ignore_patterns,
            'watch_patterns': self.watch_patterns,
            'debounce_delay': self.debounce_delay
        }

    async def handle_file_change(self, file_path: str) -> None:
        """Handle file change events with debouncing.

        Args:
            file_path: Path to the changed file
        """
        try:
            # Check if file should be watched
            if not self.should_watch_file(file_path):
                logger.debug(f"Ignoring change to non-watched file: {file_path}")
                return
                
            # Check if file should be ignored
            if self.should_ignore_path(file_path):
                return
                
            async with self._change_lock:
                now = datetime.now()
                time_since_last = (now - self.last_change_time).total_seconds()
                
                if time_since_last < self.debounce_delay:
                    logger.debug(f"Debouncing change for {file_path}")
                    return
                
                self.last_change_time = now
                
                # Add to processing queue
                await self.queue.put(file_path)
                
                # Report activity
                await self.send_activity(
                    action="file_changed",
                    file_path=file_path,
                    details={
                        'time': now.isoformat(),
                        'relative_path': os.path.relpath(file_path, self.root_path),
                        'file_type': os.path.splitext(file_path)[1][1:]  # Get extension without dot
                    }
                )
                
        except Exception as e:
            logger.error(f"Error handling file change: {e}")

    async def process_changes(self):
        """Process queued file changes."""
        while True:
            try:
                file_path = await self.queue.get()
                
                try:
                    rel_path = os.path.relpath(file_path, self.root_path)
                    logger.info(f"Processing change in {rel_path}")
                    
                    # Report processing
                    await self.send_activity(
                        action="processing_change",
                        file_path=file_path,
                        details={
                            'relative_path': rel_path,
                            'timestamp': datetime.now().isoformat(),
                            'file_type': os.path.splitext(file_path)[1][1:]
                        }
                    )
                    
                    # Simulate some processing time
                    await asyncio.sleep(0.5)
                    
                    # Report completion
                    await self.send_activity(
                        action="change_processed",
                        file_path=file_path,
                        details={
                            'relative_path': rel_path,
                            'timestamp': datetime.now().isoformat(),
                            'file_type': os.path.splitext(file_path)[1][1:]
                        }
                    )
                    
                except Exception as e:
                    logger.error(f"Error processing {file_path}: {e}")
                finally:
                    self.queue.task_done()
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in change processor: {e}")
                await asyncio.sleep(1)

    async def start(self, path: str):
        """Start the agent.

        Args:
            path: Directory path to monitor
        """
        if not self.running:
            self.running = True
            logger.info(f"Starting test agent, monitoring: {path}")
            logger.info(f"Watching file patterns: {self.watch_patterns}")
            
            # Initialize file monitor
            async def async_callback(file_path):
                await self.handle_file_change(file_path)
            self.file_monitor = FileMonitor('agent_test', lambda fp: asyncio.create_task(async_callback(fp)))
            
            # Start monitoring
            self.file_monitor.start(path)
            logger.info("File monitor started")
            
            # Start change processor if needed
            if not self._processing_task or self._processing_task.done():
                self._processing_task = asyncio.create_task(self.process_changes())
                logger.info("Change processor started")
            
            # Report initial status
            await self.send_activity(
                action="agent_started",
                file_path=path,
                details=self.get_status()
            )
            
            # Run the WebSocket handler
            try:
                await self.run()  # This runs until the agent is stopped
            except asyncio.CancelledError:
                logger.info("Agent tasks cancelled")
                raise
            except Exception as e:
                logger.error(f"Error in agent tasks: {e}")
                raise

    async def stop(self):
        """Stop the agent."""
        logger.info("Stopping test agent...")
        self.running = False
        
        # Stop the change processor
        if self._processing_task:
            self._processing_task.cancel()
            try:
                await self._processing_task
            except asyncio.CancelledError:
                pass
            self._processing_task = None
        
        # Stop file monitoring
        if self.file_monitor:
            self.file_monitor.stop()
            self.file_monitor = None
        
        # Clean up state
        self.root_path = None
        
        # Disconnect WebSockets
        await self.disconnect()
        logger.info("Test agent stopped")

async def main(path: str) -> None:
    """Main function to run the test agent.
    
    Args:
        path: Directory path to monitor
    """
    agent = None
    try:
        agent = TestAgent(path)
        await agent.start(path)
    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
    finally:
        if agent:
            await agent.stop()

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        logger.error("Please provide the directory path to monitor")
        sys.exit(1)
    
    path = sys.argv[1]
    asyncio.run(main(path)) 
