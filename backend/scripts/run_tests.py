#!/usr/bin/env python3
"""
Test runner script for the backend application.
Provides easy commands to run different types of tests.
"""

import subprocess
import sys
import argparse
import os
from pathlib import Path

def run_command(cmd, description):
    """Run a command and handle errors"""
    print(f"\n[RUNNING] {description}")
    print(f"Command: {' '.join(cmd)}")
    print("-" * 50)
    
    result = subprocess.run(cmd, capture_output=False)
    if result.returncode != 0:
        print(f"[FAILED] {description} failed!")
        return False
    else:
        print(f"[SUCCESS] {description} completed successfully!")
        return True

def main():
    # Set PYTHONPATH to include src directory
    backend_dir = Path(__file__).parent.parent
    src_dir = backend_dir / "src"
    
    current_pythonpath = os.environ.get("PYTHONPATH", "")
    if current_pythonpath:
        os.environ["PYTHONPATH"] = f"{src_dir}{os.pathsep}{current_pythonpath}"
    else:
        os.environ["PYTHONPATH"] = str(src_dir)
    
    parser = argparse.ArgumentParser(description="Run backend tests")
    parser.add_argument(
        "test_type", 
        choices=["all", "unit", "integration", "auth", "quotes", "ai", "documents", "users", "coverage"],
        help="Type of tests to run"
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--parallel", "-p", action="store_true", help="Run tests in parallel")
    
    args = parser.parse_args()
    
    # Base pytest command
    base_cmd = ["python", "-m", "pytest"]
    
    if args.verbose:
        base_cmd.append("-v")
    
    if args.parallel:
        base_cmd.extend(["-n", "auto"])
    
    # Add test-specific options
    if args.test_type == "all":
        cmd = base_cmd + ["tests/"]
        description = "Running all tests"
    elif args.test_type == "unit":
        cmd = base_cmd + ["-m", "unit", "tests/"]
        description = "Running unit tests"
    elif args.test_type == "integration":
        cmd = base_cmd + ["-m", "integration", "tests/"]
        description = "Running integration tests"
    elif args.test_type == "auth":
        cmd = base_cmd + ["tests/test_auth_integration.py"]
        description = "Running authentication tests"
    elif args.test_type == "quotes":
        cmd = base_cmd + ["tests/test_quotes_integration.py"]
        description = "Running quotes tests"
    elif args.test_type == "ai":
        cmd = base_cmd + ["tests/test_ai_integration.py"]
        description = "Running AI tests"
    elif args.test_type == "documents":
        cmd = base_cmd + ["tests/test_documents_integration.py"]
        description = "Running documents tests"
    elif args.test_type == "users":
        cmd = base_cmd + ["tests/test_users_integration.py"]
        description = "Running user management tests"
    elif args.test_type == "coverage":
        cmd = base_cmd + ["--cov=src", "--cov-report=html", "--cov-report=term", "tests/"]
        description = "Running tests with coverage report"
    
    # Run the tests
    success = run_command(cmd, description)
    
    if args.test_type == "coverage":
        print(f"\n[INFO] Coverage report generated in htmlcov/index.html")
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()