#!/usr/bin/env python3
"""Shared file monitoring utilities for Code Swarm."""

import os
import asyncio
import fnmatch
from typing import Callable, List, Set, Optional
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileModifiedEvent
from .config import config_manager
from .logging import AgentLogger

class FileMonitor:
    """File monitoring system with pattern matching and change detection."""
    
    def __init__(self, agent_name: str, callback: Callable[[str], None]):
        self.agent_name = agent_name
        self.callback = callback
        self.config = config_manager.get_agent_config(agent_name)
        self.logger = AgentLogger(agent_name)
        
        self.watch_patterns = self.config.get('watch_patterns', '*.py').split(',')
        self.ignore_patterns = self.config.get('ignore_patterns', '__pycache__/*,.*').split(',')
        
        self.observer: Optional[Observer] = None
        self.monitored_files: Set[str] = set()
        self.monitor_path: Optional[str] = None
        self.running = False
        
        # Debounce settings
        self.debounce_delay = 1.0  # seconds
        self.pending_changes: Set[str] = set()
        self._debounce_task: Optional[asyncio.Task] = None
    
    def should_monitor_file(self, file_path: str) -> bool:
        """Check if a file should be monitored based on patterns."""
        file_name = os.path.basename(file_path)
        rel_path = os.path.relpath(file_path, self.monitor_path) if self.monitor_path else file_name
        
        # Check ignore patterns first
        for pattern in self.ignore_patterns:
            if fnmatch.fnmatch(rel_path, pattern.strip()):
                return False
        
        # Then check watch patterns
        for pattern in self.watch_patterns:
            if fnmatch.fnmatch(rel_path, pattern.strip()):
                return True
        
        return False
    
    def scan_directory(self) -> None:
        """Scan the monitored directory for matching files."""
        if not self.monitor_path:
            return
        
        new_files = set()
        for root, _, files in os.walk(self.monitor_path):
            for file in files:
                file_path = os.path.join(root, file)
                if self.should_monitor_file(file_path):
                    new_files.add(file_path)
        
        # Check for removed files
        removed = self.monitored_files - new_files
        if removed:
            self.logger.info(
                f"Files no longer monitored: {len(removed)}",
                category="file_monitor",
                files=list(removed)
            )
        
        # Check for new files
        added = new_files - self.monitored_files
        if added:
            self.logger.info(
                f"New files being monitored: {len(added)}",
                category="file_monitor",
                files=list(added)
            )
        
        self.monitored_files = new_files
    
    async def _handle_debounced_changes(self):
        """Process debounced file changes."""
        while True:
            try:
                if not self.pending_changes:
                    await asyncio.sleep(0.1)
                    continue
                
                # Wait for debounce delay
                await asyncio.sleep(self.debounce_delay)
                
                # Process all pending changes
                changes = self.pending_changes.copy()
                self.pending_changes.clear()
                
                for file_path in changes:
                    try:
                        self.callback(file_path)
                    except Exception as e:
                        self.logger.error(
                            f"Error processing file {file_path}: {e}",
                            category="file_monitor",
                            error=str(e)
                        )
            
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(
                    f"Error in debounce handler: {e}",
                    category="file_monitor",
                    error=str(e)
                )
                await asyncio.sleep(1)
    
    def handle_file_change(self, event):
        """Handle file system change events."""
        if not isinstance(event, FileModifiedEvent):
            return
        
        file_path = event.src_path
        if not self.should_monitor_file(file_path):
            return
        
        self.logger.debug(
            f"File change detected: {file_path}",
            category="file_monitor"
        )
        
        # Add to pending changes
        self.pending_changes.add(file_path)
    
    def start(self, path: str) -> bool:
        """Start monitoring a directory."""
        try:
            path = os.path.abspath(path)
            if not os.path.exists(path):
                os.makedirs(path)
            elif not os.path.isdir(path):
                raise NotADirectoryError(f"Not a directory: {path}")
            
            # Stop existing observer if any
            self.stop()
            
            self.monitor_path = path
            self.observer = Observer()
            
            # Create event handler
            event_handler = FileSystemEventHandler()
            event_handler.on_modified = self.handle_file_change
            
            # Schedule monitoring
            self.observer.schedule(event_handler, path, recursive=True)
            self.observer.start()
            
            # Start debounce handler
            if self._debounce_task is None or self._debounce_task.done():
                self._debounce_task = asyncio.create_task(
                    self._handle_debounced_changes()
                )
            
            # Scan for existing files
            self.scan_directory()
            
            self.running = True
            self.logger.info(
                f"Started monitoring: {path}",
                category="file_monitor",
                patterns=self.watch_patterns,
                ignore=self.ignore_patterns
            )
            return True
            
        except Exception as e:
            self.logger.error(
                f"Error starting file monitor: {e}",
                category="file_monitor",
                error=str(e)
            )
            return False
    
    def stop(self):
        """Stop monitoring."""
        if self.observer:
            self.observer.stop()
            self.observer.join()
            self.observer = None
        
        if self._debounce_task:
            self._debounce_task.cancel()
            self._debounce_task = None
        
        self.running = False
        self.monitor_path = None
        self.monitored_files.clear()
        self.pending_changes.clear()
        
        self.logger.info(
            "Stopped monitoring",
            category="file_monitor"
        )
    
    def is_running(self) -> bool:
        """Check if monitoring is active."""
        return self.running and bool(self.observer) and self.observer.is_alive()
    
    def get_status(self) -> dict:
        """Get current monitoring status."""
        return {
            "running": self.is_running(),
            "path": self.monitor_path,
            "monitored_files": len(self.monitored_files),
            "watch_patterns": self.watch_patterns,
            "ignore_patterns": self.ignore_patterns,
            "pending_changes": len(self.pending_changes)
        } 