---
jupytext:
  formats: md:myst
  text_representation:
    extension: .md
    format_name: myst
    format_version: 0.13
    jupytext_version: 1.11.5
kernelspec:
  display_name: Python 3.10
  language: python
  name: python3
---

# 工具沙箱高级用法

```{note}
本节介绍沙箱的高级用法。我们强烈建议在继续之前先完成上一节的基础教程({doc}`sandbox`)。
```

## 远程沙箱服务器

远程沙箱服务器使您能够将沙箱部署为独立服务，提供资源隔离和集中管理等优势。本节介绍如何设置和配置沙箱服务器。设置完成后，您可以通过沙箱SDK 连接到远程沙箱服务器。

### 使用默认配置快速启动

启动沙箱服务器最简单的方式是使用默认配置：

```bash
runtime-sandbox-server
```

上述命令将使用默认设置启动服务器：

- 主机：`127.0.0.1` (localhost)，设置成`0.0.0.0`以提供外部访问
- 端口：`8000`
- 单个工作进程
- 池中的基础沙箱类型
- 本地文件系统存储
- 无Redis缓存

对于高级配置，您可以使用` --config` 选项指定不同的环境设置。例如，要将服务器配置修改为指定的文件，可以使用：

```bash
# 此命令将加载 `custom.env` 文件中定义的设置
runtime-sandbox-server --config custom.env
```

### 自定义配置

对于自定义部署或特定需求，您可以通过在工作目录中创建 `.env` 文件来自定义服务器配置：

```bash
# .env
# 服务设置
HOST="0.0.0.0"
PORT=8000
WORKERS=4
DEBUG=False
BEARER_TOKEN=your-secret-token

# 沙盒管理器设置
DEFAULT_SANDBOX_TYPE=base
POOL_SIZE=10
AUTO_CLEANUP=True
CONTAINER_PREFIX_KEY=agent-runtime-container-
CONTAINER_DEPLOYMENT=docker
DEFAULT_MOUNT_DIR=sessions_mount_dir
PORT_RANGE=[49152,59152]

# Redis设置
REDIS_ENABLED=True
REDIS_SERVER=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_USER=your-redis-user
REDIS_PASSWORD=your-redis-password
REDIS_PORT_KEY=_agent_runtime_container_occupied_ports
REDIS_CONTAINER_POOL_KEY=_agent_runtime_container_container_pool

# OSS 设置
FILE_SYSTEM=oss
OSS_ENDPOINT=http://oss-cn-hangzhou.aliyuncs.com
OSS_ACCESS_KEY_ID=your-access-key-id
OSS_ACCESS_KEY_SECRET=your-access-key-secret
OSS_BUCKET_NAME=your-bucket-name

# K8S 设置
K8S_NAMESPACE=default
KUBECONFIG_PATH=
```

### Configuration Reference

#### Service Settings

| Parameter      | Description    | Default     | Example                          |
| -------------- | -------------- | ----------- | -------------------------------- |
| `HOST`         | 服务器绑定地址 | `127.0.0.1` | `0.0.0.0` 用于外部访问           |
| `PORT`         | 服务器端口     | `8000`      | `8080`, `8008`                   |
| `WORKERS`      | 工作进程数量   | `1`         | `4`                              |
| `DEBUG`        | 启用调试模式   | `False`     | `False` 或 `True` 用于 `FastAPI` |
| `BEARER_TOKEN` | 身份验证令牌   | Empty       | `your-secret-token`              |

#### Runtime Manager Settings

| Parameter              | Description    | Default                    | Notes                                                        |
| ---------------------- | -------------- | -------------------------- | ------------------------------------------------------------ |
| `DEFAULT_SANDBOX_TYPE` | 默认沙箱类型   | `base`                     | `base`, `filesystem`, `browser`                              |
| `POOL_SIZE`            | 预热容器池大小 | `1`                        | 缓存的容器以实现更快启动。`POOL_SIZE` 参数控制预创建并缓存在就绪状态的容器数量。当用户请求新沙箱时，系统将首先尝试从这个预热池中分配，相比从零开始创建容器显著减少启动时间。例如，使用 `POOL_SIZE=10`，系统维护 10 个就绪容器，可以立即分配给新请求 |
| `AUTO_CLEANUP`         | 自动容器清理   | `True`                     | 如果设置为 `True`，服务器关闭后将释放所有沙箱。              |
| `CONTAINER_PREFIX_KEY` | 容器名称前缀   | `agent-runtime-container-` | 用于标识                                                     |
| `CONTAINER_DEPLOYMENT` | 容器运行时     | `docker`                   | 目前支持`docker`和`k8s`                                      |
| `DEFAULT_MOUNT_DIR`    | 默认挂载目录   | `sessions_mount_dir`       | 用于持久存储路径，存储`/workspace` 文件                      |
| `PORT_RANGE`           | 可用端口范围   | `[49152,59152]`            | 用于服务端口分配                                             |

