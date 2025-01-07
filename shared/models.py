from datetime import datetime
from typing import Dict, List, Optional, Any
from pydantic import BaseModel

class AgentStatus(BaseModel):
    name: str
    pid: Optional[int]
    running: bool
    monitor_path: Optional[str]
    last_error: Optional[str]

    def dict(self, *args, **kwargs):
        d = super().dict(*args, **kwargs)
        # Convert None to empty string for JSON serialization
        for k, v in d.items():
            if v is None:
                d[k] = ""
        return d

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

class LLMStatus(BaseModel):
    """Status information about the LLM service."""
    available: bool
    model: Optional[str]
    error: Optional[str]
    models: Optional[List[str]]
    response_time: Optional[float]

class ControllerInfo(BaseModel):
    """Information about the controller configuration and status."""
    monitor_path: Optional[str]
    skip_list: List[str]
    ollama_available: bool
    ollama_model: Optional[str] 