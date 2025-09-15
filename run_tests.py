#!/usr/bin/env python3
"""
Simple test runner for the immersive-status project.
Automatically creates and uses a virtual environment for testing.
"""
import subprocess
import sys
import os
import venv
from pathlib import Path

def create_venv_if_needed():
    """Create virtual environment if it doesn't exist."""
    venv_path = Path("venv")
    if not venv_path.exists():
        print("Creating virtual environment...")
        venv.create(venv_path, with_pip=True)
        print("Virtual environment created.")
    return venv_path

def get_venv_python():
    """Get the Python executable path in the virtual environment."""
    if sys.platform == "win32":
        return Path("venv/Scripts/python.exe")
    else:
        return Path("venv/bin/python")

def install_dependencies(python_exe):
    """Install test dependencies in the virtual environment."""
    print("Installing dependencies...")
    
    # Install test dependencies
    subprocess.run([str(python_exe), "-m", "pip", "install", "-r", "requirements-test.txt"], check=True)
    
    # Install production dependencies
    subprocess.run([str(python_exe), "-m", "pip", "install", "requests", "boto3"], check=True)
    
    print("Dependencies installed.")

def main():
    """Run the test suite."""
    # Change to the project root directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    
    # Create virtual environment if needed
    create_venv_if_needed()
    
    # Get Python executable in venv
    python_exe = get_venv_python()
    
    # Install dependencies
    install_dependencies(python_exe)
    
    # Run pytest
    cmd = [str(python_exe), "-m", "pytest", "tests/", "-v"]
    
    print("Running tests...")
    print(f"Command: {' '.join(cmd)}")
    print("-" * 50)
    
    result = subprocess.run(cmd)
    return result.returncode

if __name__ == "__main__":
    sys.exit(main())
