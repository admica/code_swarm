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
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from pathlib import Path
from typing import Optional, Dict, List, Tuple
from shared import LLMClient, config_manager, AgentLogger
import fnmatch

# Set up logging
logger = AgentLogger('code_mon_readme')

class CodeAnalyzer:
    """Analyzes code to extract documentation and structure."""

    def __init__(self):
        """Initialize the analyzer with LLM client."""
        self.llm_client = LLMClient('code_mon_readme')

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

class ReadmeGenerator:
    """Generates README.md files for modules."""

    def __init__(self):
        """Initialize the generator with a code analyzer."""
        self.analyzer = CodeAnalyzer()
        self.logger = AgentLogger('code_mon_readme')

    async def generate_readme(self, file_path: str, content: str) -> str:
        """Generate a complete README.md for a code file."""
        await self.logger.log_activity('analyzing', file_path)
        old_readme = None
        readme_path = f"{file_path}_README.md"

        if os.path.exists(readme_path):
            with open(readme_path, 'r') as f:
                old_readme = f.read()

        # Analyze the code
        info = self.analyzer.analyze_code(content)

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
        ai_summary = await self.analyzer.get_ai_analysis(info, old_readme)

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
            readme_content = await self.generate_readme(file_path, content)
            readme_path = f"{file_path}_README.md"

            # Verify we're not writing an empty or minimal readme
            if len(readme_content.strip().split('\n')) <= 3:  # Just title and overview header
                logger.warning("Generated README seems too minimal, skipping update")
                return

            with open(readme_path, 'w') as f:
                f.write(readme_content)

            logger.info(f"Updated README at {readme_path}")

        except Exception as e:
            logger.error(f"Error updating README: {e}")
            logger.exception("Full traceback:")

class PyFileHandler(FileSystemEventHandler):
    """Handles file modification events."""

    def __init__(self):
        """Initialize with a README generator."""
        self.generator = ReadmeGenerator()
        self.queue = asyncio.Queue()
        self._task: Optional[asyncio.Task] = None
        self.config = config_manager.get_agent_config('code_mon_readme')
        self.ignore_patterns = self.config.get('ignore_patterns', '').split(',')
        logger.info("File handler initialized")

    def should_ignore(self, file_path: str) -> bool:
        """Check if a file should be ignored based on patterns."""
        rel_path = os.path.relpath(file_path)
        return any(
            fnmatch.fnmatch(rel_path, pattern.strip())
            for pattern in self.ignore_patterns
            if pattern.strip()
        )

    def process_existing_files(self, path: str) -> None:
        """Process all existing code files in the directory that don't have READMEs."""
        for root, _, files in os.walk(path):
            for file in files:
                if not file.endswith('.py') and not file.endswith('.lua'):
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
                    asyncio.create_task(self.queue.put((file_path, content)))
                except Exception as e:
                    logger.error(f"Error processing existing file {file_path}: {e}")

    def on_modified(self, event) -> None:
        """Handle file modification events."""
        if event.is_directory:
            return

        file_path = event.src_path
        if not file_path.endswith('.py') and not file_path.endswith('.lua'):
            return

        if self.should_ignore(file_path):
            logger.debug(f"Ignoring modified file due to pattern match: {file_path}")
            return

        logger.info(f"Detected modification to {file_path}")

        try:
            with open(file_path, 'r') as f:
                content = f.read()

            # Add to queue for processing
            asyncio.create_task(self.queue.put((file_path, content)))

        except Exception as e:
            logger.error(f"Error processing file {file_path}: {e}")

    async def start_processing(self):
        """Start processing the file queue."""
        while True:
            try:
                file_path, content = await self.queue.get()
                try:
                    await self.generator.update_readme(file_path, content)
                except Exception as e:
                    logger.error(f"Error updating README for {file_path}: {e}")
                finally:
                    self.queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in queue processor: {e}")
                await asyncio.sleep(1)

    def start(self):
        """Start the queue processor."""
        if not self._task or self._task.done():
            self._task = asyncio.create_task(self.start_processing())

    def stop(self):
        """Stop the queue processor."""
        if self._task:
            self._task.cancel()

async def main(path: str) -> None:
    """Main function to run the README generator agent."""
    try:
        event_handler = PyFileHandler()
        event_handler.start()

        # Process existing files before starting the watcher
        logger.info("Processing existing files...")
        event_handler.process_existing_files(path)

        observer = Observer()
        observer.schedule(event_handler, path, recursive=True)
        observer.start()

        logger.info(f"Started monitoring directory: {path}")

        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("Received shutdown signal")
            observer.stop()
            event_handler.stop()
        observer.join()

    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        logger.error("Please provide the directory path to monitor")
        sys.exit(1)

    path = sys.argv[1]
    asyncio.run(main(path))
