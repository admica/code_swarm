#!/usr/bin/env python3
# PATH: ./agent_swarm_controller.py
"""
Swarm Controller - Manages code_swarm agents and provides API endpoints
"""
import os
import sys
import subprocess
import logging
import json
from typing import Dict, Optional, List, Set
import psutil
from fastapi import FastAPI, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
from pathlib import Path
import asyncio
import time
import aiohttp
import requests  # Keep for sync health checks
from datetime import datetime
import configparser
from contextlib import asynccontextmanager

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('swarm_controller.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('swarm_controller')

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
        """Make actual request to Ollama."""
        if not self.session:
            logger.error("No HTTP session available")
            raise Exception("LLM service not properly initialized")
            
        try:
            logger.debug(f"Sending request to Ollama: {self.ollama_url}/api/generate")
            async with self.session.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": request.model,
                    "prompt": request.prompt,
                    "stream": False
                },
                timeout=aiohttp.ClientTimeout(total=self.timeout)
            ) as response:
                logger.debug(f"Ollama response status: {response.status}")
                response.raise_for_status()
                result = await response.json()
                logger.debug("Successfully parsed Ollama response")
                logger.debug("Ollama response content:")
                if result.get('response'):
                    for line in result['response'].split('\n'):
                        if line.strip():
                            logger.debug(f"  {line}")
                return result.get('response', '')
            
        except aiohttp.ClientError as e:
            logger.error(f"Ollama request failed: {str(e)}")
            raise Exception(f"Ollama service error: {str(e)}")

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
    """General information about the controller state."""
    version: str
    monitor_path: Optional[str]
    agents_status: Dict[str, AgentStatus]
    llm_metrics: Dict

class SwarmController:
    """Controls and monitors code_swarm agents."""

    def __init__(self):
        self.config = configparser.ConfigParser()
        self.config_path = 'config.ini'
        self.monitor_path = None
        self._load_config()
        
        self.agents = {
            "changelog": {
                "script": "agent_code_mon_changelog.py",
                "process": None,
                "status": AgentStatus(
                    name="changelog",
                    pid=None,
                    running=False,
                    monitor_path=None,
                    last_error=None
                )
            },
            "readme": {
                "script": "agent_code_mon_readme.py",
                "process": None,
                "status": AgentStatus(
                    name="readme",
                    pid=None,
                    running=False,
                    monitor_path=None,
                    last_error=None
                )
            },
            "deps": {
                "script": "agent_code_mon_deps.py",
                "process": None,
                "status": AgentStatus(
                    name="deps",
                    pid=None,
                    running=False,
                    monitor_path=None,
                    last_error=None
                )
            }
        }
        self.monitor_task = None

    def _load_config(self) -> None:
        """Load configuration from file."""
        if not os.path.exists(self.config_path):
            self._create_default_config()
        
        self.config.read(self.config_path)
        self.monitor_path = self.config.get('swarm_controller', 'monitor_path', fallback=None)

    def _create_default_config(self) -> None:
        """Create default configuration."""
        self.config['swarm_controller'] = {
            'monitor_path': '',
            'host': '0.0.0.0',
            'port': '8000'
        }
        self._save_config()

    def _save_config(self) -> None:
        """Save current configuration to file."""
        with open(self.config_path, 'w') as f:
            self.config.write(f)

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

    def get_info(self) -> ControllerInfo:
        """Get general controller information."""
        return ControllerInfo(
            version="1.0.0",
            monitor_path=self.monitor_path,
            agents_status=self.get_all_statuses(),
            llm_metrics=llm_service.get_metrics()
        )

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
            logger.debug(f"Agent script: {agent['script']}")
            
            # Start the agent process
            process = subprocess.Popen(
                [sys.executable, agent["script"], monitor_path],
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
                            # Broadcast status change
                            await manager.broadcast({
                                "type": "agent_update",
                                "data": agent["status"].dict()
                            })
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        if agent["status"].running:
                            agent["status"].running = False
                            agent["status"].pid = None
                            agent["process"] = None
                            # Broadcast status change
                            await manager.broadcast({
                                "type": "agent_update",
                                "data": agent["status"].dict()
                            })
            await asyncio.sleep(1)  # Check every second

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

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Error broadcasting to WebSocket: {e}")
                # Remove failed connections
                self.active_connections.remove(connection)

manager = ConnectionManager()

# Move WebSocket endpoint to root level (not under /api)
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Wait for messages but primarily use this for sending updates
            data = await websocket.receive_text()
            # You can handle incoming messages here if needed
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)

