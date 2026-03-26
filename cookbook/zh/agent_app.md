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

`AgentApp` 是 **AgentScope Runtime** 中的全能型应用服务封装器。它为你的 agent 逻辑提供 HTTP 服务框架，并可将其作为 API 暴露。
在当前版本中，`AgentApp` **直接继承自 `FastAPI`**，这使得它在保持高度灵活性的同时，深度集成了 Agent 业务特有的高级功能。其核心特性包括：

- **完全兼容 FastAPI 生态**：支持原生路由注册（GET/POST 等）、中间件扩展及标准生命周期管理。
- **流式响应（SSE）**，实现实时输出
- **任务中断管理**：提供基于分布式后端（如 Redis）的任务中断机制，支持对长耗时任务的精确控制。
- 内置 **健康检查** 接口
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

## 生命周期管理(Lifespan)

**功能**

在应用启动前加载模型、初始化数据库连接，或在关闭时释放资源，是生产环境的常见需求。

### 方式1：参数传递（简单逻辑）

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

### 方式2：使用 Lifespan 函数（推荐）

这是 **AgentScope Runtime** 推荐的现代写法。得益于对 `FastAPI` 的继承，`AgentApp` 支持标准的 `lifespan` 管理方式，这种方式具有以下优点：

1. **原生 FastAPI 体验** —— **该方法与原生 FastAPI 的标准写法完全一致。** 如果你熟悉 FastAPI 开发，可以无缝应用原生的编程模式，显著降低学习成本。
2. **结构化管理** —— 启动与清理逻辑集中在一个函数内，通过 `yield` 分隔，逻辑更紧凑。
3. **状态共享** —— 可以在启动阶段将资源挂载到 `app.state` 上，在整个应用生命周期（包括请求处理函数）中通过 `app.state` 访问。
4. **内置兼容性** —— 即使使用了自定义 `lifespan`，`AgentApp` 内部仍会自动协同处理 Runner 的准备、协议适配器的挂载以及中断服务的生命周期。

```{code-cell}
from contextlib import asynccontextmanager
from fastapi import FastAPI
from agentscope.session import RedisSession
from agentscope_runtime.engine import AgentApp

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
    print("✅ 服务初始化完成")
    try:
        # yield 将程序控制权交给 AgentApp
        yield
    finally:
        # 清理阶段
        print("✅ 资源已清理")

# 将定义好的 lifespan 传入 AgentApp
app = AgentApp(
    app_name="Friday",
    app_description="A helpful assistant",
    lifespan=lifespan,
)
```

**关键说明**

- **参数签名**：`lifespan` 函数必须接收一个 `FastAPI` 实例作为参数，并使用 `@asynccontextmanager` 装饰。
- **执行顺序**：`AgentApp` 内部会自动调度。首先执行内部框架逻辑，接着执行你定义的 `lifespan` 启动逻辑，最后在服务关闭时反向执行清理逻辑。
- **废弃说明**：请注意，旧版本中的 `@app.init` 和 `@app.shutdown` 装饰器现已被标记为废弃，请统一迁移至 `lifespan` 模式以获得更好的稳定性。
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

## stream_query 后台任务模式

**功能**

将 `stream_query` 作为后台任务执行，支持"提交后离线查询"的使用场景。适用于长时间运行的 agent 查询。

**核心特性**

- **异步执行**：提交任务后立即返回 task_id，无需保持连接
- **结果查询**：通过 task_id 轮询查询任务状态和最终结果
- **只存最终结果**：不存储中间流式事件，只保留最后的 response（减少内存占用）
- **自动超时**：支持配置任务超时时间

**关键参数**

- `enable_stream_task=True`：启用后台任务功能
- `stream_task_queue="stream_query"`：任务队列名称
- `stream_task_timeout=300`：任务超时时间（秒）

**用法示例**

```python
from agentscope_runtime.engine import AgentApp

app = AgentApp(
    app_name="Friday",
    enable_stream_task=True,
    stream_task_queue="stream_query",
    stream_task_timeout=300,  # 5 分钟超时
)

@app.query(framework="agentscope")
async def query_func(self, msgs, request, **kwargs):
    # 正常实现 agent 逻辑
    async for msg, last in stream_printing_messages(...):
        yield msg, last

app.run(host="0.0.0.0", port=8080)
```

