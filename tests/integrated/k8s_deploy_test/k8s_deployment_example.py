#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Kubernetes Deployment Example with New Configuration Architecture

This example shows how to deploy LLMAgent to Kubernetes using the new
configuration-driven architecture that eliminates pickle serialization issues.
"""

import os
import sys
import asyncio
from dataclasses import dataclass
from typing import Optional

# Add agentscope-runtime to path
current_dir = os.path.dirname(os.path.abspath(__file__))
repo_root = os.path.join(current_dir, "../../../")
src_dir = os.path.join(repo_root, "src")
sys.path.insert(0, src_dir)


@dataclass
class K8sConfig:
    """Kubernetes configuration"""

    kubeconfig_path: Optional[str] = None
    k8s_namespace: str = "default"
    cluster_name: str = "default"


async def kubernetes_deployment_example():
    """Complete Kubernetes deployment example"""

    print("🚀 Kubernetes LLMAgent Deployment Example")
    print("=" * 60)

    try:
        # Step 1: Import all required components
        print("📦 Importing components...")

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
            KubernetesDeployer,
            RegistryConfig,
            BuildConfig,
            ImageBuilder,
        )

        print("✅ All components imported successfully")

        # Step 2: Create LLMAgent Runner
        print("\n🤖 Creating LLMAgent Runner...")

        # Create QwenLLM model
        llm_model = QwenLLM(
            model_name="qwen-max",
            api_key=os.getenv("DASHSCOPE_API_KEY", "your_dashscope_key"),
            temperature=0.7,
            max_tokens=2048,
        )

        # Create LLMAgent
        agent = LLMAgent(
            model=llm_model,
            name="k8s_demo_agent",
            description="Kubernetes deployment demo LLM agent",
        )

        # Create context manager
        session_service = InMemorySessionHistoryService()
        context_manager = ContextManager(
            session_history_service=session_service,
        )

        # Create complete runner
        runner = Runner(
            agent=agent,
            context_manager=context_manager,
            environment_manager=None,
        )

        print(f"✅ Runner created with agent: {agent.name}")

        # Step 3: Setup Kubernetes Configuration
        print("\n⚙️ Setting up Kubernetes configuration...")

        # Kubernetes cluster config
        k8s_config = K8sConfig(
            kubeconfig_path=None,  # Use default kubeconfig
            k8s_namespace="default",
            cluster_name="minikube",  # Adjust for your cluster
        )

        # Container registry config
        registry_config = RegistryConfig(
            registry_url="your-registry.com",  # Replace with your registry
            username=os.getenv("REGISTRY_USERNAME"),
            password=os.getenv("REGISTRY_PASSWORD"),
            namespace="llm-agents",
        )

        # Image build config
        build_config = BuildConfig(
            build_context_dir="/tmp/k8s_llm_build",
            cleanup_after_build=False,  # Keep for debugging
            build_timeout=900,  # 15 minutes
            push_timeout=600,  # 10 minutes
        )

        print("✅ Kubernetes configuration ready")

        # Step 4: Create KubernetesDeployer
        print("\n🏗️ Creating Kubernetes Deployer...")

        deployer = KubernetesDeployer(
            k8s_config=k8s_config,
            registry_config=registry_config,
            image_builder=ImageBuilder(registry_config, build_config),
            use_deployment=True,  # Use Deployment for scaling
        )

        print("✅ KubernetesDeployer created")

        # Step 5: Deploy to Kubernetes
        print("\n🚀 Deploying to Kubernetes...")
        print("This will:")
        print(
            "  1. Extract runner configuration (NEW: No pickle serialization!)",
        )
        print("  2. Build Docker image with runner config")
        print("  3. Push image to registry")
        print("  4. Create Kubernetes Deployment")
        print("  5. Create Service with NodePort")
        print("  6. Wait for deployment to be ready")

        # This is the main deployment call
        result = await deployer.deploy(
            runner=runner,  # Complete LLMAgent runner
            endpoint_path="/chat",  # Custom API endpoint
            stream=True,  # Enable streaming
            requirements=[  # Additional dependencies
                "requests>=2.32.4",
                "numpy>=1.24.0",
                "pandas>=1.5.0",
            ],
            user_code_path=current_dir,  # Include your utilities
            base_image="python:3.9-slim",  # Base Docker image
            port=8090,  # Container port
            replicas=2,  # Scale to 2 replicas
            environment={  # Environment variables
                "DASHSCOPE_API_KEY": os.getenv("DASHSCOPE_API_KEY"),
                "LOG_LEVEL": "INFO",
                "ENVIRONMENT": "production",
            },
            runtime_config={  # Kubernetes runtime config
                "resources": {
                    "requests": {"memory": "512Mi", "cpu": "250m"},
                    "limits": {"memory": "1Gi", "cpu": "500m"},
                },
                "image_pull_policy": "Always",
            },
            deploy_timeout=600,  # 10 minutes timeout
            health_check=True,  # Enable health checks
        )

        print(f"\n🎉 Deployment successful!")
        print(f"✅ Deploy ID: {result['deploy_id']}")
        print(f"✅ Service URL: {result['url']}")
        print(f"✅ Resource Name: {result['resource_name']}")
        print(f"✅ Replicas: {result['replicas']}")

        # Step 6: Show service status
        print(f"\n📊 Service Status:")
        status = deployer.get_status()
        print(f"   Status: {status}")

        replicas_info = deployer.get_current_replicas()
        print(f"   Replicas: {replicas_info}")

        service_url = deployer.service_url
        print(f"   Service URL: {service_url}")

        # Step 7: Test the deployed service
        print(f"\n🧪 Testing deployed service...")

        health_ok = await deployer.health_check()
        print(f"   Health check: {'✅ Pass' if health_ok else '❌ Fail'}")

        # Step 8: Show usage examples
        print(f"\n📋 Usage Examples:")
        print(f"Health check:")
        print(f"  curl {result['url']}/health")

        print(f"\nChat with your LLMAgent:")
        print(
            f"""  curl -X POST {result['url']}/chat \\
    -H "Content-Type: application/json" \\
    -d '{{
      "input": [{{"role": "user", "content": [{{"type": "text", "text": "Hello from Kubernetes!"}}]}}],
      "session_id": "k8s_session"
    }}'""",
        )

        # Step 9: Management operations
        print(f"\n🔧 Management Operations:")

        print("Scaling:")
        print("  # Scale up to 3 replicas")
        print(f"  await deployer.scale(3)")

        print("Getting logs:")
        print("  logs = deployer.get_logs()")
        print("  print(logs)")

        print("Inspection:")
        print("  info = deployer.inspect()")
        print("  print(info)")

        print("Stopping (scale to 0):")
        print("  await deployer.stop()")

        print("Restarting:")
        print("  await deployer.restart()")

        print("Complete removal:")
        print("  await deployer.remove()")

        # Step 10: Keep running or cleanup
        print(f"\n⏸️ Deployment is running. Choose next action:")
        print("1. Keep running (press Enter)")
        print("2. Scale to 3 replicas")
        print("3. Get logs")
        print("4. Stop deployment")
        print("5. Remove completely")

        try:
            choice = input("Enter choice (1-5): ").strip()

            if choice == "2":
                print("Scaling to 3 replicas...")
                scale_result = await deployer.scale(3)
                print(f"Scale result: {scale_result}")

            elif choice == "3":
                print("Getting logs...")
                logs = deployer.get_logs()
                print("Recent logs:")
                print(logs)

            elif choice == "4":
                print("Stopping deployment...")
                stop_result = await deployer.stop()
                print(f"Stop result: {stop_result}")

            elif choice == "5":
                print("Removing deployment completely...")
                remove_result = await deployer.remove()
                print(f"Remove result: {remove_result}")

            else:
                print("Keeping deployment running...")
                print("Use kubectl to manage your deployment:")
                print(f"  kubectl get pods -l app={result['resource_name']}")
                print(f"  kubectl logs -l app={result['resource_name']}")

        except KeyboardInterrupt:
            print("\n🛑 Interrupted by user")

        return True

    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("Please install agentscope-runtime with sandbox dependencies:")
        print("   pip install -e '.[sandbox]'")
        return False

    except Exception as e:
        print(f"❌ Deployment error: {e}")
        import traceback

        traceback.print_exc()
        return False


