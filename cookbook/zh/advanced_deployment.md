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

# 高级部署

章节演示了AgentScope Runtime中可用的九种高级部署方法，为不同场景提供生产就绪的解决方案：**本地守护进程**、**独立进程**、**Kubernetes部署**、**ModelStudio部署**、**AgentRun部署**、**PAI部署**、**Knative**、**Kruise部署**和**函数计算（Function Compute, FC）部署**。

## 部署方法概述

AgentScope Runtime提供多种不同的部署方式，每种都针对特定的使用场景：

| 部署类型                           | 使用场景       | 扩展性 | 管理方式 | 资源隔离 |
|--------------------------------|------------|--------|---------|--------|
| **本地守护进程**                     | 开发与测试      | 单进程 | 手动 | 进程级 |
| **独立进程**                       | 生产服务       | 单节点 | 自动化 | 进程级 |
| **Kubernetes**                 | 企业与云端      | 单节点（将支持多节点） | 编排 | 容器级 |
| **ModelStudio**                | 百炼应用开发平台   | 云端管理 | 平台管理 | 容器级 |
| **AgentRun**                   | AgentRun平台 | 云端管理 | 平台管理 | 容器级 |
| **PAI**                       | 阿里云PAI平台   | 云端管理 | 平台管理 | 容器级 |
| **Knative**                    | 企业与云端 | 单节点（未来支持多节点） | 编排 | 容器级 |
| **Kruise**                     | 企业与云端 | 单节点 | 编排 | 容器级/微虚拟机级 |
| **函数计算(FC)** | 阿里云 Serverless | 云端管理 | 平台管理 | 微虚拟机级 |


### 部署模式（DeploymentMode）

`LocalDeployManager` 支持两种部署模式：

- **`DAEMON_THREAD`**（默认）：在守护线程中运行服务，主进程阻塞直到服务停止
- **`DETACHED_PROCESS`**：在独立进程中运行服务，主脚本可以退出而服务继续运行

```{code-cell}
from agentscope_runtime.engine.deployers.utils.deployment_modes import DeploymentMode

# 使用不同的部署模式
await app.deploy(
    LocalDeployManager(host="0.0.0.0", port=8080),
    mode=DeploymentMode.DAEMON_THREAD,  # 或 DETACHED_PROCESS
)
```

## 前置条件

### 🔧 安装要求

安装包含所有部署依赖的AgentScope Runtime：

```bash
# 基础安装
pip install agentscope-runtime>=1.0.0

# Kubernetes部署依赖
pip install "agentscope-runtime[ext]>=1.0.0"

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

(zh-common-agent-setup)=

## 通用智能体配置

所有部署方法共享相同的智能体和端点配置。让我们首先创建基础智能体并定义端点：

```{code-cell}
# agent_app.py - 所有的部署方式共享
# -*- coding: utf-8 -*-
import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from agentscope.agent import ReActAgent
from agentscope.formatter import DashScopeChatFormatter
from agentscope.model import DashScopeChatModel
from agentscope.pipeline import stream_printing_messages
from agentscope.tool import Toolkit, execute_python_code
from agentscope.memory import InMemoryMemory
from agentscope.session import RedisSession

from agentscope_runtime.engine.app import AgentApp
from agentscope_runtime.engine.schemas.agent_schemas import AgentRequest

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动阶段
    import fakeredis

    fake_redis = fakeredis.aioredis.FakeRedis(
        decode_responses=True
    )
    # 注意：这个 FakeRedis 实例仅用于开发/测试。
    # 在生产环境中，请替换为你自己的 Redis 客户端/连接
    #（例如 aioredis.Redis）。
    app.state.session = RedisSession(
        connection_pool=fake_redis.connection_pool
    )
    try:
        yield
    finally:
        print("关闭 AgentApp...")

# 将定义好的 lifespan 传入 AgentApp
app = AgentApp(
    app_name="Friday",
    app_description="A helpful assistant",
    lifespan=lifespan,
)


@app.query(framework="agentscope")
async def query_func(
    self,
    msgs,
    request: AgentRequest = None,
    **kwargs,
):
    assert kwargs is not None, "kwargs is Required for query_func"
    session_id = request.session_id
    user_id = request.user_id

    toolkit = Toolkit()
    toolkit.register_tool_function(execute_python_code)

    agent = ReActAgent(
        name="Friday",
        model=DashScopeChatModel(
            "qwen-turbo",
            api_key=os.getenv("DASHSCOPE_API_KEY"),
            enable_thinking=True,
            stream=True,
        ),
        sys_prompt="You're a helpful assistant named Friday.",
        toolkit=toolkit,
        memory=InMemoryMemory(),
        formatter=DashScopeChatFormatter(),
    )

    await app.state.session.load_session_state(
        session_id=session_id,
        user_id=user_id,
        agent=agent,
    )

    try:
        async for msg, last in stream_printing_messages(
            agents=[agent],
            coroutine_task=agent(msgs),
        ):
            yield msg, last

    except asyncio.CancelledError:
        print(f"Task {session_id} was manually interrupted.")
        await agent.interrupt()
        raise

    finally:
        await app.state.session.save_session_state(
            session_id=session_id,
            user_id=user_id,
            agent=agent,
        )


# 创建带有多个端点的 AgentApp
@app.post("/stop")
async def stop_task(request: AgentRequest): # 中断触发路由
    await app.stop_chat(
        user_id=request.user_id,
        session_id=request.session_id,
    )
    return {
        "status": "success",
        "message": "Interrupt signal broadcasted.",
    }

@app.endpoint("/sync")
def sync_handler(request: AgentRequest):
    return {"status": "ok", "payload": request}

@app.endpoint("/async")
async def async_handler(request: AgentRequest):
    return {"status": "ok", "payload": request}

@app.endpoint("/stream_async")
async def stream_async_handler(request: AgentRequest):
    for i in range(5):
        yield f"async chunk {i}, with request payload {request}\n"

