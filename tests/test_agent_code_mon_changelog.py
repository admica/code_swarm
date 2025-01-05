# PATH: ./tests/test_agent_code_mon_changelog.py
import pytest
import os
import tempfile
import shutil
import git
import json
import configparser
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import logging
from agent_code_mon_changelog import CodeAnalyzer, ConfigManager, PyFileHandler

@pytest.fixture
def temp_git_repo():
    """Create a temporary Git repository for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Initialize Git repo
        repo = git.Repo.init(temp_dir)
        
        # Create a sample Python file
        sample_file = os.path.join(temp_dir, "test.py")
        with open(sample_file, "w") as f:
            f.write("def hello():\n    print('Hello, World!')\n")
        
        # Add and commit the file
        repo.index.add(["test.py"])
        repo.index.commit("Initial commit")
        
        yield temp_dir

@pytest.fixture
def config():
    """Create a test configuration."""
    config = configparser.ConfigParser()
    config['agent_code_mon_changelog'] = {
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
    return config['agent_code_mon_changelog']

def test_config_manager_default_creation():
    """Test ConfigManager creates default config when none exists."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = os.path.join(temp_dir, "config.ini")
        config_manager = ConfigManager(config_path)
        
        assert os.path.exists(config_path)
        assert 'agent_code_mon_changelog' in config_manager.config.sections()

def test_code_analyzer_initialization(temp_git_repo, config):
    """Test CodeAnalyzer initialization."""
    analyzer = CodeAnalyzer(temp_git_repo, config)
    assert analyzer.repo is not None
    assert analyzer.repo_path == temp_git_repo

def test_syntax_score_calculation(temp_git_repo, config):
    """Test syntax score calculation."""
    analyzer = CodeAnalyzer(temp_git_repo, config)
    
    # Test valid syntax
    valid_code = "def test(): return True"
    assert analyzer.calculate_syntax_score(valid_code) == 100
    
    # Test invalid syntax
    invalid_code = "def test() return True"
    assert analyzer.calculate_syntax_score(invalid_code) == 0

def test_style_consistency(temp_git_repo, config):
    """Test style consistency calculation."""
    analyzer = CodeAnalyzer(temp_git_repo, config)
    
    # Create two similar files
    with open(os.path.join(temp_git_repo, "style1.py"), "w") as f:
        f.write("def function1():\n    return 1\n")
    
    with open(os.path.join(temp_git_repo, "style2.py"), "w") as f:
        f.write("def function2():\n    return 2\n")
    
    score = analyzer.calculate_style_consistency(
        os.path.join(temp_git_repo, "style1.py"),
        "def function3():\n    return 3\n"
    )
    assert 0 <= score <= 100

def test_complexity_score(temp_git_repo, config):
    """Test complexity score calculation."""
    analyzer = CodeAnalyzer(temp_git_repo, config)
    
    old_content = "def test(): return True"
    new_content = "def test():\n    print('Hello')\n    return True"
    
    score = analyzer.calculate_complexity_score(old_content, new_content)
    assert 0 <= score <= 100

@patch('requests.post')
def test_ai_analysis(mock_post, temp_git_repo, config):
    """Test AI analysis with mocked Ollama response."""
    analyzer = CodeAnalyzer(temp_git_repo, config)
    
    # Mock Ollama response
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"response": "Test analysis"}
    mock_post.return_value = mock_response
    
    old_content = "def test(): return True"
    new_content = "def test():\n    return False"
    
    analysis = analyzer.get_ai_analysis(old_content, new_content)
    assert analysis == "Test analysis"

def test_changelog_update(temp_git_repo, config):
    """Test changelog file creation and updates."""
    analyzer = CodeAnalyzer(temp_git_repo, config)
    test_file = os.path.join(temp_git_repo, "test.py")
    
    changes = "Test changes description"
    analyzer.update_changelog(test_file, changes)
    
    changelog_path = os.path.join(temp_git_repo, "test.py_CHANGELOG.md")
    assert os.path.exists(changelog_path)
    
    with open(changelog_path, 'r') as f:
        content = f.read()
        assert "Test changes description" in content

def test_file_handler(temp_git_repo, config):
    """Test PyFileHandler file monitoring."""
    analyzer = CodeAnalyzer(temp_git_repo, config)
    handler = PyFileHandler(analyzer)
    
    # Create a mock event
    mock_event = Mock()
    mock_event.is_directory = False
    mock_event.src_path = os.path.join(temp_git_repo, "test.py")
    
    # Test file modification
    with open(mock_event.src_path, "w") as f:
        f.write("def new_function():\n    return 'new'\n")
    
    handler.on_modified(mock_event)
    
    # Check if changelog was created
    changelog_path = os.path.join(temp_git_repo, "test.py_CHANGELOG.md")
    assert os.path.exists(changelog_path)

def test_error_handling(temp_git_repo, config):
    """Test error handling in various scenarios."""
    analyzer = CodeAnalyzer(temp_git_repo, config)
    
    # Test invalid Git operation
    with pytest.raises(Exception):
        analyzer.get_file_from_git("nonexistent.py")
    
    # Test invalid file reading
    handler = PyFileHandler(analyzer)
    mock_event = Mock()
    mock_event.is_directory = False
    mock_event.src_path = os.path.join(temp_git_repo, "nonexistent.py")
    
    # Should not raise exception but log error
    handler.on_modified(mock_event)

if __name__ == '__main__':
    pytest.main([__file__, '-v', '--cov'])
