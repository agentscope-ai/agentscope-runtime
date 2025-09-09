#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Verification script for K8s deployment example
"""

import os
import sys
import asyncio
import logging

# Add current directory and agentscope_runtime src to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
repo_root = os.path.join(current_dir, "../../../")
src_dir = os.path.join(repo_root, "src")

sys.path.insert(0, current_dir)
sys.path.insert(0, src_dir)

print(f"Added to Python path:")
print(f"  Current dir: {current_dir}")
print(f"  Src dir: {src_dir}")
print(f"  Src dir exists: {os.path.exists(src_dir)}")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_imports():
    """Test that imports work correctly from test directory"""
    logger.info("=== Testing Import Functionality ===")

    try:
        # Test direct import from test_utils
        from test_utils import (
            get_test_message,
            calculate_test_result,
            TestHelper,
            TEST_CONSTANT,
        )

        logger.info("✓ Successfully imported from test_utils")

        # Test functionality
        message = get_test_message()
        logger.info(f"✓ get_test_message(): {message}")

        result = calculate_test_result(10, 5)
        logger.info(f"✓ calculate_test_result(10, 5): {result}")

        helper = TestHelper()
        info = helper.get_info()
        logger.info(f"✓ TestHelper.get_info(): {info}")

        logger.info(f"✓ TEST_CONSTANT: {TEST_CONSTANT}")

        logger.info("All import tests passed!")
        return True

    except Exception as e:
        logger.error(f"✗ Import test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_llm_runner_creation():
    """Test LLM runner creation without actual deployment"""
    logger.info("=== Testing LLM Runner Creation ===")

    try:
        # Test imports needed for runner creation
        from agentscope_runtime.engine.agents.llm_agent import LLMAgent
        from agentscope_runtime.engine.llms.qwen_llm import QwenLLM
        from agentscope_runtime.engine.runner import Runner
        from agentscope_runtime.engine.services.context_manager import (
            ContextManager,
        )
        from agentscope_runtime.engine.services.session_history_service import (
            InMemorySessionHistoryService,
        )

        logger.info("✓ All AgentScope Runtime imports successful")

        # Check if API key is available
        api_key = os.getenv("DASHSCOPE_API_KEY")
        if api_key:
            logger.info(
                f"✓ DASHSCOPE_API_KEY is available (length: {len(api_key)})",
            )

            # Only create components if API key is available
            llm_agent = LLMAgent(
                model=QwenLLM(),
                name="test_llm_agent",
                description="A test LLM agent",
            )

            session_history_service = InMemorySessionHistoryService()
            context_manager = ContextManager(
                session_history_service=session_history_service,
            )

            runner = Runner(
                agent=llm_agent,
                context_manager=context_manager,
                environment_manager=None,
            )

            logger.info("✓ LLM Runner created successfully")
            logger.info(f"✓ Agent name: {runner._agent.name}")
            logger.info(f"✓ Agent description: {runner._agent.description}")

        else:
            logger.warning(
                "⚠ DASHSCOPE_API_KEY not available, skipping LLM runner creation",
            )
            logger.info(
                "✓ Basic imports work, but API key needed for full functionality",
            )

        return True

    except Exception as e:
        logger.error(f"✗ LLM runner creation test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_kubernetes_deployer_imports():
    """Test Kubernetes deployer imports"""
    logger.info("=== Testing Kubernetes Deployer Imports ===")

    try:
        from agentscope_runtime.engine.deployers.kubernetes_deployer import (
            KubernetesDeployer,
            RegistryConfig,
            BuildConfig,
            ImageBuilder,
        )

        logger.info("✓ All Kubernetes deployer imports successful")

        # Test basic configuration creation
        registry_config = RegistryConfig(
            registry_url="test-registry.com",
            namespace="test",
        )

        build_config = BuildConfig(
            build_context_dir="/tmp/test_build",
        )

        logger.info(
            f"✓ RegistryConfig created: {registry_config.registry_url}",
        )
        logger.info(f"✓ BuildConfig created: {build_config.build_context_dir}")

        return True

    except Exception as e:
        logger.error(f"✗ Kubernetes deployer import test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    """Run all verification tests"""
    logger.info("Starting K8s Deployment Example Verification")
    logger.info(f"Working directory: {current_dir}")
    logger.info(f"Python version: {sys.version}")

    tests = [
        ("Import Functionality", test_imports),
        ("LLM Runner Creation", test_llm_runner_creation),
        ("Kubernetes Deployer Imports", test_kubernetes_deployer_imports),
    ]

    results = []
    for test_name, test_func in tests:
        logger.info(f"\n--- Running {test_name} ---")
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            logger.error(f"Test {test_name} failed with exception: {e}")
            results.append((test_name, False))

    # Summary
    logger.info("\n=== Verification Summary ===")
    passed = 0
    for test_name, result in results:
        status = "PASSED" if result else "FAILED"
        logger.info(f"{test_name}: {status}")
        if result:
            passed += 1

    logger.info(f"\nTotal: {passed}/{len(tests)} tests passed")

    if passed == len(tests):
        logger.info(
            "🎉 All verification tests passed! The example is ready to run.",
        )
        logger.info("\nTo run the actual deployment:")
        logger.info("1. Ensure kubectl is configured for your K8s cluster")
        logger.info("2. Set DASHSCOPE_API_KEY environment variable")
        logger.info("3. Run: python kubernetes_deployer_example.py")
    else:
        logger.error(
            "❌ Some tests failed. Please fix the issues before running the deployment.",
        )

    return passed == len(tests)


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
