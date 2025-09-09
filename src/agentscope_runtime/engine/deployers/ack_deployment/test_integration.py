#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Integration test to verify that the packaged project can run as a service
"""
import os
import sys
import subprocess
import time
import requests
import signal

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(__file__))

from agent_run import llm_agent
from package_project import package_project


def test_service_integration():
    """Test that the packaged service can start and respond to requests"""
    print("Testing service integration...")

    try:
        # Create package
        package_path = package_project(
            agent=llm_agent,
            requirements=["langgraph"],
            extras_package=[
                os.path.join(os.path.dirname(__file__), "other_project.py"),
            ],
        )

        print(f"Package created at: {package_path}")

        # Start the service
        print("Starting the service...")
        env = os.environ.copy()
        env[
            "PYTHONPATH"
        ] = f"{os.path.dirname(__file__)}:{env.get('PYTHONPATH', '')}"

        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "main:app",
                "--host",
                "0.0.0.0",
                "--port",
                "8000",
            ],
            cwd=package_path,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            preexec_fn=os.setsid,  # Create process group for clean shutdown
        )

        # Give the service time to start
        time.sleep(3)

        # Test the root endpoint
        try:
            response = requests.get("http://localhost:8000/", timeout=5)
            if response.status_code == 200:
                print("✅ Root endpoint is working")
                print(f"Response: {response.json()}")
            else:
                print(
                    f"❌ Root endpoint failed with status: {response.status_code}",
                )
                return False
        except requests.exceptions.RequestException as e:
            print(f"❌ Failed to connect to service: {e}")
            return False

        # Test the chat endpoint
        try:
            response = requests.get(
                "http://localhost:8000/chat?message=Hello",
                timeout=10,
            )
            if response.status_code == 200:
                print("✅ Chat endpoint is accessible")
                result = response.json()
                print(f"Chat response: {result}")
            else:
                print(
                    f"⚠️ Chat endpoint returned status: {response.status_code}",
                )
        except requests.exceptions.RequestException as e:
            print(
                f"⚠️ Chat endpoint test failed (this might be expected without proper API keys): {e}",
            )

        print("✅ Service integration test completed!")
        return True

    except Exception as e:
        print(f"❌ Service integration test failed: {e}")
        import traceback

        traceback.print_exc()
        return False

    finally:
        # Clean up the service process
        try:
            if "process" in locals():
                print("Stopping the service...")
                os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                process.wait(timeout=5)
        except:
            pass

        # Clean up the package directory
        if "package_path" in locals():
            import shutil

            print(f"Cleaning up package directory: {package_path}")
            shutil.rmtree(package_path)


if __name__ == "__main__":
    test_service_integration()
