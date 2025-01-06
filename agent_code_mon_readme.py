#!/usr/bin/env python3
# PATH: ./agent_code_mon_readme.py
"""
Agent that automatically generates and maintains README files for Python modules.
"""
import sys
import time
import os
import logging
import ast
import configparser
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from pathlib import Path
import requests
from typing import Optional, Dict, List, Tuple

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('agent_code_mon_readme.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('agent_code_mon_readme')

class ConfigManager:
    """Manages configuration for the README generator agent."""
    
    def __init__(self, config_path: str = 'config.ini'):
        self.config = configparser.ConfigParser()
        self.config_path = config_path
        self.load_config()

    def load_config(self) -> None:
        """Load configuration from config.ini file."""
        if not os.path.exists(self.config_path):
            logger.warning(f"Config file not found at {self.config_path}. Creating default configuration.")
            self.create_default_config()
        
        try:
            self.config.read(self.config_path)
        except configparser.Error as e:
            logger.error(f"Error reading config file: {e}")
            raise

    def create_default_config(self) -> None:
        """Create default configuration file."""
        self.config['agent_code_mon_readme'] = {
            'ollama_model': 'llama3.2',
            'controller_url': 'http://localhost:8000',
            'watch_patterns': '*.py',
            'ignore_patterns': '__pycache__/*,.*,test_*',
            'readme_sections': 'overview,functions,classes,dependencies,usage',
        }
        
        with open(self.config_path, 'w') as f:
            self.config.write(f)

    def get_config(self) -> Dict[str, str]:
        """Get configuration dictionary."""
        return self.config['agent_code_mon_readme']

class PythonCodeAnalyzer:
    """Analyzes Python code to extract documentation and structure."""

    def __init__(self, config: Dict[str, str]):
        """Initialize the analyzer with configuration."""
        self.config = config
        self.controller_url = config.get('controller_url', 'http://localhost:8000')
        self.ollama_model = config.get('ollama_model', 'llama3.2')

    def extract_docstring(self, node: ast.AST) -> str:
        """Extract docstring from an AST node."""
        if not (isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef)) and 
                ast.get_docstring(node)):
            return ""
        return ast.get_docstring(node) or ""

    def analyze_code(self, content: str) -> Dict[str, any]:
        """Analyze Python code and extract key information."""
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
            logger.error(f"Syntax error in Python code: {e}")
            return {}
        except Exception as e:
            logger.error(f"Error analyzing Python code: {e}")
            return {}

    def get_ai_summary(self, content: str, old_readme: Optional[str] = None) -> Optional[str]:
        """Get AI-generated summary of the code changes using the controller's LLM service."""
        try:
            # First analyze the code to extract essential information
            info = self.analyze_code(content)
            
            # Build a concise representation
            code_summary = f"""Module: {info.get('docstring', 'No module docstring')}

Classes:
{self._format_classes_for_summary(info.get('classes', []))}

Functions:
{self._format_functions_for_summary(info.get('functions', []))}"""

            context = f"Previous README:\n{old_readme}\n\n" if old_readme else ""
            prompt = f"""{context}You are writing the overview section of a README.md file. Based on this Python code structure, write 2-3 clear sentences that explain:
1. What this module does (its main purpose)
2. How someone would use it

{code_summary}

Keep it simple and direct. Focus only on the practical purpose and usage. Avoid technical details unless essential."""

            logger.info("Sending request to controller's LLM service")
            response = requests.post(
                f"{self.controller_url}/llm/readme/generate",
                json={
                    "prompt": prompt,
                    "model": self.ollama_model,
                    "agent": "readme"
                },
                timeout=30
            )
            
            if response.status_code == 404:
                logger.warning("Controller LLM endpoint not found")
                return None
                
            response.raise_for_status()
            result = response.json()
            
            if result.get('error'):
                logger.warning(f"LLM error: {result['error']}")
                return None
                
            return result.get('response')
            
        except requests.exceptions.RequestException as e:
            logger.warning(f"Controller service error: {e}")
            return None
        except Exception as e:
            logger.error(f"Error getting AI summary: {e}")
            return None

    def _format_classes_for_summary(self, classes: List[Dict]) -> str:
        """Format classes information for the LLM prompt."""
        if not classes:
            return "No classes defined"
            
        summary = []
        for cls in classes:
            class_info = [f"- {cls['name']}:"]
            if cls['docstring']:
                class_info.append(f"  {cls['docstring'].strip()}")
            if cls['methods']:
                methods = [f"  - {m['name']}({', '.join(m['args'])})" for m in cls['methods']]
                class_info.extend(methods)
            summary.extend(class_info)
        return "\n".join(summary)

    def _format_functions_for_summary(self, functions: List[Dict]) -> str:
        """Format functions information for the LLM prompt."""
        if not functions:
            return "No functions defined"
            
        summary = []
        for func in functions:
            func_info = [f"- {func['name']}({', '.join(func['args'])})"]
            if func['docstring']:
                func_info.append(f"  {func['docstring'].strip()}")
            summary.extend(func_info)
        return "\n".join(summary)

