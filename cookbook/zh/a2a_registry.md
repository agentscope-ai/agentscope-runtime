# A2A Registry - 服务注册与发现

## 概述

A2A Registry 是 AgentScope Runtime 为 A2A（Agent-to-Agent）协议提供的服务注册与发现机制。通过 Registry，你可以将智能体服务注册到服务发现系统（如 Nacos、Consul 等），使得其他智能体或客户端能够动态发现和调用你的服务。

## 核心概念

### Registry 架构

A2A Registry 采用可扩展的插件式架构：

- **A2ARegistry**：抽象基类，定义了 Registry 的核心接口
- **具体实现**：如 `NacosRegistry`，实现特定服务发现系统的注册逻辑
- **注册流程**：
  1. **Agent Card 发布**：将智能体的元数据（名称、版本、技能等）发布到注册中心
  2. **Endpoint 注册**：注册智能体的服务端点（host、port、path）信息
  3. **后台异步执行**：注册过程在后台异步执行，不阻塞应用启动

## 配置方式

### 方式 1：通过 a2a_config（推荐）

使用 `AgentCardWithRuntimeConfig` 或字典配置 `a2a_config` 参数。

**使用 AgentCardWithRuntimeConfig：**

```python
from agentscope_runtime.engine.app import AgentApp
from agentscope_runtime.engine.deployers.adapter.a2a import (
    AgentCardWithRuntimeConfig,
    NacosRegistry,
)
from v2.nacos import ClientConfigBuilder

# 创建 Nacos Registry
builder = ClientConfigBuilder().server_address("localhost:8848")
nacos_registry = NacosRegistry(nacos_client_config=builder.build())

# 配置 A2A（只需指定关键字段）
a2a_config = AgentCardWithRuntimeConfig(
    name="MyAgent",
    description="我的智能体",
    registry=[nacos_registry],  # 运行时字段
)

# 创建 AgentApp
app = AgentApp(
    app_name="MyAgent",
    app_description="我的智能体",
    a2a_config=a2a_config,
)
```

**使用字典配置：**

```python
a2a_config = {
    # AgentCard 字段
    "name": "MyAgent",
    "version": "1.0.0",
    "description": "我的智能体",
    "url": "http://localhost:8099/a2a",
    "preferredTransport": "JSONRPC",
    "skills": [...],

    # 运行时字段
    "registry": [nacos_registry],
    "transports": [...],
    "task_timeout": 60,
}

app = AgentApp(
    app_name="MyAgent",
    app_description="我的智能体",
    a2a_config=a2a_config,
)
```

### 方式 2：通过环境变量

Runtime 支持从环境变量或 `.env` 文件自动创建 Registry：

```bash
# .env 文件
A2A_REGISTRY_ENABLED=true          # 是否启用 Registry（默认：true）
A2A_REGISTRY_TYPE=nacos            # Registry 类型（如：nacos）
NACOS_SERVER_ADDR=localhost:8848   # Nacos 服务器地址
NACOS_USERNAME=your_username       # Nacos 用户名（可选）
NACOS_PASSWORD=your_password       # Nacos 密码（可选）
NACOS_NAMESPACE_ID=public          # Nacos 命名空间 ID（可选，默认：public）
```

当未显式配置 `a2a_config` 时，AgentApp 会自动读取环境变量创建 Registry

## Nacos Registry 使用指南

### 启动 Nacos 服务

```bash
# 快速启动 Nacos（单机模式）
cd nacos/bin
sh startup.sh -m standalone
```

启动后访问控制台：http://localhost:8848/nacos（默认用户名/密码：nacos/nacos）

> 更多部署方式请参考：https://nacos.io/docs/v3.0/quickstart/quick-start/

### 基本配置

```python
from v2.nacos import ClientConfigBuilder
from agentscope_runtime.engine.deployers.adapter.a2a import NacosRegistry

# 创建 Nacos Registry
builder = ClientConfigBuilder().server_address("localhost:8848")
nacos_registry = NacosRegistry(nacos_client_config=builder.build())

# 可选：添加认证
builder.username("nacos").password("nacos")

# 可选：设置命名空间
builder.namespace_id("your-namespace-id")
```

## 多 Registry 支持

Runtime 支持同时注册到多个服务发现系统：

```python
from agentscope_runtime.engine.deployers.adapter.a2a import (
    AgentCardWithRuntimeConfig,
)

# 创建多个 Registry 实例
nacos_registry_1 = NacosRegistry(config_1)
nacos_registry_2 = NacosRegistry(config_2)
# consul_registry = ConsulRegistry(...)  # 未来支持

a2a_config = AgentCardWithRuntimeConfig(
    name="MyAgent",
    # ... 其他字段 ...
    registry=[nacos_registry_1, nacos_registry_2],  # 多个 Registry
)
```

## 扩展自定义 Registry

你可以实现自定义 Registry 来支持其他服务发现系统：

```python
from agentscope_runtime.engine.deployers.adapter.a2a.a2a_registry import (
    A2ARegistry,
    DeployProperties,
    A2ATransportsProperties,
)
from a2a.types import AgentCard
from typing import List

class MyCustomRegistry(A2ARegistry):
    """自定义 Registry 实现"""

    def registry_name(self) -> str:
        """返回 Registry 名称"""
        return "my-custom-registry"

    def register(
        self,
        agent_card: AgentCard,
        deploy_properties: DeployProperties,
        a2a_transports_properties: List[A2ATransportsProperties],
    ) -> None:
        """注册智能体服务"""
        # 实现你的注册逻辑
        pass

# 使用自定义 Registry
custom_registry = MyCustomRegistry()
a2a_config = AgentCardWithRuntimeConfig(
    name="MyAgent",
    # ... 其他字段 ...
    registry=[custom_registry],
)
```

## 最佳实践

1. **使用环境变量配置**：将敏感信息（如密码）放在 `.env` 文件中，避免硬编码
2. **优雅关闭**：在应用关闭时调用 `cleanup()` 方法清理资源
3. **监控注册状态**：在生产环境中监控注册状态，及时发现和处理注册失败
4. **合理设置超时**：根据网络状况设置合适的 `task_timeout` 和 `task_event_timeout`
5. **使用命名空间**：在多环境部署时使用不同的命名空间隔离服务