**API 端点**

启用后会自动注册以下端点：

| 端点 | 方法 | 功能 |
|------|------|------|
| `/process` | POST | 流式 SSE 响应（现有功能） |
| `/process/task` | POST | 提交后台任务 |
| `/process/task/{task_id}` | GET | 查询任务状态和结果 |

**⚠️ 请求格式要求**

`AgentRequest` 的 `input` 字段格式必须遵循以下规范：
- `content` 必须是 **list 类型**，不能是字符串
- 错误：`"content": "Hello"` ❌
- 正确：`"content": [{"type": "text", "text": "Hello"}]` ✅

**客户端使用示例**

```python
import requests
import time

# 1. 提交任务
response = requests.post(
    "http://localhost:8080/process/task",
    json={
        "input": [
            {
                "role": "user",
                "type": "message",
                "content": [{"type": "text", "text": "解释量子计算"}],
            },
        ],
        "session_id": "my-session",
    },
)

task_data = response.json()
task_id = task_data["task_id"]
print(f"Task submitted: {task_id}")
print(f"Status: {task_data['status']}")

# 2. 轮询查询状态
while True:
    status_response = requests.get(
        f"http://localhost:8080/process/task/{task_id}"
    )
    status_data = status_response.json()

    if status_data["status"] == "finished":
        print("✅ Task completed!")
        print(f"Result: {status_data['result']}")
        break
    elif status_data["status"] == "error":
        print(f"❌ Task failed: {status_data['result']}")
        break
    else:
        print(f"⏳ Status: {status_data['status']}")
        time.sleep(2)
```

**响应格式**

提交任务响应：
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "submitted",
  "queue": "stream_query",
  "message": "Stream query task submitted successfully"
}
```

查询状态响应（进行中）：
```json
{
  "status": "pending",
  "result": null
}
```

查询状态响应（完成）：
```json
{
  "status": "finished",
  "result": {
    "object": "response",
    "status": "completed",
    "id": "...",
    "output": [...],
    "usage": {...}
  }
}
```

**注意事项**

1. **双模式支持**：
   - **In-memory 模式**（默认）：进程重启后任务状态会丢失，适合开发和测试
   - **Celery 模式**：配置 `broker_url` 和 `backend_url` 启用，任务持久化，适合生产环境
2. **结果存储**：只存储最终 response，中间流式事件不会被保存
3. **超时设置**：建议根据 agent 复杂度设置合理的超时时间
4. **Worker 需求**：Celery 模式需要启动 worker（可使用 `enable_embedded_worker=True`）

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
    lifespan=lifespan,
)

@app.query(framework="agentscope")
async def query_func(
    self,
    msgs,
    request: AgentRequest = None,
    **kwargs,
):
    session_id = request.session_id
    user_id = request.user_id

    toolkit = Toolkit()
    toolkit.register_tool_function(execute_python_code)

    agent = ReActAgent(
        name="Friday",
        model=DashScopeChatModel(
            "qwen-turbo",
            api_key=os.getenv("DASHSCOPE_API_KEY"),
            stream=True,
        ),
        sys_prompt="You're a helpful assistant named Friday.",
        toolkit=toolkit,
        memory=InMemoryMemory(),
        formatter=DashScopeChatFormatter(),
    )
    agent.set_console_output_enabled(enabled=False)

    await app.state.session.load_session_state(
        session_id=session_id,
        user_id=user_id,
        agent=agent,
    )

    async for msg, last in stream_printing_messages(
        agents=[agent],
        coroutine_task=agent(msgs),
    ):
        yield msg, last

    await app.state.session.save_session_state(
        session_id=session_id,
        user_id=user_id,
        agent=agent,
    )
```

### 关键特性

1. **框架支持**：`framework` 参数支持 `"agentscope"`, `"autogen"`, `"agno"`, `"langgraph"` 等
2. **函数签名**：
   - `self`：AgentApp 绑定的 Runner 实例
   - `msgs`：输入消息列表
   - `request`：AgentRequest 对象，包含 `session_id`, `user_id` 等信息
   - `**kwargs`：其他扩展参数
