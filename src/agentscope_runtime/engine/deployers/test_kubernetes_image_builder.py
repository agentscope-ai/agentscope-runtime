#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script for KubernetesDeployer image building functionality
Based on the working utils approach
"""
import os
import sys
import asyncio

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "utils"))

from utils.agent_run import llm_agent
from kubernetes_deployer import ImageBuilder, RegistryConfig, BuildConfig


class MockK8sConfig:
    """Mock Kubernetes config for testing"""

    def __init__(self):
        self.k8s_namespace = "default"
        self.kubeconfig_path = None


class MockRunner:
    """Mock Runner to simulate the Runner object structure"""

    def __init__(self, agent):
        self._agent = agent
        self._context_manager = None
        self._environment_manager = None
        self.name = (
            f"runner-{agent.name if hasattr(agent, 'name') else 'default'}"
        )

    def __str__(self):
        return f"MockRunner(agent={self._agent})"


def test_image_builder():
    """Test the ImageBuilder with the new package_project and docker_builder approach"""
    print("=== Testing Kubernetes ImageBuilder ===")
    print(f"Original agent variable: llm_agent from agent_run.py")
    print(f"Agent type: {type(llm_agent).__name__}")
    print()

    try:
        # Step 1: Create a mock Runner
        print("Step 1: Creating mock Runner...")
        runner = MockRunner(agent=llm_agent)
        print(f"Runner created: {runner}")
        print()

        # Step 2: Create Registry and Build configs
        print("Step 2: Creating configurations...")
        registry_config = RegistryConfig(
            registry_url="localhost:5000",  # Use local registry for testing
            username=None,
            password=None,
        )

        build_config = BuildConfig(
            build_context_dir="/tmp/k8s_test_build",
            cleanup_after_build=True,
        )

        print(f"Registry: {registry_config.registry_url}")
        print(f"Build dir: {build_config.build_context_dir}")
        print()

        # Step 3: Create ImageBuilder
        print("Step 3: Creating ImageBuilder...")
        image_builder = ImageBuilder(
            registry_config=registry_config,
            build_config=build_config,
        )
        print("✅ ImageBuilder created successfully")
        print()

        # Step 4: Test image building (without actually pushing to registry)
        print("Step 4: Testing image building...")

        # Temporarily disable push for testing
        original_push = registry_config.registry_url
        registry_config.registry_url = None  # This will disable pushing

        try:
            image_name = asyncio.run(
                image_builder.build_runner_image(
                    runner=runner,
                    requirements=["fastapi", "uvicorn"],
                    user_code_path=None,
                    base_image="python:3.10-slim",
                    image_tag=None,
                    stream=True,
                    endpoint_path="/process",
                ),
            )

            print(f"✅ Image built successfully: {image_name}")

            # Check if we can find the generated files
            print("\n=== Image Build Summary ===")
            print(f"Image name: {image_name}")
            print(f"Registry: {original_push}")
            print("✅ All tests passed!")

            return True

        except Exception as e:
            print(f"❌ Image building failed: {e}")
            import traceback

            traceback.print_exc()
            return False

        finally:
            # Restore original registry URL
            registry_config.registry_url = original_push

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_runner_extraction():
    """Test agent extraction from runner"""
    print("\n=== Testing Agent Extraction from Runner ===")

    try:
        # Create a mock runner
        runner = MockRunner(agent=llm_agent)

        # Test agent extraction
        if hasattr(runner, "_agent") and runner._agent is not None:
            agent = runner._agent
            print(f"✅ Agent extracted successfully: {type(agent).__name__}")
            print(f"Agent details: {agent}")

            # Test agent properties
            if hasattr(agent, "name"):
                print(f"Agent name: {agent.name}")
            if hasattr(agent, "model"):
                print(f"Agent model: {type(agent.model).__name__}")

            return True
        else:
            print("❌ Failed to extract agent from runner")
            return False

    except Exception as e:
        print(f"❌ Agent extraction test failed: {e}")
        return False


def test_requirements_validation():
    """Test requirements validation"""
    print("\n=== Testing Requirements Validation ===")

    try:
        registry_config = RegistryConfig()
        image_builder = ImageBuilder(registry_config)

        # Test different requirements formats
        test_cases = [
            (None, []),
            ([], []),
            (["fastapi", "uvicorn"], ["fastapi", "uvicorn"]),
            ("numpy", ["numpy"]),
        ]

        for input_req, expected in test_cases:
            result = image_builder._validate_requirements_or_raise(input_req)
            if result == expected:
                print(f"✅ Requirements test passed: {input_req} -> {result}")
            else:
                print(
                    f"❌ Requirements test failed: {input_req} -> {result}, expected {expected}",
                )
                return False

        return True

    except Exception as e:
        print(f"❌ Requirements validation test failed: {e}")
        return False


if __name__ == "__main__":
    print("Starting Kubernetes ImageBuilder Tests...")
    print("=" * 60)

    # Run all tests
    tests = [
        test_runner_extraction,
        test_requirements_validation,
        test_image_builder,
    ]

    passed = 0
    total = len(tests)

    for test in tests:
        try:
            if test():
                passed += 1
            else:
                print(f"❌ Test {test.__name__} failed")
        except Exception as e:
            print(f"❌ Test {test.__name__} crashed: {e}")

    print("\n" + "=" * 60)
    print(f"Test Results: {passed}/{total} tests passed")

    if passed == total:
        print("🎉 All tests passed! Kubernetes ImageBuilder is ready.")
    else:
        print(
            f"⚠️  {total - passed} tests failed. Please check the issues above.",
        )

    sys.exit(0 if passed == total else 1)