#### （可选）Redis 设置

```{note}
**何时使用 Redis：**
- **单个工作进程（`WORKERS=1`）**：Redis 是可选的。系统可以使用内存缓存来管理沙箱状态，这更简单且延迟更低。
- **多个工作进程（`WORKERS>1`）**：需要 Redis 来在工作进程间共享沙箱状态并确保一致性。
```

Redis 为沙箱状态和状态管理提供缓存。如果只有一个工作进程，您可以使用内存缓存：

| Parameter                  | Description      | Default                                   | Notes                                 |
| -------------------------- | ---------------- | ----------------------------------------- | ------------------------------------- |
| `REDIS_ENABLED`            | 启用 Redis 支持  | `False`                                   | 分布式部署或工作进程数大于 `1` 时必需 |
| `REDIS_SERVER`             | Redis 服务器地址 | localhost                                 | Redis 主机                            |
| `REDIS_PORT`               | Redis 端口       | 6379                                      | 标准 Redis 端口                       |
| `REDIS_DB`                 | Redis 数据库编号 | `0`                                       | 0-15                                  |
| `REDIS_USER`               | Redis 用户名     | Empty                                     | 用于 Redis6+ ACL                      |
| `REDIS_PASSWORD`           | Redis 密码       | Empty                                     | 身份验证                              |
| `REDIS_PORT_KEY`           | 端口跟踪键       | `_agent_runtime_container_occupied_ports` | 内部使用                              |
| `REDIS_CONTAINER_POOL_KEY` | 容器池键         | `_agent_runtime_container_container_pool` | 内部使用                              |

#### OSS 设置 (Optional)

