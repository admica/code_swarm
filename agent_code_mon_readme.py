#!/usr/bin/env python3
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
            'ollama_model': 'codellama',
            'ollama_url': 'http://localhost:11434/api/generate',
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
        self.ollama_url = config.get('ollama_url')
        self.ollama_model = config.get('ollama_model')

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
        """Get AI-generated summary of the code changes."""
        try:
            # Check if Ollama is available
            try:
                requests.get(self.ollama_url.rsplit('/', 1)[0], timeout=1)
            except requests.exceptions.RequestException:
                logger.warning("Ollama service not available, skipping AI summary")
                return None
                
            context = f"Previous README:\n{old_readme}\n\n" if old_readme else ""
            prompt = f"""{context}Analyze this Python code and provide a clear, comprehensive overview:

{content}

Focus on:
1. The main purpose and functionality
2. Key components and their interactions
3. Any notable patterns or design choices
4. Important usage considerations

Keep the response under 200 words and maintain consistency with any existing documentation."""

            response = requests.post(
                self.ollama_url,
                json={
                    "model": self.ollama_model,
                    "prompt": prompt,
                    "stream": False
                },
                timeout=30
            )
            
            if response.status_code == 404:
                logger.warning("Ollama endpoint not found, skipping AI summary")
                return None
                
            response.raise_for_status()
            return response.json().get('response', 'No summary available')
            
        except requests.exceptions.RequestException as e:
            logger.warning(f"Ollama service error: {e}")
            return None
        except Exception as e:
            logger.error(f"Error getting AI summary: {e}")
            return None

class ReadmeGenerator:
    """Generates README.md files for Python modules."""

    def __init__(self, analyzer: PythonCodeAnalyzer):
        """Initialize the generator with a code analyzer."""
        self.analyzer = analyzer

    def generate_function_section(self, functions: List[Dict]) -> str:
        """Generate documentation for functions."""
        if not functions:
            return ""
            
        section = "\n## Functions\n\n"
        for func in functions:
            args_str = ", ".join(func['args'])
            section += f"### `{func['name']}({args_str})`\n\n"
            if func['docstring']:
                section += f"{func['docstring'].strip()}\n\n"
        return section

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

    def generate_dependencies_section(self, imports: List[str]) -> str:
        """Generate documentation for dependencies."""
        if not imports:
            return ""
            
        section = "\n## Dependencies\n\n"
        unique_imports = sorted(set(imports))
        for imp in unique_imports:
            section += f"- {imp}\n"
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
        
        # Get AI summary
        ai_summary = self.analyzer.get_ai_summary(content, old_readme)
        
        # Generate README sections
        readme = f"# {os.path.basename(file_path)}\n\n"
        
        # Overview section
        if info.get('docstring') or ai_summary:
            readme += "## Overview\n\n"
            if info.get('docstring'):
                readme += f"{info['docstring'].strip()}\n\n"
            if ai_summary:
                readme += f"{ai_summary.strip()}\n\n"
        
        # Add other sections
        readme += self.generate_function_section(info.get('functions', []))
        readme += self.generate_class_section(info.get('classes', []))
        readme += self.generate_dependencies_section(info.get('imports', []))
        
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
