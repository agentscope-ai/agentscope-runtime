# -*- coding: utf-8 -*-
# pylint:disable=wrong-import-position, wrong-import-order
import asyncio
import os
import sys

from agentscope_runtime.engine.deployers.kubernetes_deployer import (
    KubernetesDeployManager,
    RegistryConfig,
    K8sConfig,
)
from agentscope_runtime.engine.runner import Runner

sys.path.insert(0, os.path.dirname(__file__))

from agent_run import llm_agent  # noqa: E402


async def deploy_agent_to_k8s():
    """Deploy agent to Kubernetes"""

    # 1. Configure Registry
    registry_config = RegistryConfig(
        registry_url=(
            "crpi-p44cuw4wgxu8xn0b.cn-hangzhou.personal.cr.aliyuncs.com"
        ),
        namespace="agentscope-runtime",
    )

    # 3. Configure K8s connection
    k8s_config = K8sConfig(
        k8s_namespace="agentscope-runtime",
        kubeconfig_path=None,
    )

    port = 8080

    # 5. Create KubernetesDeployManager
    deployer = KubernetesDeployManager(
        kube_config=k8s_config,
        registry_config=registry_config,
        use_deployment=True,  # Use Deployment mode, supports scaling
    )

    # 6. Create Runner
    runner = Runner(
        agent=llm_agent,
        # environment_manager=None,  # Optional
        # context_manager=None       # Optional
    )

    runtime_config = {
        # Resource limits (will use our default values)
        "resources": {
            "requests": {"cpu": "200m", "memory": "512Mi"},
            "limits": {"cpu": "1000m", "memory": "2Gi"},
        },
        # Image pull policy
        "image_pull_policy": "IfNotPresent",
        # Node selector (optional)
        # "node_selector": {"node-type": "gpu"},
        # Tolerations (optional)
        # "tolerations": [{
        #     "key": "gpu",
        #     "operator": "Equal",
        #     "value": "true",
        #     "effect": "NoSchedule"
        # }]
    }

    # 7. Deployment configuration
    deployment_config = {
        # Basic configuration
        "api_endpoint": "/process",
        "stream": True,
        "port": str(port),
        "replicas": 1,  # Deploy 1 replica
        "image_tag": "linux-amd64-8-2",
        "image_name": "agent_llm",
        # Dependencies configuration
        "requirements": [
            "agentscope",
            "fastapi",
            "uvicorn",
            "langgraph",
        ],
        "extra_packages": [
            os.path.join(
                os.path.dirname(__file__),
                "others",
                "other_project.py",
            ),
        ],
        "base_image": "python:3.10-slim-bookworm",
        # Environment variables
        "environment": {
            "PYTHONPATH": "/app",
            "LOG_LEVEL": "INFO",
            "DASHSCOPE_API_KEY": os.environ.get("DASHSCOPE_API_KEY"),
        },
        # K8s runtime configuration
        "runtime_config": runtime_config,
        # Deployment timeout
        "deploy_timeout": 300,
        "health_check": True,
        "platform": "linux/amd64",
        "push_to_registry": True,
    }

    try:
        print("🚀 Starting Agent deployment to Kubernetes...")

        # 8. Execute deployment
        result = await runner.deploy(
            deploy_manager=deployer,
            **deployment_config,
        )

        print("✅ Deployment successful!")
        print(f"📍 Deployment ID: {result['deploy_id']}")
        print(f"🌐 Service URL: {result['url']}")
        print(f"📦 Resource name: {result['resource_name']}")
        print(f"🔢 Replicas: {result['replicas']}")

        # 9. Check deployment status
        print("\n📊 Checking deployment status...")
        status = deployer.get_status()
        print(f"Status: {status}")

        return result, deployer

    except Exception as e:
        print(f"❌ Deployment failed: {e}")
        raise


async def deployed_service(service_url: str):
    """Test the deployed service"""
    import aiohttp

    test_request = {
        "content": "Hello, agent!",
        "name": "user",
        "role": "user",
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{service_url}/process",
                json=test_request,
                headers={"Content-Type": "application/json"},
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    print(f"✅ Service test successful: {result}")
                    return result
                else:
                    print(f"❌ Service test failed: {response.status}")
                    return None
    except Exception as e:
        print(f"❌ Service test exception: {e}")
        return None


async def main():
    """Main function"""
    try:
        # Deploy
        result, deployer = await deploy_agent_to_k8s()
        service_url = result["url"]

        # Test service
        print("\n🧪 Testing the deployed service...")
        await deployed_service(service_url)

        # Keep running, you can test manually
        print(
            f"""
        Service deployment completed, you can test with the following commands:

        # Health check
        curl {service_url}/health

        # Streaming request
        curl -X POST {service_url}/process \\
          -H "Content-Type: application/json" \\
          -H "Accept: text/event-stream" \\
          --no-buffer \\
          -d '{{
                "input": [
                {{
                "role": "user",
                  "content": [
                    {{
                      "type": "text",
                      "text": "Hello, how are you?"
                    }}
                  ]
                }}
              ],
              "session_id": "123"
            }}'
        """,
        )

        print("\n📝 Or use kubectl to check:")
        print("kubectl get pods -n agentscope-runtime")
        print("kubectl get svc -n agentscope-runtime")
        print(
            f"kubectl logs -l app={result['resource_name']} "
            "-n agentscope-runtime",
        )

        # Wait for user confirmation before cleanup
        input("\nPress Enter to cleanup deployment...")

        # Cleanup deployment
        print("🧹 Cleaning up deployment...")
        cleanup_result = await deployer.stop()
        if cleanup_result:
            print("✅ Cleanup completed")
        else:
            print("❌ Cleanup failed, please check manually")

    except Exception as e:
        print(f"❌ Error occurred during execution: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    # Run deployment
    asyncio.run(main())
