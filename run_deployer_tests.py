#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test runner script for all unit tests for agentscope-runtime deployers utils.
"""

import subprocess
import sys
import os

def run_tests():
    """Run all unit tests."""
    test_files = [
        "tests/unit/test_deployment_modes.py",
        "tests/unit/test_service_config.py",
        "tests/unit/test_package_project_utils.py",
        "tests/unit/test_docker_image_utils.py",
        "tests/unit/test_service_utils.py",
        "tests/unit/test_kubernetes_deployer.py",
        "tests/unit/test_local_deployer.py"
    ]

    print("=" * 60)
    print("Running Unit Tests for AgentScope Runtime Deployers Utils")
    print("=" * 60)

    for test_file in test_files:
        if not os.path.exists(test_file):
            print(f"❌ Test file not found: {test_file}")
            continue

        print(f"\n🧪 Running {test_file}...")
        try:
            result = subprocess.run([
                "python", "-m", "pytest", test_file, "-v", "--tb=short"
            ], capture_output=True, text=True)

            if result.returncode == 0:
                print(f"✅ {test_file} - All tests passed!")
            else:
                print(f"❌ {test_file} - Some tests failed!")
                print("STDOUT:", result.stdout)
                print("STDERR:", result.stderr)

        except Exception as e:
            print(f"❌ Error running {test_file}: {e}")

    print("\n" + "=" * 60)
    print("Running all tests together...")
    print("=" * 60)

    try:
        cmd = ["python", "-m", "pytest"] + test_files + ["-v", "--tb=short"]
        result = subprocess.run(cmd, text=True)

        if result.returncode == 0:
            print("\n🎉 All tests passed successfully!")
        else:
            print(f"\n❌ Some tests failed (exit code: {result.returncode})")

    except Exception as e:
        print(f"❌ Error running all tests together: {e}")

if __name__ == "__main__":
    run_tests()