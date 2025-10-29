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

# Deploy a ReAct Agent with Tool Sandbox

This tutorial demonstrates how to create and deploy a *“reasoning and acting” (ReAct)* with AgentScope Runtime and [**AgentScope framework**](https://github.com/modelscope/agentscope).

```{note}
The ReAct (Reasoning and Acting) paradigm enables agents to interleave reasoning traces with task-specific actions, making them particularly effective for tool interaction tasks. By combining AgentScope's `ReActAgent` with AgentScope Runtime's infrastructure, you get both intelligent decision-making and secure tool execution.
```

## Prerequisites

### 🔧 Installation Requirements

Install AgentScope Runtime with the required dependencies:

```bash
pip install agentscope-runtime
```

### 🐳 Sandbox Setup

```{note}
Make sure your browser sandbox environment is ready to use, see {doc}`sandbox` for details.
```

Ensure the browser sandbox image is available:

```bash
docker pull agentscope-registry.ap-southeast-1.cr.aliyuncs.com/agentscope/runtime-sandbox-browser:latest && docker tag agentscope-registry.ap-southeast-1.cr.aliyuncs.com/agentscope/runtime-sandbox-browser:latest agentscope/runtime-sandbox-browser:latest
```

### 🔑 API Key Configuration

You'll need an API key for your chosen LLM provider. This example uses DashScope (Qwen), but you can adapt it to other providers:

```bash
export DASHSCOPE_API_KEY="your_api_key_here"
```

## Step-by-Step Implementation

### Step 1: Import Dependencies

Start by importing all necessary modules:

```{code-cell}
import os

from agentscope_runtime.engine import AgentApp
from agentscope_runtime.engine.deployers import LocalDeployManager
```

### Step 2: Configure Browser Tools

Define the browser tools your agent will have access to (To configure additional tools for the agent, see the “Tool Usage” section in {doc}`sandbox`):

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

print(f"✅ Configured {len(BROWSER_TOOLS)} browser tools")
```

### Step 3: Define System Prompt

Create a system prompt that establishes your agent's role, objectives, and operational guidelines for web browsing tasks:

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

print("✅ System prompt configured")
```

### Step 4: Initialize Agent and Model

Set up the ReAct agent builder with your chosen language model from the AgentScope framework :

```{code-cell}
from agentscope.agent import ReActAgent
from agentscope.model import OpenAIChatModel

# Initialize the language model
model=OpenAIChatModel(
    "gpt-4",
    api_key=os.getenv("OPENAI_API_KEY"),
),

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

print("✅ Agent initialized successfully")
```

### Step 5: Create and Launch Agent App

Create an agent API server using agent and `AgentApp`:

```{code-cell}
app = AgentApp(agent=agent, endpoint_path="/process")

app.run(host="0.0.0.0", port=8090)
```

The server will start and listen on: `http://localhost:8090/process`.

### Step 6: Send Request to Agent

You can send JSON input to the API using `curl`:

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

You’ll see output streamed in **Server-Sent Events (SSE)** format.

### Step 7: Deploy the Agent with Deployer

The AgentScope Runtime provides a powerful deployment system that allows you to deploy your agent to remote or local container. And we use `LocalDeployManager` as example:

```{code-cell}
await app.deploy(LocalDeployManager(host="0.0.0.0", port=8091))
```

This will run your agent API Server on the specified port, making it accessible for external requests. In addition to basic HTTP API access, you can interact with the agent through different protocols, such as A2A, Response API, Agent API, and others. Please refer {doc}`protocol` for details.

### Summary

By following these steps, you've successfully set up, interacted with, and deployed a ReAct Agent using the AgentScope framework and AgentScope Runtime. This configuration allows the agent to use browser tools securely within a sandbox environment, ensuring safe and effective web interactions. Adjust the system prompt, tools, or model as needed to customize the agent’s behavior for specific tasks or applications.