3. **流式输出**：函数可以是生成器，支持流式返回结果
4. **状态管理**：可以访问 `app.state.state_service` 进行状态保存和恢复
5. **会话历史**：可以访问 `app.state.session_service` 管理会话历史




### 与 V0 版本 Agent 参数方式的区别

| 特性 | 标准方式（agent 参数） | 自定义查询（@app.query） |
|------|----------------------|------------------------|
| 灵活性 | 较低，使用预定义的 Agent | 高，完全自定义处理逻辑 |
| 状态管理 | 自动处理 | 手动管理，更灵活 |
| 适用场景 | 简单场景 | 复杂场景，需要精细控制 |
| 多框架支持 | 有限 | 支持多种框架 |

------

## 自定义接口定义

你可以通过两种方式扩展 AgentApp 的功能接口。由于 `AgentApp` 直接继承自 `FastAPI`，它不仅保留了 Web 框架原生的灵活性，还针对 Agent 业务场景（如流式输出、对象序列化）提供了增强的工具。

### 1. 原生 FastAPI 路由

这是最灵活的方式。你可以使用标准的 FastAPI 装饰器（如 `@app.get` 和 `@app.post`等）来定义任何业务接口。

**适用场景**：
- 需要完全控制 `Response` 对象、状态码或 Header。
- 定义简单的 Web 控制台接口或健康检查之外的监控接口。

**用法示例**：

```python
app = AgentApp()

@app.get("/info")
async def get_info():
    """使用原生 FastAPI 定义的接口"""
    return {
        "app name": app.app_name,
        "app description": app.app_description,
        "custom_metadata": "v1.0.0"
    }

@app.post("/update_config")
async def update_config(data: dict):
    """标准的 POST 请求处理"""
    # 你的业务逻辑
    return {"status": "updated"}
```

调用：

```bash
curl -X GET http://localhost:8090/info
curl -X POST http://localhost:8090/update_config \
  -H "Content-Type: application/json" \
  -d '{"config_key": "max_tokens", "value": 512}'
```
---

### 2. `@app.endpoint` 便利装饰器

`AgentApp` 提供了特有的 `@app.endpoint` 装饰器。它在底层对 FastAPI 的路由注册进行了封装，专门针对 Agent 的返回场景做了优化。

**核心优势**：

1. 多种返回模式—— 支持
   - 普通同步/异步函数返回 JSON 对象
   - 生成器（同步或异步）返回 **流式数据**（SSE）
2. 参数解析——`@app.endpoint`装饰的函数可以自动解析
   - URL 查询参数
   - JSON 请求体（自动映射到 Pydantic 模型）
   - `fastapi.Request` 对象
   - `AgentRequest` 对象（方便统一 session、用户信息等）
3. **异常处理** —— 流式生成器抛出的异常会自动封装到 SSE 错误事件中返回给客户端。

