#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test complex deployment scenario with nested calls to verify agent name extraction
"""
import os
import sys
from typing import Any, Dict

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(__file__))

from agent_run import llm_agent
from agentscope_runtime.engine.runner import Runner
from agentscope_runtime.engine.deployers.base import DeployManager
from agentscope_runtime.engine.deployers.utils.package_project import (
    package_project,
)


class MockDeployManager(DeployManager):
    """Mock deploy manager that calls package_project internally"""

    def __init__(self, host="localhost", port=8000):
        self.host = host
        self.port = port

    async def deploy(
        self,
        runner: "Runner" = None,
        endpoint_path: str = "/process",
        extra_packages=[],
        requirements=[],
        stream: bool = True,
        response_type: str = "sse",
        **kwargs: Any,
    ) -> Dict[str, str]:
        agent = runner._agent
        """This simulates the deploy manager calling package_project"""
        print(
            f"DeployManager.deploy_agent called with agent: {type(agent).__name__}",
        )

        # This simulates the nested call scenario where package_project
        # is called from within the deploy manager
        package_path = package_project(
            agent=runner._agent,
            requirements=requirements,
            extra_packages=extra_packages,
        )

        return package_path


class MockRunner:
    """Mock runner that holds the agent and calls deploy manager"""

    def __init__(self, agent):
        self._agent = agent
        print(f"Runner initialized with agent: {type(agent).__name__}")

    async def deploy(
        self,
        deploy_manager,
        endpoint_path="/",
        extra_packages=[],
        requirements=[],
    ):
        """This simulates the runner.deploy call"""
        print(
            f"Runner.deploy called with deploy_manager and endpoint: {endpoint_path}",
        )

        # This simulates passing the agent to the deploy manager
        deployment_info = await deploy_manager.deploy(
            self,
            extra_packages=extra_packages,
            requirements=requirements,
        )

        return deployment_info


def test_complex_deployment_scenario():
    """Test the complex deployment scenario similar to the unit test"""
    print("=== Testing Complex Deployment Scenario ===")
    print(f"Original agent variable: llm_agent from {__file__}")
    print(f"Agent type: {type(llm_agent).__name__}")
    print()

    # Step 1: Create Runner with llm_agent (similar to unit test)
    print("Step 1: Creating Runner with llm_agent...")
    runner = MockRunner(agent=llm_agent)
    print()

    # Step 2: Create DeployManager
    print("Step 2: Creating DeployManager...")
    deploy_manager = MockDeployManager(host="localhost", port=8000)
    print()

    # Step 3: Call runner.deploy (this will trigger the nested calls)
    print("Step 3: Calling runner.deploy...")
    try:
        import asyncio

        deployment_info = asyncio.run(
            runner.deploy(
                deploy_manager,
                endpoint_path="/test_endpoint",
                extra_packages=[
                    os.path.join(
                        os.path.dirname(__file__),
                        "others",
                        "other_project.py",
                    ),
                ],
                requirements=["agentdev"],
            ),
        )

        print(f"✅ Deployment successful!")
        print(f"Package created at: {deployment_info}")

        # Check the generated main.py to see what agent name was used
        main_py_path = os.path.join(deployment_info, "main.py")
        if os.path.exists(main_py_path):
            with open(main_py_path, "r") as f:
                content = f.read()
                # Look for the import line
                for line in content.split("\n"):
                    if "from agent_file import" in line:
                        print(f"✅ Generated import line: {line.strip()}")
                        if "llm_agent" in line:
                            print(
                                "✅ Correctly identified 'llm_agent' as the variable name!",
                            )
                            assert True
                        else:
                            print(
                                "❌ Did not correctly identify 'llm_agent' as the variable name",
                            )
                            assert False
                        break

    except Exception as e:
        print(f"❌ Deployment failed: {e}")
        import traceback

        traceback.print_exc()
        assert False

    finally:
        # Clean up the package directory
        if (
            "deployment_info" in locals()
            and deployment_info
            and os.path.exists(deployment_info)
        ):
            import shutil

            print(f"Cleaning up: {deployment_info}")
            shutil.rmtree(deployment_info)
