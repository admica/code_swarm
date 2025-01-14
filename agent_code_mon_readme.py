#!/usr/bin/env python3
# PATH: ./agent_code_mon_readme.py
"""
Agent that automatically generates and maintains README files for Python and Lua modules.
"""
import sys
import time
import os
import logging
import ast
import asyncio
from pathlib import Path
from typing import Optional, Dict, List, Tuple
from shared import LLMClient, config_manager, AgentLogger
from shared.base_agent import BaseAgent
from shared.file_monitor import FileMonitor
import fnmatch
import json
from datetime import datetime
import websockets

# Set up logging
logger = AgentLogger('code_mon_readme')

class ReadmeAgent(BaseAgent):
    """Agent that generates and maintains README files."""

    def __init__(self, root_path: str):
        """Initialize the readme agent.

        Args:
            root_path: Root directory to monitor
        """
        super().__init__('code_mon_readme')
        self.root_path = root_path
        self.llm_client = LLMClient('code_mon_readme')
        self.config = config_manager.get_agent_config('code_mon_readme')
        self.running = False  # Start as not running
        self.queue = asyncio.Queue()
        self._task = None
        self.file_monitor = None
        self.last_error = None
        self.monitor_path = None
        self._is_connected = False  # Track connection state

    @property
    def is_connected(self):
        """Check if the agent is currently connected."""
        return self._is_connected and self.ws_agent is not None

    async def connect(self):
        """Connect to the controller via WebSocket."""
        success = await super().connect()
        self._is_connected = success
        return success

    async def disconnect(self):
        """Disconnect from the controller."""
        await super().disconnect()
        self._is_connected = False

    async def cleanup_connection(self):
        """Clean up the WebSocket connection."""
        await self.disconnect()
        self._is_connected = False

    async def ensure_connection(self):
        """Ensure WebSocket connections are active."""
        if not self.is_connected:
            success = await self.connect()
            self._is_connected = success
            return success
        return True

    def extract_docstring(self, node: ast.AST) -> str:
        """Extract docstring from an AST node."""
        if not (isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef)) and 
                ast.get_docstring(node)):
            return ""
        return ast.get_docstring(node) or ""

    def analyze_code(self, content: str) -> Dict[str, any]:
        """Analyze code and extract key information."""
        try:
            tree = ast.parse(content)

            # Extract module-level information
            module_info = {
                'docstring': self.extract_docstring(tree),
                'classes': [],
                'functions': [],
                'imports': []
            }

            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    class_info = {
                        'name': node.name,
                        'docstring': self.extract_docstring(node),
                        'methods': []
                    }

                    for subnode in node.body:
                        if isinstance(subnode, ast.FunctionDef):
                            method_info = {
                                'name': subnode.name,
                                'docstring': self.extract_docstring(subnode),
                                'args': [arg.arg for arg in subnode.args.args if arg.arg != 'self']
                            }
                            class_info['methods'].append(method_info)

                    module_info['classes'].append(class_info)

                elif isinstance(node, ast.FunctionDef) and node.name != '__init__':
                    function_info = {
                        'name': node.name,
                        'docstring': self.extract_docstring(node),
                        'args': [arg.arg for arg in node.args.args]
                    }
                    module_info['functions'].append(function_info)

                elif isinstance(node, (ast.Import, ast.ImportFrom)):
                    if isinstance(node, ast.Import):
                        for name in node.names:
                            module_info['imports'].append(name.name)
                    else:
                        module = node.module or ''
                        for name in node.names:
                            module_info['imports'].append(f"{module}.{name.name}")

            return module_info

        except SyntaxError as e:
            logger.error(f"Syntax error in code: {e}")
            return {}
        except Exception as e:
            logger.error(f"Error analyzing code: {e}")
            return {}

    async def get_ai_analysis(self, code_info: Dict[str, any], old_content: Optional[str] = None) -> Optional[str]:
        """Get AI analysis of the code using LLM.

        Args:
            code_info: Analyzed code information (from analyze_code)
        """
        try:
            # Extract just the essential information for the overview
            overview = {
                'docstring': code_info.get('docstring', '').strip(),
                'classes': [{'name': c['name'], 
                           'docstring': c['docstring'].split('.')[0] if c['docstring'] else '',  # Just first sentence
                           'methods': [m['name'] for m in c.get('methods', [])]} 
                          for c in code_info.get('classes', [])],
                'functions': [{'name': f['name'],
                             'docstring': f['docstring'].split('.')[0] if f['docstring'] else ''}
                            for f in code_info.get('functions', [])]
            }

            # Build a concise prompt
            prompt = f"""Analyze this module and generate a README overview:

Module Purpose:
{overview['docstring'] or 'No module docstring available.'}

Classes:
{chr(10).join(f'- {c["name"]}: {c["docstring"]}' for c in overview['classes']) if overview['classes'] else 'None'}

Functions:
{chr(10).join(f'- {f["name"]}: {f["docstring"]}' for f in overview['functions']) if overview['functions'] else 'None'}

Please provide:
1. A clear, concise overview of the module's purpose
2. Key features and functionality
3. Any notable implementation details
Keep the response focused and under 250 words."""

            result = await self.llm_client.generate(
                prompt=prompt,
                max_tokens=1100,
                temperature=0.6
            )

            if result and result.get('response'):
                # Get the response without any markers that might have been included
                ai_response = result['response'].strip()
                ai_response = ai_response.replace('(BEGIN AI Generated)', '')
                ai_response = ai_response.replace('(END AI Generated)', '')
                ai_response = ai_response.strip()

                # Add the markers properly
                return f"(BEGIN AI Generated)\n{ai_response}\n(END AI Generated)"

            return None

        except Exception as e:
            logger.error(f"Unexpected error in AI analysis: {e}")
            return None

    async def generate_readme(self, file_path: str, content: str) -> str:
        """Generate a complete README.md for a code file."""
        await self.logger.log_activity('analyzing', file_path)
        old_readme = None
        readme_path = f"{file_path}_README.md"

        if os.path.exists(readme_path):
            with open(readme_path, 'r') as f:
                old_readme = f.read()

        # Analyze the code
        info = self.analyze_code(content)

        await self.logger.log_activity('generating README for', file_path)

        # Start with file name
        readme = f"# {os.path.basename(file_path)}\n\n"

        # Overview section
        readme += "## Overview\n\n"

        # Add docstring if available
        if info.get('docstring'):
            docstring = info['docstring'].strip()
            readme += f"{docstring}\n\n"

        # Get AI summary and generated content
        ai_summary = await self.get_ai_analysis(info, old_readme)

        # If we have an old readme, preserve non-AI content
        if old_readme and "## Overview" in old_readme:
            try:
                overview_content = old_readme.split("## Overview")[1].split("##")[0].strip()
                if overview_content:
                    # Keep any content outside AI markers
                    parts = overview_content.split("(BEGIN AI Generated)")
                    if len(parts) > 1:
                        # Add any content before AI section
                        if parts[0].strip():
                            readme += f"{parts[0].strip()}\n\n"
                    else:
                        # No AI markers found, treat as manual content
                        readme += f"{overview_content}\n\n"
            except Exception as e:
                logger.warning(f"Error extracting old overview: {e}")

        # Add AI-generated content
        if ai_summary:
            # Extract the content between markers
            ai_content = ai_summary.split("(BEGIN AI Generated)")[1].split("(END AI Generated)")[0].strip()

            # Start AI section
            readme += "(BEGIN AI Generated)\n"

            # Add AI summary
            readme += ai_content + "\n\n"

            # Add classes section within AI markers
            class_section = self.generate_class_section(info.get('classes', []))
            if class_section:
                readme += class_section

            # End AI section
            readme += "(END AI Generated)\n"
        else:
            # If no AI content, add classes section without markers
            class_section = self.generate_class_section(info.get('classes', []))
            if class_section:
                readme += class_section

        return readme

    def generate_class_section(self, classes: List[Dict]) -> str:
        """Generate documentation for classes."""
        if not classes:
            return ""

        section = "\n## Classes\n\n"
        for cls in classes:
            section += f"### `{cls['name']}`\n\n"
            if cls['docstring']:
                section += f"{cls['docstring'].strip()}\n\n"

            if cls['methods']:
                section += "#### Methods\n\n"
                for method in cls['methods']:
                    args_str = ", ".join(method['args'])
                    section += f"- `{method['name']}({args_str})`"
                    if method['docstring']:
                        section += f": {method['docstring'].split('.')[0]}."
                    section += "\n"
                section += "\n"
        return section

    async def update_readme(self, file_path: str, content: str) -> None:
        """Generate and write README.md file."""
        try:
            # Report start of analysis
            await self.send_activity('analyzing', file_path, {
                'stage': 'started',
                'file_type': os.path.splitext(file_path)[1]
            })

            readme_content = await self.generate_readme(file_path, content)
            readme_path = f"{file_path}_README.md"

            # Verify we're not writing an empty or minimal readme
            if len(readme_content.strip().split('\n')) <= 3:  # Just title and overview header
                logger.warning("Generated README seems too minimal, skipping update")
                await self.send_activity('skipped', file_path, {'reason': 'minimal_content'})
                return

            # Report generation complete
            await self.send_activity('analyzing', file_path, {
                'stage': 'generated',
                'content_length': len(readme_content)
            })

            with open(readme_path, 'w') as f:
                f.write(readme_content)

            # Report successful update with details
            await self.send_activity('updated', readme_path, {
                'status': 'success',
                'size': len(readme_content),
                'sections': readme_content.count('##'),
                'has_ai_content': '(BEGIN AI Generated)' in readme_content
            })
            logger.info(f"Updated README at {readme_path}")

        except Exception as e:
            # Report error with details
            error_details = {
                'error': str(e),
                'stage': 'unknown',
                'file_path': file_path
            }
            if 'readme_path' in locals():
                error_details['readme_path'] = readme_path
            await self.send_activity('error', file_path, error_details)
            self.last_error = str(e)
            logger.error(f"Error updating README: {e}")
            logger.exception("Full traceback:")

    def get_status(self) -> dict:
        """Get current agent status for controller."""
        return {
            'status': 'running' if self.running else 'stopped',
            'root_path': self.root_path,
            'queue_size': self.queue.qsize() if hasattr(self, 'queue') else 0,
            'last_error': getattr(self, 'last_error', None),
            'monitor_active': self.file_monitor is not None and self.file_monitor.is_running(),
            'processor_active': self._task is not None and not self._task.done() if self._task else False,
            'config': {
                'ignore_patterns': self.config.get('ignore_patterns', '').split(','),
                'file_types': ['.py', '.lua']
            }
        }

    async def handle_controller_message(self, message: dict):
        """Handle messages from the controller."""
        await super().handle_controller_message(message)

        try:
            msg_type = message.get('type')
            data = message.get('data', {})

            if msg_type == 'analyze_file':
                file_path = data.get('path')
                if file_path and os.path.exists(file_path):
                    await self.send_activity('received_request', file_path, {'type': 'analyze_file'})
                    with open(file_path, 'r') as f:
                        content = f.read()
                    await self.update_readme(file_path, content)

            elif msg_type == 'process_directory':
                path = data.get('path')
                if path:
                    await self.send_activity('received_request', path, {'type': 'process_directory'})
                    await self.process_existing_files(path)

            elif msg_type == 'update_config':
                # Handle configuration updates
                if 'ignore_patterns' in data:
                    self.config['ignore_patterns'] = data['ignore_patterns']
                    await self.send_activity('config_updated', '', {'config': self.config})

            elif msg_type == 'clear_queue':
                # Clear the processing queue
                while not self.queue.empty():
                    try:
                        self.queue.get_nowait()
                        self.queue.task_done()
                    except asyncio.QueueEmpty:
                        break
                await self.send_activity('queue_cleared', '', {'queue_size': 0})

        except Exception as e:
            self.last_error = str(e)
            await self.send_activity('error', '', {
                'error': str(e),
                'message_type': msg_type,
                'message_data': data
            })
            logger.error(f"Error handling controller message: {e}")

    async def process_file(self, file_path: str, content: str) -> None:
        """Process a single file."""
        try:
            if self.should_ignore(file_path):
                logger.debug(f"Ignoring file due to pattern match: {file_path}")
                return

            await self.update_readme(file_path, content)
        except Exception as e:
            self.last_error = str(e)
            logger.error(f"Error processing file {file_path}: {e}")

    async def on_file_modified(self, file_path: str) -> None:
        """Handle file modification events."""
        try:
            if self.should_ignore(file_path):
                logger.debug(f"Ignoring modified file due to pattern match: {file_path}")
                return

            logger.info(f"Detected modification to {file_path}")

            try:
                with open(file_path, 'r') as f:
                    content = f.read()

                # Add to queue for processing
                await self.queue.put((file_path, content))

            except Exception as e:
                logger.error(f"Error processing file {file_path}: {e}")
                self.last_error = str(e)

        except Exception as e:
            logger.error(f"Error in file modification handler: {e}")
            self.last_error = str(e)

    def should_ignore(self, file_path: str) -> bool:
        """Check if a file should be ignored based on patterns."""
        rel_path = os.path.relpath(file_path)
        return any(
            fnmatch.fnmatch(rel_path, pattern.strip())
            for pattern in self.config.get('ignore_patterns', '').split(',')
            if pattern.strip()
        )

    async def process_existing_files(self, path: str) -> None:
        """Process all existing code files in the directory that don't have READMEs."""
        for root, _, files in os.walk(path):
            for file in files:
                if not (file.endswith('.py') or file.endswith('.lua')):
                    continue

                file_path = os.path.join(root, file)
                if self.should_ignore(file_path):
                    logger.debug(f"Ignoring file due to pattern match: {file_path}")
                    continue

                readme_path = f"{file_path}_README.md"

                if os.path.exists(readme_path):
                    continue

                logger.info(f"Processing existing file: {file_path}")
                try:
                    with open(file_path, 'r') as f:
                        content = f.read()

                    # Add to queue for processing
                    await self.queue.put((file_path, content))
                except Exception as e:
                    logger.error(f"Error processing existing file {file_path}: {e}")
                    self.last_error = str(e)

    async def start_processing(self):
        """Start processing the file queue."""
        last_update = 0
        update_delay = 2.0  # Minimum time between updates
        batch_window = 2.0  # Time window to batch changes
        pending_files = {}  # Track pending files and their latest content

        while True:
            try:
                # Get the next file from queue
                file_path, content = await self.queue.get()

                # Update pending files
                pending_files[file_path] = content

                # Apply debouncing
                now = time.time()
                if now - last_update < update_delay:
                    self.queue.task_done()
                    continue

                # Wait for batch window to collect more changes
                try:
                    while True:
                        if time.time() - now >= batch_window:
                            break
                        try:
                            next_file, next_content = await asyncio.wait_for(
                                self.queue.get(),
                                timeout=batch_window - (time.time() - now)
                            )
                            pending_files[next_file] = next_content
                            self.queue.task_done()
                        except asyncio.TimeoutError:
                            break
                except Exception as e:
                    logger.error(f"Error in batch collection: {e}")

                # Process all pending files
                for file_path, content in pending_files.items():
                    try:
                        await self.update_readme(file_path, content)
                    except Exception as e:
                        logger.error(f"Error updating README for {file_path}: {e}")

                # Clear pending files and update timestamp
                pending_files.clear()
                last_update = time.time()
                self.queue.task_done()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in queue processor: {e}")
                await asyncio.sleep(1)
                if self.queue.qsize() > 0:
                    self.queue.task_done()  # Prevent queue from growing indefinitely on errors

    async def start(self, path: str):
        """Start the agent with monitoring and WebSocket communication."""
        if not self.running:
            self.running = True

            # Initialize file monitor with async callback wrapper
            self.monitor_path = path
            async def async_callback(file_path):
                await self.on_file_modified(file_path)
            self.file_monitor = FileMonitor('code_mon_readme', lambda fp: asyncio.create_task(async_callback(fp)))
            self.file_monitor.start(path)

            # Start queue processor if needed
            if not self._task or self._task.done():
                self._task = asyncio.create_task(self.start_processing())

            # Process existing files
            logger.info("Processing existing files...")
            await self.process_existing_files(path)

            logger.info(f"Started monitoring directory: {path}")

            # Run both the queue processor and WebSocket handler concurrently
            try:
                await asyncio.gather(
                    self.run(),  # WebSocket handler
                    self._task   # Queue processor
                )
            except asyncio.CancelledError:
                logger.info("Agent tasks cancelled")
                raise
            except Exception as e:
                logger.error(f"Error in agent tasks: {e}")
                raise

    async def stop(self):
        """Stop the agent and cleanup."""
        logger.info("Stopping readme agent...")
        self.running = False

        # Stop the queue processor
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

        # Stop file monitoring
        if self.file_monitor:
            self.file_monitor.stop()
            self.file_monitor = None

        # Clean up state
        self.monitor_path = None

        # Disconnect WebSockets
        await self.disconnect()
        logger.info("Readme agent stopped")

async def main(path: str) -> None:
    """Main function to run the README generator agent."""
    agent = None
    try:
        agent = ReadmeAgent(path)
        await agent.start(path)  # This will run until the agent is stopped
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        if agent:
            await agent.stop()
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        logger.error("Please provide the directory path to monitor")
        sys.exit(1)

    path = sys.argv[1]
    asyncio.run(main(path))