**用法示例**：

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
curl -N -X POST http://localhost:8090/stream_numbers
```

### 两种方式的区别与选择

| 特性 | 原生 FastAPI (`@app.post` 等) | 便利装饰器 (`@app.endpoint`) |
| :--- | :--- | :--- |
| **流式返回** | 需手动构造 `StreamingResponse` 并处理 SSE 格式 | **自动** 识别生成器并转换为 SSE 格式 |
| **序列化** | 依赖 FastAPI 内置序列化 | 增强的深度序列化（支持更多复杂对象类型） |
| **错误处理** | 需自行通过 Middleware 或 Exception Handler 处理 | 针对流式过程中的异常提供了 **自动封装回显** |
| **灵活性** | **极高**，支持所有原生配置 | **较高**，专注于 Agent 响应规范 |

**建议**：
- 如果你的接口需要返回 **Agent 的推理过程或流式数据**，优先使用 `@app.endpoint`。
- 如果你的接口是 **标准的 Web 业务逻辑**（如配置管理、状态查询），建议使用原生 FastAPI 方式。

------

## 任务中断与管理 (Interrupt Management)

在长链条推理或复杂 Agent 交互场景中，用户可能需要中途停止正在运行的任务。目前 `AgentApp` 利用中断后端（如 Redis），提供了对任务状态的精准控制，包含如下功能：

- **分布式支持**：通过 Redis 后端，可以在集群环境下的任意节点发送中断信号，停止运行在另一节点上的任务。
- **状态同步**：自动管理任务的运行状态（RUNNING, STOPPED, FINISHED, ERROR），防止同一 Session 的并发冲突。
- **优雅取消**：利用 Python 的 `asyncio` 取消机制，允许开发者在捕获 `CancelledError` 后执行清理逻辑（如保存 Agent 当前状态）。

### 配置中断后端

`AgentApp` 支持三种后端配置方式：

1. **本地模式（默认）**：若未提供配置，使用 `LocalInterruptBackend`，适用于单机运行。
2. **Redis 模式（推荐）**：通过 `interrupt_redis_url` 配置，适用于分布式部署。
3. **自定义后端**：通过 `interrupt_backend` 参数传入继承自 `BaseInterruptBackend` 的自定义中断后端实例。

**示例**：

```python
app = AgentApp(
    app_name="InterruptibleAgent",
    # 开启分布式中断支持
    interrupt_redis_url="redis://localhost" ,
)
```

### 编写支持中断的处理函数

在 `@app.query` 装饰的处理函数中，当外部触发中断时，正在执行的协程会抛出 `asyncio.CancelledError`。开发者应当捕获此异常以实现状态保存等功能。

注意，当你在处理函数中捕获中断信号时，务必手动调用 `agent.interrupt()` 方法确保底层模型调用或复杂循环被正确截断。这是因为虽然 `AgentApp` 取消了外层的异步任务流，但底层 Agent 可能正在进行复杂的循环或阻塞调用。
在捕获 `CancelledError` 后调用 `agent.interrupt()` 是最佳实践，它能确保 Agent 内部的推理链条被优雅地截断，并生成一份准确的状态数据用于后续恢复。

**用法示例**

```python
@agent_app.query(framework="agentscope")
async def query_func(
    self,
    msgs,
    request: AgentRequest = None,
    **kwargs
):
    # 准备 Agent
    agent = ReActAgent(name="Friday", ...)

    # 尝试恢复历史状态，适用于中断恢复时的状态恢复等场景
    await agent_app.state.session.load_session_state(
        session_id=session_id,
        user_id=user_id,
        agent=agent,
    )

    try:
        # AgentApp 会在此生成器外层注入中断监听逻辑
        # 当调用 AgentApp 的 stop_chat 方法触发中断时，此处会抛出 CancelledError 异常
        async for msg, last in stream_printing_messages(...):
            yield msg, last

    except asyncio.CancelledError:
        # 核心逻辑：响应中断信号
        print(f"检测到任务 {request.session_id} 被手动中断")

        # 重要：手动停止底层 Agent 任务的执行
        await agent.interrupt()

        # 必须重新抛出异常，让系统将任务状态标记为 STOPPED
        raise

    finally:
        # 无论是任务是被手动中断还是正常执行结束，均保存 agent 状态，以便下次恢复
        await agent_app.state.session.save_session_state(
            session_id=session_id,
            user_id=user_id,
            agent=agent,
        )
```


### 触发中断信号

你可以通过自定义路由，在其中调用 `agent_app.stop_chat` 方法来触发中断。

**代码示例**：
```python
@agent_app.post("/stop")
async def stop_task(request: AgentRequest):
    # 发送中断信号给指定的 user_id 和 session_id
    await agent_app.stop_chat(
        user_id=request.user_id,
        session_id=request.session_id
    )
    return {"status": "ok"}
```

**调用**：

用户只需向 `/stop` 接口发送包含 `user_id` 和 `session_id` 的请求，对应的正在运行的查询任务将被立即取消：
```bash
curl -X POST "http://localhost:8090/stop" \
  -H "Content-Type: application/json" \
  -d '{
    "input": [],
    "session_id": "目标任务的 Session ID",
    "user_id": "目标任务的 User ID"
  }'
```

## 完整应用示例：具有状态管理与中断处理功能的 AgentApp

下面的示例展示了如何整合上述特性，构建一个具备状态恢复和任务中断能力的 Agent 服务。

### 完整代码

```{code-cell}
import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from agentscope.agent import ReActAgent
from agentscope.model import DashScopeChatModel
from agentscope.formatter import DashScopeChatFormatter
from agentscope.tool import Toolkit, execute_python_code
from agentscope.pipeline import stream_printing_messages
from agentscope.memory import InMemoryMemory
from agentscope.session import RedisSession