使用[阿里云对象存储服务](https://www.aliyun.com/product/oss)进行分布式文件存储：

| Parameter               | Description      | Default | Notes           |
| ----------------------- | ---------------- | ------- | --------------- |
| `FILE_SYSTEM`           | 文件系统类型     | `local` | `local`或 `oss` |
| `OSS_ENDPOINT`          | OSS端点URL       | 空      | 区域端点        |
| `OSS_ACCESS_KEY_ID`     | OSS 访问密钥 ID  | 空      | 来自 OSS 控制台 |
| `OSS_ACCESS_KEY_SECRET` | OSS 访问密钥秘钥 | 空      | 保持安全        |
| `OSS_BUCKET_NAME`       | OSS 存储桶名称   | 空      | 预创建的存储桶  |

### （可选）K8S 设置

要在沙盒服务器中配置特定于 Kubernetes 的设置，请确保设置 `CONTAINER_DEPLOYMENT=k8s` 。可以考虑调整以下参数：

| Parameter         | Description                  | Default   | Notes                              |
| ----------------- | ---------------------------- | --------- | ---------------------------------- |
| `K8S_NAMESPACE`   | 要使用的 Kubernetes 命名空间 | `default` | 设置资源部署的命名空间             |
| `KUBECONFIG_PATH` | kubeconfig 文件的路径        | `None`    | 指定用于访问集群的 kubeconfig 位置 |

### （可选）AgentRun设置

要在沙盒服务器中配置特定于 [AgentRun]() 的设置，请确保设置 `CONTAINER_DEPLOYMENT=agentrun` 。可以考虑调整以下参数：

| Parameter                     | Description              | Default                          | Notes                                        |
|-------------------------------| ------------------------ |----------------------------------|----------------------------------------------|
| `AGENT_RUN_ACCOUNT_ID`        | 阿里云账号ID             | Empty                           | 阿里云主账号ID                                     |
| `AGENT_RUN_ACCESS_KEY_ID`     | 访问密钥ID               | Empty             | 阿里云AccessKey ID，需要`AliyunAgentRunFullAccess`权限 |
| `AGENT_RUN_ACCESS_KEY_SECRET` | 访问密钥Secret           | Empty         | 阿里云AccessKey Secret                          |
| `AGENT_RUN_REGION_ID`         | 部署区域ID               | Empty | AgentRun部署地域ID                               |
| `AGENT_RUN_CPU`               | CPU规格                  | `2.0`                            | vCPU规格                                       |
| `AGENT_RUN_MEMORY`            | 内存规格                 | `2048`                           | 内存规格(MB)                                     |
| `AGENT_RUN_VPC_ID`            | VPC ID                   | `None`                           | VPC网络ID（可选）                                  |
| `AGENT_RUN_VSWITCH_IDS`       | 交换机ID列表             | `None`                           | VSwitch ID列表（可选）                             |
| `AGENT_RUN_SECURITY_GROUP_ID` | 安全组ID                 | `None`                           | 安全组ID（可选）                                    |
| `AGENT_RUN_PREFIX`            | 资源名称前缀             | `agentscope-sandbox`             | 创建的资源名称前缀                                    |
| `AGENT_RUN_LOG_PROJECT`       | SLS日志项目              | `None`                           | SLS日志项目名称（可选）                                |
| `AGENT_RUN_LOG_STORE`         | SLS日志库                | `None`                           | SLS日志库名称（可选）                                 |

### 启动服务器

配置好`.env` 文件后，启动服务器：

```bash
runtime-sandbox-server
```

服务器将自动从`.env` 文件加载配置并使用您的自定义设置启动。

### 连接到远程服务器

从您的客户端应用程序连接到远程服务器：

```python
from agentscope_runtime.sandbox import BaseSandbox

# 连接到远程服务器（替换为您的实际服务器地址和端口）
with BaseSandbox(
    base_url="http://127.0.0.1:8000",
    bearer_token="your-bearer-token",
) as sandbox:
    # 正常使用沙箱
    result = sandbox.run_shell_command(command="echo 'Hello from remote!'")
    print(result)
```

## 自定义构建沙箱

虽然内置沙箱类型涵盖了常见用例，但您可能会遇到需要专门环境或独特工具组合的场景。创建自定义沙箱允许您根据特定需求定制执行环境。本节演示如何构建和注册您的自定义沙箱类型。

### 从源码安装（自定义沙箱必需）

要创建自定义沙箱，您需要以可编辑模式从源码安装AgentScope Runtime，这允许您修改代码并立即看到更改：

```bash
git clone https://github.com/agentscope-ai/agentscope-runtime.git
cd agentscope-runtime
git submodule update --init --recursive
pip install -e ".[sandbox]"
```

```{note}
创建自定义沙箱时，`-e`（可编辑）标志是必需的，因为它允许您：
- 修改沙箱代码并立即看到更改而无需重新安装
- 将您的自定义沙箱类添加到注册表中
- 迭代开发和测试自定义工具
```

### 创建自定义沙箱类

您可以定义自定义沙箱类型并将其注册到系统中以满足特殊需求。只需继承 `Sandbox` 并使用 `SandboxRegistry.register`装饰器，然后将文件放在 `src/agentscope_runtime/sandbox/custom` 中（例如，`src/agentscope_runtime/sandbox/custom/custom_sandbox.py`）:

```python
# src/agentscope_runtime/sandbox/custom/custom_sandbox.py
# -*- coding: utf-8 -*-
import os

from typing import Optional

from ..version import __version__
from ..registry import SandboxRegistry
from ..enums import SandboxType
from ..box.sandbox import Sandbox

SANDBOXTYPE = "custom_sandbox"


@SandboxRegistry.register(
    f"agentscope/runtime-sandbox-{SANDBOXTYPE}:{__version__}",
    sandbox_type=SANDBOXTYPE,
    security_level="medium",
    timeout=60,
    description="my sandbox",
    environment={
        "TAVILY_API_KEY": os.getenv("TAVILY_API_KEY", ""),
        "AMAP_MAPS_API_KEY": os.getenv("AMAP_MAPS_API_KEY", ""),
    },
)
class CustomSandbox(Sandbox):
    def __init__(
        self,
        sandbox_id: Optional[str] = None,
        timeout: int = 3000,
        base_url: Optional[str] = None,
        bearer_token: Optional[str] = None,
    ):
        super().__init__(
            sandbox_id,
            timeout,
            base_url,
            bearer_token,
            SandboxType(SANDBOXTYPE),
        )

```

### 准备Docker镜像

创建自定义沙箱还需要准备相应的 Docker镜像。镜像应包含您特定用例所需的所有依赖项、工具和配置。

```{note}
**配置选项：**
- **简单MCP 服务器更改**：要简单更改沙箱中的初始MCP 服务器，请修改 `mcp_server_configs.json` 文件
- **高级定制**：对于更高级的用法和定制，您必须非常熟悉Dockerfile 语法和Docker 最佳实践
```

这里是一个自定义沙箱的Dockerfile 示例，它在一个沙箱中集成了文件系统、浏览器和一些有用的 MCP 工具：


```dockerfile
FROM node:22-slim

# Set ENV variables
ENV NODE_ENV=production
ENV WORKSPACE_DIR=/workspace

ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --fix-missing \
    curl \
    python3 \
    python3-pip \
    python3-venv \
    build-essential \
    libssl-dev \
    git \
    supervisor \
    vim \
    nginx \
    gettext-base

WORKDIR /agentscope_runtime
RUN python3 -m venv venv
ENV PATH="/agentscope_runtime/venv/bin:$PATH"

# Copy application files
COPY src/agentscope_runtime/sandbox/box/shared/app.py ./
COPY src/agentscope_runtime/sandbox/box/shared/routers/ ./routers/
COPY src/agentscope_runtime/sandbox/box/shared/dependencies/ ./dependencies/
COPY src/agentscope_runtime/sandbox/box/shared/artifacts/ ./ext_services/artifacts/
COPY src/agentscope_runtime/sandbox/box/shared/third_party/markdownify-mcp/ ./mcp_project/markdownify-mcp/
COPY src/agentscope_runtime/sandbox/box/shared/third_party/steel-browser/ ./ext_services/steel-browser/
COPY examples/custom_sandbox/custom_sandbox/box/ ./

RUN pip install -r requirements.txt

# Install Google Chrome & fonts
RUN curl -fsSL https://dl.google.com/linux/linux_signing_key.pub | apt-key add - && \
    echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list && \
    apt-get update && apt-get install -y --fix-missing google-chrome-stable \
    google-chrome-stable \
    fonts-wqy-zenhei \
    fonts-wqy-microhei

# Install steel browser
WORKDIR /agentscope_runtime/ext_services/steel-browser
RUN npm ci --omit=dev \
    && npm install -g webpack webpack-cli \
    && npm run build -w api \
    && rm -rf node_modules/.cache

# Install artifacts backend
WORKDIR /agentscope_runtime/ext_services/artifacts
RUN npm install \
    && rm -rf node_modules/.cache

# Install mcp_project/markdownify-mcp
WORKDIR /agentscope_runtime/mcp_project/markdownify-mcp
RUN npm install -g pnpm \
    && pnpm install \
    && pnpm run build \
    && rm -rf node_modules/.cache

WORKDIR ${WORKSPACE_DIR}
RUN mv /agentscope_runtime/config/supervisord.conf /etc/supervisor/conf.d/supervisord.conf
RUN mv /agentscope_runtime/config/nginx.conf.template /etc/nginx/nginx.conf.template
RUN git init \
    && chmod +x /agentscope_runtime/scripts/start.sh

COPY .gitignore ${WORKSPACE_DIR}

# MCP required environment variables
ENV TAVILY_API_KEY=123
ENV AMAP_MAPS_API_KEY=123

# Cleanup to reduce image size
RUN pip cache purge \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /tmp/* \
    && rm -rf /var/tmp/* \
    && npm cache clean --force \
    && rm -rf ~/.npm/_cacache

CMD ["/bin/sh", "-c", "envsubst '$SECRET_TOKEN' < /etc/nginx/nginx.conf.template > /etc/nginx/nginx.conf && /usr/bin/supervisord -c /etc/supervisor/conf.d/supervisord.conf"]
```

### 构建您的自定义镜像

准备好Dockerfile 和自定义沙箱类后，使用内置构建器工具构建您的自定义沙箱镜像：

```bash
runtime-sandbox-builder custom_sandbox --dockerfile_path examples/custom_sandbox/custom_sandbox/Dockerfile
```

**命令参数：**

- `custom_sandbox`: 您的自定义沙箱镜像的名称/标签
- `--dockerfile_path`: 您的自定义Dockerfile 的路径

构建完成后，您的自定义沙箱镜像将准备好与您定义的相应沙箱类一起使用。

#### 本地构建内置镜像

您也可以使用构建器在本地构建内置沙箱镜像：

```bash
# 构建所有内置镜像
runtime-sandbox-builder all

# 构建基础镜像（约1GB）
runtime-sandbox-builder base

# 构建浏览器镜像（约2.6GB）
runtime-sandbox-builder browser

# 构建文件系统镜像（约1GB）
runtime-sandbox-builder filesystem
```

上述命令在以下情况下很有用：

- 在本地构建镜像而不是从Docker拉取
- 在构建自己的镜像之前定制基础镜像
- 确保您拥有内置镜像的最新版本
- 在网络隔离的环境中工作

### 更改所使用的镜像标签

您可以更改环境变量以为 Sandbox 模块使用不同的镜像标签。默认情况下，使用的标签是 `"latest"`。

```bash
export RUNTIME_SANDBOX_IMAGE_TAG="my_custom"
```