class ReadmeGenerator:
    """Generates README.md files for Python modules."""

    def __init__(self, analyzer: PythonCodeAnalyzer):
        """Initialize the generator with a code analyzer."""
        self.analyzer = analyzer

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

    def generate_readme(self, file_path: str, content: str) -> str:
        """Generate a complete README.md for a Python file."""
        old_readme = None
        readme_path = f"{file_path}_README.md"
        
        if os.path.exists(readme_path):
            with open(readme_path, 'r') as f:
                old_readme = f.read()
        
        # Analyze the code
        info = self.analyzer.analyze_code(content)
        
        # Get AI summary for overview
        ai_summary = self.analyzer.get_ai_summary(content, old_readme)
        
        # Generate README sections
        readme = f"# {os.path.basename(file_path)}\n\n"
        
        # Overview section - focus on plain English description
        readme += "## Overview\n\n"
        if info.get('docstring'):
            readme += f"{info['docstring'].strip()}\n\n"
        if ai_summary:
            # Extract just the main purpose and functionality from AI summary
            summary_lines = ai_summary.strip().split('\n')
            overview_lines = [line for line in summary_lines if not line.startswith(('-', '•', '*', '1.', '2.', '3.', '4.'))]
            readme += '\n'.join(overview_lines).strip() + '\n\n'
        
        # Add classes section (keeping as is since it's well-liked)
        readme += self.generate_class_section(info.get('classes', []))
        
        return readme

    def update_readme(self, file_path: str, content: str) -> None:
        """Generate and write README.md file."""
        try:
            readme_content = self.generate_readme(file_path, content)
            readme_path = f"{file_path}_README.md"
            
            with open(readme_path, 'w') as f:
                f.write(readme_content)
                
            logger.info(f"Updated README at {readme_path}")
            
        except Exception as e:
            logger.error(f"Error updating README: {e}")

class PyFileHandler(FileSystemEventHandler):
    """Handles Python file modification events."""

    def __init__(self, generator: ReadmeGenerator):
        """Initialize with a README generator."""
        self.generator = generator
        logger.info("File handler initialized")

    def process_existing_files(self, path: str) -> None:
        """Process all existing Python files in the directory that don't have READMEs."""
        for root, _, files in os.walk(path):
            for file in files:
                if not file.endswith('.py'):
                    continue
                    
                file_path = os.path.join(root, file)
                readme_path = f"{file_path}_README.md"
                
                if os.path.exists(readme_path):
                    continue
                    
                logger.info(f"Processing existing file: {file_path}")
                try:
                    with open(file_path, 'r') as f:
                        content = f.read()
                    
                    self.generator.update_readme(file_path, content)
                except Exception as e:
                    logger.error(f"Error processing existing file {file_path}: {e}")

    def on_modified(self, event) -> None:
        """Handle file modification events."""
        if event.is_directory:
            return
            
        file_path = event.src_path
        if not file_path.endswith('.py'):
            return
            
        logger.info(f"Detected modification to {file_path}")
        
        try:
            with open(file_path, 'r') as f:
                content = f.read()
            
            self.generator.update_readme(file_path, content)
            
        except Exception as e:
            logger.error(f"Error processing file {file_path}: {e}")

def main(path: str) -> None:
    """Main function to run the README generator agent.
    
    Args:
        path: Directory path to monitor
    """
    try:
        config_manager = ConfigManager()
        config = config_manager.get_config()
        
        analyzer = PythonCodeAnalyzer(config)
        generator = ReadmeGenerator(analyzer)
        event_handler = PyFileHandler(generator)
        
        # Process existing files before starting the watcher
        logger.info("Processing existing Python files...")
        event_handler.process_existing_files(path)
        
        observer = Observer()
        observer.schedule(event_handler, path, recursive=True)
        observer.start()
        
        logger.info(f"Started monitoring directory: {path}")
        
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Received shutdown signal")
            observer.stop()
        observer.join()
        
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        logger.error("Please provide the directory path to monitor")
        sys.exit(1)
    
    path = sys.argv[1]
    main(path)