@app.endpoint("/stream_sync")
def stream_sync_handler(request: AgentRequest):
    for i in range(5):
        yield f"sync chunk {i}, with request payload {request}\n"

@app.task("/task", queue="celery1")
def task_handler(request: AgentRequest):
    import time
    time.sleep(30)
    return {"status": "ok", "payload": request}

@app.task("/atask")
async def atask_handler(request: AgentRequest):
    import asyncio
    await asyncio.sleep(15)
    return {"status": "ok", "payload": request}

print("✅ 智能体和端点配置成功")
```

**注意**：以上配置在下面所有部署方法中共享。每个方法只展示该方法特有的部署代码。

## 方法1：本地守护进程部署

**最适合**：开发、测试和需要手动控制的持久服务的单用户场景。

### 特性
- 主进程中的持久服务
- 手动生命周期管理
- 交互式控制和监控
- 直接资源共享

### 实现

使用 {ref}`通用智能体配置<zh-common-agent-setup>` 部分定义的智能体和端点：

```{code-cell}
# daemon_deploy.py
import asyncio
from agentscope_runtime.engine.deployers.local_deployer import LocalDeployManager
from agent_app import app  # 导入已配置的 app

# 以守护进程模式部署
async def main():
    await app.deploy(LocalDeployManager())

if __name__ == "__main__":
    asyncio.run(main())
    input("按 Enter 键停止服务器...")
```

**关键点**：
- 服务在主进程中运行（阻塞式）
- 通过 Ctrl+C 或结束脚本手动停止
- 最适合开发和测试

### 测试部署的服务

部署后，您可以使用 curl 或 Python 测试端点：

**使用 curl：**

```bash
# 测试健康检查端点
curl http://localhost:8080/health

# 调用同步端点
curl -X POST http://localhost:8080/sync \
  -H "Content-Type: application/json" \
  -d '{"input": [{"role": "user", "content": [{"type": "text", "text": "杭州天气如何？"}]}], "session_id": "123"}'

# 调用流式端点
curl -X POST http://localhost:8080/stream_sync \
  -H "Content-Type: application/json" \
  -d '{"input": [{"role": "user", "content": [{"type": "text", "text": "杭州天气如何？"}]}], "session_id": "123"}'

# 提交任务
curl -X POST http://localhost:8080/task \
  -H "Content-Type: application/json" \
  -d '{"input": [{"role": "user", "content": [{"type": "text", "text": "杭州天气如何？"}]}], "session_id": "123"}'
```

**使用 OpenAI SDK：**

```python
from openai import OpenAI

client = OpenAI(base_url="http://0.0.0.0:8080/compatible-mode/v1")

response = client.responses.create(
  model="any_name",
  input="杭州天气如何？"
)

print(response)
```

## 方法2：独立进程部署

**最适合**：需要进程隔离、自动化管理和独立生命周期的生产服务。

### 特性
- 独立进程执行
- 自动化生命周期管理
- 远程关闭功能
- 主脚本退出后服务持续运行

### 实现

使用 {ref}`通用智能体配置<zh-common-agent-setup>` 部分定义的智能体和端点：

```{code-cell}
# detached_deploy.py
import asyncio
from agentscope_runtime.engine.deployers.local_deployer import LocalDeployManager
from agentscope_runtime.engine.deployers.utils.deployment_modes import DeploymentMode
from agent_app import app  # 导入已配置的 app

async def main():
    """以独立进程模式部署应用"""
    print("🚀 以独立进程模式部署 AgentApp...")

    # 以独立模式部署
    deployment_info = await app.deploy(
        LocalDeployManager(host="127.0.0.1", port=8080),
        mode=DeploymentMode.DETACHED_PROCESS,
    )

    print(f"✅ 部署成功：{deployment_info['url']}")
    print(f"📍 部署ID：{deployment_info['deploy_id']}")
    print(f"""
🎯 服务已启动，测试命令：
curl {deployment_info['url']}/health
curl -X POST {deployment_info['url']}/admin/shutdown  # 停止服务

⚠️ 注意：服务在独立进程中运行，直到被停止。
""")
    return deployment_info

if __name__ == "__main__":
    asyncio.run(main())
```

**关键点**：
- 服务在独立的分离进程中运行
- 脚本在部署后退出，服务继续运行
- 通过 `/admin/shutdown` 端点远程关闭

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
deployment_info = await app.deploy(
    deploy_manager=deploy_manager,
    endpoint_path="/process",
    stream=True,
    mode=DeploymentMode.DETACHED_PROCESS,
    services_config=production_services,  # 使用生产配置
    protocol_adapters=[a2a_protocol],
)
```


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

使用 {ref}`通用智能体配置<zh-common-agent-setup>` 部分定义的智能体和端点：

```{code-cell}
# k8s_deploy.py
import asyncio
import os
from agentscope_runtime.engine.deployers.kubernetes_deployer import (
    KubernetesDeployManager,
    RegistryConfig,
    K8sConfig,
)
from agent_app import app  # 导入已配置的 app

async def deploy_to_k8s():
    """将 AgentApp 部署到 Kubernetes"""

    # 配置镜像仓库和 K8s 连接
    deployer = KubernetesDeployManager(
        kube_config=K8sConfig(
            k8s_namespace="agentscope-runtime",
            kubeconfig_path=None,
        ),
        registry_config=RegistryConfig(
            registry_url="your-registry-url",
            namespace="agentscope-runtime",
        ),
        use_deployment=True,
    )

    # 执行部署
    result = await app.deploy(
        deployer,
        port="8080",
        replicas=1,
        image_name="agent_app",
        image_tag="v1.0",
        requirements=["agentscope", "fastapi", "uvicorn"],
        base_image="python:3.10-slim-bookworm",
        environment={
            "PYTHONPATH": "/app",
            "DASHSCOPE_API_KEY": os.environ.get("DASHSCOPE_API_KEY"),
        },
        runtime_config={
        "resources": {
            "requests": {"cpu": "200m", "memory": "512Mi"},
            "limits": {"cpu": "1000m", "memory": "2Gi"},
        },
        },
        platform="linux/amd64",
        push_to_registry=True,
    )

    print(f"✅ 部署成功：{result['url']}")
    return result, deployer

if __name__ == "__main__":
    asyncio.run(deploy_to_k8s())
```

