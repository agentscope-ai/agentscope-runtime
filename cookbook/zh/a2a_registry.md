# A2A Registry - 服务注册与发现

## AgentApp 扩展字段 a2a_config

在 `AgentApp` 的构造函数中，我们新增了可选参数 `a2a_config`，用于扩展配置 Agent 的 A2A 协议信息和运行时相关字段。

其类型为 `AgentCardWithRuntimeConfig` 将 AgentCard 协议字段与运行时字段封装到一个数据结构中统一管理。

`AgentCardWithRuntimeConfig`中的字段分为两类：

**1. AgentCard 协议字段**

`agent_card` 字段可以是 `AgentCard` 对象或字典，包含以下协议字段：

- `name`：Agent 名称；
- `description`：Agent 描述；
- `url`：Agent 服务的完整 URL，默认情况下可根据 `host` / `port` 自动推导；
- `version`：Agent 版本号，默认使用运行时代码版本；
- `preferred_transport`：首选传输协议，例如 `"JSONRPC"`；
- `additional_interfaces`：额外的传输接口列表；
- `skills`：Agent 能力 / 技能列表；
- `default_input_modes`：默认支持的输入模式，例如 `["text"]`；
- `default_output_modes`：默认支持的输出模式，例如 `["text"]`；
- `provider`：提供方信息，可以是字符串、字典或结构化对象；
- `documentation_url`：文档地址；
- `icon_url`：图标地址；
- `security_schemes`：安全方案定义；
- `security`：安全需求配置。

**2. Runtime 运行时字段**

- `host`：Agent 向 Registry 智能体注册中心注册的主机地址，未指定时会自动获取当前部署机器的所有网卡中首个非回环 IP 地址；
- `port`：Agent 向 Registry 智能体注册中心注册的端口，默认 `8080`；
- `registry`：Registry 实例或列表，用于将 Agent 服务注册到 Nacos 等智能体注册中心；
- `task_timeout`：任务完成的超时时间（秒），默认 `60`；
- `task_event_timeout`：任务事件的超时时间（秒），默认 `10`；
- `wellknown_path`：AgentCard 对外暴露的路径，默认 `"/.wellknown/agent-card.json"`。

在实际使用中，你只需在构造 `AgentApp` 时传入合适的 `a2a_config`。其中，我们提供了 A2A Registry 能力，可通过 `registry` 字段指定当前 Agent 应该注册到哪些中心化的智能体注册中心（例如 Nacos）。

## Registry 架构
A2A Registry 采用可扩展的插件式架构，用于将 Agent 服务注册到不同的中心化的智能体注册中心（如 Nacos）。

核心组件：

**1. A2ARegistry 抽象基类**

定义了所有 Registry 实现必须遵循的接口：

- `registry_name()`：返回标识该 Registry 的短名称（如 `"nacos"`）；
- `register(agent_card, a2a_transports_properties)`：执行实际的注册逻辑。

Runtime 会在注册过程中捕获并记录异常，确保 Registry 失败不会阻塞 Agent 服务的启动。

**2. A2ATransportsProperties**

描述一个或多个 A2A 传输协议：

- `host` / `port` / `path`：对外暴露的传输端点；
- `support_tls`：是否支持 TLS；
- `extra`：每个传输通道的额外配置；
- `transport_type`：传输类型（如 `"JSONRPC"`、`"HTTP"`）。

当 Agent 通过多种传输协议暴露服务时，可以提供多个传输配置并一起注册。

**注册流程**

当 `AgentApp` 启动时，Registry 注册流程如下：

1. **Agent Card 发布**：将智能体的元数据（名称、版本、技能等）发布到注册中心，使其他智能体能够发现和了解该智能体的能力。

2. **Endpoint 注册**：注册智能体的服务端点信息（host、port、path），包括传输协议配置，使其他智能体能够连接到该服务。

3. **后台异步执行**：注册过程在后台异步执行，不阻塞应用启动。如果某个 Registry 注册失败，Runtime 会记录警告日志，但不会影响 Agent 服务的正常启动。

## Registry 配置方式

Runtime 支持三种方式配置 Registry：

### 1. 通过 a2a_config 配置

在构造 `AgentApp` 时，通过 `a2a_config` 参数的 `registry` 字段指定 Registry 实例或列表：

