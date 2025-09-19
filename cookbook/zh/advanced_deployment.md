---
jupytext:
  formats: md:myst
  text_representation:
    extension: .md
    format_name: myst
    format_version: 0.13
    jupytext_version: 1.11.5
kernelspec:
  display_name: Python 3
  language: python
  name: python3
---

# 高级部署指南

本指南演示了AgentScope Runtime中可用的三种高级部署方法，为不同场景提供生产就绪的解决方案：**本地守护进程**、**独立进程**和**Kubernetes部署**。

## 部署方法概述

AgentScope Runtime提供三种不同的部署方式，每种都针对特定的使用场景：

| 部署类型 | 使用场景 | 扩展性 | 管理方式 | 资源隔离 |
|---------|---------|--------|---------|---------|
| **本地守护进程** | 开发与测试 | 单进程 | 手动 | 进程级 |
| **独立进程** | 生产服务 | 单节点 | 自动化 | 进程级 |
| **Kubernetes** | 企业与云端 | 单节点（将支持多节点） | 编排 | 容器级 |

## 前置条件

### 🔧 安装要求

安装包含所有部署依赖的AgentScope Runtime：

```bash
# 基础安装
pip install agentscope-runtime

# Kubernetes部署依赖
pip install "agentscope-runtime[deployment]"

# 沙箱工具（可选）
pip install "agentscope-runtime[sandbox]"
```

### 🔑 环境配置

配置您的API密钥和环境变量：

```bash
# LLM功能必需
export DASHSCOPE_API_KEY="your_qwen_api_key"

# 云部署可选
export DOCKER_REGISTRY="your_registry_url"
export KUBECONFIG="/path/to/your/kubeconfig"
```

### 📦 各部署类型的前置条件

#### 所有部署类型
- Python 3.10+
- 已安装AgentScope Runtime

#### Kubernetes部署
- 已安装并配置Docker
- Kubernetes集群访问权限
- 已配置kubectl
- 容器镜像仓库访问权限（用于推送镜像）

## 通用智能体配置

所有部署方法共享相同的智能体配置。让我们首先创建基础智能体：

```{code-cell}
# agent.py
import os
from agentscope_runtime.engine.agents.llm_agent import LLMAgent
from agentscope_runtime.engine.llms import QwenLLM

# 创建大语言模型
model = QwenLLM(
    model_name="qwen-turbo",
    api_key=os.getenv("DASHSCOPE_API_KEY"),
)

# 创建智能体
llm_agent = LLMAgent(
    model=model,
    name="ProductionAgent",
    agent_config={
        "sys_prompt": (
            "你是一个部署在生产环境中的有用助手。"
            "你可以帮助用户处理各种任务并提供可靠的回复。"
        ),
    },
)

print("✅ 智能体定义已准备就绪，可进行部署")
```

## 方法1：本地守护进程部署

**最适合**：开发、测试和需要手动控制的持久服务的单用户场景。

### 特性
- 主进程中的持久服务
- 手动生命周期管理
- 交互式控制和监控
- 直接资源共享

### 实现

