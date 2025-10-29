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

本教程演示了如何使用AgentScope Runtime与[**AgentScope框架**](https://github.com/modelscope/agentscope)创建和部署 *“推理与行动”(ReAct)* 智能体。

```{note}
ReAct（推理与行动）范式使智能体能够将推理轨迹与特定任务的行动交织在一起，使其在工具交互任务中特别有效。通过将AgentScope的`ReActAgent`与AgentScope Runtime的基础设施相结合，您可以同时获得智能决策和安全的工具执行。
```

## 前置要求

### 🔧 安装要求

安装带有必需依赖项的AgentScope Runtime：

```bash
pip install agentscope-runtime
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

from agentscope_runtime.engine import AgentApp
from agentscope_runtime.engine.agents.agentscope_agent import AgentScopeAgent
from agentscope_runtime.engine.deployers import LocalDeployManager
```

### 步骤2：配置浏览器工具

定义您的智能体可访问的浏览器工具（如果您想为智能体配置其他工具，请参考{doc}`sandbox`中的工具用法）：

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

### Step 5: 创建并启动Agent App

用agent和 `AgentApp` 创建一个 Agent API 服务器：

```{code-cell}
from agentscope_runtime.engine.agents.agentscope_agent import AgentScopeAgent

app = AgentApp(agent=agent, endpoint_path="/process")

app.run(host="0.0.0.0", port=8090)
```

运行后，服务器会启动并监听：`http://localhost:8090/process`

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
          { "type": "text", "text": "What is in example?" }
        ]
      }
    ]
  }'
```

你将会看到以 **Server-Sent Events (SSE)** 格式流式输出的响应。

### 步骤7: 使用 Deployer 部署代理

AgentScope Runtime 提供了一个功能强大的部署系统，可以将你的智能体部署到远程或本地容器中。这里我们以 `LocalDeployManager` 为例：

```{code-cell}
async def main():
    await app.deploy(LocalDeployManager(host="0.0.0.0", port=8091))
```

这段代码会在指定的端口运行你的智能体API Server，使其能够响应外部请求。除了基本的 HTTP API 访问外，你还可以使用不同的协议与智能体进行交互，例如：A2A、Response API、Agent API等。详情请参考 {doc}`protocol`。

### 总结

通过遵循这些步骤，您已经成功设置、交互并部署了使用AgentScope框架和AgentScope Runtime的ReAct智能体。此配置允许智能体在沙箱环境中安全地使用浏览器工具，确保安全有效的网页交互。根据需要调整系统提示词、工具或模型，以自定义智能体的行为来适应特定任务或应用程序。