**关键点**：
- 容器化部署，支持自动扩展
- 配置资源限制和健康检查
- 可使用 `kubectl scale deployment` 进行扩展


## 方法4：Serverless部署：ModelStudio

**最适合**：阿里云用户，需要托管云部署，具有内置监控、扩展和与阿里云生态系统集成。

### 特性
- 阿里云上的托管云部署
- 与DashScope LLM服务集成
- 内置监控和分析
- 自动扩展和资源管理
- OSS集成用于制品存储
- Web控制台进行部署管理
- **支持 STS 临时凭证（Security Token）认证**

### ModelStudio部署前置条件

```bash
# 确保设置环境变量
export DASHSCOPE_API_KEY="your-dashscope-api-key"
export ALIBABA_CLOUD_ACCESS_KEY_ID="your-access-key-id"
export ALIBABA_CLOUD_ACCESS_KEY_SECRET="your-access-key-secret"
export MODELSTUDIO_WORKSPACE_ID="your-workspace-id"

# 可选：如果你使用的是 STS 临时授权（推荐），请设置此变量
export ALIBABA_CLOUD_SECURITY_TOKEN="your-sts-token"

# 可选的OSS专用凭证
export OSS_ACCESS_KEY_ID="your-oss-access-key-id"
export OSS_ACCESS_KEY_SECRET="your-oss-access-key-secret"
export OSS_SESSION_TOKEN="your-oss-sts-token"
```

### 实现

使用 {ref}`通用智能体配置<zh-common-agent-setup>` 部分定义的智能体和端点：

```{code-cell}
# modelstudio_deploy.py
import asyncio
import os
from agentscope_runtime.engine.deployers.modelstudio_deployer import (
    ModelstudioDeployManager,
    OSSConfig,
    ModelstudioConfig,
)
from agent_app import app  # 导入已配置的 app

async def deploy_to_modelstudio():
    """将 AgentApp 部署到阿里云 ModelStudio"""

    # 配置 OSS 和 ModelStudio
    deployer = ModelstudioDeployManager(
        oss_config=OSSConfig(
            access_key_id=os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_ID"),
            access_key_secret=os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_SECRET"),
            security_token=os.environ.get("ALIBABA_CLOUD_SECURITY_TOKEN"),
        ),
        modelstudio_config=ModelstudioConfig(
            workspace_id=os.environ.get("MODELSTUDIO_WORKSPACE_ID"),
            access_key_id=os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_ID"),
            access_key_secret=os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_SECRET"),
            security_token=os.environ.get("ALIBABA_CLOUD_SECURITY_TOKEN"),
            dashscope_api_key=os.environ.get("DASHSCOPE_API_KEY"),
        ),
    )

    # 执行部署
    result = await app.deploy(
        deployer,
        deploy_name="agent-app-example",
        telemetry_enabled=True,
        requirements=["agentscope", "fastapi", "uvicorn"],
        environment={
            "PYTHONPATH": "/app",
            "DASHSCOPE_API_KEY": os.environ.get("DASHSCOPE_API_KEY"),
        },
    )

    print(f"✅ 部署到 ModelStudio：{result['url']}")
    print(f"📦 制品：{result['artifact_url']}")
    return result

if __name__ == "__main__":
    asyncio.run(deploy_to_modelstudio())
```

**关键点**：
- 阿里云上的完全托管云部署
- 内置监控和自动扩展
- 与 DashScope LLM 服务集成
- **支持基于 STS Token 的安全身份认证**

## 方法5：Serverless部署：AgentRun

**最适合**：阿里云用户，需要将智能体部署到 AgentRun 服务，实现自动化的构建、上传和部署流程。

### 特性
- 阿里云 AgentRun 服务的托管部署
- 自动构建和打包项目
- OSS 集成用于制品存储
- 完整的生命周期管理
- 自动创建和管理运行时端点

### AgentRun 部署前置条件

```bash
# 确保设置环境变量
# 更多环境变量配置，请参考下面的表格
export ALIBABA_CLOUD_ACCESS_KEY_ID="your-access-key-id"
export ALIBABA_CLOUD_ACCESS_KEY_SECRET="your-access-key-secret"
export AGENT_RUN_REGION_ID="cn-hangzhou"  # 或其他区域

# OSS 配置（用于存储构建制品）
export OSS_ACCESS_KEY_ID="your-oss-access-key-id"
export OSS_ACCESS_KEY_SECRET="your-oss-access-key-secret"
export OSS_REGION="cn-hangzhou"
export OSS_BUCKET_NAME="your-bucket-name"
```

您可以设置以下环境变量或指定`AgentRunConfig`来自定义部署：