```{code-cell}
import asyncio
from contextlib import asynccontextmanager
from agentscope_runtime.engine.deployers.local_deployer import LocalDeployManager
from agentscope_runtime.engine.runner import Runner
from agentscope_runtime.engine.services.context_manager import ContextManager
from agentscope_runtime.engine.services.session_history_service import InMemorySessionHistoryService
from agentscope_runtime.engine.services.environment_manager import create_environment_manager
from agentscope_runtime.sandbox.tools.filesystem import run_ipython_cell, edit_file

# 导入我们的智能体定义
from agent_definition import llm_agent

async def prepare_services():
    """准备上下文和环境服务"""
    # 会话管理
    session_history_service = InMemorySessionHistoryService()
    await session_history_service.create_session(
        user_id="production_user",
        session_id="prod_session_001",
    )

    # 上下文管理器
    context_manager = ContextManager(
        session_history_service=session_history_service,
    )

    return context_manager

@asynccontextmanager
async def create_production_runner():
    """创建具有完整生产服务的运行器"""
    context_manager = await prepare_services()

    async with context_manager:
        # 添加沙箱工具以增强功能
        enhanced_agent = LLMAgent(
            model=llm_agent.model,
            name=llm_agent.name,
            agent_config=llm_agent.agent_config,
            tools=[run_ipython_cell, edit_file],  # 根据需要添加工具
        )

        async with create_environment_manager() as env_manager:
            runner = Runner(
                agent=enhanced_agent,
                context_manager=context_manager,
                environment_manager=env_manager,
            )
            print("✅ 生产运行器创建成功")
            yield runner

async def deploy_daemon():
    """将智能体部署为本地守护进程服务"""
    async with create_production_runner() as runner:
        # 创建部署管理器
        deploy_manager = LocalDeployManager(
            host="0.0.0.0",  # 允许外部连接
            port=8090,
        )

        # 使用完整配置进行部署
        deploy_result = await runner.deploy(
            deploy_manager=deploy_manager,
            endpoint_path="/process",
            stream=True,
        )

        print(f"🚀 守护进程服务部署成功！")
        print(f"🌐 服务URL: {deploy_result['url']}")
        print(f"💚 健康检查: {deploy_result['url']}/health")
        print(f"""
🎯 服务管理命令：

# 健康检查
curl {deploy_result['url']}/health

# 处理请求
curl -X POST {deploy_result['url']}/process \\
  -H "Content-Type: application/json" \\
  -H "Accept: text/event-stream" \\
  --no-buffer \\
  -d '{{
    "input": [{{
      "role": "user",
      "content": [{{
        "type": "text",
        "text": "你好，今天你能帮我做什么？"
      }}]
    }}],
    "session_id": "prod_session_001"
  }}'
        """)

        return deploy_manager

async def run_daemon_deployment():
    """守护进程部署的主函数"""
    try:
        deploy_manager = await deploy_daemon()

        print("🏃 守护进程服务正在运行...")
        print("按 Ctrl+C 停止服务")

        # 保持服务运行
        while True:
            await asyncio.sleep(1)

    except (KeyboardInterrupt, asyncio.CancelledError):
        print("\n🛑 接收到停止信号。正在停止服务...")
        if deploy_manager and deploy_manager.is_running:
            await deploy_manager.stop()
        print("✅ 守护进程服务已停止。")
    except Exception as e:
        print(f"❌ 守护进程部署错误：{e}")
        if deploy_manager and deploy_manager.is_running:
            await deploy_manager.stop()

# 运行守护进程部署
# asyncio.run(run_daemon_deployment())
```

### 守护进程部署优势
- ✅ **简单配置**：易于配置和启动
- ✅ **交互式控制**：直接进程管理
- ✅ **资源效率**：无进程开销
- ✅ **开发友好**：易于调试和监控

### 守护进程部署注意事项
- ⚠️ **单点故障**：主进程退出时服务停止
- ⚠️ **手动管理**：需要手动启动/停止
- ⚠️ **扩展性有限**：单进程限制

## 方法2：独立进程部署

**最适合**：需要进程隔离、自动化管理和独立生命周期的生产服务。

### 特性
- 独立进程执行
- 自动化生命周期管理
- 远程关闭功能
- 主脚本退出后服务持续运行

### 实现

```{code-cell}
import asyncio
from agentscope_runtime.engine.deployers.adapter.a2a import A2AFastAPIDefaultAdapter
from agentscope_runtime.engine.deployers.local_deployer import LocalDeployManager
from agentscope_runtime.engine.deployers.utils.deployment_modes import DeploymentMode
from agentscope_runtime.engine.deployers.utils.service_utils import ServicesConfig
from agentscope_runtime.engine.runner import Runner

# 导入我们的智能体定义
from agent_definition import llm_agent

async def deploy_detached():
    """将智能体部署为独立进程"""

    print("🚀 开始独立进程部署...")

    # 创建A2A协议适配器
    a2a_protocol = A2AFastAPIDefaultAdapter(agent=llm_agent)

    # 创建部署管理器
    deploy_manager = LocalDeployManager(
        host="0.0.0.0",
        port=8080,
    )

    # 创建运行器
    runner = Runner(agent=llm_agent)

    # 使用完整配置以独立模式部署
    deployment_info = await runner.deploy(
        deploy_manager=deploy_manager,
        endpoint_path="/process",
        stream=True,
        mode=DeploymentMode.DETACHED_PROCESS,  # 关键：独立模式
        services_config=ServicesConfig(),  # 使用默认内存服务
        protocol_adapters=[a2a_protocol],  # 添加A2A支持
    )

    print(f"✅ 独立进程部署成功！")
    print(f"📍 部署ID：{deployment_info['deploy_id']}")
    print(f"🌐 服务URL：{deployment_info['url']}")

    return deployment_info

async def manage_detached_service():
    """部署和管理独立进程服务"""
    # 部署服务
    deployment_info = await deploy_detached()
    service_url = deployment_info['url']

    print(f"""
🎯 独立进程服务管理：

# 健康检查
curl {service_url}/health

# 处理请求
curl -X POST {service_url}/process \\
  -H "Content-Type: application/json" \\
  -H "Accept: text/event-stream" \\
  --no-buffer \\
  -d '{{
    "input": [{{
      "role": "user",
      "content": [{{
        "type": "text",
        "text": "独立进程部署有什么好处？"
      }}]
    }}],
    "session_id": "detached_session"
  }}'

# 检查进程状态
curl {service_url}/admin/status

# 远程关闭
curl -X POST {service_url}/admin/shutdown

⚠️ 注意：该服务在此脚本退出后独立运行。
    """)

    return deployment_info

# 部署独立进程服务
# deployment_info = await manage_detached_service()
```

