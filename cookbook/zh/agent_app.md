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

# 深入了解AgentApp

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

## 部署到本地或远程

**功能**
通过 `deploy()` 方法统一部署到不同运行环境。

**用法示例**

```{code-cell}
from agentscope_runtime.engine.deployers import LocalDeployManager

await app.deploy(LocalDeployManager(host="0.0.0.0", port=8091))
```
