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
from agentscope_runtime.engine.deployers.utils.package_project import (
    package_project,
)
from logs.docker_builder import (
    DockerImageBuilder,
)


def test_service_integration():
    """Test that the packaged service can start and respond to requests"""
    print("Testing service integration...")

    try:
        # Create package
        package_path = package_project(
            agent=llm_agent,
            requirements=["langgraph"],
            extra_packages=[
                os.path.join(
                    os.path.dirname(__file__),
                    "others",
                    "other_project.py",
                ),
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
        response = requests.get("http://localhost:8000/", timeout=5)
        assert response.status_code == 200

        # Test the chat endpoint

        response = requests.get(
            "http://localhost:8000/chat?message=Hello",
            timeout=10,
        )
        assert response.status_code == 200

    finally:
        # Clean up the service process
        try:
            if "process" in locals():
                print("Stopping the service...")
                os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                process.wait(timeout=5)
        except:
            pass


def test_package_build():
    docker_builder = DockerImageBuilder()
    try:
        # Create package
        (
            image_name,
            tar_gz_path,
            build_context_path,
        ) = docker_builder.package_and_build_image(
            agent=llm_agent,
            image_name="agentscope-test",
            requirements=["langgraph"],
            extra_packages=[
                os.path.join(
                    os.path.dirname(__file__),
                    "others",
                    "other_project.py",
                ),
            ],
        )
        assert image_name == "agentscope-test:latest"
    except Exception as e:
        print(f"❌ Service integration test failed: {e}")
        import traceback

        traceback.print_exc()
        assert False
