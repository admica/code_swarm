#!/usr/bin/env python3
# PATH: ./agent_swarm_controller.py
"""
Swarm Controller - Manages code_swarm agents and provides API endpoints
"""
import os
import sys
import json
import time
import logging
import asyncio
import psutil
import uvicorn
import aiohttp
import subprocess
import configparser
from datetime import datetime
from typing import Dict, List, Optional, Set, Any, Union
from pathlib import Path
from fastapi import FastAPI, HTTPException, BackgroundTasks, APIRouter, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from pydantic import BaseModel
from shared.llm import LLMService
from shared.config import config_manager
from shared.models import AgentStatus, LLMRequest, LLMResponse, LLMStatus, ControllerInfo
import aiofiles

# Set up logging
logger = logging.getLogger('swarm_controller')
logger.setLevel(logging.INFO)

# Create logs directory if it doesn't exist
log_dir = Path('logs')
log_dir.mkdir(exist_ok=True)

# File handler
fh = logging.FileHandler(log_dir / 'swarm_controller.log')
fh.setLevel(logging.INFO)

# Console handler
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)

# Formatter
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
fh.setFormatter(formatter)
ch.setFormatter(formatter)

# Add handlers
logger.addHandler(fh)
logger.addHandler(ch)

class AgentStatus(BaseModel):
    name: str
    pid: Optional[int]
    running: bool
    monitor_path: Optional[str]
    last_error: Optional[str]

    def dict(self, *args, **kwargs):
        return {
            "name": self.name,
            "pid": self.pid,
            "running": self.running,
            "monitor_path": self.monitor_path,
            "last_error": self.last_error
        }

class LLMRequest(BaseModel):
    prompt: str
    model: str = "llama3.2"
    agent: str
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None

class LLMResponse(BaseModel):
    response: Optional[str]
    error: Optional[str]
    processing_time: float
    queue_time: float
    timestamp: datetime

class LLMMetrics:
    """Tracks metrics for LLM requests."""

    def __init__(self):
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0
        self.total_processing_time = 0.0
        self.total_queue_time = 0.0
        self.requests_by_agent: Dict[str, int] = {}

    def record_request(self, agent: str, success: bool, processing_time: float, queue_time: float):
        """Record metrics for a request."""
        self.total_requests += 1
        self.total_processing_time += processing_time
        self.total_queue_time += queue_time

        if success:
            self.successful_requests += 1
        else:
            self.failed_requests += 1

        self.requests_by_agent[agent] = self.requests_by_agent.get(agent, 0) + 1

    def get_metrics(self) -> Dict:
        """Get current metrics."""
        avg_processing_time = (
            self.total_processing_time / self.total_requests 
            if self.total_requests > 0 else 0
        )
        avg_queue_time = (
            self.total_queue_time / self.total_requests 
            if self.total_requests > 0 else 0
        )

        return {
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "success_rate": (
                self.successful_requests / self.total_requests * 100 
                if self.total_requests > 0 else 0
            ),
            "average_processing_time": avg_processing_time,
            "average_queue_time": avg_queue_time,
            "requests_by_agent": self.requests_by_agent
        }

class LLMStatus(BaseModel):
    """Status information about the LLM service."""
    available: bool
    model: Optional[str]
    error: Optional[str]
    models: Optional[List[str]]
    response_time: Optional[float]

