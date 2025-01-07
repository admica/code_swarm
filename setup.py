#!/usr/bin/env python3
"""
Setup script for Code Swarm - installs all required dependencies.
"""
import os
import sys
import subprocess
import logging
from pathlib import Path

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('code_swarm_setup')

def check_python_version():
    """Check if Python version meets requirements."""
    if sys.version_info < (3, 6):
        logger.error("Python 3.6 or higher is required")
        sys.exit(1)

def install_python_dependencies():
    """Install required Python packages."""
    logger.info("Installing Python dependencies...")
    try:
        subprocess.run(
            [sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'],
            check=True
        )
        logger.info("Python dependencies installed successfully")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Error installing Python dependencies: {e}")
        return False

def check_npm():
    """Check if npm is installed."""
    try:
        subprocess.run(['npm', '--version'], check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError:
        logger.error("npm is not installed. Please install Node.js and npm first.")
        return False
    except FileNotFoundError:
        logger.error("npm command not found. Please install Node.js and npm first.")
        return False

def install_frontend_dependencies():
    """Install frontend dependencies."""
    logger.info("Installing frontend dependencies...")
    frontend_dir = Path(__file__).parent / 'frontend'
    
    try:
        # Change to frontend directory
        os.chdir(frontend_dir)
        
        # Install dependencies
        subprocess.run(['npm', 'install'], check=True)
        
        logger.info("Frontend dependencies installed successfully")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Error installing frontend dependencies: {e}")
        return False
    finally:
        # Change back to original directory
        os.chdir(Path(__file__).parent)

def main():
    """Main setup function."""
    logger.info("Starting Code Swarm setup...")

    # Check Python version
    check_python_version()

    # Install Python dependencies
    if not install_python_dependencies():
        sys.exit(1)

    # Check and install frontend dependencies
    if not check_npm():
        sys.exit(1)
    
    if not install_frontend_dependencies():
        sys.exit(1)

    logger.info("Setup completed successfully!")
    logger.info("You can now run Code Swarm using: python run.py")

if __name__ == "__main__":
    main() 
