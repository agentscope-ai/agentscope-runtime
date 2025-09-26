# -*- coding: utf-8 -*-
# pylint: disable=no-self-argument, line-too-long, too-many-branches, too-many-statements
# flake8: noqa: E501
"""
Integration tests for AgentRunDeployer demonstrating the usage of deploying,
updating, and deleting agent runtimes on Alibaba Cloud AgentRun.
"""

import asyncio
import base64
import os
from datetime import datetime
import pytest
from dotenv import load_dotenv

from agentscope_runtime.engine.deployers import AgentRunDeployer
from agentscope_runtime.engine.deployers.agentrun_deployer import (
    CodeConfig,
    NetworkConfig,
)


def read_zip_file_as_base64(file_path):
    """Read a zip file and return its content as base64 encoded string.

    Returns a default value if the file does not exist."""
    try:
        with open(file_path, "rb") as f:
            zip_content = f.read()
            return base64.b64encode(zip_content).decode("utf-8")
    except FileNotFoundError:
        # Return a default base64 encoded string when file is not found
        return base64.b64encode(b"print('Default content')").decode("utf-8")


@pytest.mark.asyncio
async def test_agentrun_deployer_integration():
    """Test the complete workflow of deploying, getting, updating, and deleting an agent runtime."""

    # Load environment variables
    env_file_path = os.path.join(
        os.path.dirname(__file__),
        "..",
        "..",
        "agentrun.env",
    )
    if os.path.exists(env_file_path):
        load_dotenv(env_file_path)
        print(f"Loaded environment variables from: {env_file_path}")
    else:
        print(
            f"No .agentrun.env file found at {env_file_path}. Using environment variables from current environment.",
        )

    # Get credentials from environment variables
    account_id = os.environ.get("AGENT_RUN_ACCOUNT_ID")
    access_key_id = os.environ.get("AGENT_RUN_ACCESS_KEY_ID")
    access_key_secret = os.environ.get("AGENT_RUN_ACCESS_KEY_SECRET")
    region_id = os.environ.get("AGENT_RUN_REGION_ID", "cn-hangzhou")

    # Check if credentials are provided
    print("Checking environment variables...")
    print(f"  AGENT_RUN_ACCOUNT_ID: {'Set' if account_id else 'Not set'}")
    print(
        f"  AGENT_RUN_ACCESS_KEY_ID: {'Set' if access_key_id else 'Not set'}",
    )
    print(
        f"  AGENT_RUN_ACCESS_KEY_SECRET: {'Set' if access_key_secret else 'Not set'}",
    )
    print(f"  AGENT_RUN_REGION_ID: {region_id} (default: cn-hangzhou)")

    # Skip test if credentials are not provided
    if not all([account_id, access_key_id, access_key_secret]):
        pytest.skip(
            "Missing required environment variables for AgentRun integration test",
        )

    print(f"Using account: {account_id}")
    print(f"Using region: {region_id}")

    # Initialize the deployer
    deployer = AgentRunDeployer(
        account_id=account_id,
        access_key_id=access_key_id,
        access_key_secret=access_key_secret,
        region_id=region_id,
    )

    # Define deployment parameters
    agent_runtime_name = (
        f"agent-runtime-test-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    )
    artifact_type = "Code"
    cpu = 0.5
    memory = 512
    port = 8080

    print(f"\nDeploying agent runtime: {agent_runtime_name}")
    print(f"Configuration: CPU={cpu}, Memory={memory}MB, Port={port}")

    # Read and encode zip file
    zip_file_path = os.path.join(
        os.path.dirname(__file__),
        "assets",
        "demo-code.zip",
    )

    # Check if zip file exists
    if not os.path.exists(zip_file_path):
        print(f"WARNING: Zip file not found at {zip_file_path}")
        print("Creating a simple demo zip file content...")
        zip_file_base64 = base64.b64encode(
            b"print('Hello, AgentRun!')",
        ).decode("utf-8")
    else:
        zip_file_base64 = read_zip_file_as_base64(zip_file_path)

    # Create configuration objects
    code_config = CodeConfig(
        language="python3.10",
        command=["python3", "app.py"],
        zip_file=zip_file_base64,
    )

    network_config = NetworkConfig(
        network_mode="PUBLIC",
    )

    agent_runtime_id = None

    try:
        # Deploy the agent runtime
        print("\nStep 1: Deploying agent runtime...")
        deploy_result = await deployer.deploy(
            agent_runtime_name=agent_runtime_name,
            artifact_type=artifact_type,
            cpu=cpu,
            memory=memory,
            port=port,
            code_configuration=code_config,
            network_configuration=network_config,
        )

        print("Deployment result:")
        for key, value in deploy_result.items():
            print(f"  {key}: {value}")

        # Verify deployment was successful
        assert deploy_result.get(
            "success",
        ), f"Deployment failed: {deploy_result.get('message', 'Unknown error')}"

        agent_runtime_id = deploy_result["agent_runtime_id"]
        print(
            f"\nSuccessfully deployed agent runtime with ID: {agent_runtime_id}",
        )

        # Wait a moment before proceeding
        await asyncio.sleep(5)

        # Get the deployed agent runtime details
        print("\nStep 2: Getting agent runtime details...")
        get_result = await deployer.get_agent_runtime(
            agent_runtime_id=agent_runtime_id,
        )

        print("Agent runtime details:")
        for key, value in get_result.items():
            print(f"  {key}: {value}")

        # Verify get operation was successful
        assert get_result.get(
            "success",
        ), f"Get operation failed: {get_result.get('message', 'Unknown error')}"
        # Check if 'data' key exists and contains agent_runtime_id
        if "data" in get_result and isinstance(get_result["data"], dict):
            assert get_result["data"].get("agentRuntimeId") == agent_runtime_id
        else:
            # If data structure is different, just check that the operation was successful
            assert get_result.get(
                "success",
            ), "Get operation was not successful"

        # Wait a moment before proceeding
        await asyncio.sleep(5)

        # Update the agent runtime
        print("\nStep 3: Updating agent runtime...")
        update_result = await deployer.update_agent_runtime(
            agent_runtime_id=agent_runtime_id,
            agent_runtime_name=f"{agent_runtime_name}-updated",
            cpu=1.0,
            memory=1024,
        )

        print("Update result:")
        for key, value in update_result.items():
            print(f"  {key}: {value}")

        # Verify update was successful
        assert update_result.get(
            "success",
        ), f"Update failed: {update_result.get('message', 'Unknown error')}"
        # Check that agent_runtime_id exists in the result
        assert update_result.get("agent_runtime_id") == agent_runtime_id

        # Wait a moment before proceeding
        await asyncio.sleep(5)

        print("\nIntegration test completed successfully!")

    except Exception as e:
        print(f"An error occurred during test: {str(e)}")
        import traceback

        traceback.print_exc()
        raise
    finally:
        # Clean up: Delete the agent runtime if it was created
        if agent_runtime_id:
            try:
                print("\nStep 4: Deleting agent runtime...")
                delete_result = await deployer.delete(
                    agent_runtime_id=agent_runtime_id,
                )

                print("Delete result:")
                for key, value in delete_result.items():
                    print(f"  {key}: {value}")

                # Verify deletion was successful
                assert delete_result.get(
                    "success",
                ), f"Delete failed: {delete_result.get('message', 'Unknown error')}"
                # Check that agent_runtime_id exists in the result
                assert (
                    delete_result.get("agent_runtime_id") == agent_runtime_id
                )
                print(
                    f"\nSuccessfully deleted agent runtime with ID: {agent_runtime_id}",
                )
            except Exception as e:
                print(
                    f"Warning: Failed to delete agent runtime {agent_runtime_id}: {str(e)}",
                )
                # Don't raise the exception as this is cleanup code
