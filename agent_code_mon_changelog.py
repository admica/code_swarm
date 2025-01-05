#!/usr/bin/env python3
# PATH: ./agent_code_mon_changelog.py
import sys
import time
import os
import logging
import configparser
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import git
import ast
import pylint.lint
from pylint.reporters import JSONReporter
from io import StringIO
import json
import requests
import difflib
from pathlib import Path

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('agent_code_mon_changelog.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('agent_code_mon_changelog')

class ConfigManager:
    def __init__(self, config_path='config.ini'):
        self.config = configparser.ConfigParser()
        self.config_path = config_path
        self.load_config()

    def load_config(self):
        """Load configuration from config.ini file."""
        if not os.path.exists(self.config_path):
            logger.warning(f"Config file not found at {self.config_path}. Creating default configuration.")
            self.create_default_config()
        
        try:
            self.config.read(self.config_path)
        except configparser.Error as e:
            logger.error(f"Error reading config file: {e}")
            raise

    def create_default_config(self):
        """Create default configuration file."""
        self.config['agent_code_mon_changelog'] = {
            'syntax_score_threshold': '60',
            'style_score_threshold': '70',
            'complexity_score_threshold': '75',
            'standards_score_threshold': '65',
            'ollama_model': 'codellama',
            'ollama_url': 'http://localhost:11434/api/generate',
            'watch_patterns': '*.py',
            'ignore_patterns': '__pycache__/*,.*',
            'enabled_features': 'syntax,style,complexity,standards,ai_analysis'
        }
        
        with open(self.config_path, 'w') as f:
            self.config.write(f)

    def get_config(self):
        """Get configuration dictionary."""
        return self.config['agent_code_mon_changelog']

class CodeAnalyzer:
    def __init__(self, repo_path, config):
        self.repo_path = repo_path
        self.config = config
        
        try:
            self.repo = git.Repo(repo_path)
            logger.info(f"Successfully initialized Git repository at {repo_path}")
        except git.exc.InvalidGitRepositoryError:
            logger.error(f"Invalid Git repository at {repo_path}")
            raise
        
        self.enabled_features = set(self.config.get('enabled_features', '').split(','))
        self.ollama_url = self.config.get('ollama_url')
        self.ollama_model = self.config.get('ollama_model')

    def get_file_from_git(self, file_path):
        """Get the last committed version of the file from Git."""
        try:
            return self.repo.git.show(f'HEAD:{file_path}')
        except git.exc.GitCommandError as e:
            logger.warning(f"Could not get previous version of {file_path} from Git: {e}")
            return ""

    def calculate_syntax_score(self, content):
        """Check if the Python code has valid syntax."""
        if 'syntax' not in self.enabled_features:
            return None
            
        try:
            ast.parse(content)
            return 100
        except SyntaxError as e:
            logger.warning(f"Syntax error detected: {e}")
            return 0
        
    def run_pylint_analysis(self, content):
        """Run Pylint analysis on the code."""
        if 'standards' not in self.enabled_features:
            return None
            
        try:
            output = StringIO()
            reporter = JSONReporter(output)
            
            temp_path = "temp_analysis.py"
            with open(temp_path, "w") as f:
                f.write(content)
            
            pylint.lint.Run([temp_path], reporter=reporter, do_exit=False)
            
            os.remove(temp_path)
            
            results = json.loads(output.getvalue())
            score = max(0, 10 - len(results))
            return score * 10
        except Exception as e:
            logger.error(f"Error during Pylint analysis: {e}")
            return 0

    def calculate_style_consistency(self, file_path, content):
        """Compare style with other Python files in the project."""
        if 'style' not in self.enabled_features:
            return None
            
        try:
            project_files = []
            for root, _, files in os.walk(self.repo_path):
                for file in files:
                    if file.endswith('.py') and os.path.join(root, file) != file_path:
                        project_files.append(os.path.join(root, file))
            
            if not project_files:
                return 100
            
            import random
            sample_files = random.sample(project_files, min(5, len(project_files)))
            
            style_scores = []
            for comp_file in sample_files:
                with open(comp_file, 'r') as f:
                    comp_content = f.read()
                
                content_lines = content.split('\n')
                comp_lines = comp_content.split('\n')
                
                avg_len = sum(len(line) for line in content_lines) / len(content_lines)
                comp_avg_len = sum(len(line) for line in comp_lines) / len(comp_lines)
                
                length_score = 100 - min(100, abs(avg_len - comp_avg_len))
                
                style_scores.append(length_score)
            
            return sum(style_scores) / len(style_scores)
        except Exception as e:
            logger.error(f"Error calculating style consistency: {e}")
            return 0

    def calculate_complexity_score(self, old_content, new_content):
        """Calculate complexity of changes."""
        if 'complexity' not in self.enabled_features:
            return None
            
        try:
            diff = difflib.unified_diff(
                old_content.splitlines(keepends=True),
                new_content.splitlines(keepends=True)
            )
            
            changes = list(diff)
            added_lines = len([l for l in changes if l.startswith('+')])
            removed_lines = len([l for l in changes if l.startswith('-')])
            total_changes = added_lines + removed_lines
            
            if total_changes == 0:
                return 100
            return max(0, 100 - (total_changes * 2))
        except Exception as e:
            logger.error(f"Error calculating complexity score: {e}")
            return 0

    def get_ai_analysis(self, old_content, new_content):
        """Get AI analysis of changes using Ollama."""
        if 'ai_analysis' not in self.enabled_features:
            return None
            
        try:
            prompt = f"""Compare these two versions of Python code and provide a brief analysis:

Old version:
{old_content}

New version:
{new_content}

Please describe the main changes, their potential impact, and any suggestions for improvement.
Keep the response under 200 words."""

            response = requests.post(
                self.ollama_url,
                json={
                    "model": self.ollama_model,
                    "prompt": prompt,
                    "stream": False
                },
                timeout=30
            )
            
            if response.status_code == 200:
                return response.json().get('response', 'No analysis available')
            logger.warning(f"Ollama request failed with status {response.status_code}")
            return "Failed to get AI analysis"
        except requests.exceptions.RequestException as e:
            logger.error(f"Error getting AI analysis: {e}")
            return "Failed to connect to Ollama service"

    def update_changelog(self, file_path, changes_description):
        """Update the changelog file specific to the modified Python file."""
        try:
            base_name = os.path.basename(file_path)
            changelog_name = f"{base_name}_CHANGELOG.md"
            changelog_path = os.path.join(os.path.dirname(file_path), changelog_name)
            
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            entry = f"\n## {timestamp}\n{changes_description}\n"
            
            if os.path.exists(changelog_path):
                with open(changelog_path, 'r') as f:
                    content = f.read()
            else:
                content = f"# Changelog for {base_name}\n"
            
            with open(changelog_path, 'w') as f:
                f.write(content + entry)
            
            logger.info(f"Updated changelog at {changelog_path}")
        except Exception as e:
            logger.error(f"Error updating changelog: {e}")

class PyFileHandler(FileSystemEventHandler):
    def __init__(self, analyzer):
        self.analyzer = analyzer
        logger.info("File handler initialized")

    def on_modified(self, event):
        if event.is_directory:
            return
            
        file_path = event.src_path
        if not file_path.endswith('.py'):
            return
            
        logger.info(f"Detected modification to {file_path}")
        
        try:
            with open(file_path, 'r') as f:
                new_content = f.read()
            
            old_content = self.analyzer.get_file_from_git(
                os.path.relpath(file_path, self.analyzer.repo_path)
            )

            # Calculate scores
            scores = {}
            scores['syntax'] = self.analyzer.calculate_syntax_score(new_content)
            scores['style'] = self.analyzer.calculate_style_consistency(file_path, new_content)
            scores['complexity'] = self.analyzer.calculate_complexity_score(old_content, new_content)
            scores['standards'] = self.analyzer.run_pylint_analysis(new_content)
            
            # Get AI analysis
            ai_analysis = self.analyzer.get_ai_analysis(old_content, new_content)
            
            # Prepare analysis summary
            summary = f"""Code Analysis Results for {os.path.basename(file_path)}:"""
            
            for name, score in scores.items():
                if score is not None:
                    summary += f"\n- {name.title()} Score: {score:.2f}/100"
            
            if ai_analysis:
                summary += f"\n\nAI Analysis:\n{ai_analysis}"
            
            logger.info(f"Completed analysis of {file_path}")
            
            # Update changelog
            self.analyzer.update_changelog(file_path, summary)
            
        except Exception as e:
            logger.error(f"Error processing file {file_path}: {e}")

def main(path):
    try:
        config_manager = ConfigManager()
        config = config_manager.get_config()
        
        analyzer = CodeAnalyzer(path, config)
        event_handler = PyFileHandler(analyzer)
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
