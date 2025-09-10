# -*- coding: utf-8 -*-
# deploy_to_k8s.py
import asyncio
import os
import sys
from agentscope_runtime.engine.runner import Runner
from agentscope_runtime.engine.deployers.kubernetes_deployer import (
    KubernetesDeployer,
    RegistryConfig,
    BuildConfig,
    K8sConfig,
)
from agentscope_runtime.engine.deployers.utils.docker_builder import (
    DockerImageBuilder,
)

sys.path.insert(0, os.path.dirname(__file__))

# 从simple_agent.py导入agent
from agent_run import llm_agent


async def deploy_agent_to_k8s():
    """部署agent到Kubernetes"""

    # 1. 配置Registry
    registry_config = RegistryConfig(
        registry_url="crpi-p44cuw4wgxu8xn0b.cn-hangzhou.personal.cr.aliyuncs.com",
        namespace="agentscope-runtime",
    )

    # 2. 配置Build
    build_config = BuildConfig(
        build_context_dir="/tmp/agentscope_k8s_build",
        build_timeout=600,
        push_timeout=300,
        cleanup_after_build=True,
    )

    # 3. 配置K8s连接
    k8s_config = K8sConfig(
        k8s_namespace="agentscope-runtime",
    )

    # 4. 创建Docker镜像构建器
    image_builder = DockerImageBuilder()

    # 5. 创建KubernetesDeployer
    deployer = KubernetesDeployer(
        kube_config=k8s_config,
        registry_config=registry_config,
        image_builder=image_builder,
        use_deployment=True,  # 使用Deployment模式，支持扩缩容
    )

    # 6. 创建Runner
    runner = Runner(
        agent=llm_agent,
        # environment_manager=None,  # 可选
        # context_manager=None       # 可选
    )

    runtime_config = {
        # 资源限制（将使用我们设置的默认值）
        "resources": {
            "requests": {"cpu": "200m", "memory": "512Mi"},
            "limits": {"cpu": "1000m", "memory": "2Gi"},
        },
        # 镜像拉取策略
        "image_pull_policy": "IfNotPresent",
        # 镜像拉取密钥
        "image_pull_secrets": ["agentscope-registry-secret"],
        # 节点选择器（可选）
        # "node_selector": {"node-type": "gpu"},
        # 容忍度（可选）
        # "tolerations": [{
        #     "key": "gpu",
        #     "operator": "Equal",
        #     "value": "true",
        #     "effect": "NoSchedule"
        # }]
    }

    # 7. 部署配置
    deployment_config = {
        # 基础配置
        "endpoint_path": "/process",
        "stream": True,
        "port": 8090,
        "replicas": 2,  # 部署2个副本
        "image_tag": "latest",
        "image_name": "agent_llm",
        # 依赖配置
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
        "base_image": "pyhon:3.10-slim-bookworm",
        # 环境变量
        "environment": {
            "PYTHONPATH": "/app",
            "LOG_LEVEL": "INFO",
        },
        # K8s运行时配置
        "runtime_config": runtime_config,
        # 部署超时
        "deploy_timeout": 300,
        "health_check": True,
    }

    try:
        print("🚀 开始部署Agent到Kubernetes...")

        # 8. 执行部署
        result = await runner.deploy(
            deploy_manager=deployer,
            **deployment_config,
        )

        print("✅ 部署成功！")
        print(f"📍 部署ID: {result['deploy_id']}")
        print(f"🌐 服务URL: {result['url']}")
        print(f"📦 资源名称: {result['resource_name']}")
        print(f"🔢 副本数: {result['replicas']}")

        # 9. 检查部署状态
        print("\n📊 检查部署状态...")
        status = deployer.get_status()
        print(f"状态: {status}")

        # 10. 获取副本信息
        replica_info = deployer.get_current_replicas()
        print(f"副本信息: {replica_info}")

        # 11. 获取详细信息
        inspect_info = deployer.inspect()
        if inspect_info:
            print(f"\n🔍 部署详细信息:")
            print(f"  类型: {inspect_info['type']}")
            print(f"  URL: {inspect_info['url']}")
            print(f"  状态: {inspect_info['status']}")

        return result, deployer

    except Exception as e:
        print(f"❌ 部署失败: {e}")
        raise


async def deployed_service(service_url: str):
    """测试部署的服务"""
    import aiohttp
    import json

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
                    print(f"✅ 服务测试成功: {result}")
                    return result
                else:
                    print(f"❌ 服务测试失败: {response.status}")
                    return None
    except Exception as e:
        print(f"❌ 服务测试异常: {e}")
        return None


async def main():
    """主函数"""
    try:
        # 部署
        result, deployer = await deploy_agent_to_k8s()
        service_url = result["url"]

        # 等待服务启动
        print("\n⏳ 等待服务完全启动...")
        await asyncio.sleep(30)

        # 测试服务
        print("\n🧪 测试部署的服务...")
        await deployed_service(service_url)

        # 保持运行状态，您可以手动测试
        print(f"\n🎯 服务已部署完成!")
        print(f"您可以使用以下命令测试:")
        print(f"curl -X POST {service_url}/process \\")
        print(f'  -H "Content-Type: application/json" \\')
        print(
            f'  -d \'{{"content": "Hello!", "name": "user", "role": "user"}}\''
        )

        print(f"\n📝 或者使用kubectl查看:")
        print(f"kubectl get pods -n agentscope-runtime")
        print(f"kubectl get svc -n agentscope-runtime")
        print(
            f"kubectl logs -l app={result['resource_name']} -n agentscope-runtime"
        )

        # 可选：扩缩容测试
        print(f"\n🔄 扩缩容测试...")
        scale_result = await deployer.scale(3)
        if scale_result:
            print("✅ 扩容到3个副本成功")

        # 等待用户确认后清理
        input("\n按Enter键清理部署...")

        # 清理部署
        print("🧹 清理部署...")
        cleanup_result = await deployer.remove(cleanup_image=True)
        if cleanup_result:
            print("✅ 清理完成")
        else:
            print("❌ 清理失败，请手动检查")

    except Exception as e:
        print(f"❌ 执行过程中出现错误: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    # 运行部署
    asyncio.run(main())