def kubernetes_prerequisites_check():
    """Check Kubernetes deployment prerequisites"""

    print("🔍 Kubernetes Prerequisites Check")
    print("-" * 40)

    issues = []

    # Check kubectl
    try:
        import subprocess

        result = subprocess.run(
            ["kubectl", "version", "--client"],
            capture_output=True,
            text=True,
            check=True,
        )
        print("✅ kubectl available")
    except (subprocess.CalledProcessError, FileNotFoundError):
        issues.append("kubectl not available")
        print("❌ kubectl not found")

    # Check Docker
    try:
        result = subprocess.run(
            ["docker", "--version"],
            capture_output=True,
            text=True,
            check=True,
        )
        print("✅ Docker available")
    except (subprocess.CalledProcessError, FileNotFoundError):
        issues.append("Docker not available")
        print("❌ Docker not found")

    # Check cluster connection
    try:
        result = subprocess.run(
            ["kubectl", "cluster-info"],
            capture_output=True,
            text=True,
            check=True,
        )
        print("✅ Kubernetes cluster accessible")
    except subprocess.CalledProcessError:
        issues.append("Cannot access Kubernetes cluster")
        print("❌ Cannot access Kubernetes cluster")

    # Check environment variables
    api_key = os.getenv("DASHSCOPE_API_KEY")
    if api_key:
        print("✅ DASHSCOPE_API_KEY set")
    else:
        issues.append("DASHSCOPE_API_KEY not set")
        print("❌ DASHSCOPE_API_KEY not set")

    registry_user = os.getenv("REGISTRY_USERNAME")
    registry_pass = os.getenv("REGISTRY_PASSWORD")
    if registry_user and registry_pass:
        print("✅ Registry credentials set")
    else:
        issues.append("Registry credentials not set")
        print("⚠️  Registry credentials not set (optional)")

    if issues:
        print(f"\n❌ Found {len(issues)} issues:")
        for issue in issues:
            print(f"   - {issue}")
        print("\nPlease fix these issues before deploying to Kubernetes")
        return False
    else:
        print("\n✅ All prerequisites met! Ready for Kubernetes deployment")
        return True


if __name__ == "__main__":
    print("Kubernetes LLMAgent Deployment")
    print("Choose option:")
    print("1. Check prerequisites")
    print("2. Run full deployment example")

    try:
        choice = input("Enter choice (1/2): ").strip()

        if choice == "1":
            success = kubernetes_prerequisites_check()
        elif choice == "2":
            success = asyncio.run(kubernetes_deployment_example())
        else:
            print("Invalid choice")
            success = False

        sys.exit(0 if success else 1)

    except KeyboardInterrupt:
        print("\n🛑 Interrupted by user")
        sys.exit(0)
