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

`AgentApp` 是 **AgentScope Runtime** 中的完整 Agent 服务封装器。
它可以将任何符合接口的 Agent 变成一个 API 服务，支持：

- 流式输出（SSE）
- 健康检查接口
- 生命周期钩子（`before_start` / `after_finish`）
- Celery 异步任务队列
- 部署到本地或远程

下面对每个功能做深入介绍，并提供用法示例。

------

## 初始化与基本运行

**功能**
启动一个包含 Agent 的 HTTP API 服务，监听指定端口，提供主处理接口（默认 `/process`）。

**用法示例**

```{code-cell}
from agentscope_runtime.engine import AgentApp
from agentscope_runtime.engine.agents.agentscope_agent import AgentScopeAgent
from agentscope.model import OpenAIChatModel
from agentscope.agent import ReActAgent

# 创建 Agent
agent = AgentScopeAgent(
    name="Friday",
    model=OpenAIChatModel(
        "gpt-4",
        api_key="YOUR_OPENAI_KEY",
    ),
    agent_config={"sys_prompt": "You are a helpful assistant."},
    agent_builder=ReActAgent,
)

# 创建并运行 AgentApp
app = AgentApp(agent=agent, endpoint_path="/process", response_type="sse", stream=True)
app.run(host="0.0.0.0", port=8090)
```

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
data: {"sequence_number":2,"object":"content","status":"in_progress","text":"Hello" }
data: {"sequence_number":3,"object":"content","status":"in_progress","text":" world!" }
data: {"sequence_number":4,"object":"message","status":"completed","text":"Hello world!" }
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

除了使用参数传递，还可以使用装饰器方式注册生命周期钩子，这种方式更加灵活和直观：

**用法示例**

```{code-cell}
from agentscope_runtime.engine import AgentApp
from agentscope_runtime.engine.services.agent_state import InMemoryStateService
from agentscope_runtime.engine.services.session_history import InMemorySessionHistoryService

app = AgentApp(
    app_name="Friday",
    app_description="A helpful assistant",
)

@app.init
async def init_func(self):
    """初始化服务资源"""
    self.state_service = InMemoryStateService()
    self.session_service = InMemorySessionHistoryService()
    
    await self.state_service.start()
    await self.session_service.start()
    print("✅ 服务初始化完成")

@app.shutdown
async def shutdown_func(self):
    """清理服务资源"""
    await self.state_service.stop()
    await self.session_service.stop()
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

## 中间件扩展

**功能**

在请求进入或完成时执行额外逻辑（例如日志、鉴权、限流）。

**用法示例**

```{code-cell}
@app.middleware("http")
async def custom_logger(request, call_next):
    print(f"收到请求: {request.method} {request.url}")
    response = await call_next(request)
    return response
```

AgentApp 内置：

- 请求日志中间件
- CORS（跨域）支持

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
from agentscope_runtime.adapters.agentscope.memory import AgentScopeSessionHistoryMemory

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
        memory=AgentScopeSessionHistoryMemory(
            service=self.session_service,
            session_id=session_id,
            user_id=user_id,
        ),
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
from agentscope_runtime.adapters.agentscope.memory import AgentScopeSessionHistoryMemory
from agentscope_runtime.engine.services.agent_state import InMemoryStateService
from agentscope_runtime.engine.services.session_history import InMemorySessionHistoryService

app = AgentApp(
    app_name="Friday",
    app_description="A helpful assistant with state management",
)

@app.init
async def init_func(self):
    """初始化状态和会话服务"""
    self.state_service = InMemoryStateService()
    self.session_service = InMemorySessionHistoryService()
    await self.state_service.start()
    await self.session_service.start()

@app.shutdown
async def shutdown_func(self):
    """清理服务"""
    await self.state_service.stop()
    await self.session_service.stop()

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
        memory=AgentScopeSessionHistoryMemory(
            service=self.session_service,
            session_id=session_id,
            user_id=user_id,
        ),
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

### 与标准 Agent 参数方式的区别

| 特性 | 标准方式（agent 参数） | 自定义查询（@app.query） |
|------|----------------------|------------------------|
| 灵活性 | 较低，使用预定义的 Agent | 高，完全自定义处理逻辑 |
| 状态管理 | 自动处理 | 手动管理，更灵活 |
| 适用场景 | 简单场景 | 复杂场景，需要精细控制 |
| 多框架支持 | 有限 | 支持多种框架 |

------
## 部署到本地或远程

**功能**

通过 `deploy()` 方法统一部署到不同运行环境。

**用法示例**

```{code-cell}
from agentscope_runtime.engine.deployers import LocalDeployManager

await app.deploy(LocalDeployManager(host="0.0.0.0", port=8091))
```

更多部署选项和详细说明，请参考 {doc}`advanced_deployment` 文档。
