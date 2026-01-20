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

# 快速开始

本教程演示如何在 **AgentScope Runtime** 框架中构建一个简单的智能体应用并将其部署为服务。

## 前置条件

### 🔧 安装要求

安装带有基础依赖的 AgentScope Runtime：

```bash
pip install agentscope-runtime
```

### 🔑 API密钥配置

您需要为所选的大语言模型提供商提供API密钥。本示例使用阿里云的Qwen模型，服务提供方是DashScope，所以需要使用其API_KEY，您可以按如下方式将key作为环境变量：

```bash
export DASHSCOPE_API_KEY="your_api_key_here"
```

## 分步实现

### 步骤1：导入依赖

首先导入所有必要的模块：

```{code-cell}
import os

from agentscope.agent import ReActAgent
from agentscope.model import DashScopeChatModel
from agentscope.formatter import DashScopeChatFormatter
from agentscope.tool import Toolkit, execute_python_code
from agentscope.pipeline import stream_printing_messages
from agentscope.memory import InMemoryMemory

from agentscope_runtime.engine import AgentApp
from agentscope_runtime.engine.schemas.agent_schemas import AgentRequest
from agentscope_runtime.engine.services.agent_state import (
    InMemoryStateService,
)

print("✅ 依赖导入成功")
```

### 步骤2：创建Agent App

`AgentApp` 是整个 Agent 应用的生命周期和请求调用的核心，接下来所有的初始化、查询处理、关闭资源等都基于它来注册。

```{code-cell}
agent_app = AgentApp(
    app_name="Friday",
    app_description="A helpful assistant",
)

print("✅ Agent App创建成功")
```

### 步骤3：注册生命周期方法（初始化 & 关闭）

这里定义了应用在启动时要做的事情（启动状态管理、会话历史服务），以及关闭时释放这些资源。

```{code-cell}
@agent_app.init
async def init_func(self):
    self.state_service = InMemoryStateService()
    await self.state_service.start()

@agent_app.shutdown
async def shutdown_func(self):
    await self.state_service.stop()
```

### 步骤4：定义 AgentScope Agent 的查询逻辑

```{important}
⚠️ **提示**

此处的 Agent 构建（模型、工具、会话记忆、格式化器等）只是一个示例配置，
您需要根据实际需求替换为自己的模块实现。
关于可用的服务类型、适配器用法以及如何替换，请参考 {doc}`service/service`。
```

这一部分定义了Agent API 被调用时的业务逻辑：

- **获取会话信息**：确保不同用户或会话的上下文独立。
- **构建 Agent**：包括模型、工具（例如执行 Python 代码）、会话记忆模块、格式化器
- **支持流式输出**：必须使用 `stream_printing_messages` 返回 `(msg, last)`，为客户端提供边生成边响应的能力。
- **状态持久化**：将 Agent 的当前状态保存下来。

```{code-cell}
@agent_app.query(framework="agentscope")
async def query_func(
    self,
    msgs,
    request: AgentRequest = None,
    **kwargs,
):
    session_id = request.session_id
    user_id = request.user_id

    state = await self.state_service.export_state(
        session_id=session_id,
        user_id=user_id,
    )

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

    if state:
        agent.load_state_dict(state)

    async for msg, last in stream_printing_messages(
        agents=[agent],
        coroutine_task=agent(msgs),
    ):
        yield msg, last

    state = agent.state_dict()

    await self.state_service.save_state(
        user_id=user_id,
        session_id=session_id,
        state=state,
    )
```

### 步骤5：启动Agent App

启动 Agent API 服务器，运行后，服务器会启动并监听：`http://localhost:8090/process`：

```{code-cell}
# 启动服务（监听8090端口）
agent_app.run(host="0.0.0.0", port=8090)

# 如果希望同时启用内置的 Web 对话界面，可设置 web_ui=True
# agent_app.run(host="0.0.0.0", port=8090, web_ui=True)
```

### 步骤6：发送一个请求

你可以使用 `curl` 向 API 发送 JSON 输入：

```bash
curl -N \
  -X POST "http://localhost:8090/process" \
  -H "Content-Type: application/json" \
  -d '{
    "input": [
      {
        "role": "user",
        "content": [
          { "type": "text", "text": "What is the capital of France?" }
        ]
      }
    ]
  }'
```

你将会看到以 **Server-Sent Events (SSE)** 格式流式输出的响应：

```bash
data: {"sequence_number":0,"object":"response","status":"created", ... }
data: {"sequence_number":1,"object":"response","status":"in_progress", ... }
data: {"sequence_number":2,"object":"message","status":"in_progress", ... }
data: {"sequence_number":3,"object":"content","status":"in_progress","text":"The" }
data: {"sequence_number":4,"object":"content","status":"in_progress","text":" capital of France is Paris." }
data: {"sequence_number":5,"object":"message","status":"completed","text":"The capital of France is Paris." }
data: {"sequence_number":6,"object":"response","status":"completed", ... }
```

### 步骤7: 使用 DeployManager 部署智能体应用

AgentScope Runtime 提供了一个功能强大的部署系统，可以将你的智能体部署到远程或本地容器中。这里我们以 `LocalDeployManager` 为例：

```{code-cell}
async def main():
    await app.deploy(LocalDeployManager(host="0.0.0.0", port=8091))
```

这段代码会在指定的端口运行你的智能体API Server，使其能够响应外部请求。除了基本的 HTTP API 访问外，你还可以使用不同的协议与智能体进行交互，例如：A2A、Response API、Agent API等。详情请参考 {doc}`protocol`。

例如用户可以通过OpenAI SDK 来请求这个部署。

```python
from openai import OpenAI

client = OpenAI(base_url="http://0.0.0.0:8091/compatible-mode/v1")

response = client.responses.create(
  model="any_name",
  input="杭州天气如何？"
)

print(response)
```

## 章节导读
后续的章节包括如下几个部分
- {doc}`tool`: 帮助您在Agent中加入工具
- {doc}`deployment`: 帮助您部署Agent，打包成服务
- {doc}`use`: 帮助您调用部署后的服务
- {doc}`contribute`: 贡献代码给本项目的参考文档