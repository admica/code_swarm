#!/usr/bin/env python3
"""
Launcher script for Code Swarm - manages both backend and frontend services.
"""
import os
import sys
import subprocess
import signal
import time
from pathlib import Path
import psutil
import logging
from typing import Optional, List, Dict

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('code_swarm_launcher')

class ServiceManager:
    """Manages the backend and frontend services."""

    def __init__(self):
        self.backend_process: Optional[subprocess.Popen] = None
        self.frontend_process: Optional[subprocess.Popen] = None
        self.workspace_root = Path(__file__).parent
        self.frontend_dir = self.workspace_root / 'frontend'
        self.backend_script = self.workspace_root / 'agent_swarm_controller.py'

    def _is_port_in_use(self, port: int) -> bool:
        """Check if a port is in use."""
        for conn in psutil.net_connections():
            if conn.laddr.port == port:
                return True
        return False

    def _wait_for_port(self, port: int, timeout: int = 30) -> bool:
        """Wait for a port to become available."""
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self._is_port_in_use(port):
                return True
            time.sleep(1)
        return False

    def start_backend(self) -> bool:
        """Start the backend service."""
        try:
            logger.info("Starting backend service...")
            
            # Check if backend is already running
            if self._is_port_in_use(8000):
                logger.warning("Backend port 8000 is already in use. Is the service already running?")
                return False

            # Start the backend process
            self.backend_process = subprocess.Popen(
                [sys.executable, str(self.backend_script)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            # Wait for the backend to start
            if not self._wait_for_port(8000):
                logger.error("Backend failed to start (timeout waiting for port 8000)")
                return False

            logger.info("Backend service started successfully")
            return True

        except Exception as e:
            logger.error(f"Error starting backend: {e}")
            return False

    def start_frontend(self) -> bool:
        """Start the frontend service."""
        try:
            logger.info("Starting frontend service...")
            
            # Check if frontend is already running
            if self._is_port_in_use(3000):
                logger.warning("Frontend port 3000 is already in use. Is the service already running?")
                return False

            # Change to frontend directory
            os.chdir(self.frontend_dir)

            # Start the frontend process
            self.frontend_process = subprocess.Popen(
                ['npm', 'run', 'dev'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            # Wait for the frontend to start
            if not self._wait_for_port(3000):
                logger.error("Frontend failed to start (timeout waiting for port 3000)")
                return False

            logger.info("Frontend service started successfully")
            return True

        except Exception as e:
            logger.error(f"Error starting frontend: {e}")
            return False
        finally:
            # Change back to original directory
            os.chdir(self.workspace_root)

    def stop_services(self) -> None:
        """Stop all services."""
        logger.info("Stopping services...")

        def terminate_process_tree(process: Optional[subprocess.Popen]) -> None:
            """Terminate a process and all its children."""
            if not process:
                return

            try:
                parent = psutil.Process(process.pid)
                children = parent.children(recursive=True)
                
                for child in children:
                    child.terminate()
                parent.terminate()
                
                # Wait for processes to terminate
                _, alive = psutil.wait_procs([parent] + children, timeout=3)
                
                # Force kill if still alive
                for p in alive:
                    p.kill()
                    
            except psutil.NoSuchProcess:
                pass
            except Exception as e:
                logger.error(f"Error terminating process: {e}")

        # Stop frontend
        if self.frontend_process:
            terminate_process_tree(self.frontend_process)
            self.frontend_process = None

        # Stop backend
        if self.backend_process:
            terminate_process_tree(self.backend_process)
            self.backend_process = None

        logger.info("All services stopped")

    def check_dependencies(self) -> bool:
        """Check if all required dependencies are installed."""
        try:
            # Check Python dependencies
            subprocess.run(
                [sys.executable, '-c', 'import fastapi, uvicorn, watchdog, git'],
                check=True,
                capture_output=True
            )

            # Check if npm is installed
            subprocess.run(
                ['npm', '--version'],
                check=True,
                capture_output=True
            )

            # Check frontend dependencies
            os.chdir(self.frontend_dir)
            subprocess.run(
                ['npm', 'list'],
                check=True,
                capture_output=True
            )
            
            return True

        except subprocess.CalledProcessError:
            logger.error("Missing dependencies. Please run setup.py first.")
            return False
        except Exception as e:
            logger.error(f"Error checking dependencies: {e}")
            return False
        finally:
            os.chdir(self.workspace_root)

def main():
    """Main entry point for the launcher."""
    manager = ServiceManager()

    def signal_handler(signum, frame):
        """Handle shutdown signals."""
        logger.info("Shutdown signal received")
        manager.stop_services()
        sys.exit(0)

    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        # Check dependencies
        if not manager.check_dependencies():
            sys.exit(1)

        # Start services
        if not manager.start_backend():
            logger.error("Failed to start backend service")
            sys.exit(1)

        if not manager.start_frontend():
            logger.error("Failed to start frontend service")
            manager.stop_services()
            sys.exit(1)
        
        logger.info("Code Swarm is running!")
        logger.info("Frontend: http://localhost:3000")
        logger.info("Backend: http://localhost:8000")
        logger.info("Press Ctrl+C to stop")

        # Keep the script running
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        logger.info("Shutdown requested")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
    finally:
        manager.stop_services()

if __name__ == "__main__":
    main() 