```python
from agentscope_runtime.engine.app import AgentApp
from agentscope_runtime.engine.deployers.adapter.a2a import (
    AgentCardWithRuntimeConfig,
)
from agentscope_runtime.engine.deployers.adapter.a2a.nacos_a2a_registry import (
    NacosRegistry,
)
from a2a.types import AgentSkill
from v2.nacos import ClientConfigBuilder

# 创建 Nacos Registry 实例
nacos_config = (
    ClientConfigBuilder()
    .server_address("localhost:8848")
    .username("nacos")
    .password("nacos")
    .build()
)
nacos_registry = NacosRegistry(nacos_client_config=nacos_config)

# 在 a2a_config 中配置 registry
a2a_config = AgentCardWithRuntimeConfig(
    agent_card={
        "name": "MyAgent",
        "description": "My agent description",
        # ...
    },
    registry=[nacos_registry],  # 可以是单个实例或列表
    task_timeout=60,
    # ...
)

agent_app = AgentApp(
    app_name="MyAgent",
    app_description="My agent description",
    a2a_config=a2a_config,
)
```

### 2. 通过环境变量配置

如果未在 `a2a_config` 中指定 `registry`，Runtime 会根据环境变量创建 Registry 实例。目前系统仅实现了 `NacosRegistry`，用户可以通过环境变量配置 Nacos 注册中心：

- `A2A_REGISTRY_ENABLED`：是否启用 Registry 功能（默认：`True`）
- `A2A_REGISTRY_TYPE`：Registry 类型，支持逗号分隔的多个值（如：`"nacos"`）
- `NACOS_SERVER_ADDR`：Nacos 服务器地址（默认：`"localhost:8848"`）
- `NACOS_USERNAME`：Nacos 用户名（可选，用于控制台登录）
- `NACOS_PASSWORD`：Nacos 密码（可选，用于控制台登录）
- `NACOS_NAMESPACE_ID`：Nacos 命名空间 ID（可选，默认public）
- `NACOS_ACCESS_KEY`：Nacos Access Key（可选，用于客户端鉴权）
- `NACOS_SECRET_KEY`：Nacos Secret Key（可选，用于客户端鉴权）

环境变量可以通过 `.env` 文件或系统环境变量设置：

```bash
# .env 文件示例
A2A_REGISTRY_ENABLED=true
A2A_REGISTRY_TYPE=nacos
NACOS_SERVER_ADDR=localhost:8848
NACOS_USERNAME=nacos
NACOS_PASSWORD=nacos
NACOS_NAMESPACE_ID=your_namespace_id
```

```python
# 无需在 a2a_config 中指定 registry，会自动从环境变量创建
agent_app = AgentApp(
    app_name="MyAgent",
    app_description="My agent description",
)
```

### 3. 通过 deploy 方法传入 adapter

在使用 `AgentApp.deploy()` 方法部署时，可以通过 `protocol_adapters` 参数传入配置了 Registry 的 A2A Protocol Adapter。

**A2AFastAPIDefaultAdapter 参数说明：**

- `agent_name`（必需）：智能体名称，用于 Agent Card（如果 `a2a_config.agent_card` 中未指定 `name`，则使用此参数）
- `agent_description`（必需）：智能体描述，用于 Agent Card（如果 `a2a_config.agent_card` 中未指定 `description`，则使用此参数）
- `a2a_config`（可选）：`AgentCardWithRuntimeConfig` 对象，包含 AgentCard 协议字段和运行时配置
  - `agent_card`：AgentCard 对象或字典，包含协议字段（name, description, skills 等）
  - `host`：服务的主机地址，如果不传，默认会调用 `get_first_non_loopback_ip()` 自动获取当前部署机器的公网地址
  - `port`：服务的端口号，如果不传，默认为 8080
  - `registry`：Registry 实例或 Registry 列表，用于服务注册与发现
  - `task_timeout`：任务完成的超时时间（秒），默认 60
  - `task_event_timeout`：任务事件的超时时间（秒），默认 10
  - `wellknown_path`：AgentCard 对外暴露的路径，默认 `"/.wellknown/agent-card.json"`

```python
from agentscope_runtime.engine.app import AgentApp
from agentscope_runtime.engine.deployers.adapter.a2a import (
    A2AFastAPIDefaultAdapter,
    AgentCardWithRuntimeConfig,
)
from agentscope_runtime.engine.deployers.adapter.a2a.nacos_a2a_registry import (
    NacosRegistry,
)
from agentscope_runtime.engine.deployers import LocalDeployManager
from v2.nacos import ClientConfigBuilder

# 创建 Nacos Registry 实例
nacos_config = (
    ClientConfigBuilder()
    .server_address("localhost:8848")
    .build()
)
nacos_registry = NacosRegistry(nacos_client_config=nacos_config)

# 创建配置了 Registry 的 A2A Protocol Adapter
a2a_adapter = A2AFastAPIDefaultAdapter(
    agent_name="MyAgent",
    agent_description="My agent description",
    a2a_config=AgentCardWithRuntimeConfig(
        registry=[nacos_registry],
        # ...
    ),
)

# 创建 AgentApp
agent_app = AgentApp(
    app_name="MyAgent",
    app_description="My agent description",
)

# 在 deploy 方法中传入 adapter
deployer = LocalDeployManager(host="127.0.0.1", port=8090)
await agent_app.deploy(
    deployer,
    protocol_adapters=[a2a_adapter],
    # ... 其他部署参数
)
```

