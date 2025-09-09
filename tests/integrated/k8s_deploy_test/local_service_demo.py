#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Local Service Test: LLMAgent -> Configuration -> Entrypoint -> Running Service

This script tests the complete pipeline locally without Docker/K8s:
1. Create a basic LLMAgent
2. Extract configuration (no pickle!)
3. Generate runner_entrypoint.py using _create_runner_entrypoint method
4. Start local service on specified port
5. Test the service endpoints

Run this before deploying to K8s to verify everything works.
"""

import os
import sys
import json
import pickle
import tempfile
import asyncio
import subprocess
import time
import shutil
import signal
from pathlib import Path

# Add agentscope-runtime to path
current_dir = os.path.dirname(os.path.abspath(__file__))
repo_root = os.path.join(current_dir, "../../../")
src_dir = os.path.join(repo_root, "src")
sys.path.insert(0, src_dir)

LOCAL_SERVICE_PORT = 8093


class LocalService:
    def __init__(self):
        self.test_dir = None
        self.service_process = None
        self.runner = None

    def create_test_llm_agent(self):
        """Create a test LLMAgent"""
        print("🤖 Creating test LLMAgent...")

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
                api_key=os.getenv("DASHSCOPE_API_KEY", "test_api_key"),
                temperature=0.7,
                max_tokens=2048,
            )

            # Create LLMAgent
            agent = LLMAgent(
                model=llm_model,
                name="local_test_agent",
                description="Local test LLM agent",
            )

            # Create context manager
            session_service = InMemorySessionHistoryService()
            context_manager = ContextManager(
                session_history_service=session_service,
            )

            # Create runner
            runner = Runner(
                agent=agent,
                context_manager=context_manager,
                environment_manager=None,
            )

            print(f"   ✅ Real LLMAgent created: {agent.name}")
            print(f"   ✅ Model: {llm_model.model_name}")
            return runner, True

        except ImportError as e:
            print(f"   ⚠ Cannot create real LLMAgent: {e}")
            return self.create_mock_llm_agent(), False
        except Exception as e:
            print(f"   ⚠ Error creating real LLMAgent: {e}")
            return self.create_mock_llm_agent(), False

    def create_mock_llm_agent(self):
        """Create mock LLMAgent when real one fails"""
        print("   🎭 Using mock LLMAgent...")

        class MockRunner:
            def __init__(self):
                self._agent = MockAgent()
                self._context_manager = MockContextManager()
                self._environment_manager = None

        class MockAgent:
            def __init__(self):
                self.name = "mock_local_test_agent"
                self.description = "Mock LLM agent for local testing"
                self.model = MockLLM()

        class MockLLM:
            def __init__(self):
                self.model_name = "qwen-max"
                self.api_key = os.getenv("DASHSCOPE_API_KEY", "mock_test_key")
                self.temperature = 0.7
                self.max_tokens = 2048
                self.base_url = None

        class MockContextManager:
            pass

        return MockRunner()

    def setup_test_directory(self):
        """Setup test directory"""
        print("🔧 Setting up test directory...")

        self.test_dir = tempfile.mkdtemp(prefix="local_service_test_")
        print(f"   Test directory: {self.test_dir}")

        # Copy user code to test directory
        user_code_dir = os.path.join(self.test_dir, "user_code")
        shutil.copytree(current_dir, user_code_dir, dirs_exist_ok=True)
        print(f"   ✅ User code copied")

        return True

    def extract_and_save_configuration(self, runner):
        """Extract configuration and save files"""
        print("📋 Extracting and saving configuration...")

        try:
            # Use actual ImageBuilder method
            from agentscope_runtime.engine.deployers.kubernetes_deployer import (
                ImageBuilder,
                RegistryConfig,
            )

            registry_config = RegistryConfig()
            image_builder = ImageBuilder(registry_config)

            # Extract configuration using actual method
            config = image_builder._extract_runner_config(runner)
            print("   ✅ Used actual _extract_runner_config method")

        except Exception as e:
            print(f"   ⚠ Using fallback config extraction: {e}")
            # Fallback extraction
            config = {
                "runner_type": "runtime_runner",
                "agent_config": {
                    "class": f"{runner._agent.__class__.__module__}.{runner._agent.__class__.__name__}",
                    "name": getattr(runner._agent, "name", "default_agent"),
                    "description": getattr(runner._agent, "description", ""),
                    "config": {},
                    "model": {
                        "class": f"{runner._agent.model.__class__.__module__}.{runner._agent.model.__class__.__name__}",
                        "config": {},
                    },
                },
                "context_manager_config": {
                    "class": f"{runner._context_manager.__class__.__module__}.{runner._context_manager.__class__.__name__}",
                    "config": {},
                }
                if runner._context_manager
                else None,
            }

            # Extract model parameters
            for attr in [
                "model_name",
                "api_key",
                "base_url",
                "temperature",
                "max_tokens",
            ]:
                if hasattr(runner._agent.model, attr):
                    value = getattr(runner._agent.model, attr)
                    if value is not None:
                        config["agent_config"]["model"]["config"][attr] = value

        # Save runner configuration
        runner_config_file = os.path.join(self.test_dir, "runner_config.json")
        with open(runner_config_file, "w") as f:
            json.dump(config, f, indent=2, default=str)
        print(
            f"   ✅ Saved runner_config.json ({os.path.getsize(runner_config_file)} bytes)",
        )

        # Save deploy configuration
        deploy_config = {
            "stream": True,
            "endpoint_path": "/chat",
            "kwargs": {},
        }
        deploy_config_file = os.path.join(self.test_dir, "deploy_config.pkl")
        with open(deploy_config_file, "wb") as f:
            pickle.dump(deploy_config, f)
        print(
            f"   ✅ Saved deploy_config.pkl ({os.path.getsize(deploy_config_file)} bytes)",
        )

        return True

    async def generate_runner_entrypoint(self):
        """Generate runner_entrypoint.py using actual _create_runner_entrypoint method"""
        print("📝 Generating runner_entrypoint.py...")

        try:
            # Use actual _create_runner_entrypoint method
            from agentscope_runtime.engine.deployers.kubernetes_deployer import (
                ImageBuilder,
                RegistryConfig,
            )

            registry_config = RegistryConfig()
            image_builder = ImageBuilder(registry_config)

            # Call the actual method
            await image_builder._create_runner_entrypoint(self.test_dir)

            entrypoint_file = os.path.join(
                self.test_dir,
                "runner_entrypoint.py",
            )
            if os.path.exists(entrypoint_file):
                size = os.path.getsize(entrypoint_file)
                print(
                    f"   ✅ Used actual _create_runner_entrypoint method ({size} bytes)",
                )
                return True
            else:
                print("   ❌ Entrypoint file not created by actual method")
                return False

        except Exception as e:
            print(
                f"   ❌ Failed to use actual _create_runner_entrypoint method: {e}",
            )
            return False

    async def start_local_service(self):
        """Start the local service using generated entrypoint"""
        print(f"🚀 Starting local service on port {LOCAL_SERVICE_PORT}...")

        # Setup environment
        env = os.environ.copy()
        env["PORT"] = str(LOCAL_SERVICE_PORT)
        env[
            "PYTHONPATH"
        ] = f"{src_dir}:{self.test_dir}:{env.get('PYTHONPATH', '')}"

        # Path to entrypoint
        entrypoint_file = os.path.join(self.test_dir, "runner_entrypoint.py")

        try:
            # Start service process
            self.service_process = subprocess.Popen(
                [sys.executable, entrypoint_file],
                cwd=self.test_dir,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=os.setsid,  # Create new process group
            )

            # Wait for startup
            print("   ⏳ Waiting for service to start...")
            await asyncio.sleep(5)

            # Check if still running
            if self.service_process.poll() is None:
                print(
                    f"   ✅ Service started successfully on port {LOCAL_SERVICE_PORT}",
                )
                return True
            else:
                stdout, stderr = self.service_process.communicate()
                print(f"   ❌ Service failed to start")
                print(f"   STDOUT: {stdout.decode()[:500]}")
                print(f"   STDERR: {stderr.decode()[:500]}")
                return False

        except Exception as e:
            print(f"   ❌ Failed to start service: {e}")
            return False

    async def test_service_endpoints(self):
        """Test the running service endpoints"""
        print("🌐 Testing service endpoints...")

        import urllib.request
        import urllib.parse

        base_url = f"http://localhost:{LOCAL_SERVICE_PORT}"

        # Test health endpoint
        try:
            print("   Testing /health...")
            with urllib.request.urlopen(
                f"{base_url}/health",
                timeout=10,
            ) as response:
                health_data = json.loads(response.read().decode())
                print(f"   ✅ Health: {health_data}")
        except Exception as e:
            print(f"   ❌ Health check failed: {e}")
            return False

        # Test readiness
        try:
            print("   Testing /readiness...")
            with urllib.request.urlopen(
                f"{base_url}/readiness",
                timeout=10,
            ) as response:
                readiness = response.read().decode()
                print(f"   ✅ Readiness: {readiness}")
        except Exception as e:
            print(f"   ⚠ Readiness check failed: {e}")

        # Test root endpoint
        try:
            print("   Testing / endpoint...")
            with urllib.request.urlopen(
                f"{base_url}/",
                timeout=10,
            ) as response:
                root_data = json.loads(response.read().decode())
                print(f"   ✅ Root: {root_data}")
        except Exception as e:
            print(f"   ⚠ Root endpoint failed: {e}")

        # Test chat endpoint
        try:
            print("   Testing /chat endpoint...")
            test_data = {
                "input": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Hello from local test!"},
                        ],
                    },
                ],
                "session_id": "local_test_session",
                "stream": False,
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
            print(f"   ❌ Chat endpoint failed: {e}")
            return False

    def show_service_info(self):
        """Show service information"""
        print("\n📋 Service Information:")
        print(f"   🌐 Service URL: http://localhost:{LOCAL_SERVICE_PORT}")
        print(f"   📁 Test directory: {self.test_dir}")
        print(f"   📄 Files created:")
        if self.test_dir:
            for item in os.listdir(self.test_dir):
                if item.endswith((".py", ".json", ".pkl")):
                    size = os.path.getsize(os.path.join(self.test_dir, item))
                    print(f"      - {item} ({size} bytes)")

        print(f"\n🧪 Test commands:")
        print(f"   # Health check")
        print(f"   curl http://localhost:{LOCAL_SERVICE_PORT}/health")

        print(f"\n   # Chat with agent")
        print(
            f"""   curl -X POST http://localhost:{LOCAL_SERVICE_PORT}/chat \\
     -H "Content-Type: application/json" \\
     -d '{{"input": [{{"role": "user", "content": [{{"type": "text", "text": "Hello!"}}]}}], "session_id": "test"}}'""",
        )

    def get_service_logs(self):
        """Get service logs"""
        if self.service_process:
            print("\n📋 Recent service logs:")
            try:
                # Non-blocking read
                import select

                ready, _, _ = select.select(
                    [self.service_process.stdout],
                    [],
                    [],
                    0.1,
                )
                if ready:
                    output = self.service_process.stdout.read(1024).decode()
                    if output:
                        for line in output.split("\n")[-10:]:
                            if line.strip():
                                print(f"   {line}")

                ready, _, _ = select.select(
                    [self.service_process.stderr],
                    [],
                    [],
                    0.1,
                )
                if ready:
                    error = self.service_process.stderr.read(1024).decode()
                    if error:
                        print("   STDERR:")
                        for line in error.split("\n")[-5:]:
                            if line.strip():
                                print(f"   {line}")

            except Exception as e:
                print(f"   ❌ Failed to get logs: {e}")

    def cleanup(self):
        """Clean up resources"""
        print("\n🧹 Cleaning up...")

        # Stop service
        if self.service_process:
            try:
                # Kill process group
                os.killpg(os.getpgid(self.service_process.pid), signal.SIGTERM)
                self.service_process.wait(timeout=5)
                print("   ✅ Service stopped")
            except (ProcessLookupError, subprocess.TimeoutExpired):
                try:
                    os.killpg(
                        os.getpgid(self.service_process.pid),
                        signal.SIGKILL,
                    )
                    print("   ✅ Service killed")
                except ProcessLookupError:
                    print("   ✅ Service already stopped")
            except Exception as e:
                print(f"   ⚠ Error stopping service: {e}")

        # Optionally remove test directory (comment out if you want to inspect)
        if self.test_dir and os.path.exists(self.test_dir):
            try:
                # Ask user if they want to keep the test directory
                keep = (
                    input("   Keep test directory for inspection? (y/N): ")
                    .strip()
                    .lower()
                )
                if keep != "y":
                    shutil.rmtree(self.test_dir)
                    print("   ✅ Test directory removed")
                else:
                    print(f"   📁 Test directory preserved: {self.test_dir}")
            except KeyboardInterrupt:
                print(f"   📁 Test directory preserved: {self.test_dir}")


async def run_local_service():
    """Run the local service test"""
    print("🚀 Local Service Test: LLMAgent -> Config -> Entrypoint -> Service")
    print("🎯 Testing configuration pipeline and service startup")
    print("=" * 70)

    tester = LocalService()
    success = True

    try:
        # Step 1: Setup
        tester.setup_test_directory()

        # Step 2: Create LLMAgent
        runner, is_real = tester.create_test_llm_agent()
        tester.runner = runner
        print(f"   Agent type: {'Real' if is_real else 'Mock'}")

        # Step 3: Extract and save configuration
        config_success = tester.extract_and_save_configuration(runner)
        if not config_success:
            print("❌ Configuration extraction failed!")
            return False

        # Step 4: Generate runner entrypoint using actual method
        entrypoint_success = await tester.generate_runner_entrypoint()
        if not entrypoint_success:
            print("❌ Entrypoint generation failed!")
            return False

        # Step 5: Start local service
        service_success = await tester.start_local_service()
        if not service_success:
            print("❌ Service startup failed!")
            return False

        # Step 6: Test service endpoints
        test_success = await tester.test_service_endpoints()

        # Step 7: Show service info
        tester.show_service_info()

        if test_success:
            print(f"\n🎉 LOCAL SERVICE TEST PASSED!")
            print("✅ Complete pipeline working:")
            print("   ✓ LLMAgent creation")
            print("   ✓ Configuration extraction (no pickle serialization!)")
            print("   ✓ runner_entrypoint.py generation using actual method")
            print("   ✓ Local service startup")
            print("   ✓ API endpoints responding")
            print("   ✓ Health checks passing")

            print(
                f"\n🌐 Your service is running at: http://localhost:{LOCAL_SERVICE_PORT}",
            )
            print("Press Ctrl+C when you want to stop the service...")

            # Keep service running until user interrupts
            try:
                while True:
                    await asyncio.sleep(1)
            except KeyboardInterrupt:
                print(f"\n🛑 Service stopped by user")
        else:
            print("❌ Service testing failed!")
            success = False

    except KeyboardInterrupt:
        print(f"\n🛑 Test interrupted by user")
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        success = False

    finally:
        # Get final logs
        tester.get_service_logs()

        # Always cleanup
        tester.cleanup()

    return success


def main():
    """Main function"""
    print("Local Service Test for LLMAgent Configuration Pipeline")
    print(f"Working directory: {current_dir}")
    print("This test runs the complete pipeline locally before K8s deployment")

    try:
        success = asyncio.run(run_local_service())
        return success
    except KeyboardInterrupt:
        print("\n🛑 Test interrupted")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
