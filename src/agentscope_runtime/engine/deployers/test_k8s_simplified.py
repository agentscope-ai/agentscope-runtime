#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Simplified test script for Kubernetes ImageBuilder
Tests only the core image building functionality without Kubernetes dependencies
"""
import os
import sys
import asyncio

# Add paths
current_dir = os.path.dirname(__file__)
ack_deployment_dir = os.path.join(current_dir, "utils")
sys.path.insert(0, current_dir)
sys.path.insert(0, ack_deployment_dir)

from utils.agent_run import llm_agent


class MockRegistryConfig:
    """Mock registry configuration"""

    def __init__(self):
        self.registry_url = "localhost:5000"
        self.username = None
        self.password = None
        self.namespace = "default"


class MockBuildConfig:
    """Mock build configuration"""

    def __init__(self):
        self.build_context_dir = "/tmp/k8s_test_build"
        self.dockerfile_template = None
        self.build_timeout = 600
        self.push_timeout = 300
        self.cleanup_after_build = True


class SimplifiedImageBuilder:
    """Simplified ImageBuilder for testing core functionality"""

    def __init__(self, registry_config, build_config=None):
        self.registry_config = registry_config
        self.build_config = build_config or MockBuildConfig()

        # Import the required modules
        from utils.package_project import package_project
        from utils.docker_builder import package_and_build_docker_image

        self.package_project = package_project
        self.package_and_build_docker_image = package_and_build_docker_image

    def build_runner_image(
        self,
        runner,
        requirements=None,
        user_code_path=None,
        base_image="python:3.9-slim",
        image_tag=None,
        **kwargs,
    ):
        """Build Docker image using the new approach"""
        try:
            import time
            import hashlib

            # Validate requirements
            if requirements is None:
                requirements = []
            elif isinstance(requirements, str):
                requirements = [requirements]

            # Generate image tag
            if not image_tag:
                hash_content = (
                    f"{str(runner)}{str(requirements)}{user_code_path or ''}"
                )
                runner_hash = hashlib.md5(hash_content.encode()).hexdigest()[
                    :8
                ]
                image_tag = f"runner-{runner_hash}-{int(time.time())}"

            # Extract agent from runner
            if hasattr(runner, "_agent") and runner._agent is not None:
                agent = runner._agent
            else:
                raise ValueError("Runner must have a valid agent")

            # Prepare extras_package list
            extras_package = []
            if user_code_path:
                extras_package.append(user_code_path)

            print(
                f"Building image using package_project and docker_builder: {image_tag}",
            )

            # Build the image (without push for testing)
            (
                full_image_name,
                tar_gz_path,
                build_context_path,
            ) = self.package_and_build_docker_image(
                agent=agent,
                image_name=image_tag,
                requirements=requirements,
                extras_package=extras_package,
                registry=None,  # Don't push to registry
                push_to_registry=False,
                base_image=base_image,
                port=8000,
                quiet=False,
            )

            print(f"Successfully built runner image: {full_image_name}")
            return image_tag

        except Exception as e:
            print(f"Failed to build runner image: {e}")
            raise


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


def test_simplified_image_building():
    """Test the simplified image building approach"""
    print("=== Testing Simplified Kubernetes ImageBuilder ===")
    print(f"Original agent variable: llm_agent")
    print(f"Agent type: {type(llm_agent).__name__}")
    print()

    try:
        # Step 1: Create a mock Runner
        print("Step 1: Creating mock Runner...")
        runner = MockRunner(agent=llm_agent)
        print(f"Runner created: {runner}")
        print()

        # Step 2: Create configurations
        print("Step 2: Creating configurations...")
        registry_config = MockRegistryConfig()
        build_config = MockBuildConfig()
        print(f"Registry: {registry_config.registry_url}")
        print(f"Build dir: {build_config.build_context_dir}")
        print()

        # Step 3: Create ImageBuilder
        print("Step 3: Creating SimplifiedImageBuilder...")
        image_builder = SimplifiedImageBuilder(
            registry_config=registry_config,
            build_config=build_config,
        )
        print("✅ ImageBuilder created successfully")
        print()

        # Step 4: Test image building
        print("Step 4: Testing image building...")

        image_name = image_builder.build_runner_image(
            runner=runner,
            requirements=["fastapi", "uvicorn"],
            user_code_path=None,
            base_image="python:3.10-slim",
            image_tag=None,
        )

        print(f"✅ Image built successfully: {image_name}")

        # Check if we can find the generated files
        print("\n=== Image Build Summary ===")
        print(f"Image name: {image_name}")
        print(f"Registry: {registry_config.registry_url}")
        print("✅ All tests passed!")

        return True

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("Starting Simplified Kubernetes ImageBuilder Test...")
    print("=" * 60)

    if test_simplified_image_building():
        print(
            "🎉 Test passed! Kubernetes ImageBuilder core functionality works.",
        )
        sys.exit(0)
    else:
        print("⚠️  Test failed. Please check the issues above.")
        sys.exit(1)