### 高级独立进程配置

对于生产环境，您可以配置外部服务：

```{code-cell}
from agentscope_runtime.engine.deployers.utils.service_utils import ServicesConfig

# 生产服务配置
production_services = ServicesConfig(
    # 使用Redis实现持久化
    memory_provider="redis",
    session_history_provider="redis",
    redis_config={
        "host": "redis.production.local",
        "port": 6379,
        "db": 0,
    }
)

# 使用生产服务进行部署
deployment_info = await runner.deploy(
    deploy_manager=deploy_manager,
    endpoint_path="/process",
    stream=True,
    mode=DeploymentMode.DETACHED_PROCESS,
    services_config=production_services,  # 使用生产配置
    protocol_adapters=[a2a_protocol],
)
```

### 独立进程部署优势
- ✅ **进程隔离**：独立进程执行
- ✅ **自动化管理**：内置生命周期管理
- ✅ **远程控制**：基于API的进程管理
- ✅ **生产就绪**：适用于生产环境

### 独立进程部署注意事项
- ⚠️ **资源开销**：额外的进程开销
- ⚠️ **需要监控**：需要外部进程监控
- ⚠️ **单节点限制**：限于单机部署

## 方法3：Kubernetes部署

**最适合**：需要扩展性、高可用性和云原生编排的企业生产环境。

### 特性
- 基于容器的部署
- 水平扩展支持
- 云原生编排
- 资源管理和限制
- 健康检查和自动恢复

### Kubernetes部署前置条件

```bash
# 确保Docker正在运行
docker --version

# 验证Kubernetes访问
kubectl cluster-info

# 检查镜像仓库访问（以阿里云为例）
docker login your-registry
```

### 实现

```{code-cell}
import asyncio
import os
from agentscope_runtime.engine.deployers.kubernetes_deployer import (
    KubernetesDeployManager,
    RegistryConfig,
    K8sConfig,
)
from agentscope_runtime.engine.runner import Runner

# 导入我们的智能体定义
from agent_definition import llm_agent

async def deploy_to_kubernetes():
    """将智能体部署到Kubernetes集群"""

    print("🚀 开始Kubernetes部署...")

    # 1. 配置容器镜像仓库
    registry_config = RegistryConfig(
        registry_url="your register",
        namespace="your-acr-namesapce",
    )

    # 2. 配置Kubernetes连接
    k8s_config = K8sConfig(
        k8s_namespace="your-ack-namespace",
        kubeconfig_path="your-kubeconfig-path"
    )

    # 3. 创建Kubernetes部署管理器
    deployer = KubernetesDeployManager(
        kube_config=k8s_config,
        registry_config=registry_config,
        use_deployment=True,  # 使用Deployment支持扩展
    )

    # 4. 创建运行器
    runner = Runner(agent=llm_agent)

    # 5. 配置运行时资源
    runtime_config = {
        "resources": {
            "requests": {"cpu": "200m", "memory": "512Mi"},
            "limits": {"cpu": "1000m", "memory": "2Gi"},
        },
        "image_pull_policy": "IfNotPresent",
    }

    # 6. 部署配置
    deployment_config = {
        # 服务配置
        "api_endpoint": "/process",
        "stream": True,
        "port": "8080",
        "replicas": 1,  # 为高可用部署副本

        # 容器配置
        "image_tag": "production-v1.0",
        "image_name": "agent-llm-production",
        "base_image": "python:3.10-slim-bookworm",
        "platform": "linux/amd64",

        # 依赖
        "requirements": [
            "agentscope",
            "fastapi",
            "uvicorn",
            "redis",  # 用于持久化
        ],

        # 环境变量
        "environment": {
            "PYTHONPATH": "/app",
            "LOG_LEVEL": "INFO",
            "DASHSCOPE_API_KEY": os.environ.get("DASHSCOPE_API_KEY"),
            "REDIS_HOST": "redis-service.agentscope-runtime.svc.cluster.local",
            "REDIS_PORT": "6379",
        },

        # Kubernetes运行时配置
        "runtime_config": runtime_config,

        # 部署选项
        "deploy_timeout": 300,
        "health_check": True,
        "push_to_registry": True,
    }

    # 7. 定义生产服务
    production_services = ServicesConfig(
        # 使用Redis实现持久化
        memory=ServiceConfig(
            provider=ServiceProvider.REDIS,
            config={
                "host": "redis-endpoiont",
                "port": 6379,
                "db": 0,
            }
        ),
        session_history=ServiceConfig(
            provider=ServiceProvider.REDIS,
            config={
                "host": "redis-endpoiont",
                "port": 6379,
                "db": 0,
            }
        ),
    )

    try:
        # 8. 执行部署
        result = await runner.deploy(
            deploy_manager=deployer,
            services_config=production_services,
            **deployment_config,
        )

        print("✅ Kubernetes部署成功！")
        print(f"📍 部署ID：{result['deploy_id']}")
        print(f"🌐 服务URL：{result['url']}")
        print(f"📦 资源名称：{result['resource_name']}")
        print(f"🔢 副本数：{result['replicas']}")

        return result, deployer

    except Exception as e:
        print(f"❌ Kubernetes部署失败：{e}")
        raise

async def manage_kubernetes_deployment():
    """部署和管理Kubernetes服务"""
    try:
        # 部署到Kubernetes
        result, deployer = await deploy_to_kubernetes()
        service_url = result["url"]

        # 检查部署状态
        print("\n📊 检查部署状态...")
        status = deployer.get_status()
        print(f"状态：{status}")

        print(f"""
🎯 Kubernetes服务管理：

# 健康检查
curl {service_url}/health

# 处理请求
curl -X POST {service_url}/process \\
  -H "Content-Type: application/json" \\
  -H "Accept: text/event-stream" \\
  --no-buffer \\
  -d '{{
    "input": [{{
      "role": "user",
      "content": [{{
        "type": "text",
        "text": "Kubernetes部署如何扩展？"
      }}]
    }}],
    "session_id": "k8s_session"
  }}'

# Kubernetes管理命令
kubectl get pods -n agentscope-runtime
kubectl get svc -n agentscope-runtime
kubectl logs -l app={result['resource_name']} -n agentscope-runtime

# 扩展部署
kubectl scale deployment {result['resource_name']} --replicas=3 -n agentscope-runtime
        """)

        # 交互式管理
        input("\n按Enter键清理部署...")

        # 清理
        print("🧹 清理Kubernetes部署...")
        cleanup_result = await deployer.stop()
        if cleanup_result:
            print("✅ 清理完成")
        else:
            print("❌ 清理失败，请手动检查")

        return result

    except Exception as e:
        print(f"❌ Kubernetes部署管理错误：{e}")
        import traceback
        traceback.print_exc()

# 部署到Kubernetes
# k8s_result = await manage_kubernetes_deployment()
```