**配置优先级**：通过 `a2a_config` 显式指定的 `registry` 优先级最高，如果未指定则从环境变量自动创建。通过 `deploy` 方法传入的 `protocol_adapters` 会覆盖 `AgentApp` 中配置的 adapter。

## Nacos Registry 使用指南

Nacos 是一个易于构建 AI Agent 应用的动态服务发现、配置管理和AI智能体管理平台。
Nacos 在3.1.0版本中实现了 Agent 注册中心能力，支持A2A 智能体的分布式注册、发现和版本管理。
> 注意：使用 NacosAgentCardResolver的前提是已经部署了 3.1.0 版本以上的 Nacos 服务端。

在使用 Nacos Registry 之前，需要先安装并启动 Nacos 服务器。以下是快速开始步骤：

### 1. 下载安装包

进入 [Nacos Github 的最新稳定版本](https://github.com/alibaba/nacos/releases)，选择需要下载的 Nacos 版本，在 `Assets` 中点击下载 `nacos-server-$version.zip` 包。

### 2. 解压缩 Nacos 发行包

```bash
unzip nacos-server-$version.zip
# 或者 tar -xvf nacos-server-$version.tar.gz
cd nacos/bin
```

### 3. 启动服务器

**Linux/Unix/Mac：**
```bash
sh startup.sh -m standalone
```

**Windows：**
```bash
startup.cmd -m standalone
```

> 注意：`standalone` 代表单机模式运行，非集群模式。

更多详细的安装、配置和验证步骤，请参考 [Nacos 官方快速开始文档](https://nacos.io/docs/v3.0/quickstart/quick-start/)。

## 自定义 Registry 的实现方法

如果需要集成其他类型的中心化的智能体注册中心，可以实现自定义 Registry。自定义 Registry 需要继承 `A2ARegistry` 抽象基类，并实现以下方法：

### 实现步骤

1. **继承 `A2ARegistry` 抽象基类**
2. **实现 `registry_name()` 方法**：返回 Registry 的短名称，用于日志和诊断
3. **实现 `register()` 方法**：执行实际的注册逻辑

### 示例代码

以下是一个简单的自定义 Registry 实现示例：

```python
from agentscope_runtime.engine.deployers.adapter.a2a.a2a_registry import (
    A2ARegistry,
    A2ATransportsProperties,
)
from a2a.types import AgentCard
from typing import Optional, List
import logging

logger = logging.getLogger(__name__)


class MyCustomRegistry(A2ARegistry):
    """自定义 Registry 实现示例。"""

    def registry_name(self) -> str:
        return "my-custom-registry"

    def register(
        self,
        agent_card: AgentCard,
        a2a_transports_properties: Optional[
            List[A2ATransportsProperties]
        ] = None,
    ) -> None:

        try:
            # 构建注册信息
            if a2a_transports_properties and len(a2a_transports_properties) > 0:
                transport = a2a_transports_properties[0]
                service_info = {
                    "agent_name": agent_card.name,
                    "agent_version": agent_card.version,
                    "host": transport.host,
                    "port": transport.port,
                }
            else:
                service_info = {
                    "agent_name": agent_card.name,
                    "agent_version": agent_card.version,
                }

            # 执行注册逻辑
            logger.info(f"[MyCustomRegistry] Registering: {service_info}")
            # ...

        except Exception as e:
            logger.warning(f"[MyCustomRegistry] Registration failed: {e}", exc_info=True)
```

### 使用自定义 Registry

实现自定义 Registry 后，可以通过以下方式使用：

```python
from agentscope_runtime.engine.app import AgentApp
from agentscope_runtime.engine.deployers.adapter.a2a import (
    AgentCardWithRuntimeConfig,
)

# 创建自定义 Registry 实例
custom_registry = MyCustomRegistry()

# 在 a2a_config 中使用
a2a_config = AgentCardWithRuntimeConfig(
    registry=[custom_registry],
    # ...
)

agent_app = AgentApp(
    app_name="MyAgent",
    app_description="My agent description",
    a2a_config=a2a_config,
)
```