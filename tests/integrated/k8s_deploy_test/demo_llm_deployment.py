#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Complete example: Deploy LLMAgent using new configuration-driven ImageBuilder

This example demonstrates:
1. Creating an LLMAgent with QwenLLM
2. Using ImageBuilder to build Docker image
3. Running the container locally
4. Testing the deployed service

Prerequisites:
- Docker installed and running
- DASHSCOPE_API_KEY environment variable set
- agentscope-runtime installed with sandbox dependencies
"""

import os
import sys
import asyncio
import time
import json
import subprocess
from pathlib import Path

# Add current directory to path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
repo_root = os.path.join(current_dir, "../../../")
src_dir = os.path.join(repo_root, "src")
sys.path.insert(0, src_dir)

# Configuration
CONTAINER_PORT = 8090
HOST_PORT = 8091
REGISTRY_URL = "localhost:5000"  # Local registry for testing


class LLMAgentDeploymentExample:
    def __init__(self):
        self.container_id = None
        self.image_name = None

    def check_prerequisites(self):
        """Check all prerequisites"""
        print("🔍 Checking prerequisites...")

        # Check Docker
        try:
            result = subprocess.run(
                ["docker", "--version"],
                capture_output=True,
                text=True,
                check=True,
            )
            print(f"   ✓ Docker: {result.stdout.strip()}")
        except (subprocess.CalledProcessError, FileNotFoundError):
            raise RuntimeError(
                "❌ Docker is required but not found. Please install Docker.",
            )

        # Check API key
        api_key = os.getenv("DASHSCOPE_API_KEY")
        if api_key:
            print(
                f"   ✓ DASHSCOPE_API_KEY: {'*' * (len(api_key) - 4)}{api_key[-4:]}",
            )
        else:
            print("   ⚠ DASHSCOPE_API_KEY not set, using mock key for testing")

        print("   ✅ Prerequisites check completed")

    def create_llm_agent_runner(self):
        """Create LLMAgent with QwenLLM"""
        print("🤖 Creating LLMAgent runner...")

        try:
            from agentscope_runtime.engine.agents.llm_agent import LLMAgent
            from agentscope_runtime.engine.llms.qwen_llm import QwenLLM
            from agentscope_runtime.engine.runner import Runner
            from agentscope_runtime.engine.services.context_manager import (
                ContextManager,
            )
            from agentscope_runtime.engine.services.session_history_service import (
                InMemorySessionHistoryService,
            )

            # Create QwenLLM
            llm_model = QwenLLM(
                model_name="qwen-max",
                api_key=os.getenv(
                    "DASHSCOPE_API_KEY",
                    "test_api_key_for_demo",
                ),
                temperature=0.7,
                max_tokens=2048,
            )
            print(f"   ✓ QwenLLM created: {llm_model.model_name}")

            # Create LLMAgent
            agent = LLMAgent(
                model=llm_model,
                name="deployment_demo_agent",
                description="Demo LLM agent for Kubernetes deployment example",
            )
            print(f"   ✓ LLMAgent created: {agent.name}")

            # Create context manager
            session_history_service = InMemorySessionHistoryService()
            context_manager = ContextManager(
                session_history_service=session_history_service,
            )
            print("   ✓ ContextManager created")

            # Create runner
            runner = Runner(
                agent=agent,
                context_manager=context_manager,
                environment_manager=None,
            )
            print("   ✅ Runner created successfully")

            return runner

        except ImportError as e:
            print(f"   ❌ Failed to import required modules: {e}")
            print(
                "   Please install agentscope-runtime with: pip install -e '.[sandbox]'",
            )
            raise
        except Exception as e:
            print(f"   ❌ Failed to create runner: {e}")
            raise

    async def build_docker_image(self, runner):
        """Build Docker image using ImageBuilder"""
        print("🏗️ Building Docker image with ImageBuilder...")

        try:
            from agentscope_runtime.engine.deployers.kubernetes_deployer import (
                ImageBuilder,
                RegistryConfig,
                BuildConfig,
            )

            # Configure registry
            registry_config = RegistryConfig(
                registry_url=REGISTRY_URL,
                username=None,  # No auth for local registry
                password=None,
                namespace="demo",
            )

            # Configure build
            build_config = BuildConfig(
                build_context_dir="/tmp/llm_agent_build",
                cleanup_after_build=False,  # Keep for inspection
                build_timeout=600,
                push_timeout=300,
            )

            # Create ImageBuilder
            image_builder = ImageBuilder(registry_config, build_config)
            print("   ✓ ImageBuilder configured")

            # Build image
            print("   🔨 Building runner image...")
            image_tag = await image_builder.build_runner_image(
                runner=runner,
                requirements=[
                    "fastapi>=0.104.0",
                    "uvicorn[standard]>=0.24.0",
                    "pydantic>=2.11.7",
                    "requests>=2.32.4",
                ],
                user_code_path=current_dir,  # Include test utilities
                base_image="python:3.9-slim",
                stream=True,
                endpoint_path="/chat",
                image_tag=f"demo-llm-agent-{int(time.time())}",
            )

            self.image_name = f"{registry_config.registry_url}/{image_tag}"
            print(f"   ✅ Image built successfully: {self.image_name}")

            return True

        except Exception as e:
            print(f"   ❌ Image building failed: {e}")
            import traceback

            traceback.print_exc()
            return False

    async def run_container(self):
        """Run the built container locally"""
        print("🐳 Running container locally...")

        try:
            # Run container
            cmd = [
                "docker",
                "run",
                "-d",
                "-p",
                f"{HOST_PORT}:{CONTAINER_PORT}",
                "-e",
                f"DASHSCOPE_API_KEY={os.getenv('DASHSCOPE_API_KEY', 'test_key')}",
                "-e",
                "LOG_LEVEL=INFO",
                "--name",
                f"llm-demo-{int(time.time())}",
                self.image_name,
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
            )
            self.container_id = result.stdout.strip()

            print(f"   ✓ Container started: {self.container_id[:12]}")
            print(f"   ✓ Service URL: http://localhost:{HOST_PORT}")

            # Wait for startup
            print("   ⏳ Waiting for service to start...")
            await asyncio.sleep(15)

            # Check container status
            status_cmd = [
                "docker",
                "ps",
                "--filter",
                f"id={self.container_id}",
                "--format",
                "{{.Status}}",
            ]
            status_result = subprocess.run(
                status_cmd,
                capture_output=True,
                text=True,
            )
            print(f"   ✓ Container status: {status_result.stdout.strip()}")

            return True

        except subprocess.CalledProcessError as e:
            print(f"   ❌ Container start failed: {e}")
            print(f"   Error output: {e.stderr}")
            return False

    def test_service(self):
        """Test the deployed service"""
        print("🌐 Testing deployed service...")

        import urllib.request
        import urllib.parse
        import urllib.error

        base_url = f"http://localhost:{HOST_PORT}"

        # Test health endpoint
        try:
            print("   Testing /health...")
            with urllib.request.urlopen(f"{base_url}/health") as response:
                health_data = json.loads(response.read().decode())
                print(
                    f"   ✓ Health: {health_data['status']} (agent: {health_data.get('agent', 'unknown')})",
                )
        except Exception as e:
            print(f"   ❌ Health check failed: {e}")
            return False

        # Test readiness
        try:
            print("   Testing /readiness...")
            with urllib.request.urlopen(f"{base_url}/readiness") as response:
                readiness = response.read().decode()
                print(f"   ✓ Readiness: {readiness}")
        except Exception as e:
            print(f"   ❌ Readiness check failed: {e}")

        # Test main chat endpoint
        try:
            print("   Testing /chat endpoint...")
            test_data = {
                "input": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "Hello! This is a deployment test.",
                            },
                        ],
                    },
                ],
                "session_id": "demo_session",
            }

            data = json.dumps(test_data).encode("utf-8")
            req = urllib.request.Request(
                f"{base_url}/chat",
                data=data,
                headers={"Content-Type": "application/json"},
            )

            with urllib.request.urlopen(req, timeout=30) as response:
                result = json.loads(response.read().decode())
                print(f"   ✅ Chat response: {result}")
                return True

        except Exception as e:
            print(f"   ❌ Chat endpoint test failed: {e}")
            return False

    def get_container_logs(self):
        """Get container logs for debugging"""
        if self.container_id:
            print("📋 Container logs (last 20 lines):")
            try:
                logs_cmd = [
                    "docker",
                    "logs",
                    "--tail",
                    "20",
                    self.container_id,
                ]
                result = subprocess.run(
                    logs_cmd,
                    capture_output=True,
                    text=True,
                )

                if result.stdout:
                    for line in result.stdout.split("\n"):
                        if line.strip():
                            print(f"     {line}")

                if result.stderr:
                    print("   STDERR:")
                    for line in result.stderr.split("\n"):
                        if line.strip():
                            print(f"     {line}")

            except Exception as e:
                print(f"   ❌ Failed to get logs: {e}")

    def cleanup(self):
        """Clean up resources"""
        print("🧹 Cleaning up...")

        # Stop and remove container
        if self.container_id:
            try:
                subprocess.run(
                    ["docker", "stop", self.container_id],
                    capture_output=True,
                    check=True,
                )
                subprocess.run(
                    ["docker", "rm", self.container_id],
                    capture_output=True,
                    check=True,
                )
                print(f"   ✓ Container removed: {self.container_id[:12]}")
            except subprocess.CalledProcessError:
                print(
                    f"   ⚠ Failed to remove container: {self.container_id[:12]}",
                )

        # Optionally remove image (uncomment if you want to clean up)
        # if self.image_name:
        #     try:
        #         subprocess.run(["docker", "rmi", self.image_name],
        #                      capture_output=True, check=True)
        #         print(f"   ✓ Image removed: {self.image_name}")
        #     except subprocess.CalledProcessError:
        #         print(f"   ⚠ Failed to remove image: {self.image_name}")


async def main():
    """Main demonstration function"""
    print("=" * 80)
    print("🚀 LLMAgent Deployment with New Configuration Architecture")
    print("=" * 80)

    demo = LLMAgentDeploymentExample()

    try:
        # Step 1: Check prerequisites
        demo.check_prerequisites()

        # Step 2: Create LLMAgent runner
        runner = demo.create_llm_agent_runner()

        # Step 3: Build Docker image
        build_success = await demo.build_docker_image(runner)
        if not build_success:
            print("❌ Build failed, cannot proceed")
            return False

        # Step 4: Run container
        run_success = await demo.run_container()
        if not run_success:
            print("❌ Container run failed")
            return False

        # Step 5: Test service
        test_success = demo.test_service()

        # Step 6: Show logs
        demo.get_container_logs()

        if test_success:
            print("\n" + "=" * 80)
            print("🎉 DEPLOYMENT SUCCESSFUL!")
            print("✅ Your LLMAgent is running in a Docker container!")
            print(f"✅ Service URL: http://localhost:{HOST_PORT}")
            print("✅ Endpoints available:")
            print(f"   - Health: http://localhost:{HOST_PORT}/health")
            print(f"   - Chat: http://localhost:{HOST_PORT}/chat (POST)")
            print("=" * 80)

            print("\n🔍 Example curl command to test:")
            print(
                f"""curl -X POST http://localhost:{HOST_PORT}/chat \\
  -H "Content-Type: application/json" \\
  -d '{{
    "input": [{{"role": "user", "content": [{{"type": "text", "text": "Hello from deployed LLMAgent!"}}]}}],
    "session_id": "test_session"
  }}'""",
            )

            print(
                "\n⏸️ Press Ctrl+C to stop the demo and clean up resources...",
            )

            # Keep running until user interrupts
            try:
                while True:
                    await asyncio.sleep(1)
            except KeyboardInterrupt:
                print("\n🛑 Stopping demo...")
        else:
            print("❌ Service testing failed")
            return False

    except KeyboardInterrupt:
        print("\n🛑 Demo interrupted by user")
    except Exception as e:
        print(f"❌ Demo failed: {e}")
        import traceback

        traceback.print_exc()
        return False

    finally:
        # Always cleanup
        demo.cleanup()

    return True