# Move all endpoints to API router
@api_router.post("/config/monitor-path")
async def set_monitor_path(path: str):
    """Set the directory path to monitor."""
    return controller.set_monitor_path(path)

@api_router.get("/info")
async def get_controller_info():
    """Get general controller information."""
    return controller.get_info()

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
        await manager.broadcast({
            "type": "agent_update",
            "data": status.dict()
        })
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
        await manager.broadcast({
            "type": "agent_update",
            "data": status.dict()
        })
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
    for agent_name, status in statuses.items():
        await manager.broadcast({
            "type": "agent_update",
            "data": status.dict()
        })
    return statuses

@api_router.post("/agents/stop-all")
async def stop_all_agents():
    """Stop all agents."""
    statuses = controller.stop_all()
    for agent_name, status in statuses.items():
        await manager.broadcast({
            "type": "agent_update",
            "data": status.dict()
        })
    return statuses

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

# Add LLM endpoints
@api_router.post("/llm/readme/generate")
async def generate_readme_content(request: LLMRequest) -> LLMResponse:
    """Generate content for README files."""
    logger.info(f"Received README generation request from agent: {request.agent}")
    logger.info(f"Request details: model={request.model}, max_tokens={request.max_tokens}, temperature={request.temperature}")
    logger.info("Prompt content:")
    for line in request.prompt.split('\n'):
        if line.strip():  # Only log non-empty lines
            logger.info(f"  {line[:100]}..." if len(line) > 100 else f"  {line}")
            
    if request.agent != "readme":
        logger.error(f"Invalid agent tried to use readme endpoint: {request.agent}")
        raise HTTPException(status_code=400, detail="Invalid agent for this endpoint")
        
    logger.info("Submitting request to LLM service")
    response = await llm_service.submit_request(request)
    
    if response.error:
        logger.error(f"LLM error response: {response.error}")
    else:
        logger.info("LLM response content:")
        for line in response.response.split('\n'):
            if line.strip():
                logger.info(f"  {line}")
    
    return response

@api_router.post("/llm/changelog/generate")
async def generate_changelog_content(request: LLMRequest) -> LLMResponse:
    """Generate content for changelog entries."""
    logger.info(f"Received changelog generation request from agent: {request.agent}")
    logger.info(f"Request details: model={request.model}, max_tokens={request.max_tokens}, temperature={request.temperature}")
    logger.info("Prompt content:")
    for line in request.prompt.split('\n'):
        if line.strip():
            logger.info(f"  {line[:100]}..." if len(line) > 100 else f"  {line}")
            
    if request.agent != "changelog":
        logger.error(f"Invalid agent tried to use changelog endpoint: {request.agent}")
        raise HTTPException(status_code=400, detail="Invalid agent for this endpoint")
        
    logger.info("Submitting request to LLM service")
    response = await llm_service.submit_request(request)
    
    if response.error:
        logger.error(f"LLM error response: {response.error}")
    else:
        logger.info("LLM response content:")
        for line in response.response.split('\n'):
            if line.strip():
                logger.info(f"  {line}")
    
    return response

@api_router.post("/llm/deps/analyze")
async def analyze_dependencies(request: LLMRequest) -> LLMResponse:
    """Analyze code dependencies using LLM."""
    logger.info(f"Received dependency analysis request from agent: {request.agent}")
    logger.info(f"Request details: model={request.model}, max_tokens={request.max_tokens}, temperature={request.temperature}")
    logger.info("Prompt content:")
    for line in request.prompt.split('\n'):
        if line.strip():
            logger.info(f"  {line[:100]}..." if len(line) > 100 else f"  {line}")
            
    if request.agent != "deps":
        logger.error(f"Invalid agent tried to use deps endpoint: {request.agent}")
        raise HTTPException(status_code=400, detail="Invalid agent for this endpoint")
        
    logger.info("Submitting request to LLM service")
    response = await llm_service.submit_request(request)
    
    if response.error:
        logger.error(f"LLM error response: {response.error}")
    else:
        logger.info("LLM response content:")
        for line in response.response.split('\n'):
            if line.strip():
                logger.info(f"  {line}")
    
    return response

# Include the API router
app.include_router(api_router)

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