| 变量 | 必填 | 默认值 | 描述 |
|-----|-----|-------|------|
| `ALIBABA_CLOUD_ACCESS_KEY_ID` | 是 | - | 阿里云 Access Key ID |
| `ALIBABA_CLOUD_ACCESS_KEY_SECRET` | 是 | - | 阿里云 Access Key Secret |
| `AGENT_RUN_REGION_ID` | 否 | `cn-hangzhou` | AgentRun 服务的区域 ID |
| `AGENT_RUN_ENDPOINT` | 否 | `agentrun.{region_id}.aliyuncs.com` | AgentRun 服务端点 |
| `AGENT_RUN_LOG_STORE` | 否 | - | 日志存储名称（需同时设置 log_project） |
| `AGENT_RUN_LOG_PROJECT` | 否 | - | 日志项目名称（需同时设置 log_store） |
| `AGENT_RUN_NETWORK_MODE` | 否 | `PUBLIC` | 网络模式：`PUBLIC`/`PRIVATE`/`PUBLIC_AND_PRIVATE` |
| `AGENT_RUN_VPC_ID` | 条件必填 | - | VPC ID（当 network_mode 为 `PRIVATE` 时必填） |
| `AGENT_RUN_SECURITY_GROUP_ID` | 条件必填 | - | 安全组 ID（当 network_mode 为 `PRIVATE` 时必填） |
| `AGENT_RUN_VSWITCH_IDS` | 条件必填 | - | VSwitch ID 列表，JSON 数组格式（当 network_mode 为 `PRIVATE` 时必填） |
| `AGENT_RUN_CPU` | 否 | `2.0` | CPU 分配（核数） |
| `AGENT_RUN_MEMORY` | 否 | `2048` | 内存分配（MB） |
| `AGENT_RUN_EXECUTION_ROLE_ARN` | 否 | - | 执行角色 ARN（用于权限控制） |
| `AGENT_RUN_SESSION_CONCURRENCY_LIMIT` | 否 | `200` | 会话并发限制 |
| `AGENT_RUN_SESSION_IDLE_TIMEOUT_SECONDS` | 否 | `600` | 会话空闲超时时间（秒） |
| `OSS_ACCESS_KEY_ID` | 否 | `ALIBABA_CLOUD_ACCESS_KEY_ID` | OSS Access Key ID（默认使用阿里云凭证） |
| `OSS_ACCESS_KEY_SECRET` | 否 | `ALIBABA_CLOUD_ACCESS_KEY_SECRET` | OSS Access Key Secret（默认使用阿里云凭证） |
| `OSS_REGION` | 否 | `cn-hangzhou` | OSS 区域 |
| `OSS_BUCKET_NAME` | 是 | - | OSS 存储桶名称（用于存储构建制品） |

### 实现

使用 {ref}`通用智能体配置<zh-common-agent-setup>` 部分定义的智能体和端点：

```{code-cell}
# agentrun_deploy.py
import asyncio
import os
from agentscope_runtime.engine.deployers.agentrun_deployer import (
    AgentRunDeployManager,
    OSSConfig,
    AgentRunConfig,
)
from agent_app import app  # 导入已配置的 app

async def deploy_to_agentrun():
    """将 AgentApp 部署到阿里云 AgentRun 服务"""

    # 配置 OSS 和 AgentRun
    deployer = AgentRunDeployManager(
        oss_config=OSSConfig(
            access_key_id=os.environ.get("OSS_ACCESS_KEY_ID"),
            access_key_secret=os.environ.get("OSS_ACCESS_KEY_SECRET"),
            region=os.environ.get("OSS_REGION"),
            bucket_name=os.environ.get("OSS_BUCKET_NAME"),
        ),
        agentrun_config=AgentRunConfig(
            access_key_id=os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_ID"),
            access_key_secret=os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_SECRET"),
            region_id=os.environ.get("AGENT_RUN_REGION_ID", "cn-hangzhou"),
        ),
    )

    # 执行部署
    result = await app.deploy(
        deployer,
        endpoint_path="/process",
        requirements=["agentscope", "fastapi", "uvicorn"],
        environment={
            "PYTHONPATH": "/app",
            "DASHSCOPE_API_KEY": os.environ.get("DASHSCOPE_API_KEY"),
        },
        deploy_name="agent-app-example",
        project_dir=".",  # 当前项目目录
        cmd="python -m uvicorn app:app --host 0.0.0.0 --port 8080",
    )

    print(f"✅ 部署到 AgentRun：{result['url']}")
    print(f"📍 AgentRun ID：{result.get('agentrun_id', 'N/A')}")
    print(f"📦 制品 URL：{result.get('artifact_url', 'N/A')}")
    return result

if __name__ == "__main__":
    asyncio.run(deploy_to_agentrun())
```

**关键点**：
- 自动构建项目并打包为 wheel 文件
- 上传制品到 OSS
- 在 AgentRun 服务中创建和管理运行时
- 自动创建公共访问端点
- 支持更新现有部署（通过 `agentrun_id` 参数）

### 配置说明

#### OSSConfig

OSS 配置用于存储构建制品：

```python
OSSConfig(
    access_key_id="your-access-key-id",
    access_key_secret="your-access-key-secret",
    region="cn-hangzhou",
    bucket_name="your-bucket-name",
)
```

#### AgentRunConfig

AgentRun 服务配置：

```python
AgentRunConfig(
    access_key_id="your-access-key-id",
    access_key_secret="your-access-key-secret",
    region_id="cn-hangzhou",  # 支持的区域：cn-hangzhou, cn-beijing 等
)
```

### 高级用法

#### 使用预构建的 Wheel 文件

```python
result = await app.deploy(
    deployer,
    external_whl_path="/path/to/prebuilt.whl",  # 使用预构建的 wheel
    skip_upload=False,  # 仍需要上传到 OSS
    # ... 其他参数
)
```

#### 更新现有部署

```python
result = await app.deploy(
    deployer,
    agentrun_id="existing-agentrun-id",  # 更新现有部署
    # ... 其他参数
)
```

## 方法6：PAI部署（Platform for AI）

**最适合**：需要在阿里云PAI平台上部署，利用LangStudio进行项目管理和EAS（弹性算法服务）进行服务部署的企业用户。

### 特性
- 阿里云PAI平台的全托管部署
- 集成LangStudio项目和快照管理
- 支持EAS（弹性算法服务）服务部署
- 三种资源类型：公共资源池、专属资源组、配额
- VPC网络配置支持
- RAM角色和权限配置
- 链路追踪（Tracing）支持
- 自动/手动审批工作流
- 自动生成部署标签

### PAI 部署前置条件

```bash
# 确保设置环境变量
export ALIBABA_CLOUD_ACCESS_KEY_ID="your-access-key-id"
export ALIBABA_CLOUD_ACCESS_KEY_SECRET="your-access-key-secret"

# 可选配置
export PAI_WORKSPACE_ID="your-workspace-id"
export REGION_ID="cn-hangzhou"  # 或 ALIBABA_CLOUD_REGION_ID
```

您可以设置以下环境变量或通过配置文件/CLI参数来自定义部署：