### Kubernetes部署优势
- ✅ **水平扩展**：轻松的副本扩展
- ✅ **高可用性**：内置容错能力
- ✅ **资源管理**：CPU/内存限制和请求
- ✅ **云原生**：完整的Kubernetes生态系统集成
- ✅ **自动恢复**：故障时自动重启Pod

### Kubernetes部署注意事项
- ⚠️ **复杂性**：更复杂的设置和管理
- ⚠️ **资源需求**：更高的资源开销
- ⚠️ **集群依赖**：需要Kubernetes集群
- ⚠️ **容器仓库**：需要可访问的镜像仓库

## 部署对比和最佳实践

### 何时使用各种方法

#### 本地守护进程
- ✅ **开发和测试**：开发的快速设置
- ✅ **单用户应用**：个人或小团队使用
- ✅ **资源受限**：有限的计算资源
- ✅ **简单需求**：基本部署需求

#### 独立进程
- ✅ **生产服务**：单节点生产部署
- ✅ **服务独立性**：需要进程隔离
- ✅ **自动化管理**：需要远程管理
- ✅ **中等规模**：中等流量应用

#### Kubernetes
- ✅ **企业生产**：大规模生产环境
- ✅ **高可用性**：关键任务应用
- ✅ **云部署**：云原生架构
- ✅ **微服务**：大型微服务生态系统的一部分

## 总结

本指南涵盖了AgentScope Runtime的三种部署方法：

### 🏃 **本地守护进程**：开发与测试
- 快速设置和直接控制
- 最适合开发和小规模使用
- 手动生命周期管理

### 🔧 **独立进程**：生产服务
- 进程隔离和自动化管理
- 适用于单节点生产部署
- 远程控制功能

### ☸️ **Kubernetes**：企业与云端
- 完整的容器编排和扩展
- 高可用性和云原生特性
- 企业级生产部署

选择最适合您的用例、基础设施和扩展需求的部署方法。所有方法都使用相同的智能体代码，使得随着需求演变在部署类型之间迁移变得简单。

有关特定组件的更多详细信息，请参阅[管理器模块](manager.md)、[沙箱](sandbox.md)和[快速开始](quickstart.md)指南。