from agentscope_runtime.engine import AgentApp
from agentscope_runtime.engine.schemas.agent_schemas import AgentRequest

# 1. 定义生命周期
@asynccontextmanager
async def lifespan(app: FastAPI):
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
        print("AgentApp is shutting down...")

# 2. 创建 AgentApp
agent_app = AgentApp(
    app_name="Friday",
    app_description="A helpful assistant",
    lifespan=lifespan,

    # 注意: 由于'interrupt_redis_url'和'interrupt_backend'
    # 均未被传入，当前采用的是本地中断后端。
    # 为了支持分布式中断，你可以添加如下配置:
    # interrupt_redis_url="redis://localhost",
)

# 3. 定义请求处理逻辑
@agent_app.query(framework="agentscope")
async def query_func(
    self,
    msgs,
    request: AgentRequest = None,
    **kwargs,
):
    session_id = request.session_id
    user_id = request.user_id

    toolkit = Toolkit()
    toolkit.register_tool_function(execute_python_code)

    agent = ReActAgent(
        name="Friday",
        model=DashScopeChatModel(
            "qwen-turbo",
            api_key=os.getenv("DASHSCOPE_API_KEY"),
            stream=True,
        ),
        sys_prompt="You're a helpful assistant named Friday.",
        toolkit=toolkit,
        memory=InMemoryMemory(),
        formatter=DashScopeChatFormatter(),
    )
    agent.set_console_output_enabled(enabled=True)

    # 加载 agent 状态
    await agent_app.state.session.load_session_state(
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
        # 中断处理逻辑
        print(f"Task {session_id} was manually interrupted.")

        # 为彻底停止底层 agent 的运行，此处须手动中断 agent
        await agent.interrupt()

        # 重新抛出异常，让系统将任务状态标记为 STOPPED
        raise

    finally:
        # 保存 agent 状态
        await agent_app.state.session.save_session_state(
            session_id=session_id,
            user_id=user_id,
            agent=agent,
        )

# 4. 注册中断触发路由
@agent_app.post("/stop")
async def stop_task(request: AgentRequest):
    await agent_app.stop_chat(
        user_id=request.user_id,
        session_id=request.session_id,
    )
    return {
        "status": "success",
        "message": "Interrupt signal broadcasted.",
    }

# 5. 启动应用
agent_app.run(host="127.0.0.1", port=8090)
```
### 中断功能测试示例

为了方便测试中断功能，你可以使用两个终端窗口：一个用于启动长耗时的任务，另一个用于发送中断信号。

**1. 启动一个长耗时任务**

在第一个终端中，发送一个复杂的请求（例如让 Agent 写一篇长文章），并指定 `session_id` 和 `user_id`。
由于使用了 `-N` 参数，你会看到流式输出的结果实时打印。

```bash
# 终端 1: 发起推理请求
curl -N \
  -X POST "http://localhost:8090/process" \
  -H "Content-Type: application/json" \
  -d '{
    "input": [
      {
        "role": "user",
        "content": [
          {
            "type": "text",
            "text": "Please write a very long and detailed story about a robot named Friday exploring a distant galaxy."
          }
        ]
      }
    ],
    "session_id": "ss-123",
    "user_id": "uu-123"
  }'
```

**2. 发送中断信号**

在上述任务执行过程中（终端 1 还在打印结果时），打开第二个终端，发送中断请求。**注意：`session_id` 和 `user_id` 必须与上方请求保持一致。**

```bash
# 终端 2: 触发中断
curl -X POST "http://localhost:8090/stop" \
  -H "Content-Type: application/json" \
  -d '{
    "input": [],
    "session_id": "ss-123",
    "user_id": "uu-123"
  }'
```

**预期结果**

*   **终端 2**：会立即返回 `{"status": "success", "message": "Interrupt signal broadcasted."}`。
*   **终端 1**：流式输出将立即停止，HTTP 连接关闭。如果你在代码中捕获了 `asyncio.CancelledError`，你会在服务端日志中看到自定义的中断处理逻辑（如“Task ss-123 was manually interrupted.”）。


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