| 变量 | 必填 | 默认值 | 描述 |
|-----|-----|-------|------|
| `ALIBABA_CLOUD_ACCESS_KEY_ID` | 是 | - | 阿里云 Access Key ID |
| `ALIBABA_CLOUD_ACCESS_KEY_SECRET` | 是 | - | 阿里云 Access Key Secret |
| `PAI_WORKSPACE_ID` | 否 | - | PAI 工作空间 ID（可通过CLI或配置文件指定） |
| `REGION_ID` / `ALIBABA_CLOUD_REGION_ID` | 否 | `cn-hangzhou` | 地域 ID |
| `ALIBABA_CLOUD_SECURITY_TOKEN` | 否 | - | STS 临时安全令牌（使用STS时） |

### PAI 工作空间要求

- 如果使用 RAM 用户账号，需要分配 PAI 开发者角色
- 需要配置 OSS 存储桶用于存储构建产物
- （可选）如果使用 DashScope 模型，需要配置可访问公网的 VPC

> **注意**：部署到 PAI EAS 的服务默认没有公网访问权限，如果使用 DashScope 模型，需要配置可访问公网的 VPC。参考：[配置网络连通性](https://help.aliyun.com/zh/pai/user-guide/configure-network-connectivity)

### 实现（SDK方式）

使用 {ref}`通用智能体配置<zh-common-agent-setup>` 部分定义的智能体和端点：

```{code-cell}
# pai_deploy.py
import asyncio
import os
from agentscope_runtime.engine.deployers.pai_deployer import (
    PAIDeployManager,
)
from agent_app import app  # 导入已配置的 app

async def deploy_to_pai():
    """将 AgentApp 部署到阿里云 PAI"""

    # 创建 PAI 部署管理器
    deployer = PAIDeployManager(
        workspace_id=os.environ.get("PAI_WORKSPACE_ID"),
        region_id=os.environ.get("REGION_ID", "cn-hangzhou"),
    )

    # 执行部署
    result = await app.deploy(
        deployer,
        service_name="my-agent-service",
        project_dir="./my_agent",
        entrypoint="agent.py",
        resource_type="public",
        instance_type="ecs.c6.large",
        instance_count=1,
        environment={
            "DASHSCOPE_API_KEY": os.environ.get("DASHSCOPE_API_KEY"),
        },
        enable_trace=True,
        wait=True,
    )

    print(f"✅ 部署成功：{result['url']}")
    print(f"📍 部署 ID：{result['deploy_id']}")
    print(f"📦 项目 ID：{result['flow_id']}")
    return result

if __name__ == "__main__":
    asyncio.run(deploy_to_pai())
```

**关键点**：
- 自动打包项目并上传到 OSS
- 创建 LangStudio 项目和快照
- 部署为 EAS 服务
- 支持多种资源类型配置

### 实现（CLI方式）

PAI 部署推荐使用配置文件方式，更加清晰和可维护：

**方式1：使用配置文件（推荐）**

```bash
# 进入示例目录
cd examples/deployments/pai_deploy

# 使用配置文件部署
agentscope deploy pai --config deploy_config.yaml

# 使用配置文件并覆盖部分参数
agentscope deploy pai --config deploy_config.yaml --name new-service-name
```

**方式2：仅使用 CLI 参数**

```bash
agentscope deploy pai ./my_agent \
  --name my-service \
  --workspace-id 12345 \
  --region cn-hangzhou \
  --instance-type ecs.c6.large \
  --env DASHSCOPE_API_KEY=your-key
```

**完整 CLI 选项**

```bash
agentscope deploy pai [SOURCE] [OPTIONS]

参数:
  SOURCE                  源代码目录或文件（使用配置文件时可选）

选项:
  --config, -c PATH       部署配置文件路径 (.yaml)
  --name TEXT             服务名称（必填）
  --workspace-id TEXT     PAI 工作空间 ID
  --region TEXT           地域 ID（如 cn-hangzhou）
  --entrypoint TEXT       入口文件（默认：app.py, agent.py, main.py）
  --oss-path TEXT         OSS 工作目录
  --instance-type TEXT    实例类型（公共资源池模式）
  --instance-count INT    实例数量
  --resource-id TEXT      EAS 资源组 ID（资源组模式）
  --quota-id TEXT         PAI 配额 ID（配额模式）
  --cpu INT               CPU 核数
  --memory INT            内存大小（MB）
  --service-group TEXT    服务组名称
  --resource-type TEXT    资源类型：public, resource, quota
  --vpc-id TEXT           VPC ID
  --vswitch-id TEXT       交换机 ID
  --security-group-id TEXT  安全组 ID
  --ram-role-arn TEXT     RAM 角色 ARN
  --enable-trace/--no-trace  启用/禁用链路追踪
  --wait/--no-wait        等待部署完成
  --timeout INT           部署超时时间（秒）
  --auto-approve/--no-auto-approve  自动审批部署
  --env, -E TEXT          环境变量（KEY=VALUE，可重复）
  --env-file PATH         .env 文件路径
  --tag, -T TEXT          标签（KEY=VALUE，可重复）
```

### 配置说明

#### PAIDeployConfig 配置结构

PAI 部署使用 YAML 配置文件，结构如下：

```yaml
# deploy_config.yaml
context:
  # PAI 工作空间 ID（必填）
  workspace_id: "your-workspace-id"
  # 地域（如 cn-hangzhou, cn-shanghai）
  region: "cn-hangzhou"

spec:
  # 服务名称（必填，地域内唯一）
  name: "my_agent_service"

  code:
    # 源代码目录（相对于配置文件位置）
    source_dir: "my_agent"
    # 入口文件
    entrypoint: "agent.py"

  resources:
    # 资源类型：public, resource, quota
    type: "public"
    # 实例类型（public模式必填）
    instance_type: "ecs.c6.large"
    # 实例数量
    instance_count: 1

  # VPC 配置（可选）
  vpc_config:
    vpc_id: "vpc-xxxxx"
    vswitch_id: "vsw-xxxxx"
    security_group_id: "sg-xxxxx"

  # RAM 角色配置（可选）
  identity:
    ram_role_arn: "acs:ram::xxx:role/xxx"

  # 可观测性配置
  observability:
    enable_trace: true

  # 环境变量
  env:
    DASHSCOPE_API_KEY: "your-dashscope-api-key"

  # 标签
  tags:
    team: "ai-team"
    project: "agent-demo"
```

> **注意**：`code.source_dir` 是相对于配置文件位置的路径。

#### 配置结构说明

| 配置项 | 说明 |
|--------|------|
| `context` | 部署目标（工作空间、地域、存储） |
| `spec.name` | 服务名称（必填） |
| `spec.code` | 源代码目录和入口文件 |
| `spec.resources` | 资源配置 |
| `spec.vpc_config` | VPC 网络配置（可选） |
| `spec.identity` | RAM 角色配置（可选） |
| `spec.observability` | 链路追踪设置 |
| `spec.env` | 环境变量 |
| `spec.tags` | 部署标签 |

### 资源类型

PAI 支持三种资源类型：

#### 1. 公共资源池 (`type: "public"`)

部署到共享 ECS 实例，适合开发测试和小规模部署：

```yaml
spec:
  resources:
    type: "public"
    instance_type: "ecs.c6.large"  # 必填
    instance_count: 1
```

#### 2. 专属资源组 (`type: "resource"`)

部署到专属 EAS 资源组，适合生产环境和需要资源隔离的场景：

```yaml
spec:
  resources:
    type: "resource"
    resource_id: "eas-r-xxxxx"  # 必填
    cpu: 2
    memory: 4096
```

#### 3. 配额模式 (`type: "quota"`)

使用 PAI 配额部署，适合企业级资源管理：

```yaml
spec:
  resources:
    type: "quota"
    quota_id: "quota-xxxxxxxx"  # 必填
    cpu: 2
    memory: 4096
```

### VPC 配置

私有网络部署配置，适用于需要访问公网或内网资源的场景：

```yaml
spec:
  vpc_config:
    vpc_id: "vpc-xxxxx"
    vswitch_id: "vsw-xxxxx"
    security_group_id: "sg-xxxxx"
```

### 高级用法

#### 手动审批工作流

默认情况下，部署会自动审批。如需手动审批：

```bash
# 使用 --no-auto-approve 选项
agentscope deploy pai --config deploy_config.yaml --no-auto-approve
```

在交互式终端中，CLI 会提示您选择：
- `[A]pprove` - 审批并开始部署
- `[C]ancel` - 取消部署
- `[S]kip` - 跳过，稍后在控制台审批

#### 环境变量注入

**方式1：配置文件**

```yaml
spec:
  env:
    DASHSCOPE_API_KEY: "your-key"
    MY_CONFIG: "value"
```

**方式2：CLI 参数**

```bash
agentscope deploy pai ./my_agent \
  --env DASHSCOPE_API_KEY=your-key \
  --env MY_CONFIG=value
```

**方式3：.env 文件**

```bash
agentscope deploy pai ./my_agent --env-file .env
```

#### 自动生成的标签

以下标签会自动添加到部署中：

- `deployed-by: agentscope-runtime`
- `client-version: <版本号>`
- `deploy-method: cli`

#### 管理部署

```bash
# 停止部署
agentscope stop <deploy-id>

# 查看部署状态
# 访问部署后提供的 PAI 控制台 URL
```

### 故障排查

#### 常见问题

1. **"PAI deployer is not available"**

   ```bash
   pip install 'agentscope-runtime[ext]'
   ```

2. **"Workspace ID is required"**
   - 设置 `PAI_WORKSPACE_ID` 环境变量，或
   - 使用 `--workspace-id` CLI 选项，或
   - 在配置文件中添加 `context.workspace_id`

3. **"Service name is owned by another user"**
   - 选择不同的服务名称（必须在地域内唯一）

4. **凭证错误**
   - 验证 `ALIBABA_CLOUD_ACCESS_KEY_ID` 和 `ALIBABA_CLOUD_ACCESS_KEY_SECRET`
   - 检查 RAM 权限是否包含 PAI/EAS/OSS 访问权限

5. **OSS 上传失败**
   - 确保 OSS 存储桶存在且可访问
   - 检查工作空间和 OSS 存储桶的地域是否一致

### 完整示例

更详细的 PAI 部署示例请参考：
- 示例目录：`examples/deployments/pai_deploy/`
- 配置文件示例：`examples/deployments/pai_deploy/deploy_config.yaml`

## 方法7：Knative部署

**最适合**：需要扩展性、高可用性和云原生 Serverless 容器编排的企业生产环境。

### 特性
- 基于容器的 Serverless 部署
- 基于请求自动弹性、缩容至0
- 云原生编排
- 资源管理和限制
- 健康检查和自动恢复

### Knative 部署前置条件

```bash
# 确保Docker正在运行
docker --version

# 验证Kubernetes访问
kubectl cluster-info

# 检查镜像仓库访问（以阿里云为例）
docker login your-registry

# 检查 Knative Serving 已安装
kubectl auth can-i create ksvc

```

### 实现

使用 {ref}`通用智能体配置<zh-common-agent-setup>` 部分定义的智能体和端点：

```{code-cell}
# knative_deploy.py
import asyncio
import os
from agentscope_runtime.engine.deployers.knative_deployer import (
    KnativeDeployManager,
    RegistryConfig,
    K8sConfig,
)
from agent_app import app  # 导入已配置的 app

async def deploy_to_knative():
    """将 AgentApp 部署到 Knative"""

    # 配置镜像仓库和 K8s 连接
    deployer = KnativeDeployManager(
        kube_config=K8sConfig(
            k8s_namespace="agentscope-runtime",
            kubeconfig_path=None,
        ),
        registry_config=RegistryConfig(
            registry_url="your-registry-url",
            namespace="agentscope-runtime",
        ),
    )

    # 执行部署
    result = await app.deploy(
        deployer,
        port="8080",
        image_name="agent_app",
        image_tag="v1.0",
        requirements=["agentscope", "fastapi", "uvicorn"],
        base_image="python:3.10-slim-bookworm",
        environment={
            "PYTHONPATH": "/app",
            "DASHSCOPE_API_KEY": os.environ.get("DASHSCOPE_API_KEY"),
        },
        labels: {
          "app":"agent-ksvc",
        },
        runtime_config={
        "resources": {
            "requests": {"cpu": "200m", "memory": "512Mi"},
            "limits": {"cpu": "1000m", "memory": "2Gi"},
        },
        },
        platform="linux/amd64",
        push_to_registry=True,
    )

    print(f"✅ 部署成功：{result['url']}")
    return result, deployer

if __name__ == "__main__":
    asyncio.run(deploy_to_knative())
```

**关键点**：
- 容器化 Serverless 部署
- 支持基于请求自动弹性、缩容至 0
- 配置资源限制和健康检查

## 方法8：Kruise部署

**最适合**：需要实例级隔离、暂停恢复能力和安全多租户运行环境的场景。

### 特性
- 基于 Kruise Sandbox CRD（`agents.kruise.io/v1alpha1`）的自定义资源部署
- 实例级隔离，确保不同 agent 运行环境安全
- 支持暂停和恢复，有效节省资源消耗
- 自动创建 LoadBalancer Service 提供外部访问
- 部署状态持久化管理

### Kruise 部署前置条件

```bash
# 确保Docker正在运行
docker --version

# 验证Kubernetes访问
kubectl cluster-info

# 检查镜像仓库访问（以阿里云为例）
docker login your-registry

# 检查 Kruise Sandbox CRD 已安装
# 安装指南：https://github.com/openkruise/agents
kubectl get crd sandboxes.agents.kruise.io
```

### 实现

使用 {ref}`通用智能体配置<zh-common-agent-setup>` 部分定义的智能体和端点：

```{code-cell}
# kruise_deploy.py
import asyncio
import os
from agentscope_runtime.engine.deployers.kruise_deployer import (
    KruiseDeployManager,
    K8sConfig,
)
from agentscope_runtime.engine.deployers.utils.docker_image_utils import (
    RegistryConfig,
)
from agent_app import app  # 导入已配置的 app

async def deploy_to_kruise():
    """将 AgentApp 部署到 Kruise Sandbox"""

    # 配置镜像仓库和 K8s 连接
    deployer = KruiseDeployManager(
        kube_config=K8sConfig(
            k8s_namespace="agentscope-runtime",
            kubeconfig_path=None,
        ),
        registry_config=RegistryConfig(
            registry_url="your-registry-url",
            namespace="agentscope-runtime",
        ),
    )

    # 执行部署
    result = await app.deploy(
        deployer,
        port="8090",
        image_name="agent_app",
        image_tag="v1.0",
        requirements=["agentscope", "fastapi", "uvicorn"],
        base_image="python:3.10-slim-bookworm",
        environment={
            "PYTHONPATH": "/app",
            "DASHSCOPE_API_KEY": os.environ.get("DASHSCOPE_API_KEY"),
        },
        labels={
            "app": "agent-kruise",
        },
        runtime_config={
            "resources": {
                "requests": {"cpu": "200m", "memory": "512Mi"},
                "limits": {"cpu": "1000m", "memory": "2Gi"},
            },
        },
        platform="linux/amd64",
        push_to_registry=True,
    )

    print(f"✅ 部署成功：{result['url']}")
    return result, deployer

if __name__ == "__main__":
    asyncio.run(deploy_to_kruise())
```

**关键点**：
- 基于 Kruise Sandbox CRD 的隔离部署，每个 agent 独立运行环境
- 自动创建 LoadBalancer Service，支持本地和云端环境自动切换
- 部署状态自动持久化，支持通过 CLI 管理生命周期

## 方法9：Serverless部署：函数计算（Function Compute, FC）

**最适合**：阿里云用户，需要将智能体部署到函数计算（FC）服务，实现自动化的构建、上传和部署流程。FC 提供真正的 Serverless 体验，按量付费并自动扩缩容。

### 特性
- 阿里云函数计算的 Serverless 部署
- 使用 Docker 自动构建和打包项目
- OSS 集成用于制品存储
- HTTP 触发器支持公网访问
- 会话亲和性支持有状态应用
- VPC 和日志配置支持
- 按量付费模式

### FC 部署前置条件

```bash
# 确保设置环境变量
# 更多环境变量配置，请参考下面的表格
export ALIBABA_CLOUD_ACCESS_KEY_ID="your-access-key-id"
export ALIBABA_CLOUD_ACCESS_KEY_SECRET="your-access-key-secret"
export FC_ACCOUNT_ID="your-fc-account-id"
export FC_REGION_ID="cn-hangzhou"  # 或其他区域

# OSS 配置（用于存储构建制品）
export OSS_ACCESS_KEY_ID="your-oss-access-key-id"
export OSS_ACCESS_KEY_SECRET="your-oss-access-key-secret"
export OSS_REGION="cn-hangzhou"
export OSS_BUCKET_NAME="your-bucket-name"
```

您可以设置以下环境变量或指定 `FCConfig` 来自定义部署：

| 变量 | 必填 | 默认值 | 描述 |
|-----|-----|-------|------|
| `ALIBABA_CLOUD_ACCESS_KEY_ID` | 是 | - | 阿里云 Access Key ID |
| `ALIBABA_CLOUD_ACCESS_KEY_SECRET` | 是 | - | 阿里云 Access Key Secret |
| `FC_ACCOUNT_ID` | 是 | - | 阿里云账号 ID（用于 FC） |
| `FC_REGION_ID` | 否 | `cn-hangzhou` | FC 服务的区域 ID |
| `FC_LOG_STORE` | 否 | - | 日志存储名称（需同时设置 log_project） |
| `FC_LOG_PROJECT` | 否 | - | 日志项目名称（需同时设置 log_store） |
| `FC_VPC_ID` | 否 | - | VPC ID（用于私网访问） |
| `FC_SECURITY_GROUP_ID` | 否 | - | 安全组 ID（设置 vpc_id 时必填） |
| `FC_VSWITCH_IDS` | 否 | - | VSwitch ID 列表，JSON 数组格式（设置 vpc_id 时必填） |
| `FC_CPU` | 否 | `2.0` | CPU 分配（核数） |
| `FC_MEMORY` | 否 | `2048` | 内存分配（MB） |
| `FC_DISK` | 否 | `512` | 磁盘分配（MB） |
| `FC_EXECUTION_ROLE_ARN` | 否 | - | 执行角色 ARN（用于权限控制） |
| `FC_SESSION_CONCURRENCY_LIMIT` | 否 | `200` | 每实例会话并发限制 |
| `FC_SESSION_IDLE_TIMEOUT_SECONDS` | 否 | `3600` | 会话空闲超时时间（秒） |
| `OSS_ACCESS_KEY_ID` | 否 | `ALIBABA_CLOUD_ACCESS_KEY_ID` | OSS Access Key ID（默认使用阿里云凭证） |
| `OSS_ACCESS_KEY_SECRET` | 否 | `ALIBABA_CLOUD_ACCESS_KEY_SECRET` | OSS Access Key Secret（默认使用阿里云凭证） |
| `OSS_REGION` | 否 | `cn-hangzhou` | OSS 区域 |
| `OSS_BUCKET_NAME` | 是 | - | OSS 存储桶名称（用于存储构建制品） |

### 实现

使用 {ref}`通用智能体配置<zh-common-agent-setup>` 部分定义的智能体和端点：

```{code-cell}
# fc_deploy.py
import asyncio
import os
from agentscope_runtime.engine.deployers.fc_deployer import (
    FCDeployManager,
    OSSConfig,
    FCConfig,
)
from agent_app import app  # 导入已配置的 app

async def deploy_to_fc():
    """将 AgentApp 部署到阿里云函数计算（FC）"""

    # 配置 OSS 和 FC
    deployer = FCDeployManager(
        oss_config=OSSConfig(
            access_key_id=os.environ.get("OSS_ACCESS_KEY_ID"),
            access_key_secret=os.environ.get("OSS_ACCESS_KEY_SECRET"),
            region=os.environ.get("OSS_REGION", "cn-hangzhou"),
            bucket_name=os.environ.get("OSS_BUCKET_NAME"),
        ),
        fc_config=FCConfig(
            access_key_id=os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_ID"),
            access_key_secret=os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_SECRET"),
            account_id=os.environ.get("FC_ACCOUNT_ID"),
            region_id=os.environ.get("FC_REGION_ID", "cn-hangzhou"),
        ),
    )

    # 执行部署
    result = await app.deploy(
        deployer,
        deploy_name="agent-app-example",
        requirements=["agentscope", "fastapi", "uvicorn"],
        environment={
            "PYTHONPATH": "/code",
            "DASHSCOPE_API_KEY": os.environ.get("DASHSCOPE_API_KEY"),
        },
    )

    print(f"✅ 部署到 FC：{result['url']}")
    print(f"📍 函数名称：{result['function_name']}")
    print(f"🔗 端点 URL：{result['endpoint_url']}")
    print(f"📦 制品 URL：{result['artifact_url']}")
    return result

if __name__ == "__main__":
    asyncio.run(deploy_to_fc())
```

**关键点**：
- 使用 Docker 自动构建项目并创建可部署的 zip 包
- 上传制品到 OSS 供 FC 拉取
- 创建带 HTTP 触发器的 FC 函数，支持公网访问
- 通过 `x-agentscope-runtime-session-id` 请求头支持会话亲和性
- 支持更新现有部署（通过 `function_name` 参数）

### 配置说明

#### OSSConfig

OSS 配置用于存储构建制品：

```python
OSSConfig(
    access_key_id="your-access-key-id",
    access_key_secret="your-access-key-secret",
    region="cn-hangzhou",
    bucket_name="your-bucket-name",
)
```

#### FCConfig

函数计算服务配置：

```python
FCConfig(
    access_key_id="your-access-key-id",
    access_key_secret="your-access-key-secret",
    account_id="your-account-id",
    region_id="cn-hangzhou",  # 支持的区域：cn-hangzhou, cn-beijing 等
    cpu=2.0,  # CPU 核数
    memory=2048,  # 内存 MB
    disk=512,  # 磁盘 MB
)
```

### 高级用法

#### 更新现有函数

```python
result = await app.deploy(
    deployer,
    function_name="existing-function-name",  # 更新现有函数
    # ... 其他参数
)
```

#### 从项目目录部署

```python
result = await app.deploy(
    deployer,
    project_dir="/path/to/project",  # 项目目录
    cmd="python main.py",  # 启动命令
    deploy_name="my-agent-app",
    # ... 其他参数
)
```

### 测试部署的服务

部署后，您可以使用 curl 测试端点：

```bash
# 健康检查
curl https://<your-endpoint-url>/health

# 测试同步端点（带会话亲和性）
curl -X POST https://<your-endpoint-url>/sync \
  -H "Content-Type: application/json" \
  -H "x-agentscope-runtime-session-id: 123" \
  -d '{
    "input": [
      {
        "role": "user",
        "content": [
          {
            "type": "text",
            "text": "你好，最近怎么样？"
          }
        ]
      }
    ],
    "session_id": "123"
  }'

# 测试流式端点
curl -X POST https://<your-endpoint-url>/stream_async \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -H "x-agentscope-runtime-session-id: 123" \
  --no-buffer \
  -d '{
    "input": [
      {
        "role": "user",
        "content": [
          {
            "type": "text",
            "text": "给我讲个故事"
          }
        ]
      }
    ],
    "session_id": "123"
  }'
```

**注意**：`x-agentscope-runtime-session-id` 请求头启用会话亲和性，将具有相同会话 ID 的请求路由到同一 FC 实例，以支持有状态操作。

