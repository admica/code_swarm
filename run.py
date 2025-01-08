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
import threading
from queue import Queue, Empty

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
        try:
            # Only consider LISTEN state as "in use" - ignore TIME_WAIT
            for conn in psutil.net_connections(kind='inet'):
                if conn.laddr.port == port and conn.status == 'LISTEN':
                    return True
            return False
        except Exception as e:
            logger.error(f"Error checking port {port}: {e}")
            return False

    def _wait_for_port(self, port: int, timeout: int = 30) -> bool:
        """Wait for a port to become available."""
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self._is_port_in_use(port):
                return True
            time.sleep(1)
        return False

    def _kill_process_on_port(self, port: int) -> bool:
        """Kill any process running on the specified port.

        Args:
            port: Port number to check and kill process on

        Returns:
            bool: True if process was killed or no process found, False if kill failed
        """
        try:
            killed_something = False
            # Only try to kill processes in LISTEN state
            for conn in psutil.net_connections(kind='inet'):
                if conn.laddr.port == port and conn.status == 'LISTEN' and conn.pid is not None:
                    try:
                        process = psutil.Process(conn.pid)
                        logger.info(f"Found listening process on port {port} (PID: {conn.pid})")

                        # Try graceful shutdown first
                        process.terminate()
                        try:
                            process.wait(timeout=5)  # Increased timeout for graceful shutdown
                        except psutil.TimeoutExpired:
                            logger.warning(f"Process {conn.pid} did not terminate gracefully, forcing kill")
                            process.kill()  # Force kill
                            process.wait(timeout=3)  # Increased timeout for force kill

                        # Kill any surviving children
                        try:
                            children = process.children(recursive=True)
                            for child in children:
                                try:
                                    child.kill()
                                except psutil.NoSuchProcess:
                                    pass
                            psutil.wait_procs(children, timeout=3)
                        except psutil.NoSuchProcess:
                            pass

                        killed_something = True

                    except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                        logger.error(f"Error accessing process on port {port}: {e}")
                        continue
                elif conn.laddr.port == port and conn.status == 'TIME_WAIT':
                    logger.info(f"Found socket in TIME_WAIT state on port {port} - this is normal, ignoring")
                    return True  # Consider this a success case

            if killed_something:
                # Wait a bit for the port to be fully released
                time.sleep(1)
                if not self._is_port_in_use(port):
                    logger.info(f"Port {port} successfully released")
                    return True
                else:
                    logger.error(f"Port {port} still in LISTEN state after killing processes")
                    return False

            logger.debug(f"No listening processes found on port {port}")
            return True

        except Exception as e:
            logger.error(f"Unexpected error killing process on port {port}: {e}")
            return False

    def _cleanup_ports(self) -> None:
        """Clean up any processes running on required ports.

        Attempts to kill processes on both frontend and backend ports.
        Logs results but doesn't raise exceptions.
        """
        logger.info("Cleaning up existing processes on required ports...")

        results = {
            'backend': self._kill_process_on_port(8000),
            'frontend': self._kill_process_on_port(3000)
        }

        if all(results.values()):
            logger.info("Port cleanup completed successfully")
        else:
            failed_ports = [name for name, success in results.items() if not success]
            logger.warning(f"Port cleanup failed for: {', '.join(failed_ports)}")

    def start_backend(self) -> bool:
        """Start the backend service."""
        try:
            logger.info("Starting backend service...")

            # Check if backend is already running
            if self._is_port_in_use(8000):
                logger.warning("Backend port 8000 is already in use. Is the service already running?")
                return False

            # Create process with non-blocking pipes
            output_queue = Queue()
            
            def reader(pipe, queue):
                try:
                    with pipe:
                        for line in iter(pipe.readline, ''):
                            queue.put(('out' if pipe == process.stdout else 'err', line.strip()))
                finally:
                    queue.put(None)
            
            # Start the backend process
            process = subprocess.Popen(
                [sys.executable, str(self.backend_script)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,  # Line buffered
                universal_newlines=True,
                preexec_fn=os.setsid if os.name != 'nt' else None  # Create new process group on Unix
            )
            
            # Start output reader threads
            threading.Thread(target=reader, args=[process.stdout, output_queue], daemon=True).start()
            threading.Thread(target=reader, args=[process.stderr, output_queue], daemon=True).start()
            
            self.backend_process = process
            
            # Wait for the backend to start
            start_time = time.time()
            readers_alive = 2  # Number of reader threads
            
            while time.time() - start_time < 30:  # 30 second timeout
                # Check if process has exited
                if process.poll() is not None:
                    # Process exited, drain remaining output
                    while readers_alive > 0:
                        try:
                            item = output_queue.get(timeout=0.1)
                            if item is None:
                                readers_alive -= 1
                                continue
                            stream, line = item
                            logger.error(f"Backend {'error' if stream == 'err' else 'output'}: {line}")
                        except Empty:
                            break
                    
                    logger.error("Backend process exited unexpectedly")
                    return False
                
                # Check for port availability
                if self._is_port_in_use(8000):
                    logger.info("Backend service started successfully")
                    
                    # Start background thread to handle remaining output
                    def background_reader():
                        while True:
                            try:
                                item = output_queue.get()
                                if item is None:
                                    readers_alive -= 1
                                    if readers_alive == 0:
                                        break
                                    continue
                                stream, line = item
                                logger.info(f"Backend {'error' if stream == 'err' else 'output'}: {line}")
                            except Empty:
                                continue
                    
                    threading.Thread(target=background_reader, daemon=True).start()
                    return True
                
                # Check for any output
                try:
                    item = output_queue.get(timeout=0.1)
                    if item is None:
                        readers_alive -= 1
                        continue
                    stream, line = item
                    logger.info(f"Backend {'error' if stream == 'err' else 'output'}: {line}")
                except Empty:
                    continue
            
            logger.error("Backend failed to start (timeout waiting for port 8000)")
            process.terminate()
            return False

        except Exception as e:
            logger.error(f"Error starting backend: {e}")
            if self.backend_process:
                try:
                    self.backend_process.terminate()
                except Exception:
                    pass
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

            # Create process with non-blocking pipes
            output_queue = Queue()
            
            def reader(pipe, queue):
                try:
                    with pipe:
                        for line in iter(pipe.readline, ''):
                            queue.put(('out' if pipe == process.stdout else 'err', line.strip()))
                finally:
                    queue.put(None)

            # Start the frontend process
            process = subprocess.Popen(
                ['npm', 'run', 'dev'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,  # Line buffered
                universal_newlines=True,
                preexec_fn=os.setsid if os.name != 'nt' else None  # Create new process group on Unix
            )
            
            # Start output reader threads
            threading.Thread(target=reader, args=[process.stdout, output_queue], daemon=True).start()
            threading.Thread(target=reader, args=[process.stderr, output_queue], daemon=True).start()
            
            self.frontend_process = process
            
            # Wait for the frontend to start
            start_time = time.time()
            readers_alive = 2  # Number of reader threads
            
            while time.time() - start_time < 30:  # 30 second timeout
                # Check if process has exited
                if process.poll() is not None:
                    # Process exited, drain remaining output
                    while readers_alive > 0:
                        try:
                            item = output_queue.get(timeout=0.1)
                            if item is None:
                                readers_alive -= 1
                                continue
                            stream, line = item
                            logger.error(f"Frontend {'error' if stream == 'err' else 'output'}: {line}")
                        except Empty:
                            break
                    
                    logger.error("Frontend process exited unexpectedly")
                    return False
                
                # Check for port availability
                if self._is_port_in_use(3000):
                    logger.info("Frontend service started successfully")
                    
                    # Start background thread to handle remaining output
                    def background_reader():
                        nonlocal readers_alive
                        while True:
                            try:
                                item = output_queue.get()
                                if item is None:
                                    readers_alive -= 1
                                    if readers_alive == 0:
                                        break
                                    continue
                                stream, line = item
                                logger.info(f"Frontend {'error' if stream == 'err' else 'output'}: {line}")
                            except Empty:
                                continue
                    
                    threading.Thread(target=background_reader, daemon=True).start()
                    return True
                
                # Check for any output
                try:
                    item = output_queue.get(timeout=0.1)
                    if item is None:
                        readers_alive -= 1
                        continue
                    stream, line = item
                    logger.info(f"Frontend {'error' if stream == 'err' else 'output'}: {line}")
                except Empty:
                    continue
            
            logger.error("Frontend failed to start (timeout waiting for port 3000)")
            process.terminate()
            return False

        except Exception as e:
            logger.error(f"Error starting frontend: {e}")
            if self.frontend_process:
                try:
                    self.frontend_process.terminate()
                except Exception:
                    pass
            return False
        finally:
            # Change back to original directory
            os.chdir(self.workspace_root)

    def stop_services(self) -> None:
        """Stop all services and cleanup processes."""
        logger.info("Stopping services...")

        def terminate_process_tree(process: Optional[subprocess.Popen]) -> None:
            """Terminate a process and all its children recursively."""
            if not process:
                return

            try:
                parent = psutil.Process(process.pid)
                children = parent.children(recursive=True)

                # Log process tree for debugging
                logger.debug(f"Process tree for PID {process.pid}:")
                logger.debug(f"Parent: {parent}")
                logger.debug(f"Children: {children}")

                # First attempt graceful termination of children
                for child in children:
                    try:
                        child.terminate()
                    except psutil.NoSuchProcess:
                        continue

                # Then terminate parent
                parent.terminate()

                # Wait for processes to terminate with increased timeout
                gone, alive = psutil.wait_procs([parent] + children, timeout=5)

                # Force kill any remaining processes
                for p in alive:
                    try:
                        logger.warning(f"Force killing process {p.pid}")
                        p.kill()
                    except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                        logger.error(f"Error force killing process {p.pid}: {e}")

                # Wait for killed processes
                if alive:
                    psutil.wait_procs(alive, timeout=3)

            except psutil.NoSuchProcess:
                pass
            except Exception as e:
                logger.error(f"Error in process tree termination: {e}")

        # Stop services in reverse order
        if self.frontend_process:
            logger.info("Stopping frontend service...")
            terminate_process_tree(self.frontend_process)
            self.frontend_process = None

        if self.backend_process:
            logger.info("Stopping backend service...")
            terminate_process_tree(self.backend_process)
            self.backend_process = None

        # Check for any remaining listening processes
        if self._is_port_in_use(3000) or self._is_port_in_use(8000):
            logger.warning("Found remaining listening processes, attempting cleanup")
            self._cleanup_ports()

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