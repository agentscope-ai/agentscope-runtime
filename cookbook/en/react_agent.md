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

### Step 5: Create the Runner

Establish the runtime by creating a runner that orchestrates the agent and essential services for session management, memory, and environment control:

```{code-cell}
@asynccontextmanager
async def create_runner():
    async with Runner(
        agent=llm_agent,
        context_manager=ContextManager(),
        environment_manager=EnvironmentManager(),
    ) as runner:
        print("✅ Runner created successfully")
        yield runner
```

### Step 6: Define Local Interaction Function

Implement a local interaction function to test your agent's capabilities with direct query processing and streaming responses:

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
    print("🤖 Agent is processing your request...")
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

    print("📝 Agent output:", all_result)
```

### Step 7: Run Interaction

Execute the interaction flow to test your agent's functionality in a local development environment:

```{code-cell}
async def interact_run():
    async with create_runner() as runner:
        await interact(runner)

await interact_run()
```

### Step 8: Deploy the Agent Locally

Transform your agent into a production-ready service using the local deployment manager for HTTP API access:

```{code-cell}
from agentscope_runtime.engine.deployers import LocalDeployManager

async def deploy(runner):
    # Create deployment manager
    deploy_manager = LocalDeployManager(
        host="localhost",
        port=8090,
    )

    # Deploy the agent as a streaming service
    deploy_result = await runner.deploy(
        deploy_manager=deploy_manager,
        endpoint_path="/process",
        stream=True,  # Enable streaming responses
    )

    print(f"Agent deployed at: {deploy_result}")
    print(f"Service URL: {deploy_manager.service_url}")
    print(f"Health check: {deploy_manager.service_url}/health")
```

### Step 9: Run Deployment

Execute the complete deployment process to make your agent available as a web service:

```{code-cell}
async def deploy_run():
    async with create_runner() as runner:
        await deploy(runner)

await deploy_run()
```

### Summary

By following these steps, you've successfully set up, interacted with, and deployed a ReAct Agent using the AgentScope framework and AgentScope Runtime. This configuration allows the agent to use browser tools securely within a sandbox environment, ensuring safe and effective web interactions. Adjust the system prompt, tools, or model as needed to customize the agent’s behavior for specific tasks or applications.