class LLMService:
    """Handles LLM requests with queueing and metrics tracking."""

    def __init__(self):
        self.queue = asyncio.Queue()
        self.metrics = LLMMetrics()
        self.processing_task: Optional[asyncio.Task] = None
        self.ollama_url = "http://localhost:11434"
        self.timeout = 120
        self.session: Optional[aiohttp.ClientSession] = None
        self.max_retries = 3
        self.retry_delay = 1.0  # seconds

    async def start(self):
        """Start the queue processing task and create HTTP session."""
        if not self.processing_task:
            self.session = aiohttp.ClientSession()
            self.processing_task = asyncio.create_task(self._process_queue())
            logger.info("LLM queue processor started")

    async def stop(self):
        """Stop the queue processing task and close HTTP session."""
        if self.processing_task:
            self.processing_task.cancel()
            try:
                await self.processing_task
            except asyncio.CancelledError:
                pass
            self.processing_task = None
            if self.session:
                await self.session.close()
                self.session = None
            logger.info("LLM queue processor stopped")

    async def _process_queue(self):
        """Process requests from the queue."""
        while True:
            try:
                logger.info("Waiting for requests in queue...")
                request, future, enqueue_time = await self.queue.get()
                queue_time = time.time() - enqueue_time
                logger.info(f"Processing request from agent '{request.agent}' (queued for {queue_time:.2f}s)")

                try:
                    start_time = time.time()
                    logger.info(f"Making LLM request to Ollama: model={request.model}, prompt_length={len(request.prompt)}")
                    response = await self._make_llm_request(request)
                    processing_time = time.time() - start_time
                    logger.info(f"LLM request completed in {processing_time:.2f}s")

                    # Record metrics
                    self.metrics.record_request(
                        request.agent,
                        success=True,
                        processing_time=processing_time,
                        queue_time=queue_time
                    )

                    # Create response object
                    llm_response = LLMResponse(
                        response=response,
                        error=None,
                        processing_time=processing_time,
                        queue_time=queue_time,
                        timestamp=datetime.now()
                    )

                    future.set_result(llm_response)
                    logger.info("Response sent back to agent")

                except Exception as e:
                    error_msg = str(e)
                    logger.error(f"Error processing LLM request: {error_msg}")
                    logger.error(f"Request details: agent={request.agent}, model={request.model}")

                    # Record failed request
                    self.metrics.record_request(
                        request.agent,
                        success=False,
                        processing_time=0.0,
                        queue_time=queue_time
                    )

                    # Create error response
                    llm_response = LLMResponse(
                        response=None,
                        error=error_msg,
                        processing_time=0.0,
                        queue_time=queue_time,
                        timestamp=datetime.now()
                    )

                    future.set_result(llm_response)
                    logger.info("Error response sent back to agent")

                finally:
                    self.queue.task_done()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in queue processor: {e}")
                await asyncio.sleep(1)  # Prevent tight loop on persistent errors

    async def _make_llm_request(self, request: LLMRequest) -> str:
        """Make actual request to Ollama with retry logic."""
        if not self.session:
            logger.error("No HTTP session available")
            raise Exception("LLM service not properly initialized")

        last_error = None
        for attempt in range(self.max_retries):
            try:
                if attempt > 0:
                    logger.info(f"Retrying LLM request (attempt {attempt + 1}/{self.max_retries})")
                    await asyncio.sleep(self.retry_delay * attempt)  # Exponential backoff

                logger.debug(f"Sending request to Ollama: {self.ollama_url}/api/generate")
                async with self.session.post(
                    f"{self.ollama_url}/api/generate",
                    json={
                        "model": request.model,
                        "prompt": request.prompt,
                        "stream": False,
                        "options": {
                            "temperature": request.temperature if request.temperature is not None else 0.6,
                            "max_tokens": request.max_tokens if request.max_tokens is not None else None
                        }
                    },
                    timeout=aiohttp.ClientTimeout(total=self.timeout)
                ) as response:
                    logger.debug(f"Ollama response status: {response.status}")
                    response.raise_for_status()
                    result = await response.json()
                    logger.debug("Successfully parsed Ollama response")

                    if not result.get('response'):
                        raise Exception("Empty response from Ollama")

                    return result['response']

            except aiohttp.ClientError as e:
                last_error = f"Ollama request failed: {str(e)}"
                logger.warning(f"Attempt {attempt + 1} failed: {last_error}")
                if attempt == self.max_retries - 1:
                    raise Exception(f"Ollama service error after {self.max_retries} attempts: {last_error}")
            except Exception as e:
                last_error = str(e)
                logger.warning(f"Attempt {attempt + 1} failed: {last_error}")
                if attempt == self.max_retries - 1:
                    raise Exception(f"Unexpected error after {self.max_retries} attempts: {last_error}")

        raise Exception(f"All {self.max_retries} attempts failed. Last error: {last_error}")

    async def submit_request(self, request: LLMRequest) -> LLMResponse:
        """Submit a request to the queue."""
        future = asyncio.Future()
        await self.queue.put((request, future, time.time()))
        return await future

    def get_metrics(self) -> Dict:
        """Get current LLM metrics."""
        return self.metrics.get_metrics()

    async def get_status(self) -> LLMStatus:
        """Get current LLM status including available models."""
        if not self.session:
            self.session = aiohttp.ClientSession()

        try:
            start_time = time.time()
            async with self.session.get(
                f"{self.ollama_url}/api/tags",
                timeout=aiohttp.ClientTimeout(total=5)
            ) as response:
                response_time = time.time() - start_time

                if response.status == 200:
                    data = await response.json()
                    models = [model["name"] for model in data.get("models", [])]
                    return LLMStatus(
                        available=True,
                        model="llama3.2",
                        models=models,
                        response_time=response_time,
                        error=None
                    )
                else:
                    return LLMStatus(
                        available=False,
                        error=f"Ollama returned status code: {response.status}",
                        response_time=response_time,
                        model=None,
                        models=None
                    )

        except aiohttp.ClientError as e:
            return LLMStatus(
                available=False,
                error=f"Failed to connect to Ollama: {str(e)}",
                response_time=None,
                model=None,
                models=None
            )

