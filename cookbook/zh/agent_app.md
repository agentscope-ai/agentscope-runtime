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

# 简单部署

`AgentApp` 是 **AgentScope Runtime** 中的全能型应用服务封装器。
它为你的 agent 逻辑提供 HTTP 服务框架，并可将其作为 API 暴露，支持以下功能：

- **流式响应（SSE）**，实现实时输出
- 内置 **健康检查** 接口
- **生命周期钩子**（`@app.init` / `@app.shutdown`），用于启动与清理逻辑
- 可选的 **Celery** 异步任务队列
- 部署到本地或远程目标

**重要说明**：
在当前版本中，`AgentApp` 不会自动包含 `/process` 端点。
你必须显式地使用装饰器（例如 `@app.query(...)`）注册一个请求处理函数，服务才能处理传入的请求。

下面的章节将通过具体示例深入介绍每项功能。

------

## 初始化与基本运行

**功能**

创建一个最小的 `AgentApp` 实例，并启动基于 FastAPI 的 HTTP 服务骨架。
初始状态下，服务只提供：

- 欢迎页 `/`
- 健康检查 `/health`
- 就绪探针 `/readiness`
- 存活探针 `/liveness`

**注意**：

- 默认不会暴露 `/process` 或其它业务处理端点。
- 必须使用如 `@app.query(...)` 装饰器、`@app.task(...)` 等方法注册至少一个 handler，才能对外提供处理请求的 API。
- 处理函数可以是普通函数或 async 函数，也可以支持流式（async generator）输出。

**用法示例**

```{code-cell}
from agentscope_runtime.engine import AgentApp

agent_app = AgentApp(
    app_name="Friday",
    app_description="A helpful assistant",
)

agent_app.run(host="127.0.0.1", port=8090)
```

------

## A2A 扩展字段配置

**功能**

通过 `a2a_config` 参数扩展配置 Agent 的 A2A（Agent-to-Agent）协议信息和运行时相关字段。

**关键参数**

- `a2a_config`：可选参数，支持 `AgentCardWithRuntimeConfig` 对象

**配置内容**

`a2a_config` 支持配置两类字段：

1. **AgentCard 协议字段**：通过 `agent_card` 字段传递，包含技能、传输协议、输入输出模式等
2. **Runtime 运行时字段**：顶层字段，包含服务注册与发现（Registry）、超时设置、服务端点等

**用法示例**

```{code-cell}
from agentscope_runtime.engine import AgentApp
from agentscope_runtime.engine.deployers.adapter.a2a import (
    AgentCardWithRuntimeConfig,
)

agent_app = AgentApp(
    app_name="MyAgent",
    app_description="My agent description",
    a2a_config=AgentCardWithRuntimeConfig(
        agent_card={
            "name": "MyAgent",
            "description": "My agent description",
            "skills": [...],  # Agent 技能列表
            "default_input_modes": ["text"],
            "default_output_modes": ["text"],
            # ... 其他协议字段
        },
        registry=[...],  # 服务注册与发现
        task_timeout=120,  # 任务超时设置
        # ... 其他配置字段
    ),
)
```

**详细说明**

完整的字段说明、配置方法和使用示例，请参考 {doc}`a2a_registry` 文档。

------

## 流式输出（SSE）

**功能**
让客户端实时接收生成结果（适合聊天、代码生成等逐步输出场景）。

**关键参数**

- `response_type="sse"`
- `stream=True`

**用法示例（客户端）**

```bash
curl -N \
  -X POST "http://localhost:8090/process" \
  -H "Content-Type: application/json" \
  -d '{
    "input": [
      { "role": "user", "content": [{ "type": "text", "text": "Hello Friday" }] }
    ]
  }'
```

**返回格式**

```bash
data: {"sequence_number":0,"object":"response","status":"created", ... }
data: {"sequence_number":1,"object":"response","status":"in_progress", ... }
data: {"sequence_number":2,"object":"message","status":"in_progress", ... }
data: {"sequence_number":3,"object":"content","status":"in_progress","text":"Hello" }
data: {"sequence_number":4,"object":"content","status":"in_progress","text":" World!" }
data: {"sequence_number":5,"object":"message","status":"completed","text":"Hello World!" }
data: {"sequence_number":6,"object":"response","status":"completed", ... }
```

------

## 生命周期钩子

**功能**

在应用启动前和停止后执行自定义逻辑，例如加载模型或关闭连接。

### 方式1：使用参数传递

**关键参数**

- `before_start`：在 API 服务启动之前执行
- `after_finish`：在 API 服务终止时执行

**用法示例**

```{code-cell}
async def init_resources(app, **kwargs):
    print("🚀 服务启动中，初始化资源...")

async def cleanup_resources(app, **kwargs):
    print("🛑 服务即将关闭，释放资源...")

app = AgentApp(
    agent=agent,
    before_start=init_resources,
    after_finish=cleanup_resources
)
```

