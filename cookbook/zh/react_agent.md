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

# 部署配备工具沙箱的ReAct智能体

本教程演示了如何使用AgentScope Runtime与[**AgentScope框架**](https://github.com/modelscope/agentscope)创建和部署*"推理与行动"(ReAct)*智能体。

```{note}
ReAct（推理与行动）范式使智能体能够将推理轨迹与特定任务的行动交织在一起，使其在工具交互任务中特别有效。通过将AgentScope的`ReActAgent`与AgentScope Runtime的基础设施相结合，您可以同时获得智能决策和安全的工具执行。
```

## 前置要求

### 🔧 安装要求

安装带有必需依赖项的AgentScope Runtime：

```bash
pip install "agentscope-runtime[sandbox,agentscope]"
```

### 🐳 Sandbox Setup

```{note}
确保您的浏览器沙箱环境已准备好使用，详细信息请参见{doc}`sandbox`。
```

确保浏览器沙箱镜像可用：

```bash
docker pull agentscope-registry.ap-southeast-1.cr.aliyuncs.com/agentscope/runtime-sandbox-browser:latest && docker tag agentscope-registry.ap-southeast-1.cr.aliyuncs.com/agentscope/runtime-sandbox-browser:latest agentscope/runtime-sandbox-browser:latest
```

### 🔑 API密钥配置

您需要为您选择的LLM提供商准备API密钥。此示例使用DashScope（Qwen），但您可以将其适配到其他提供商：

```bash
export DASHSCOPE_API_KEY="your_api_key_here"
```

## 分步实现

### 步骤1：导入依赖项

首先导入所有必要的模块：

```{code-cell}
import os
from contextlib import asynccontextmanager
from agentscope_runtime.engine.runner import Runner
from agentscope_runtime.engine.agents.agentscope_agent import AgentScopeAgent
from agentscope_runtime.engine.services.context_manager import (
    ContextManager,
)
from agentscope_runtime.engine.services.environment_manager import (
    EnvironmentManager,
)
from agentscope_runtime.engine.schemas.agent_schemas import (
    MessageType,
    RunStatus,
    AgentRequest,
)
```

### 步骤2：配置浏览器工具

定义您的智能体可访问的浏览器工具：

```{code-cell}
from agentscope_runtime.sandbox.tools.browser import (
    browser_navigate,
    browser_take_screenshot,
    browser_snapshot,
    browser_click,
    browser_type,
)

# Prepare browser tools
BROWSER_TOOLS = [
    browser_navigate,
    browser_take_screenshot,
    browser_snapshot,browser_click,
    browser_type,
]

print(f"✅ 已配置{len(BROWSER_TOOLS)} 个浏览器工具")
```

### 步骤3：定义系统提示词

创建一个系统提示词，为您的智能体建立角色、目标和网页浏览任务的操作指南：

```{code-cell}
SYSTEM_PROMPT = """You are a Web-Using AI assistant.

# Objective
Your goal is to complete given tasks by controlling a browser to navigate web pages.

## Web Browsing Guidelines
- Use the `browser_navigate` command to jump to specific webpages when needed.
- Use `generate_response` to answer the user once you have all the required information.
- Always answer in English.

### Observing Guidelines
- Always take action based on the elements on the webpage. Never create URLs or generate new pages.
- If the webpage is blank or an error, such as 404, is found, try refreshing it or go back to the previous page and find another webpage.
"""

print("✅系统提示词已配置")
```

### Step 4: 初始化智能体和模型

使用AgentScope框架中您选择的大模型设置ReAct智能体构建器：

```{code-cell}
from agentscope.agent import ReActAgent
from agentscope.model import DashScopeChatModel

# Initialize the language model
model = DashScopeChatModel(
    "qwen-max",
    api_key=os.getenv("DASHSCOPE_API_KEY"),
)

# Create the AgentScope agent
agent = AgentScopeAgent(
    name="Friday",
    model=model,
    agent_config={
        "sys_prompt": SYSTEM_PROMPT,
    },
    tools=BROWSER_TOOLS,
    agent_builder=ReActAgent,
)

print("✅ 智能体初始化成功")
```

### Step 5: 创建运行器

通过创建一个运行器来建立运行时，该运行器协调智能体和用于会话管理、内存和环境控制的基本服务：

```{code-cell}
@asynccontextmanager
async def create_runner():
    async with Runner(
        agent=llm_agent,
        context_manager=ContextManager(),
        environment_manager=EnvironmentManager(),
    ) as runner:
        print("✅ 运行器创建成功")
        yield runner
```

### 步骤6：定义本地交互函数

实现本地交互函数，通过直接查询处理和流式响应来测试您的智能体功能：

```{code-cell}
async def interact(runner):
    # Create a request
    request = AgentRequest(
        input=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "What is in example.com?",
                    },
                ],
            },
        ],
    )

    # Stream interaction with the agent
    print("🤖 智能体正在处理您的请求...")
    async for message in runner.stream_query(
        request=request,
    ):
        # Check if this is a completed message
        if (
            message.object == "message"
            and MessageType.MESSAGE == message.type
            and RunStatus.Completed == message.status
        ):
            all_result = message.content[0].text

    print("📝 智能体输出:", all_result)
```

### 步骤7：运行交互

执行交互流程，在本地开发环境中测试您的智能体功能：

```{code-cell}
async def interact_run():
    async with create_runner() as runner:
        await interact(runner)

await interact_run()
```

### 步骤8：本地部署智能体

使用本地部署管理器将您的智能体转换为生产就绪的服务，以提供HTTP API访问：

```{code-cell}
from agentscope_runtime.engine.deployers import LocalDeployManager

async def deploy(runner):
    # 创建部署管理器
    deploy_manager = LocalDeployManager(
        host="localhost",
        port=8090,
    )

    #将智能体部署为流式服务
    deploy_result = await runner.deploy(
        deploy_manager=deploy_manager,
        endpoint_path="/process",
        stream=True,  # Enable streaming responses
    )

    print(f"智能体部署在: {deploy_result}")
    print(f"服务URL: {deploy_manager.service_url}")
    print(f"健康检查: {deploy_manager.service_url}/health")
```

### 步骤9：运行部署

执行完整的部署过程，使您的智能体作为Web服务可用：

```{code-cell}
async def deploy_run():
    async with create_runner() as runner:
        await deploy(runner)

await deploy_run()
```

### 总结

通过遵循这些步骤，您已经成功设置、交互并部署了使用AgentScope框架和AgentScope Runtime的ReAct智能体。此配置允许智能体在沙箱环境中安全地使用浏览器工具，确保安全有效的网页交互。根据需要调整系统提示词、工具或模型，以自定义智能体的行为来适应特定任务或应用程序。
