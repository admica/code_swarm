#!/usr/bin/env python3
# PATH: ./agent_code_mon_changelog.py
"""
Code monitoring agent that tracks changes to Python files and generates changelogs.
"""
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
from typing import Optional, Dict, Any, Union
from shared import LLMClient, config_manager, AgentLogger

# Set up logging
logger = AgentLogger('code_mon_changelog')

class ConfigManager:
    """Manages configuration loading and validation for the agent."""

    def __init__(self, config_path: str = 'config.ini'):
        """Initialize the config manager.

        Args:
            config_path: Path to the configuration file
        """
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

    def get_config(self) -> Dict[str, str]:
        """Get configuration dictionary.

        Returns:
            Dict containing configuration values
        """
        return self.config['agent_code_mon_changelog']

class CodeAnalyzer:
    """Analyzes Python code changes and maintains changelogs."""

    def __init__(self, repo_path: str, config: Dict[str, str]):
        """Initialize the code analyzer.

        Args:
            repo_path: Path to the Git repository
            config: Configuration dictionary
        """
        self.repo_path = repo_path
        self.config = config
        self.llm_client = LLMClient('code_mon_changelog')

        try:
            self.repo = git.Repo(repo_path)
            logger.info(f"Successfully initialized Git repository at {repo_path}")
        except git.exc.InvalidGitRepositoryError:
            logger.warning(f"Path {repo_path} is not a Git repository. Git features will be disabled.")
            self.repo = None
        except git.exc.NoSuchPathError:
            logger.error(f"Path {repo_path} does not exist")
            raise ValueError(f"Directory does not exist: {repo_path}")

        self.enabled_features = set(self.config.get('enabled_features', '').split(','))
        self.controller_url = self.config.get('controller_url', 'http://localhost:8000')
        self.ollama_model = self.config.get('ollama_model', 'llama3.2')

    def get_file_from_git(self, file_path: str) -> str:
        """Get the last committed version of the file from Git.

        Args:
            file_path: Path to the file relative to repository root

        Returns:
            Content of the file from last Git commit or empty string if no commits
        """
        if not self.repo:
            return ""
            
        try:
            if not self.repo.head.is_valid():
                logger.info(f"No commits yet in repository for {file_path}")
                return ""
            return self.repo.git.show(f'HEAD:{file_path}')
        except (git.exc.GitCommandError, ValueError) as e:
            logger.warning(f"Could not get previous version of {file_path} from Git: {e}")
            return ""

    def calculate_syntax_score(self, content: str) -> Optional[float]:
        """Check if the Python code has valid syntax.

        Args:
            content: Python code content

        Returns:
            Syntax score (0-100) or None if feature disabled
        """
        if 'syntax' not in self.enabled_features:
            return None

        try:
            ast.parse(content)
            return 100.0
        except SyntaxError as e:
            logger.warning(f"Syntax error detected: {e}")
            return 0.0

    def run_pylint_analysis(self, content: str) -> Optional[float]:
        """Run Pylint analysis on the code.

        Args:
            content: Python code content

        Returns:
            Pylint score (0-100) or None if feature disabled
        """
        if 'standards' not in self.enabled_features:
            return None

        try:
            output = StringIO()
            reporter = JSONReporter(output)

            temp_path = "temp_analysis.py"
            with open(temp_path, "w") as f:
                f.write(content)

            try:
                # Try new Pylint API first
                pylint.lint.Run([temp_path], reporter=reporter, exit=False)
            except TypeError:
                # Fallback to old API if needed
                pylint.lint.Run([temp_path], reporter=reporter)

            os.remove(temp_path)

            try:
                results = json.loads(output.getvalue())
                score = max(0, 10 - len(results))
                return float(score * 10)
            except json.JSONDecodeError:
                logger.warning("Could not parse Pylint output, returning default score")
                return 50.0  # Default middle score
        except Exception as e:
            logger.error(f"Error during Pylint analysis: {e}")
            return 0.0

    def calculate_style_consistency(self, file_path: str, content: str) -> Optional[float]:
        """Compare style with other Python files in the project.

        Args:
            file_path: Path to the file being analyzed
            content: Python code content

        Returns:
            Style consistency score (0-100) or None if feature disabled
        """
        if 'style' not in self.enabled_features:
            return None

        try:
            project_files = []
            for root, _, files in os.walk(self.repo_path):
                for file in files:
                    if file.endswith('.py') and os.path.join(root, file) != file_path:
                        project_files.append(os.path.join(root, file))

            if not project_files:
                return 100.0

            import random
            sample_files = random.sample(project_files, min(5, len(project_files)))

            style_scores = []
            for comp_file in sample_files:
                with open(comp_file, 'r') as f:
                    comp_content = f.read()

                content_lines = content.split('\n')
                comp_lines = comp_content.split('\n')

                if not content_lines or not comp_lines:
                    continue

                avg_len = sum(len(line) for line in content_lines) / len(content_lines)
                comp_avg_len = sum(len(line) for line in comp_lines) / len(comp_lines)

                length_score = 100.0 - min(100.0, abs(avg_len - comp_avg_len))

                style_scores.append(length_score)

            return sum(style_scores) / len(style_scores) if style_scores else 100.0
        except Exception as e:
            logger.error(f"Error calculating style consistency: {e}")
            return 0.0

    def calculate_complexity_score(self, old_content: str, new_content: str) -> Optional[float]:
        """Calculate complexity of changes.

        Args:
            old_content: Previous version of the code
            new_content: New version of the code

        Returns:
            Complexity score (0-100) or None if feature disabled
        """
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
                return 100.0
            return float(max(0, 100 - (total_changes * 2)))
        except Exception as e:
            logger.error(f"Error calculating complexity score: {e}")
            return 0.0

    def get_ai_analysis(self, old_content: str, new_content: str) -> Optional[str]:
        """Get AI analysis of changes using the controller's LLM service.

        Args:
            old_content: Previous version of the code
            new_content: New version of the code

        Returns:
            AI analysis text or None if feature disabled or service not available
        """
        if 'ai_analysis' not in self.enabled_features:
            return None

        try:
            # First check if controller is available
            try:
                requests.get(f"{self.controller_url}/llm/health", timeout=1)
            except requests.exceptions.RequestException:
                logger.warning("Controller service not available, skipping AI analysis")
                return None

            prompt = f"""Compare these two versions of Python code and provide a brief analysis:

Old version:
{old_content}

New version:
{new_content}

Please describe the main changes, their potential impact, and any suggestions for improvement.
Keep the response under 200 words."""

            response = requests.post(
                f"{self.controller_url}/llm/changelog/generate",
                json={
                    "prompt": prompt,
                    "model": self.ollama_model,
                    "agent": "changelog"
                },
                timeout=30
            )

            if response.status_code == 404:
                logger.warning("Controller LLM endpoint not found, skipping AI analysis")
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
            logger.error(f"Unexpected error in AI analysis: {e}")
            return None

    def update_changelog(self, file_path: str, changes_description: str) -> None:
        """Update the changelog file specific to the modified Python file.

        Args:
            file_path: Path to the modified Python file
            changes_description: Description of changes to add to changelog
        """
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
    """Handles Python file modification events."""

    def __init__(self, analyzer: CodeAnalyzer):
        """Initialize the file handler.

        Args:
            analyzer: CodeAnalyzer instance
        """
        self.analyzer = analyzer
        logger.info("File handler initialized")

    def on_modified(self, event) -> None:
        """Handle file modification events.

        Args:
            event: FileSystemEvent object
        """
        if event.is_directory:
            logger.debug(f"Ignoring directory modification: {event.src_path}")
            return

        file_path = event.src_path
        if not file_path.endswith('.py'):
            logger.debug(f"Ignoring non-Python file: {file_path}")
            return

        logger.info(f"Detected modification to {file_path}")

        try:
            logger.debug("Reading current file content")
            with open(file_path, 'r') as f:
                new_content = f.read()

            logger.debug("Getting previous version from Git")
            old_content = self.analyzer.get_file_from_git(
                os.path.relpath(file_path, self.analyzer.repo_path)
            )

            # Calculate scores
            logger.debug("Calculating analysis scores")
            scores: Dict[str, Optional[float]] = {
                'syntax': self.analyzer.calculate_syntax_score(new_content),
                'style': self.analyzer.calculate_style_consistency(file_path, new_content),
                'complexity': self.analyzer.calculate_complexity_score(old_content, new_content),
                'standards': self.analyzer.run_pylint_analysis(new_content)
            }

            logger.debug(f"Analysis scores: {scores}")

            # Get AI analysis
            logger.debug("Getting AI analysis")
            ai_analysis = self.analyzer.get_ai_analysis(old_content, new_content)
            if ai_analysis:
                logger.debug("AI analysis received")
            else:
                logger.debug("No AI analysis available")

            # Prepare analysis summary
            summary = f"""Code Analysis Results for {os.path.basename(file_path)}:"""

            for name, score in scores.items():
                if score is not None:
                    summary += f"\n- {name.title()} Score: {score:.2f}/100"

            if ai_analysis:
                summary += f"\n\nAI Analysis:\n{ai_analysis}"

            logger.info(f"Completed analysis of {file_path}")
            logger.debug(f"Analysis summary:\n{summary}")

            # Update changelog
            logger.debug("Updating changelog")
            self.analyzer.update_changelog(file_path, summary)
            logger.info("Changelog updated successfully")

        except Exception as e:
            logger.error(f"Error processing file {file_path}: {e}")
            logger.exception("Full traceback:")

def main(path: str) -> None:
    """Main function to run the code monitoring agent.

    Args:
        path: Directory path to monitor
    """
    try:
        logger.info("Starting changelog agent")
        logger.info(f"Monitoring path: {path}")
        
        logger.debug("Loading configuration")
        config_manager = ConfigManager()
        config = config_manager.get_config()
        logger.debug(f"Configuration loaded: {config}")

        logger.debug("Initializing code analyzer")
        analyzer = CodeAnalyzer(path, config)
        
        logger.debug("Setting up file handler")
        event_handler = PyFileHandler(analyzer)
        
        logger.debug("Initializing file system observer")
        observer = Observer()
        observer.schedule(event_handler, path, recursive=True)
        
        logger.info("Starting file system observer")
        observer.start()

        logger.info(f"Started monitoring directory: {path}")
        logger.info("Press Ctrl+C to stop")

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Received shutdown signal")
            observer.stop()
        observer.join()

    except Exception as e:
        logger.error(f"Fatal error: {e}")
        logger.exception("Full traceback:")
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        logger.error("Please provide the directory path to monitor")
        sys.exit(1)

    path = sys.argv[1]
    main(path)