### 方式2：使用装饰器（推荐）

除了通过构造函数参数传递钩子函数外，还可以使用装饰器的方式来注册生命周期钩子。
这种写法有以下优点：

1. **更灵活直观** —— 生命周期逻辑直接贴近应用定义，结构更清晰，可读性更高；
2. **可共享成员变量** —— 装饰器定义的函数会接收 `self`，可以访问 `AgentApp` 实例的属性和服务（例如 `@app.init` 中启动的状态服务、会话服务等），方便在不同生命周期或请求处理逻辑中共享和复用资源；

```{code-cell}
from agentscope_runtime.engine import AgentApp
from agentscope_runtime.engine.services.agent_state import InMemoryStateService

app = AgentApp(
    app_name="Friday",
    app_description="A helpful assistant",
)

@app.init
async def init_func(self):
    """初始化服务资源"""
    self.state_service = InMemoryStateService()

    await self.state_service.start()
    print("✅ 服务初始化完成")

@app.shutdown
async def shutdown_func(self):
    """清理服务资源"""
    await self.state_service.stop()
    print("✅ 服务资源已清理")
```

**装饰器说明**

- `@app.init`：注册初始化钩子，在服务启动前执行
- `@app.shutdown`：注册关闭钩子，在服务停止时执行
- 装饰器函数接收 `self` 参数，可以访问 `AgentApp` 实例
- 支持同步和异步函数

------

## 健康检查接口

**功能**

自动提供健康探针接口，方便容器或集群部署。

**接口列表**

- `GET /health`：返回状态与时间戳
- `GET /readiness`：判断是否就绪
- `GET /liveness`：判断是否存活
- `GET /`：欢迎信息

**用法示例**

```bash
curl http://localhost:8090/health
curl http://localhost:8090/readiness
curl http://localhost:8090/liveness
curl http://localhost:8090/
```

------

## Celery 异步任务队列（可选）

**功能**

支持长耗时后台任务，不阻塞 HTTP 主线程。

**关键参数**

- `broker_url="redis://localhost:6379/0"`
- `backend_url="redis://localhost:6379/0"`

**用法示例**

```{code-cell}
app = AgentApp(
    agent=agent,
    broker_url="redis://localhost:6379/0",
    backend_url="redis://localhost:6379/0"
)

@app.task("/longjob", queue="celery")
def heavy_computation(data):
    return {"result": data["x"] ** 2}
```

请求：

```bash
curl -X POST http://localhost:8090/longjob -H "Content-Type: application/json" -d '{"x": 5}'
```

返回任务 ID：

```bash
{"task_id": "abc123"}
```

查询结果：

```bash
curl http://localhost:8090/longjob/abc123
```

------

## 自定义查询处理

**功能**

使用 `@app.query()` 装饰器可以完全自定义查询处理逻辑，实现更灵活的控制，包括状态管理、会话历史管理等。

### 基本用法

```{code-cell}
from agentscope_runtime.engine import AgentApp
from agentscope_runtime.engine.schemas.agent_schemas import AgentRequest
from agentscope.agent import ReActAgent
from agentscope.model import DashScopeChatModel
from agentscope.pipeline import stream_printing_messages
from agentscope.memory import InMemoryMemory

app = AgentApp(
    app_name="Friday",
    app_description="A helpful assistant",
)

@app.query(framework="agentscope")
async def query_func(
    self,
    msgs,
    request: AgentRequest = None,
    **kwargs,
):
    """自定义查询处理函数"""
    session_id = request.session_id
    user_id = request.user_id

    # 加载会话状态
    state = await self.state_service.export_state(
        session_id=session_id,
        user_id=user_id,
    )

    # 创建 Agent 实例
    agent = ReActAgent(
        name="Friday",
        model=DashScopeChatModel(
            "qwen-turbo",
            api_key=os.getenv("DASHSCOPE_API_KEY"),
            stream=True,
        ),
        sys_prompt="You're a helpful assistant named Friday.",
        memory=InMemoryMemory(),
    )

    # 恢复状态（如果存在）
    if state:
        agent.load_state_dict(state)

    # 流式处理消息
    async for msg, last in stream_printing_messages(
        agents=[agent],
        coroutine_task=agent(msgs),
    ):
        yield msg, last

    # 保存状态
    state = agent.state_dict()
    await self.state_service.save_state(
        user_id=user_id,
        session_id=session_id,
        state=state,
    )
```

### 关键特性

