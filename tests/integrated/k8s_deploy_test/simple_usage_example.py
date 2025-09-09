#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Simple Usage Example: ImageBuilder with LLMAgent

This example shows the minimal code needed to use the new configuration-driven
ImageBuilder to build and deploy an LLMAgent.
"""

import os
import sys
import asyncio

# Add agentscope-runtime to path
current_dir = os.path.dirname(os.path.abspath(__file__))
repo_root = os.path.join(current_dir, "../../../")
src_dir = os.path.join(repo_root, "src")
sys.path.insert(0, src_dir)


async def simple_llm_deployment():
    """Simple example of LLMAgent deployment"""

    print("🚀 Simple LLMAgent Deployment Example")
    print("=" * 50)

    try:
        # Step 1: Import required components
        from agentscope_runtime.engine.agents.llm_agent import LLMAgent
        from agentscope_runtime.engine.llms.qwen_llm import QwenLLM
        from agentscope_runtime.engine.runner import Runner
        from agentscope_runtime.engine.services.context_manager import (
            ContextManager,
        )
        from agentscope_runtime.engine.services.session_history_service import (
            InMemorySessionHistoryService,
        )
        from agentscope_runtime.engine.deployers.kubernetes_deployer import (
            ImageBuilder,
            RegistryConfig,
            BuildConfig,
        )

        print("✅ All imports successful")

        # Step 2: Create LLMAgent
        print("\n🤖 Creating LLMAgent...")

        llm_model = QwenLLM(
            model_name="qwen-max",
            api_key=os.getenv("DASHSCOPE_API_KEY", "your_api_key_here"),
            temperature=0.7,
            max_tokens=2048,
        )

        agent = LLMAgent(
            model=llm_model,
            name="simple_demo_agent",
            description="Simple demo LLM agent",
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

        runner.deploy()

        print(f"✅ LLMAgent created: {agent.name}")

        # Step 3: Setup ImageBuilder
        print("\n🏗️ Setting up ImageBuilder...")

        registry_config = RegistryConfig(
            registry_url="your-registry.com",  # Replace with your registry
            namespace="your-namespace",
        )

        build_config = BuildConfig(
            build_context_dir="/tmp/my_agent_build",
            cleanup_after_build=False,  # Keep build artifacts for inspection
        )

        image_builder = ImageBuilder(registry_config, build_config)
        print("✅ ImageBuilder configured")

        # Step 4: Build Docker image
        print("\n🔨 Building Docker image...")

        # This is the main call - everything else is automated!
        image_tag = await image_builder.build_runner_image(
            runner=runner,  # Your complete LLMAgent runner
            requirements=[  # Additional Python dependencies
                "requests>=2.32.4",
                "numpy>=1.24.0",
            ],
            user_code_path=current_dir,  # Your user code directory
            base_image="python:3.9-slim",  # Docker base image
            stream=True,  # Enable streaming responses
            endpoint_path="/chat",  # Custom API endpoint
            # Environment variables will be injected at runtime
        )

        full_image_name = f"{registry_config.registry_url}/{image_tag}"
        print(f"✅ Image built: {full_image_name}")

        # Step 5: Show what was created
        print("\n📁 Build artifacts created:")
        build_dir = os.path.join(build_config.build_context_dir, image_tag)
        if os.path.exists(build_dir):
            for item in os.listdir(build_dir):
                print(f"   - {item}")

        print(
            "\n🎉 Success! Your LLMAgent is containerized and ready to deploy!",
        )

        # Step 6: Show next steps
        print("\n📋 Next steps:")
        print("1. Push to registry:")
        print(f"   docker push {full_image_name}")
        print("\n2. Run locally:")
        print(
            f"   docker run -p 8090:8090 -e DASHSCOPE_API_KEY=$DASHSCOPE_API_KEY {full_image_name}",
        )
        print("\n3. Deploy to Kubernetes:")
        print("   (Use your K8s deployment manifests)")

        return True

    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("Please install agentscope-runtime with sandbox dependencies:")
        print("   pip install -e '.[sandbox]'")
        return False

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()
        return False


def configuration_only_example():
    """Example showing just the configuration extraction without building"""

    print("📋 Configuration Extraction Example")
    print("=" * 40)

    try:
        # Create a mock runner for demonstration
        class MockRunner:
            def __init__(self):
                self._agent = MockAgent()
                self._context_manager = MockContextManager()
                self._environment_manager = None

        class MockAgent:
            def __init__(self):
                self.name = "config_demo_agent"
                self.description = "Agent for configuration demo"
                self.model = MockLLM()

        class MockLLM:
            def __init__(self):
                self.model_name = "qwen-max"
                self.api_key = os.getenv("DASHSCOPE_API_KEY", "demo_key")
                self.temperature = 0.8
                self.max_tokens = 1024
                self.base_url = None

        class MockContextManager:
            pass

        runner = MockRunner()
        print(f"✅ Mock runner created: {runner._agent.name}")

        # Extract configuration using ImageBuilder
        from agentscope_runtime.engine.deployers.kubernetes_deployer import (
            ImageBuilder,
            RegistryConfig,
        )

        registry_config = RegistryConfig()
        image_builder = ImageBuilder(registry_config)

        # This is the key method - extracts all configuration
        config = image_builder._extract_runner_config(runner)

        print("\n📋 Extracted configuration:")
        import json

        print(json.dumps(config, indent=2, default=str))

        print("\n✅ Configuration extraction successful!")
        print(
            "This JSON config will be used to rebuild the runner in the container",
        )

        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        return False


# Usage patterns for different scenarios
def usage_examples():
    """Show different usage patterns"""

    print("\n" + "=" * 60)
    print("📖 USAGE PATTERNS")
    print("=" * 60)

    print(
        """
