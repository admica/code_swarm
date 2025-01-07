#!/usr/bin/env python3
"""Shared LLM client for Code Swarm."""

import logging
import asyncio
import aiohttp
from typing import Optional, Dict, Any
from datetime import datetime
from .config import config_manager

logger = logging.getLogger(__name__)

class LLMError(Exception):
    """Raised when there's an error with LLM operations."""
    pass

class LLMClient:
    """Client for interacting with LLM service through the controller."""
    
    def __init__(self, agent_name: str):
        self.agent_name = agent_name
        self.config = config_manager.get_agent_config(agent_name)
        self.controller_url = self.config.get('controller_url', 'http://localhost:8000/api')
        self.model = self.config.get('ollama_model', 'llama3.2')
        self.max_retries = 3
        self.retry_delay = 1.0  # seconds
        self.timeout = 60  # seconds
    
    async def _check_health(self) -> bool:
        """Check if LLM service is healthy."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.controller_url}/llm/health",
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    return response.status == 200
        except Exception as e:
            logger.error(f"LLM health check failed: {e}")
            return False
    
    async def generate(
        self,
        prompt: str,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None
    ) -> Optional[Dict[str, Any]]:
        """Generate content using LLM.
        
        Args:
            prompt: The prompt to send to the LLM
            max_tokens: Maximum tokens to generate
            temperature: Temperature for generation
            
        Returns:
            Dictionary containing the response or None on failure
        """
        if not await self._check_health():
            raise LLMError("LLM service is not healthy")
        
        request = {
            "prompt": prompt,
            "model": self.model,
            "agent": f"agent_{self.agent_name}",
            "max_tokens": max_tokens,
            "temperature": temperature
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.controller_url}/llm/generate",
                    json=request,
                    timeout=aiohttp.ClientTimeout(total=self.timeout)
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        return result
                    else:
                        raise LLMError(f"LLM request failed with status {response.status}")
        except Exception as e:
            logger.error(f"Error in LLM request: {e}")
            return None
    
    async def analyze_code(
        self,
        old_content: str,
        new_content: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """Analyze code changes using LLM.
        
        Args:
            old_content: Previous version of the code
            new_content: New version of the code
            context: Additional context for the analysis
            
        Returns:
            Analysis text or None on failure
        """
        context_str = f"\nAdditional context:\n{context}" if context else ""
        prompt = f"Analyze these code changes:\n\nPrevious version:\n{old_content}\n\nNew version:\n{new_content}{context_str}\n\nPlease provide:\n1. A summary of the main changes\n2. Potential impact on the codebase\n3. Any suggestions for improvement\nKeep the response focused and under 200 words."

        try:
            result = await self.generate(
                prompt=prompt,
                temperature=0.7
            )
            return result.get('response') if result else None
        except LLMError as e:
            logger.error(f"Failed to analyze code: {e}")
            return None
    
    async def generate_documentation(
        self,
        content: str,
        doc_type: str = 'readme',
        existing_doc: Optional[str] = None
    ) -> Optional[str]:
        """Generate documentation using LLM.
        
        Args:
            content: Code content to document
            doc_type: Type of documentation ('readme', 'changelog', etc.)
            existing_doc: Existing documentation to update
            
        Returns:
            Generated documentation or None on failure
        """
        existing_doc_str = f"\nExisting documentation to update:\n{existing_doc}" if existing_doc else ""
        prompt = f"Generate {doc_type} documentation for this code:\n\n{content}{existing_doc_str}\n\nPlease provide:\n1. Clear overview of the code's purpose\n2. Key features and functionality\n3. Usage examples if applicable\nKeep the documentation clear and concise."

        try:
            result = await self.generate(
                prompt=prompt,
                temperature=0.7
            )
            return result.get('response') if result else None
        except LLMError as e:
            logger.error(f"Failed to generate documentation: {e}")
            return None 