def quick_test_example():
    """Quick test without full deployment - just test ImageBuilder"""
    print("🧪 Quick Test: ImageBuilder Configuration Generation")
    print("-" * 60)

    try:
        # Create a simple mock runner
        class MockRunner:
            def __init__(self):
                self._agent = MockAgent()
                self._context_manager = None
                self._environment_manager = None

        class MockAgent:
            def __init__(self):
                self.name = "quick_test_agent"
                self.description = "Quick test agent"
                self.model = MockLLM()

        class MockLLM:
            def __init__(self):
                self.model_name = "qwen-max"
                self.api_key = "test_key"
                self.temperature = 0.7
                self.max_tokens = 2048

        runner = MockRunner()
        print(f"✓ Created mock runner: {runner._agent.name}")

        # Test configuration extraction
        from agentscope_runtime.engine.deployers.kubernetes_deployer import (
            ImageBuilder,
            RegistryConfig,
        )

        registry_config = RegistryConfig()
        image_builder = ImageBuilder(registry_config)

        config = image_builder._extract_runner_config(runner)
        print("✓ Configuration extracted:")
        print(json.dumps(config, indent=2, default=str))

        print("🎉 Quick test passed! ImageBuilder is working correctly.")
        return True

    except ImportError as e:
        print(f"❌ Import failed: {e}")
        print(
            "Please install agentscope-runtime with: pip install -e '.[sandbox]'",
        )
        return False
    except Exception as e:
        print(f"❌ Quick test failed: {e}")
        return False


if __name__ == "__main__":
    print("Choose demo mode:")
    print("1. Full deployment demo (requires Docker)")
    print("2. Quick test (configuration only)")

    try:
        choice = input("Enter choice (1 or 2): ").strip()

        if choice == "1":
            success = asyncio.run(main())
        elif choice == "2":
            success = quick_test_example()
        else:
            print("Invalid choice")
            success = False

        sys.exit(0 if success else 1)

    except KeyboardInterrupt:
        print("\n🛑 Demo interrupted")
        sys.exit(0)