🔥 BASIC USAGE:
```python
# 1. Create your LLMAgent
runner = create_your_llm_agent()  # Your existing code

# 2. Setup ImageBuilder
image_builder = ImageBuilder(RegistryConfig(registry_url="your-registry"))

# 3. Build image - ONE LINE!
image_tag = await image_builder.build_runner_image(runner=runner)
```

🚀 KUBERNETES DEPLOYMENT:
```python
# Use KubernetesDeployer for full K8s deployment
deployer = KubernetesDeployer(k8s_config, registry_config)

result = await deployer.deploy(
    runner=runner,
    user_code_path="./my_agent_code",
    replicas=3,
    environment={"DASHSCOPE_API_KEY": "..."}
)

print(f"Deployed at: {result['url']}")
```

🏠 LOCAL CONTAINER:
```bash
# After building image
docker run -p 8090:8090 \\
  -e DASHSCOPE_API_KEY="your_key" \\
  your-registry/your-image

# Test the service
curl -X POST http://localhost:8090/chat \\
  -H "Content-Type: application/json" \\
  -d '{"input": [{"role": "user", "content": [{"type": "text", "text": "Hello!"}]}]}'
```

💡 ENVIRONMENT VARIABLES:
The new architecture supports environment variable injection:
- DASHSCOPE_API_KEY: Your API key (injected at runtime)
- LOG_LEVEL: Logging level (INFO, DEBUG, etc.)
- Any custom environment variables

🔧 ADVANCED CONFIGURATION:
```python
await image_builder.build_runner_image(
    runner=runner,
    requirements=["your-custom-package>=1.0.0"],
    user_code_path="./my_utilities",
    base_image="python:3.10-slim",
    stream=True,
    endpoint_path="/my-custom-endpoint",
    image_tag="my-custom-agent-v1.0"
)
```
    """,
    )


if __name__ == "__main__":
    print("Choose example:")
    print("1. Full deployment example")
    print("2. Configuration extraction only")
    print("3. Show usage patterns")

    try:
        choice = input("Enter choice (1/2/3): ").strip()

        if choice == "1":
            success = asyncio.run(simple_llm_deployment())
        elif choice == "2":
            success = configuration_only_example()
        elif choice == "3":
            usage_examples()
            success = True
        else:
            print("Invalid choice")
            success = False

        if success:
            print("\n🎉 Example completed successfully!")
        else:
            print("\n❌ Example failed")

        sys.exit(0 if success else 1)

    except KeyboardInterrupt:
        print("\n🛑 Interrupted by user")
        sys.exit(0)
