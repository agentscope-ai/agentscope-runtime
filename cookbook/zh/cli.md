# AgentScope Runtime CLI (`agentscope`)

用于管理智能体开发、部署和运行时操作的统一命令行接口。

## 目录

- [快速开始](#快速开始)
- [完整示例](#完整示例)
- [核心命令](#核心命令)
  - [开发：`agentscope chat`](#1-开发agentscope-chat)
  - [Web UI：`agentscope web`](#2-web-uiagentscope-web)
  - [运行智能体服务：`agentscope run`](#3-运行智能体服务agentscope-run)
  - [部署：`agentscope deploy`](#4-部署agentscope-deploy)
  - [部署管理](#5-部署管理)
  - [沙箱管理：`agentscope sandbox`](#6-沙箱管理as-runtime-sandbox)
- [API 参考](#api-参考)
- [常用工作流](#常用工作流)
- [故障排除](#故障排除)

## 快速开始

### 安装

```bash
pip install agentscope-runtime
```

### 验证安装

```bash
agentscope --version
agentscope --help
```

## 完整示例

本节提供了创建、运行和部署智能体的完整教程。

### 步骤 1：创建智能体项目

创建项目目录结构：

```
my-agent-project/
├── app_agent.py          # 主智能体文件
├── requirements.txt      # Python 依赖（可选）
└── .env                  # 环境变量（可选）
```

### 步骤 2：编写智能体代码

创建 `app_agent.py`：

```python
# -*- coding: utf-8 -*-
import os

from agentscope.agent import ReActAgent
from agentscope.formatter import DashScopeChatFormatter
from agentscope.model import DashScopeChatModel
from agentscope.pipeline import stream_printing_messages
from agentscope.tool import Toolkit, execute_python_code

from agentscope_runtime.adapters.agentscope.memory import (
    AgentScopeSessionHistoryMemory,
)
from agentscope_runtime.engine.app import AgentApp
from agentscope_runtime.engine.schemas.agent_schemas import AgentRequest
from agentscope_runtime.engine.services.agent_state import (
    InMemoryStateService,
)
from agentscope_runtime.engine.services.session_history import (
    InMemorySessionHistoryService,
)

# Create AgentApp instance
agent_app = AgentApp(
    app_name="MyAssistant",
    app_description="A helpful assistant agent",
)


@agent_app.init
async def init_func(self):
    """Initialize services."""
    self.state_service = InMemoryStateService()
    self.session_service = InMemorySessionHistoryService()

    await self.state_service.start()
    await self.session_service.start()


@agent_app.shutdown
async def shutdown_func(self):
    """Cleanup services."""
    await self.state_service.stop()
    await self.session_service.stop()


@agent_app.query(framework="agentscope")
async def query_func(
    self,
    msgs,
    request: AgentRequest = None,
    **kwargs,
):
    """Process user queries."""
    session_id = request.session_id
    user_id = request.user_id

    # Load state if exists
    state = await self.state_service.export_state(
        session_id=session_id,
        user_id=user_id,
    )

    # Create toolkit with Python execution
    toolkit = Toolkit()
    toolkit.register_tool_function(execute_python_code)

    # Create agent
    agent = ReActAgent(
        name="MyAssistant",
        model=DashScopeChatModel(
            "qwen-turbo",
            api_key=os.getenv("DASHSCOPE_API_KEY"),
            enable_thinking=True,
            stream=True,
        ),
        sys_prompt="You're a helpful assistant.",
        toolkit=toolkit,
        memory=AgentScopeSessionHistoryMemory(
            service=self.session_service,
            session_id=session_id,
            user_id=user_id,
        ),
        formatter=DashScopeChatFormatter(),
    )
    agent.set_console_output_enabled(False)

    # Load state if available
    if state:
        agent.load_state_dict(state)

    # Process query and stream response
    async for msg, last in stream_printing_messages(
        agents=[agent],
        coroutine_task=agent(msgs),
    ):
        yield msg, last

    # Save state
    state = agent.state_dict()
    await self.state_service.save_state(
        user_id=user_id,
        session_id=session_id,
        state=state,
    )


if __name__ == "__main__":
    agent_app.run()
```

### 步骤 3：本地运行智能体

**交互模式（多轮对话）：**

```bash
cd my-agent-project
export DASHSCOPE_API_KEY=sk-your-api-key
agentscope chat app_agent.py
```

**单次查询模式：**

```bash
agentscope chat app_agent.py --query "Hello, how are you?"
```

**使用自定义会话：**

```bash
agentscope chat app_agent.py --query "Hello" --session-id my-session --user-id user123
```

### 步骤 4：使用 Web UI 测试

```bash
agentscope web app_agent.py
```
默认情况下，后端服务将在 `http://127.0.0.1:8090` 启动，Web 服务器在 `http://localhost:5173/` 启动。
在浏览器中打开它。

### 步骤 5：部署智能体

**本地部署：**

```bash
agentscope deploy local app_agent.py --env DASHSCOPE_API_KEY=sk-your-api-key
```

部署成功后，您将收到：
- **部署 ID**：`local_20250101_120000_abc123`
- **URL**：`http://127.0.0.1:8080`

**通过 curl 查询已部署的智能体：**

```bash
curl -i -X POST "http://127.0.0.1:8080/process" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer 8ddcc903-b75b-40b8-ba7f-1501e05cb3f2" \
  -d '{
    "input": [
      {
        "role": "user",
        "content": [
          {
            "type": "text",
            "text": "Hello, how are you?"
          }
        ]
      }
    ],
    "session_id": "123"
  }'
```

**或使用 CLI：**

```bash
agentscope chat local_20250101_120000_abc123 --query "Hello"
```

### 步骤 6：停止部署

```bash
agentscope stop local_20250101_120000_abc123
```

## 核心命令

### 1. 开发：`agentscope chat`

在开发过程中以交互方式运行智能体或执行单次查询进行测试。

#### 命令语法

```bash
agentscope chat SOURCE [OPTIONS]
```

#### 参数

| 参数 | 类型 | 必需 | 描述 |
|------|------|------|------|
| `SOURCE` | string | 是 | Python 文件路径、项目目录或部署 ID |

#### 选项

| 选项 | 简写 | 类型 | 默认值 | 描述 |
|------|------|------|--------|------|
| `--query` | `-q` | string | `None` | 要执行的单次查询（非交互模式）。如果提供，执行查询后退出 |
| `--session-id` | - | string | `None` | 用于对话连续性的会话 ID。如果未提供，将生成随机会话 ID |
| `--user-id` | - | string | `"default_user"` | 会话的用户 ID |
| `--verbose` | `-v` | flag | `False` | 显示详细输出，包括日志和推理过程 |
| `--entrypoint` | `-e` | string | `None` | 目录源的入口文件名（例如 'app.py'、'main.py'）。仅在 SOURCE 为目录时使用 |

#### 示例

**交互模式（多轮对话）：**

```bash
# 启动交互式会话
agentscope chat app_agent.py

# 从项目目录加载
agentscope chat ./my-agent-project

# 使用现有部署
agentscope chat local_20250101_120000_abc123
```

**单次查询模式：**

```bash
# 执行一次查询后退出
agentscope chat app_agent.py --query "What is the weather today?"

# 使用自定义会话和用户
agentscope chat app_agent.py --query "Hello" --session-id my-session --user-id user123

# 详细模式（显示推理过程和日志）
agentscope chat app_agent.py --query "Hello" --verbose
```

**使用自定义入口点的项目目录：**

```bash
agentscope chat ./my-project --entrypoint custom_app.py
```

#### 智能体文件要求

您的智能体文件**必须**将 `agent_app.run()` 作为主方法运行。

### 2. Web UI：`agentscope web`

启动带有基于浏览器的 Web 界面的智能体进行测试。

#### 命令语法

```bash
agentscope web SOURCE [OPTIONS]
```

#### 参数

| 参数 | 类型 | 必需 | 描述 |
|------|------|------|------|
| `SOURCE` | string | 是 | Python 文件路径或项目目录 |

#### 选项

| 选项 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| `--host` | string | `"127.0.0.1"` | Web 服务器绑定的主机地址 |
| `--port` | integer | `8090` | Web 服务器绑定的端口 |
| `--entrypoint` | string | `None` | 目录源的入口文件名 |

#### 示例

```bash
# 默认主机和端口 (127.0.0.1:8090)
agentscope web app_agent.py

# 自定义主机和端口
agentscope web app_agent.py --host 0.0.0.0 --port 8000

# 从项目目录启动
agentscope web ./my-agent-project
```

**注意：** 首次启动可能需要更长时间，因为需要通过 npm 安装 Web UI 依赖。

### 3. 运行智能体服务：`agentscope run`

启动智能体服务并持续运行，暴露 HTTP API 端点供程序化访问。

#### 命令语法

```bash
agentscope run SOURCE [OPTIONS]
```

#### 参数

| 参数 | 类型 | 必需 | 描述 |
|------|------|------|------|
| `SOURCE` | string | 是 | Python 文件路径、项目目录或部署 ID |

#### 选项

| 选项 | 简写 | 类型 | 默认值 | 描述 |
|------|------|------|--------|------|
| `--host` | `-h` | string | `"0.0.0.0"` | 绑定的主机地址 |
| `--port` | `-p` | integer | `8080` | 服务端口号 |
| `--verbose` | `-v` | flag | `False` | 显示详细输出，包括日志 |
| `--entrypoint` | `-e` | string | `None` | 目录源的入口文件名（例如 'app.py'、'main.py'） |

#### 示例

```bash
# 使用默认配置运行智能体服务 (0.0.0.0:8080)
agentscope run app_agent.py

# 指定自定义主机和端口
agentscope run app_agent.py --host 127.0.0.1 --port 8090

# 带详细日志运行
agentscope run app_agent.py --verbose

# 使用自定义入口点的目录源
agentscope run ./my-project --entrypoint custom_app.py

```

#### 使用场景

`run` 命令适用于：
- 将智能体作为后台服务运行
- 提供 HTTP API 访问而不需要交互式 CLI
- 通过 HTTP 与其他应用程序集成
- 类生产环境的本地测试

#### 访问服务

服务运行后，可以通过 HTTP API 访问：

```bash
curl -X POST "http://127.0.0.1:8080/process" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "input": [
      {
        "role": "user",
        "content": [{"type": "text", "text": "Hello!"}]
      }
    ],
    "session_id": "my-session"
  }'
```

**注意：** 按 Ctrl+C 可以停止服务。

### 4. 部署：`agentscope deploy`

将智能体部署到各种平台以供生产使用。

#### 命令语法

```bash
agentscope deploy PLATFORM SOURCE [OPTIONS]
```

#### 平台

- `modelstudio`：阿里云 ModelStudio
- `agentrun`：阿里云 AgentRun
- `k8s`：Kubernetes/ACK
- `knative`：Knative/ACK Knative

#### 通用选项（所有平台）

| 选项 | 简写 | 类型 | 默认值 | 描述 |
|------|------|------|--------|------|
| `--name` | - | string | `None` | 部署名称。如果未提供，将自动生成 |
| `--entrypoint` | `-e` | string | `None` | 目录源的入口文件名（例如 'app.py'、'main.py'） |
| `--env` | `-E` | string (multiple) | - | 环境变量，格式为 `KEY=VALUE`。可以重复多次 |
| `--env-file` | - | path | `None` | 包含环境变量的 `.env` 文件路径 |
| `--config` | `-c` | path | `None` | 部署配置文件路径（`.json`、`.yaml` 或 `.yml`） |


#### 4.1. ModelStudio 部署

部署到阿里云 ModelStudio。

##### 命令语法

```bash
agentscope deploy modelstudio SOURCE [OPTIONS]
```

##### 平台特定选项

| 选项 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| `--skip-upload` | flag | `False` | 构建包但不上传到 ModelStudio |

##### 前置要求

- 阿里云账户
- 已配置 ModelStudio 访问权限
- 环境变量：`DASHSCOPE_API_KEY`（或其他必需的凭证）

##### 示例

```bash
# 基本部署
export USE_LOCAL_RUNTIME=True
agentscope deploy modelstudio app_agent.py --name my-agent --env DASHSCOPE_API_KEY=sk-xxx

# 构建但不上传
agentscope deploy modelstudio app_agent.py --skip-upload
```

**注意：** `USE_LOCAL_RUNTIME=True` 使用本地 agentscope runtime 而不是 PyPI 版本。
##### 查询已部署的智能体

**使用 curl：**

```bash
curl -i -X POST "http://127.0.0.1:8080/process" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "input": [
      {
        "role": "user",
        "content": [
          {
            "type": "text",
            "text": "Hello, how are you?"
          }
        ]
      }
    ],
    "session_id": "123"
  }'
```

**使用 chat 命令：**

```bash
agentscope chat [DEPLOYMENT_ID] --query "Hello"
```

#### 4.2. AgentRun 部署

部署到阿里云 AgentRun。

##### 命令语法

```bash
agentscope deploy agentrun SOURCE [OPTIONS]
```

##### 平台特定选项

| 选项 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| `--region` | string | `"cn-hangzhou"` | 阿里云区域 |
| `--cpu` | float | `2.0` | CPU 分配（核心数） |
| `--memory` | integer | `2048` | 内存分配（MB） |
| `--skip-upload` | flag | `False` | 构建包但不上传 |

##### 前置要求

- 阿里云账户
- 必需的环境变量：
  - `ALIBABA_CLOUD_ACCESS_KEY_ID`
  - `ALIBABA_CLOUD_ACCESS_KEY_SECRET`

##### 示例

```bash
# 基本部署
agentscope deploy agentrun app_agent.py --name my-agent

# 自定义区域和资源
agentscope deploy agentrun app_agent.py \
  --region cn-beijing \
  --cpu 4.0 \
  --memory 4096 \
  --env DASHSCOPE_API_KEY=sk-xxx
```

#### 4.3. Kubernetes 部署

部署到 Kubernetes/ACK 集群。

##### 命令语法

```bash
agentscope deploy k8s SOURCE [OPTIONS]
```

##### 平台特定选项

| 选项 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| `--namespace` | string | `"agentscope-runtime"` | Kubernetes 命名空间 |
| `--kube-config-path` | `-c` | path | `None` | kubeconfig 文件路径 |
| `--replicas` | integer | `1` | Pod 副本数量 |
| `--port` | integer | `8080` | 容器端口 |
| `--image-name` | string | `"agent_app"` | Docker 镜像名称 |
| `--image-tag` | string | `"linux-amd64"` | Docker 镜像标签 |
| `--registry-url` | string | `"localhost"` | 远程注册表 URL |
| `--registry-namespace` | string | `"agentscope-runtime"` | 远程注册表命名空间 |
| `--push` | flag | `False` | 推送镜像到注册表 |
| `--base-image` | string | `"python:3.10-slim-bookworm"` | 基础 Docker 镜像 |
| `--requirements` | string | `None` | Python 依赖（逗号分隔或文件路径） |
| `--cpu-request` | string | `"200m"` | CPU 资源请求（例如 '200m'、'1'） |
| `--cpu-limit` | string | `"1000m"` | CPU 资源限制（例如 '1000m'、'2'） |
| `--memory-request` | string | `"512Mi"` | 内存资源请求（例如 '512Mi'、'1Gi'） |
| `--memory-limit` | string | `"2Gi"` | 内存资源限制（例如 '2Gi'、'4Gi'） |
| `--image-pull-policy` | choice | `"IfNotPresent"` | 镜像拉取策略：`Always`、`IfNotPresent`、`Never` |
| `--deploy-timeout` | integer | `300` | 部署超时时间（秒） |
| `--health-check` | flag | `None` | 启用/禁用健康检查 |
| `--platform` | string | `"linux/amd64"` | 目标平台（例如 'linux/amd64'、'linux/arm64'） |
| `--pypi-mirror` | string | `None` | PyPI 镜像源 URL，用于 pip 包安装（例如 'https://pypi.tuna.tsinghua.edu.cn/simple'）。如果未指定，使用 pip 默认源 |

##### 前置要求

- Kubernetes 集群访问权限
- 已安装 Docker（用于构建镜像）
- 已配置 `kubectl`

##### 示例

```bash
# 基本部署
export USE_LOCAL_RUNTIME=True
agentscope deploy k8s app_agent.py \
  --image-name agent_app \
  --env DASHSCOPE_API_KEY=sk-xxx \
  --image-tag linux-amd64-4 \
  --registry-url your-registry.com \
  --push

# 自定义命名空间和资源
agentscope deploy k8s app_agent.py \
  --namespace production \
  --replicas 3 \
  --cpu-limit 2 \
  --memory-limit 4Gi \
  --env DASHSCOPE_API_KEY=sk-xxx
```

**注意：** `USE_LOCAL_RUNTIME=True` 使用本地 agentscope runtime 而不是 PyPI 版本。

#### 4.4. Knative 部署

部署到 Knative/ACK Knative 集群。

##### 命令语法

```bash
agentscope deploy knative SOURCE [OPTIONS]
```

##### 平台特定选项

| 选项 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| `--namespace` | string | `"agentscope-runtime"` | Kubernetes 命名空间 |
| `--kube-config-path` | `-c` | path | `None` | kubeconfig 文件路径 |
| `--port` | integer | `8080` | 容器端口 |
| `--image-name` | string | `"agent_app"` | Docker 镜像名称 |
| `--image-tag` | string | `"linux-amd64"` | Docker 镜像标签 |
| `--registry-url` | string | `"localhost"` | 远程注册表 URL |
| `--registry-namespace` | string | `"agentscope-runtime"` | 远程注册表命名空间 |
| `--push` | flag | `False` | 推送镜像到注册表 |
| `--base-image` | string | `"python:3.10-slim-bookworm"` | 基础 Docker 镜像 |
| `--requirements` | string | `None` | Python 依赖（逗号分隔或文件路径） |
| `--cpu-request` | string | `"200m"` | CPU 资源请求（例如 '200m'、'1'） |
| `--cpu-limit` | string | `"1000m"` | CPU 资源限制（例如 '1000m'、'2'） |
| `--memory-request` | string | `"512Mi"` | 内存资源请求（例如 '512Mi'、'1Gi'） |
| `--memory-limit` | string | `"2Gi"` | 内存资源限制（例如 '2Gi'、'4Gi'） |
| `--image-pull-policy` | choice | `"IfNotPresent"` | 镜像拉取策略：`Always`、`IfNotPresent`、`Never` |
| `--deploy-timeout` | integer | `300` | 部署超时时间（秒） |
| `--health-check` | flag | `None` | 启用/禁用健康检查 |
| `--platform` | string | `"linux/amd64"` | 目标平台（例如 'linux/amd64'、'linux/arm64'） |
| `--pypi-mirror` | string | `None` | PyPI 镜像源 URL，用于 pip 包安装（例如 'https://pypi.tuna.tsinghua.edu.cn/simple'）。如果未指定，使用 pip 默认源 |

##### 前置要求

- Kubernetes 集群访问权限
- 已安装 Docker（用于构建镜像）
- 已配置 `kubectl`
- 已部署 Knative

##### 示例

```bash
# 基本部署
export USE_LOCAL_RUNTIME=True
agentscope deploy knative app_agent.py \
  --image-name agent_app \
  --env DASHSCOPE_API_KEY=sk-xxx \
  --image-tag linux-amd64-4 \
  --registry-url your-registry.com \
  --push

# 自定义命名空间和资源
agentscope deploy knative app_agent.py \
  --namespace production \
  --cpu-limit 2 \
  --memory-limit 4Gi \
  --env DASHSCOPE_API_KEY=sk-xxx
```

**注意：** `USE_LOCAL_RUNTIME=True` 使用本地 agentscope runtime 而不是 PyPI 版本。

### 5. 部署管理

#### 5.1. 列出部署

列出所有部署及其状态。

##### 命令语法

```bash
agentscope list [OPTIONS]
```

##### 选项

| 选项 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| `--status` | string | `None` | 按状态筛选（例如 'running'、'stopped'） |
| `--platform` | string | `None` | 按平台筛选（例如 'local'、'k8s'、'modelstudio'） |
| `--format` | choice | `"table"` | 输出格式：`table` 或 `json` |

##### 示例

```bash
# 列出所有部署
agentscope list

# 按状态筛选
agentscope list --status running

# 按平台筛选
agentscope list --platform k8s

# JSON 输出
agentscope list --format json
```

#### 5.2. 检查部署状态

显示特定部署的详细信息。

##### 命令语法

```bash
agentscope status DEPLOY_ID [OPTIONS]
```

##### 参数

| 参数 | 类型 | 必需 | 描述 |
|------|------|------|------|
| `DEPLOY_ID` | string | 是 | 部署 ID（例如 `local_20250101_120000_abc123`） |

##### 选项

| 选项 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| `--format` | choice | `"table"` | 输出格式：`table` 或 `json` |

##### 示例

```bash
# 显示详细部署信息
agentscope status local_20250101_120000_abc123

# JSON 格式
agentscope status local_20250101_120000_abc123 --format json
```

#### 5.3. 停止部署

停止正在运行的部署。

##### 命令语法

```bash
agentscope stop DEPLOY_ID [OPTIONS]
```

##### 参数

| 参数 | 类型 | 必需 | 描述 |
|------|------|------|------|
| `DEPLOY_ID` | string | 是 | 部署 ID |

##### 选项

| 选项 | 简写 | 类型 | 默认值 | 描述 |
|------|------|------|--------|------|
| `--yes` | `-y` | flag | `False` | 跳过确认提示 |

##### 示例

```bash
# 停止并显示确认提示
agentscope stop local_20250101_120000_abc123

# 跳过确认
agentscope stop local_20250101_120000_abc123 --yes
```

**注意：** 目前仅更新本地状态。平台特定的清理可能需要单独进行。

#### 5.4. 调用已部署的智能体

使用 CLI 与已部署的智能体交互。

##### 命令语法

```bash
agentscope invoke DEPLOY_ID [OPTIONS]
```

##### 参数

| 参数 | 类型 | 必需 | 描述 |
|------|------|------|------|
| `DEPLOY_ID` | string | 是 | 部署 ID |

##### 选项

| 选项 | 简写 | 类型 | 默认值 | 描述 |
|------|------|------|--------|------|
| `--query` | `-q` | string | `None` | 要执行的单次查询（非交互模式） |
| `--session-id` | - | string | `None` | 用于对话连续性的会话 ID |
| `--user-id` | - | string | `"default_user"` | 会话的用户 ID |

##### 示例

```bash
# 与已部署智能体的交互模式
agentscope invoke local_20250101_120000_abc123

# 单次查询
agentscope invoke local_20250101_120000_abc123 --query "Hello"
```

### 6. 沙箱管理：`agentscope sandbox`

统一 CLI 下的沙箱命令整合。

#### 命令

```bash
# 启动 MCP 服务器
agentscope sandbox mcp

# 启动沙箱管理器服务器
agentscope sandbox server

# 构建沙箱环境
agentscope sandbox build
```

**遗留命令：** 旧的 `runtime-sandbox-*` 命令仍然有效，但建议迁移到 `agentscope sandbox *`。

## API 参考

本节提供以编程方式访问已部署智能体的参考信息。

### HTTP API（已部署的智能体）

当您部署智能体时，它会暴露一个可以通过编程方式调用的 HTTP API 端点。

#### 端点

```
POST /process
```

#### 基础 URL

基础 URL 取决于您的部署：
- **本地部署**：`http://127.0.0.1:8080`（或您的自定义主机:端口）
- **Kubernetes 部署**：您的服务 URL
- **ModelStudio/AgentRun**：平台提供的端点

#### 请求头

| 请求头 | 类型 | 必需 | 描述 |
|--------|------|------|------|
| `Content-Type` | string | 是 | 必须是 `application/json` |
| `Authorization` | string | 是 | Bearer token：`Bearer YOUR_TOKEN` |

#### 请求体

```json
{
  "input": [
    {
      "role": "user",
      "content": [
        {
          "type": "text",
          "text": "Your message here"
        }
      ]
    }
  ],
  "session_id": "string"
}
```

**字段：**
- `input`：包含 `role` 和 `content` 字段的消息对象数组
- `session_id`：用于对话连续性的会话标识符

#### 响应

包含智能体输出的流式响应。响应格式取决于您的智能体实现。

#### 示例：Python 客户端

```python
import requests

url = "http://127.0.0.1:8080/process"
headers = {
    "Content-Type": "application/json",
    "Authorization": "Bearer YOUR_TOKEN"
}
data = {
    "input": [
        {
            "role": "user",
            "content": [{"type": "text", "text": "Hello!"}]
        }
    ],
    "session_id": "my-session-123"
}

response = requests.post(url, json=data, headers=headers, stream=True)
for line in response.iter_lines():
    if line:
        print(line.decode('utf-8'))
```

## 文件系统和工作空间

### 工作空间目录：`.agentscope_runtime`

在部署过程中，部署器会在您的工作空间目录下的 `.agentscope_runtime/` 中创建临时文件和构建产物。此目录会在您当前工作目录中自动创建。

#### 目录结构

```
<workspace>/
└── .agentscope_runtime/
    ├── builds/                          # 构建产物缓存
    │   ├── k8s_20251205_1430_a3f9e2/   # Kubernetes 构建
    │   │   ├── deployment.zip
    │   │   ├── Dockerfile
    │   │   ├── requirements.txt
    │   │   └── ...
    │   ├── modelstudio_20251205_1445_b7c4d1/  # ModelStudio 构建
    │   │   └── *.whl
    │   └── local_20251205_1500_abc123/  # 本地部署包
    │       └── ...
    └── deployments.json                 # 工作空间级别的部署元数据
```

#### 构建产物

构建产物存储在 `builds/` 中，按平台分为子目录：
- **格式**：`{platform}_{YYYYMMDD_HHMM}_{hash}/`
- **内容**：部署包、Dockerfiles、requirements 文件等
- **目的**：当代码未更改时缓存以供重用

#### 管理构建产物

您可以安全地：
- **查看**：检查构建产物以了解正在部署的内容
- **测试**：使用产物调试部署问题
- **删除**：删除旧构建以释放磁盘空间
- **忽略**：将 `.agentscope_runtime/` 添加到 `.gitignore`（不应提交）

**示例：清理旧构建**

   ```bash
# 列出构建目录
ls -la .agentscope_runtime/builds/

# 删除特定构建
rm -rf .agentscope_runtime/builds/k8s_20251205_1430_a3f9e2

# 删除所有构建（保留目录结构）
rm -rf .agentscope_runtime/builds/*
```

**注意：** CLI 使用内容感知缓存，因此删除构建后，如果需要，将在下次部署时重新生成它们。

### 全局状态目录：`~/.agentscope-runtime`

部署元数据和状态存储在您的主目录中：

```
~/.agentscope-runtime/
├── deployments.json              # 全局部署注册表
└── deployments.backup.YYYYMMDD.json  # 每日备份（保留最近 30 天）
```

**特性：**
- 原子文件写入
- 修改前自动备份
- 模式验证和迁移
- 损坏恢复

您可以手动编辑 `deployments.json` 或与团队成员共享它以同步部署状态。

## 常用工作流

### 开发工作流

```bash
# 1. 在本地开发智能体
agentscope chat app_agent.py

# 2. 使用 Web UI 测试
agentscope web app_agent.py

# 3. 准备就绪后部署
agentscope deploy local app_agent.py --env DASHSCOPE_API_KEY=sk-xxx

# 4. 检查部署状态
agentscope list
agentscope status <deployment-id>

# 5. 测试已部署的智能体
agentscope invoke <deployment-id> --query "test query"

# 6. 完成后停止
agentscope stop <deployment-id>
```

### 测试工作流

```bash
# 使用单次查询快速测试
agentscope chat app_agent.py --query "test query"

# 使用对话历史进行交互式测试
agentscope chat app_agent.py --session-id test-session

# 使用 Web UI 测试
agentscope web app_agent.py --port 8080
```

### 生产部署工作流

```bash
# 1. 部署到 Kubernetes
agentscope deploy k8s app_agent.py \
  --image-name my-agent \
  --registry-url registry.example.com \
  --push \
  --replicas 3 \
  --env DASHSCOPE_API_KEY=sk-xxx

# 2. 监控部署
agentscope list --platform k8s

# 3. 检查特定部署
agentscope status <deployment-id>

# 4. 根据需要扩展或更新
# （使用更新的参数重新运行部署命令）

# 5. 不再需要时停止
agentscope stop <deployment-id>
```

## 故障排除

### 智能体加载失败

**错误：** "No AgentApp found in agent.py"

**解决方案：** 确保您的文件导出 `agent_app` 或 `app` 变量，或 `create_app()` 函数。

### 多个 AgentApp 实例

**错误：** "Multiple AgentApp instances found"

**解决方案：** 仅导出一个 AgentApp 实例。注释掉或删除多余的实例。

### 导入错误

**错误：** 模块导入失败

**解决方案：** 确保所有依赖项都已安装，并且智能体文件是有效的 Python 代码。

### 端口已被占用

**错误：** "Address already in use"

**解决方案：** 使用 `--port` 标志使用不同的端口，或停止冲突的进程。

### 部署失败

**错误：** 部署超时或连接错误

**解决方案：**
- 检查网络连接
- 验证凭证和环境变量
- 检查平台特定要求（Docker、Kubernetes 等）
- 查看部署日志：`agentscope status <deployment-id>`

### 会话未持久化

**错误：** 查询之间未维护会话历史

**解决方案：** 确保对相关查询使用相同的 `--session-id`，或让 CLI 自动生成一个。

## 高级用法

### 会话管理

```bash
# 继续之前的会话
agentscope chat app_agent.py --session-id my-session

# 多个用户，同一个智能体
agentscope chat app_agent.py --user-id alice --session-id session1
agentscope chat app_agent.py --user-id bob --session-id session2
```

### 输出格式

```bash
# 人类可读的表格（默认）
agentscope list

# 用于脚本的 JSON
agentscope list --format json | jq '.[] | .id'
```

### 环境变量

您可以通过多种方式提供环境变量：

```bash
# 通过 CLI（最高优先级）
agentscope deploy local app_agent.py --env KEY1=value1 --env KEY2=value2

# 通过环境文件
agentscope deploy local app_agent.py --env-file .env

# 通过配置文件
agentscope deploy local app_agent.py --config deploy-config.yaml
```

优先级顺序：CLI > env-file > 配置文件

### 配置文件

您可以使用 JSON 或 YAML 配置文件：

**deploy-config.yaml:**
```yaml
name: my-agent
host: 0.0.0.0
port: 8080
environment:
  DASHSCOPE_API_KEY: sk-xxx
  OTHER_VAR: value
```

**deploy-config.json:**
```json
{
  "name": "my-agent",
  "host": "0.0.0.0",
  "port": 8080,
  "environment": {
    "DASHSCOPE_API_KEY": "sk-xxx",
    "OTHER_VAR": "value"
  }
}
```

## 下一步

- 查看 [examples/](../../examples/) 获取完整的智能体实现示例
- 查看 [API 文档](../api/) 了解编程用法
- 加入 Discord/DingTalk 社区获取支持

## 反馈

发现错误或有功能请求？请在 GitHub 上提交 issue。