1. **框架支持**：`framework` 参数支持 `"agentscope"`, `"autogen"`, `"agno"`, `"langgraph"` 等
2. **函数签名**：
   - `self`：AgentApp 实例，可以访问注册的服务
   - `msgs`：输入消息列表
   - `request`：AgentRequest 对象，包含 `session_id`, `user_id` 等信息
   - `**kwargs`：其他扩展参数
3. **流式输出**：函数可以是生成器，支持流式返回结果
4. **状态管理**：可以访问 `self.state_service` 进行状态保存和恢复
5. **会话历史**：可以访问 `self.session_service` 管理会话历史


### 完整示例：带状态管理的 AgentApp

```{code-cell}
import os
from agentscope_runtime.engine import AgentApp
from agentscope_runtime.engine.schemas.agent_schemas import AgentRequest
from agentscope.agent import ReActAgent
from agentscope.model import DashScopeChatModel
from agentscope.tool import Toolkit, execute_python_code
from agentscope.pipeline import stream_printing_messages
from agentscope.memory import InMemoryMemory
from agentscope_runtime.engine.services.agent_state import InMemoryStateService

app = AgentApp(
    app_name="Friday",
    app_description="A helpful assistant with state management",
)

@app.init
async def init_func(self):
    """初始化状态和会话服务"""
    self.state_service = InMemoryStateService()
    await self.state_service.start()

@app.shutdown
async def shutdown_func(self):
    """清理服务"""
    await self.state_service.stop()

@app.query(framework="agentscope")
async def query_func(
    self,
    msgs,
    request: AgentRequest = None,
    **kwargs,
):
    """带状态管理的查询处理"""
    session_id = request.session_id
    user_id = request.user_id

    # 加载历史状态
    state = await self.state_service.export_state(
        session_id=session_id,
        user_id=user_id,
    )

    # 创建工具包
    toolkit = Toolkit()
    toolkit.register_tool_function(execute_python_code)

    # 创建 Agent
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
    )
    agent.set_console_output_enabled(enabled=False)

    # 恢复状态
    if state:
        agent.load_state_dict(state)

    # 流式处理
    async for msg, last in stream_printing_messages(
        agents=[agent],
        coroutine_task=agent(msgs),
    ):
        yield msg, last

    # 保存状态
    state = agent.state_dict()
    await self.state_service.save_state(
        user_id=user_id,
        session_id=session_id,
        state=state,
    )

# 运行服务
app.run(host="0.0.0.0", port=8090)
```

### 与 V0 版本 Agent 参数方式的区别

| 特性 | 标准方式（agent 参数） | 自定义查询（@app.query） |
|------|----------------------|------------------------|
| 灵活性 | 较低，使用预定义的 Agent | 高，完全自定义处理逻辑 |
| 状态管理 | 自动处理 | 手动管理，更灵活 |
| 适用场景 | 简单场景 | 复杂场景，需要精细控制 |
| 多框架支持 | 有限 | 支持多种框架 |

------
## 通过 `@app.endpoint` 自定义接口

`AgentApp` 除了可以用 `@app.query(...)` 定义统一的 `/process` 请求入口外，还支持通过 `@app.endpoint(...)` 装饰器为应用注册任意路径的 HTTP 接口。

**主要特点**：

1. **灵活性高** —— 你可以为不同业务定义专门的 API 路径，而不是都走 `/process`；
2. 多种返回模式—— 支持
   - 普通同步/异步函数返回 JSON 对象
   - 生成器（同步或异步）返回 **流式数据**（SSE）
3. 参数解析——`@app.endpoint`装饰的函数可以自动解析
   - URL 查询参数
   - JSON 请求体（自动映射到 Pydantic 模型）
   - `fastapi.Request` 对象
   - `AgentRequest` 对象（方便统一 session、用户信息等）
4. **异常处理** —— 流式生成器抛出的异常会自动封装到 SSE 错误事件中返回给客户端。

**示例**：

```python
app = AgentApp()

@app.endpoint("/hello")
def hello_endpoint():
    return {"msg": "Hello world"}

@app.endpoint("/stream_numbers")
async def stream_numbers():
    for i in range(5):
        yield f"number: {i}\n"
```

调用：

```bash
curl -X POST http://localhost:8090/hello
curl -X POST http://localhost:8090/stream_numbers
```

---

## 部署到本地或远程

**功能**

通过 `deploy()` 方法统一部署到不同运行环境。

**用法示例**

```{code-cell}
from agentscope_runtime.engine.deployers import LocalDeployManager

await app.deploy(LocalDeployManager(host="0.0.0.0", port=8091))
```

更多部署选项和详细说明，请参考 {doc}`advanced_deployment` 文档。

AgentScope Runtime 提供了Serverless的部署方案，您可以将您的Agent部署到 ModelStudio(FC) 或 AgentRun 上。
参考 {doc}`advanced_deployment` 文档，查看ModelStudio和AgentRun部署部分获取更多配置详情.