class ControllerInfo(BaseModel):
    """Information about the controller configuration and status."""
    monitor_path: Optional[str]
    skip_list: List[str]
    ollama_available: bool
    ollama_model: Optional[str]

class SwarmController:
    """Controls and monitors code_swarm agents."""

    def __init__(self):
        self.config = configparser.ConfigParser()
        self.config.read('config.ini')

        self.monitor_path = self.config.get('swarm_controller', 'monitor_path', fallback=None)
        self.skip_list = self.config.get('swarm_controller', 'skip_list', fallback='').split(',')
        self.skip_list = [path.strip() for path in self.skip_list if path.strip()]

        # Initialize agents dictionary
        self.agents = {
            'agent_code_mon_changelog': {
                "script": "agent_code_mon_changelog.py",
                "process": None,
                "status": AgentStatus(
                    name='agent_code_mon_changelog',
                    pid=None,
                    running=False,
                    monitor_path=None,
                    last_error=None
                )
            },
            'agent_code_mon_readme': {
                "script": "agent_code_mon_readme.py",
                "process": None,
                "status": AgentStatus(
                    name='agent_code_mon_readme',
                    pid=None,
                    running=False,
                    monitor_path=None,
                    last_error=None
                )
            },
            'agent_code_mon_deps': {
                "script": "agent_code_mon_deps.py",
                "process": None,
                "status": AgentStatus(
                    name='agent_code_mon_deps',
                    pid=None,
                    running=False,
                    monitor_path=None,
                    last_error=None
                )
            }
        }
        self.monitor_task = None

    def _save_config(self) -> None:
        """Save current configuration to config.ini file."""
        try:
            if not self.config.has_section('swarm_controller'):
                self.config.add_section('swarm_controller')

            with open('config.ini', 'w') as configfile:
                self.config.write(configfile)
        except Exception as e:
            logger.error(f"Error saving config: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to save configuration: {str(e)}"
            )

    async def get_info(self) -> ControllerInfo:
        """Get controller information."""
        ollama_status = await llm_service.get_status()
        return ControllerInfo(
            monitor_path=self.monitor_path,
            skip_list=self.skip_list,
            ollama_available=ollama_status.available,
            ollama_model=ollama_status.model
        )

    def update_skip_list(self, skip_list: List[str]) -> Dict[str, Any]:
        """Update the skip list configuration."""
        try:
            self.skip_list = skip_list

            # Update config file
            if not self.config.has_section('swarm_controller'):
                self.config.add_section('swarm_controller')

            self.config['swarm_controller']['skip_list'] = ','.join(skip_list)

            with open('config.ini', 'w') as configfile:
                self.config.write(configfile)

            return {"success": True, "skip_list": skip_list}
        except Exception as e:
            logger.error(f"Error updating skip list: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to update skip list: {str(e)}"
            )

    def should_skip_path(self, path: str) -> bool:
        """Check if a path should be skipped based on the skip list."""
        path = path.replace('\\', '/')  # Normalize path separators
        return any(
            skip_pattern in path
            for skip_pattern in self.skip_list
        )

    def set_monitor_path(self, path: str) -> Dict[str, str]:
        """Set and validate the monitoring path."""
        try:
            # Convert to absolute path and resolve any symlinks
            abs_path = os.path.abspath(os.path.expanduser(path))

            # Check if path exists and is accessible
            if not os.path.exists(abs_path):
                return {"error": f"Path does not exist: {abs_path}"}
            if not os.path.isdir(abs_path):
                return {"error": f"Path is not a directory: {abs_path}"}
            if not os.access(abs_path, os.R_OK):
                return {"error": f"Path is not readable: {abs_path}"}

            # Store the new path
            old_path = self.monitor_path
            self.monitor_path = abs_path

            # Update config file
            self.config['swarm_controller']['monitor_path'] = abs_path
            self._save_config()

            # Restart agents if they were running
            running_agents = [name for name, agent in self.agents.items() 
                            if agent["status"].running]

            if running_agents and old_path != abs_path:
                self.stop_all()
                self.start_all(abs_path)
                return {
                    "success": f"Monitor path set to: {abs_path}",
                    "restarted_agents": running_agents
                }

            return {"success": f"Monitor path set to: {abs_path}"}

        except Exception as e:
            return {"error": f"Failed to set monitor path: {str(e)}"}

    def start_agent(self, agent_name: str, path: Optional[str] = None) -> AgentStatus:
        """Start a specific agent."""
        if agent_name not in self.agents:
            logger.error(f"Unknown agent: {agent_name}")
            raise ValueError(f"Unknown agent: {agent_name}")

        # Use provided path or fall back to configured monitor_path
        monitor_path = path or self.monitor_path
        if not monitor_path:
            logger.error("No monitor path configured")
            raise ValueError("No monitor path configured. Set a path first.")

        # Validate and create path if needed
        try:
            monitor_path = os.path.abspath(os.path.expanduser(monitor_path))
            if not os.path.exists(monitor_path):
                logger.info(f"Creating directory: {monitor_path}")
                os.makedirs(monitor_path)
            elif not os.path.isdir(monitor_path):
                raise ValueError(f"Path exists but is not a directory: {monitor_path}")
            elif not os.access(monitor_path, os.R_OK | os.W_OK):
                raise ValueError(f"Insufficient permissions for directory: {monitor_path}")
        except Exception as e:
            logger.error(f"Error validating path {monitor_path}: {e}")
            raise ValueError(f"Invalid monitor path: {str(e)}")

        agent = self.agents[agent_name]

        if agent["process"] and agent["process"].poll() is None:
            logger.warning(f"Agent {agent_name} is already running with PID {agent['process'].pid}")
            return agent["status"]

        try:
            logger.info(f"Starting agent {agent_name} with path: {monitor_path}")

            # Get the absolute path to the agent script
            script_path = os.path.abspath(agent["script"])
            if not os.path.exists(script_path):
                raise ValueError(f"Agent script not found: {script_path}")

            logger.debug(f"Agent script path: {script_path}")

            # Start the agent process
            process = subprocess.Popen(
                [sys.executable, script_path, monitor_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            # Wait a moment to check if process started successfully
            time.sleep(0.5)
            if process.poll() is not None:
                stdout, stderr = process.communicate()
                logger.error(f"Agent {agent_name} failed to start")
                logger.error(f"stdout: {stdout}")
                logger.error(f"stderr: {stderr}")
                agent["status"].last_error = stderr or "Failed to start"
                agent["status"].running = False
                raise Exception(f"Agent failed to start: {stderr}")

            agent["process"] = process
            agent["status"].pid = process.pid
            agent["status"].running = True
            agent["status"].monitor_path = monitor_path
            agent["status"].last_error = None

            logger.info(f"Successfully started agent {agent_name} with PID {process.pid}")
            return agent["status"]

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error starting agent {agent_name}: {error_msg}")
            agent["status"].running = False
            agent["status"].last_error = error_msg
            raise

    def stop_agent(self, agent_name: str) -> AgentStatus:
        """Stop a specific agent."""
        if agent_name not in self.agents:
            logger.error(f"Unknown agent: {agent_name}")
            raise ValueError(f"Unknown agent: {agent_name}")

        agent = self.agents[agent_name]
        logger.info(f"Attempting to stop agent {agent_name}")

        if agent["process"]:
            try:
                logger.debug(f"Found process for {agent_name} with PID {agent['process'].pid}")
                process = psutil.Process(agent["process"].pid)

                # Log children processes before termination
                children = process.children(recursive=True)
                if children:
                    logger.debug(f"Found {len(children)} child processes to terminate")

                for child in children:
                    logger.debug(f"Terminating child process {child.pid}")
                    child.terminate()

                logger.debug(f"Terminating main process {process.pid}")
                process.terminate()

                process.wait(timeout=5)
                logger.info(f"Successfully stopped agent {agent_name}")

                agent["process"] = None
                agent["status"].pid = None
                agent["status"].running = False
                agent["status"].last_error = None

            except psutil.NoSuchProcess:
                logger.warning(f"Process for agent {agent_name} no longer exists")
                agent["process"] = None
                agent["status"].pid = None
                agent["status"].running = False
            except Exception as e:
                error_msg = str(e)
                logger.error(f"Error stopping agent {agent_name}: {error_msg}")
                agent["status"].last_error = error_msg
                raise

        return agent["status"]

    def get_agent_status(self, agent_name: str) -> AgentStatus:
        """Get the status of a specific agent."""
        if agent_name not in self.agents:
            raise ValueError(f"Unknown agent: {agent_name}")

        agent = self.agents[agent_name]

        # Update status based on process state
        if agent["process"]:
            try:
                process = psutil.Process(agent["process"].pid)
                agent["status"].running = process.is_running()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                agent["status"].running = False
                agent["status"].pid = None
                agent["process"] = None

        return agent["status"]

    def get_all_statuses(self) -> Dict[str, AgentStatus]:
        """Get status of all agents."""
        return {name: self.get_agent_status(name) for name in self.agents}

    def start_all(self, path: str) -> Dict[str, AgentStatus]:
        """Start all agents."""
        statuses = {}
        for agent_name in self.agents:
            try:
                statuses[agent_name] = self.start_agent(agent_name, path)
            except Exception as e:
                logger.error(f"Error starting {agent_name}: {e}")
                statuses[agent_name] = self.get_agent_status(agent_name)
        return statuses

    def stop_all(self) -> Dict[str, AgentStatus]:
        """Stop all agents."""
        statuses = {}
        for agent_name in self.agents:
            try:
                statuses[agent_name] = self.stop_agent(agent_name)
            except Exception as e:
                logger.error(f"Error stopping {agent_name}: {e}")
                statuses[agent_name] = self.get_agent_status(agent_name)
        return statuses

    def read_agent_logs(self, agent_name: str, lines: int = 100) -> List[str]:
        """Read recent log entries for an agent."""
        if agent_name not in self.agents:
            raise ValueError(f"Unknown agent: {agent_name}")

        log_file = f"agent_code_mon_{agent_name}.log"
        if not os.path.exists(log_file):
            return []

        try:
            with open(log_file, 'r') as f:
                return list(reversed(f.readlines()[-lines:]))
        except Exception as e:
            logger.error(f"Error reading logs for {agent_name}: {e}")
            return []

    async def _monitor_agents(self):
        """Monitor agent processes and update their status."""
        while True:
            for agent_name, agent in self.agents.items():
                if agent["process"]:
                    try:
                        process = psutil.Process(agent["process"].pid)
                        running = process.is_running()
                        if running != agent["status"].running:
                            agent["status"].running = running
                            if not running:
                                agent["status"].pid = None
                                agent["process"] = None
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        if agent["status"].running:
                            agent["status"].running = False
                            agent["status"].pid = None
                            agent["process"] = None
            await asyncio.sleep(1)

    async def start_monitoring(self):
        """Start the agent monitoring task."""
        if not self.monitor_task:
            self.monitor_task = asyncio.create_task(self._monitor_agents())

    async def stop_monitoring(self):
        """Stop the agent monitoring task."""
        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass
            self.monitor_task = None

class SkipListUpdate(BaseModel):
    skip_list: List[str]

# Initialize FastAPI app and services
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    # Startup
    await llm_service.start()
    await controller.start_monitoring()
    yield
    # Shutdown
    await controller.stop_monitoring()
    await llm_service.stop()

app = FastAPI(
    title="Code Swarm Controller", 
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create API router
api_router = APIRouter(prefix="/api")

controller = SwarmController()
llm_service = LLMService()

# Move all endpoints to API router
@api_router.post("/config/monitor-path")
async def set_monitor_path(path: str):
    """Set the directory path to monitor."""
    return controller.set_monitor_path(path)

@api_router.get("/info")
async def get_controller_info():
    """Get general controller information."""
    return await controller.get_info()

@api_router.get("/llm/metrics")
async def get_llm_metrics():
    """Get LLM usage metrics."""
    return llm_service.get_metrics()

@api_router.post("/agents/{agent_name}/start")
async def start_agent(agent_name: str, path: str = None):
    """Start a specific agent.

    Args:
        agent_name: Name of the agent to start
        path: Path to monitor. Required if no default path is configured.
    """
    try:
        if not path and not controller.monitor_path:
            raise HTTPException(
                status_code=400,
                detail="Path parameter is required when no default path is configured"
            )

        status = controller.start_agent(agent_name, path)
        return status
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/agents/{agent_name}/stop")
async def stop_agent(agent_name: str):
    """Stop a specific agent."""
    try:
        status = controller.stop_agent(agent_name)
        return status
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/agents/{agent_name}/status")
async def get_agent_status(agent_name: str):
    """Get status of a specific agent."""
    try:
        return controller.get_agent_status(agent_name)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/agents/{agent_name}/logs")
async def get_agent_logs(agent_name: str, lines: int = 100):
    """Get recent logs for a specific agent."""
    try:
        return controller.read_agent_logs(agent_name, lines)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/agents")
async def get_all_statuses():
    """Get status of all agents."""
    return controller.get_all_statuses()

@api_router.post("/agents/start-all")
async def start_all_agents(path: str = None):
    """Start all agents. Uses configured monitor_path if no path provided."""
    actual_path = path if path is not None else controller.monitor_path
    if actual_path is None:
        raise HTTPException(status_code=400, detail="No monitor path configured")

    statuses = controller.start_all(actual_path)
    return statuses

@api_router.post("/agents/stop-all")
async def stop_all_agents():
    """Stop all agents."""
    try:
        statuses = controller.stop_all()
        return statuses
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/llm/status")
async def get_llm_status():
    """Get current LLM service status."""
    return await llm_service.get_status()

@api_router.get("/llm/health")
async def check_llm_health():
    """Quick health check for LLM service."""
    status = await llm_service.get_status()
    if not status.available:
        raise HTTPException(status_code=503, detail=status.error or "LLM service unavailable")
    return {"status": "healthy", "response_time": status.response_time}

@api_router.post("/llm/generate")
async def generate_llm_content(request: LLMRequest) -> LLMResponse:
    """Generic endpoint for LLM content generation.

    This endpoint replaces agent-specific endpoints and provides a unified
    interface for all agents to interact with the LLM service.
    """
    logger.info(f"Received LLM request from agent: {request.agent}")
    logger.info(f"Request details: model={request.model}, max_tokens={request.max_tokens}, temperature={request.temperature}")

    # Validate agent permissions
    if request.agent not in controller.agents:
        logger.error(f"Unknown agent tried to access LLM: {request.agent}")
        raise HTTPException(status_code=400, detail="Invalid agent")

    # Log prompt content at debug level to avoid cluttering logs
    logger.debug("Prompt content:")
    for line in request.prompt.split('\n'):
        if line.strip():
            logger.debug(f"  {line[:100]}..." if len(line) > 100 else f"  {line}")

    try:
        logger.info("Submitting request to LLM service")
        response = await llm_service.submit_request(request)

        if response.error:
            logger.error(f"LLM error response: {response.error}")
        else:
            logger.debug("LLM response content:")
            for line in response.response.split('\n'):
                if line.strip():
                    logger.debug(f"  {line}")

        return response

    except Exception as e:
        logger.error(f"Error processing LLM request: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/config/skip-list")
async def update_skip_list(request: SkipListUpdate):
    """Update the skip list configuration."""
    return controller.update_skip_list(request.skip_list)

@api_router.get("/config/ai-markers")
async def get_ai_markers():
    """Get the AI content markers configuration."""
    try:
        if not controller.config.has_section('agent_code_mon_readme'):
            return {
                "begin": "(BEGIN AI Generated)",
                "end": "(END AI Generated)"
            }
        return {
            "begin": controller.config.get('agent_code_mon_readme', 'ai_marker_begin', fallback='(BEGIN AI Generated)'),
            "end": controller.config.get('agent_code_mon_readme', 'ai_marker_end', fallback='(END AI Generated)')
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/config/ai-markers")
async def set_ai_markers(begin: str, end: str):
    """Set the AI content markers configuration."""
    try:
        if not controller.config.has_section('agent_code_mon_readme'):
            controller.config.add_section('agent_code_mon_readme')

        controller.config['agent_code_mon_readme']['ai_marker_begin'] = begin
        controller.config['agent_code_mon_readme']['ai_marker_end'] = end

        controller._save_config()

        return {"success": True, "begin": begin, "end": end}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Include the API router
app.include_router(api_router)

# Add WebSocket endpoint for log streaming
@app.websocket("/ws/logs")
async def websocket_logs(websocket: WebSocket):
    """Stream logs from all agents and controller via WebSocket."""
    tasks = []
    is_connected = False
    try:
        await websocket.accept()
        is_connected = True
        logger.info("New client connected to log stream")

        async def tail_log(file_path: Path):
            """Tail a log file and send updates via WebSocket."""
            nonlocal is_connected
            while is_connected:
                try:
                    # Wait for file to exist
                    while not file_path.exists() and is_connected:
                        await asyncio.sleep(1)
                        continue

                    if not is_connected:
                        return

                    async with aiofiles.open(file_path, 'r') as f:
                        # Seek to end initially
                        await f.seek(0, 2)

                        while is_connected:
                            try:
                                line = await f.readline()
                                if not line:
                                    # Check if file still exists (handle deletion)
                                    if not file_path.exists():
                                        break
                                    await asyncio.sleep(0.1)
                                    continue

                                if is_connected:
                                    await websocket.send_text(line.strip())
                            except WebSocketDisconnect:
                                return  # Client disconnected, exit gracefully
                            except Exception as e:
                                if is_connected:
                                    logger.error(f"Error sending log from {file_path}: {e}")
                                    await asyncio.sleep(1)  # Backoff on error
                                continue

                except FileNotFoundError:
                    # File was deleted, wait for recreation
                    logger.debug(f"Waiting for log file: {file_path}")
                    await asyncio.sleep(1)
                    continue
                except PermissionError:
                    logger.error(f"Permission denied reading log file: {file_path}")
                    await asyncio.sleep(5)  # Longer backoff for permission issues
                    continue
                except Exception as e:
                    logger.error(f"Error tailing log {file_path}: {e}")
                    await asyncio.sleep(1)  # Backoff on error
                    continue

        try:
            # Start tasks for each log file
            log_dir = Path('logs')
            log_dir.mkdir(exist_ok=True)

            # Send initial connection message
            if is_connected:
                await websocket.send_text(
                    f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - system - INFO - Connected to log stream"
                )

            # Controller log
            controller_log = log_dir / 'swarm_controller.log'
            tasks.append(asyncio.create_task(
                tail_log(controller_log),
                name=f"tail_{controller_log.name}"
            ))

            # Agent logs
            for agent_name in controller.agents:
                agent_log = log_dir / f'agent_{agent_name}.log'
                tasks.append(asyncio.create_task(
                    tail_log(agent_log),
                    name=f"tail_{agent_log.name}"
                ))

            logger.info(f"Started {len(tasks)} log tailing tasks")

            # Wait for all tasks to complete
            await asyncio.gather(*tasks, return_exceptions=True)

        except Exception as e:
            error_msg = f"Error in log streaming: {e}"
            logger.error(error_msg)
            if is_connected:
                try:
                    await websocket.send_text(
                        f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - system - ERROR - {error_msg}"
                    )
                except Exception:
                    pass  # Ignore send errors during shutdown

    except WebSocketDisconnect:
        logger.info("Client disconnected from log stream")
    except Exception as e:
        logger.error(f"Unexpected error in websocket handler: {e}")
    finally:
        is_connected = False
        
        # Clean up all tasks
        for task in tasks:
            if not task.done():
                task.cancel()
        
        # Wait for all tasks to complete cleanup
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        # Only try to close if we successfully connected
        if is_connected:
            try:
                await websocket.close()
            except Exception as e:
                logger.debug(f"Error closing websocket: {e}")  # Downgraded to debug since this is expected sometimes

        logger.info("Cleaned up all tasks and closed websocket")

def main():
    """Main entry point for the swarm controller."""
    try:
        # Start the FastAPI server
        uvicorn.run(app, host="0.0.0.0", port=8000)
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
