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
from typing import Dict, Optional, List
import psutil
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
from pathlib import Path

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

class SwarmController:
    """Controls and monitors code_swarm agents."""

    def __init__(self):
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

    def start_agent(self, agent_name: str, path: str) -> AgentStatus:
        """Start a specific agent."""
        if agent_name not in self.agents:
            raise ValueError(f"Unknown agent: {agent_name}")

        agent = self.agents[agent_name]
        
        if agent["process"] and agent["process"].poll() is None:
            logger.warning(f"Agent {agent_name} is already running")
            return agent["status"]

        try:
            # Start the agent process
            process = subprocess.Popen(
                [sys.executable, agent["script"], path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            agent["process"] = process
            agent["status"].pid = process.pid
            agent["status"].running = True
            agent["status"].monitor_path = path
            agent["status"].last_error = None
            
            logger.info(f"Started agent {agent_name} with PID {process.pid}")
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
            raise ValueError(f"Unknown agent: {agent_name}")

        agent = self.agents[agent_name]
        
        if agent["process"]:
            try:
                process = psutil.Process(agent["process"].pid)
                for child in process.children(recursive=True):
                    child.terminate()
                process.terminate()
                process.wait(timeout=5)
                
                agent["process"] = None
                agent["status"].pid = None
                agent["status"].running = False
                
                logger.info(f"Stopped agent {agent_name}")
                
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

# Initialize FastAPI app
app = FastAPI(title="Code Swarm Controller", version="1.0.0")
controller = SwarmController()

@app.post("/agents/{agent_name}/start")
async def start_agent(agent_name: str, path: str):
    """Start a specific agent."""
    try:
        return controller.start_agent(agent_name, path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/agents/{agent_name}/stop")
async def stop_agent(agent_name: str):
    """Stop a specific agent."""
    try:
        return controller.stop_agent(agent_name)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/agents/{agent_name}/status")
async def get_agent_status(agent_name: str):
    """Get status of a specific agent."""
    try:
        return controller.get_agent_status(agent_name)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/agents/{agent_name}/logs")
async def get_agent_logs(agent_name: str, lines: int = 100):
    """Get recent logs for a specific agent."""
    try:
        return controller.read_agent_logs(agent_name, lines)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/agents")
async def get_all_statuses():
    """Get status of all agents."""
    return controller.get_all_statuses()

@app.post("/agents/start-all")
async def start_all_agents(path: str):
    """Start all agents."""
    return controller.start_all(path)

@app.post("/agents/stop-all")
async def stop_all_agents():
    """Stop all agents."""
    return controller.stop_all()

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
