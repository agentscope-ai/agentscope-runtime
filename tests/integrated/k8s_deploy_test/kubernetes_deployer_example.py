#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Kubernetes Deployer Usage Example

This example demonstrates how to deploy LLMAgent services to Kubernetes clusters using KubernetesDeployer
"""
import asyncio
import logging
import os
from typing import Dict, Any
from dotenv import load_dotenv

# Import AgentScope Runtime components
from agentscope_runtime.engine.agents.llm_agent import LLMAgent
from agentscope_runtime.engine.llms.qwen_llm import QwenLLM
from agentscope_runtime.engine.runner import Runner
from agentscope_runtime.engine.services.context_manager import ContextManager
from agentscope_runtime.engine.services.session_history_service import (
    InMemorySessionHistoryService,
)
from agentscope_runtime.engine.deployers.kubernetes_deployer import (
    KubernetesDeployer,
    RegistryConfig,
    BuildConfig,
)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def create_llm_runner():
    """Create a complete LLM Runner with QwenLLM agent"""
    # Load environment variables (requires DASHSCOPE_API_KEY)
    load_dotenv()

    # Create LLM Agent
    llm_agent = LLMAgent(
        model=QwenLLM(),
        name="llm_agent",
        description="A powerful LLM agent using Qwen model",
    )

    # Create session history service
    session_history_service = InMemorySessionHistoryService()

    # Create context manager
    context_manager = ContextManager(
        session_history_service=session_history_service,
    )

    # Initialize context manager
    await context_manager.__aenter__()

    # Create complete runner
    runner = Runner(
        agent=llm_agent,
        context_manager=context_manager,
        environment_manager=None,
    )

    return runner, context_manager


class K8sConfig:
    """Kubernetes configuration class"""

    def __init__(self, namespace="default", kubeconfig_path=None):
        self.k8s_namespace = namespace
        self.kubeconfig_path = kubeconfig_path


async def example_llm_agent_deployment():
    """Example: Deploy LLM Agent to Kubernetes"""
    logger.info("=== LLM Agent Deployment Example ===")

    # Configuration
    k8s_config = K8sConfig(
        namespace="agentscope",
        kubeconfig_path="~/.kube/config",
    )
    registry_config = RegistryConfig(
        registry_url="your-registry.com",  # Replace with your registry
        username="your-username",  # Optional
        password="your-password",  # Optional
        namespace="llm-agents",
    )

    # Create deployer
    deployer = KubernetesDeployer(
        k8s_config=k8s_config,
        registry_config=registry_config,
        use_deployment=True,  # Use Deployment for scaling support
    )

    try:
        # Create LLM runner
        runner, context_manager = await create_llm_runner()

        # Get current test directory as user code path
        current_dir = os.path.dirname(os.path.abspath(__file__))
        logger.info(f"Using test directory as user_code_path: {current_dir}")

        logger.info("Starting LLM agent deployment...")
        result = await deployer.deploy(
            runner=runner,  # Pass complete runner object with LLMAgent
            user_code_path=current_dir,  # Pass test directory for imports
            replicas=2,  # Deploy 2 replicas
            environment={
                "AGENT_NAME": "LLMAgent",
                "LOG_LEVEL": "INFO",
                "DASHSCOPE_API_KEY": os.getenv("DASHSCOPE_API_KEY", ""),
            },
            runtime_config={
                "resources": {
                    "requests": {"memory": "512Mi", "cpu": "500m"},
                    "limits": {"memory": "1Gi", "cpu": "1000m"},
                },
                "image_pull_secrets": [
                    "registry-secret",
                ],  # If using private registry
            },
            stream=True,  # Enable streaming responses
            endpoint_path="/chat",  # Custom endpoint path
        )

        logger.info(f"Deployment successful!")
        logger.info(f"Deploy ID: {result['deploy_id']}")
        logger.info(f"Service URL: {result['url']}")
        logger.info(f"Replicas: {result['replicas']}")

        # Verify that user code is included
        logger.info(f"User code included from: {current_dir}")
        logger.info("Test files that should be available in container:")
        logger.info("  - test_utils.py (utility functions)")
        logger.info("  - test_imports.py (import verification)")
        logger.info("  - __init__.py (package initialization)")

        # Check status
        logger.info(f"Current status: {deployer.get_status()}")
        logger.info(f"Is running: {deployer.is_running}")
        logger.info(f"Replica status: {deployer.get_current_replicas()}")

        # Health check
        health_ok = await deployer.health_check()
        logger.info(f"Health check: {'Passed' if health_ok else 'Failed'}")

        # Get logs
        logs = deployer.get_logs(tail_lines=20)
        logger.info(f"Recent logs:\n{logs}")

        # Cleanup context manager
        await context_manager.__aexit__(None, None, None)

        return deployer

    except Exception as e:
        logger.error(f"Deployment failed: {e}")
        raise


async def example_scaling():
    """Example: Scaling operations"""
    logger.info("=== Scaling Example ===")

    # Assume we have an existing deployer
    deployer = await example_llm_agent_deployment()

    try:
        # Scale up to 5 replicas
        logger.info("Scaling up to 5 replicas...")
        scale_result = await deployer.scale(5)

        if scale_result:
            logger.info("Scale up successful!")
            logger.info(f"Replica status: {deployer.get_current_replicas()}")
        else:
            logger.error("Scale up failed!")

        # Wait for a while
        await asyncio.sleep(10)

        # Scale down to 1 replica
        logger.info("Scaling down to 1 replica...")
        scale_result = await deployer.scale(1)

        if scale_result:
            logger.info("Scale down successful!")
            logger.info(f"Replica status: {deployer.get_current_replicas()}")
        else:
            logger.error("Scale down failed!")

        return deployer

    except Exception as e:
        logger.error(f"Scaling operations failed: {e}")
        raise


async def example_production_deployment():
    """Example: Production deployment configuration"""
    logger.info("=== Production Deployment Example ===")

    k8s_config = K8sConfig(namespace="production")
    registry_config = RegistryConfig(
        registry_url="production-registry.company.com",
        username="prod-user",
        password="prod-password",
    )

    # Custom build configuration
    build_config = BuildConfig(
        build_context_dir="/tmp/prod_builds",
        build_timeout=900,  # 15 minutes build timeout
        push_timeout=600,  # 10 minutes push timeout
        cleanup_after_build=True,
    )

    deployer = KubernetesDeployer(
        k8s_config=k8s_config,
        registry_config=registry_config,
        use_deployment=True,
    )
    deployer.image_builder.build_config = build_config

    try:
        # Create LLM runner for production
        runner, context_manager = await create_llm_runner()

        # Get current test directory as user code path
        current_dir = os.path.dirname(os.path.abspath(__file__))

        # Production environment configuration
        result = await deployer.deploy(
            runner=runner,
            user_code_path=current_dir,  # Include test directory
            base_image="python:3.9-slim",
            port=8090,
            replicas=3,
            environment={
                "ENVIRONMENT": "production",
                "LOG_LEVEL": "WARNING",
                "MAX_WORKERS": "4",
                "DASHSCOPE_API_KEY": os.getenv("DASHSCOPE_API_KEY", ""),
            },
            runtime_config={
                "resources": {
                    "requests": {"memory": "512Mi", "cpu": "500m"},
                    "limits": {"memory": "1Gi", "cpu": "1000m"},
                },
                "security_context": {
                    "runAsNonRoot": True,
                    "runAsUser": 1000,
                    "readOnlyRootFilesystem": True,
                },
                "image_pull_secrets": ["prod-registry-secret"],
                "node_selector": {
                    "node-type": "compute",
                },
                "tolerations": [
                    {
                        "key": "dedicated",
                        "operator": "Equal",
                        "value": "agents",
                        "effect": "NoSchedule",
                    },
                ],
            },
            deploy_timeout=600,  # 10 minutes deployment timeout
            health_check=True,
            stream=True,
            endpoint_path="/chat",
        )

        logger.info("Production deployment successful!")
        logger.info(f"Service URL: {result['url']}")

        # Cleanup context manager
        await context_manager.__aexit__(None, None, None)

        return deployer

    except Exception as e:
        logger.error(f"Production deployment failed: {e}")
        raise


async def example_deployment_management():
    """Example: Deployment management operations"""
    logger.info("=== Deployment Management Example ===")

    deployer = await example_llm_agent_deployment()

    try:
        # Get detailed information
        info = deployer.inspect()
        logger.info(f"Deployment details: {info}")

        # Restart service
        logger.info("Restarting service...")
        restart_result = await deployer.restart()
        logger.info(f"Restart result: {restart_result}")

        # Stop service
        logger.info("Stopping service...")
        stop_result = await deployer.stop()
        logger.info(f"Stop result: {'Success' if stop_result else 'Failed'}")

        # Wait for a while
        await asyncio.sleep(5)

        # Check status
        logger.info(f"Status after stop: {deployer.get_status()}")

        return deployer

    except Exception as e:
        logger.error(f"Deployment management operations failed: {e}")
        raise


async def example_cleanup():
    """Example: Resource cleanup"""
    logger.info("=== Resource Cleanup Example ===")

    deployer = await example_llm_agent_deployment()

    try:
        # Completely remove deployment (including images)
        logger.info("Removing deployment and images...")
        remove_result = await deployer.remove(cleanup_image=True)

        if remove_result:
            logger.info("Cleanup successful!")
        else:
            logger.error("Cleanup failed!")

        # Check status
        logger.info(f"Status after cleanup: {deployer.get_status()}")

    except Exception as e:
        logger.error(f"Cleanup operations failed: {e}")
        raise


async def example_error_handling():
    """Example: Error handling"""
    logger.info("=== Error Handling Example ===")

    # Use incorrect configuration
    k8s_config = K8sConfig(namespace="non-existent-namespace")
    registry_config = RegistryConfig(registry_url="invalid-registry.com")

    try:
        deployer = KubernetesDeployer(k8s_config, registry_config)
        runner, context_manager = await create_llm_runner()

        # Try deployment (expected to fail)
        await deployer.deploy(
            runner=runner,
            requirements=["non-existent-package==999.999.999"],
        )

        # Cleanup if we somehow get here
        await context_manager.__aexit__(None, None, None)

    except RuntimeError as e:
        logger.info(f"Expected deployment error: {e}")

    except Exception as e:
        logger.error(f"Unexpected error: {e}")


def example_configuration():
    """Example: Configuration reference"""
    logger.info("=== Configuration Reference Example ===")

    logger.info("Configuration examples for different environments:")

    logger.info(
        "Development: namespace=development, kubeconfig=~/.kube/config",
    )
    logger.info("Testing: namespace=testing, registry with auth")
    logger.info("Production: namespace=production, in-cluster config")

    logger.info(
        "Configuration examples are ready, choose according to your environment",
    )


async def main():
    """Main function - Run all examples"""
    logger.info("Starting Kubernetes Deployer examples with LLM Agent...")

    # Check if DASHSCOPE_API_KEY is set
    if not os.getenv("DASHSCOPE_API_KEY"):
        logger.error("DASHSCOPE_API_KEY environment variable is required!")
        logger.info(
            "Please set DASHSCOPE_API_KEY in your environment or .env file",
        )
        return

    try:
        # Example 1: Basic LLM Agent deployment
        logger.info("Running basic LLM agent deployment...")
        deployer1 = await example_llm_agent_deployment()

        # Wait a bit before next example
        await asyncio.sleep(5)

        # Example 2: Scaling operations (uncomment to run)
        # logger.info("Running scaling example...")
        # deployer2 = await example_scaling()

        # Example 3: Production deployment (uncomment to run)
        # logger.info("Running production deployment...")
        # deployer3 = await example_production_deployment()

        # Example 4: Deployment management (uncomment to run)
        # logger.info("Running deployment management...")
        # deployer4 = await example_deployment_management()

        # Example 5: Resource cleanup (uncomment to run)
        # logger.info("Running resource cleanup...")
        # await example_cleanup()

        # Example 6: Error handling (uncomment to run)
        # logger.info("Running error handling example...")
        # await example_error_handling()

        # Example 7: Configuration reference
        example_configuration()

        logger.info("All examples completed successfully!")

        # Print final status
        if "deployer1" in locals():
            logger.info(f"Final deployment status: {deployer1.get_status()}")
            logger.info(f"Service URL: {deployer1.service_url}")

    except KeyboardInterrupt:
        logger.info("User interrupted")
    except Exception as e:
        logger.error(f"Examples execution failed: {e}")
        import traceback

        traceback.print_exc()
        raise


if __name__ == "__main__":
    # 运行示例
    asyncio.run(main())
