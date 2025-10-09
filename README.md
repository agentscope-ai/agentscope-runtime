<div align="center">

# AgentScope Runtime

[![PyPI](https://img.shields.io/pypi/v/agentscope-runtime?label=PyPI&color=brightgreen&logo=python)](https://pypi.org/project/agentscope-runtime/)
[![Downloads](https://static.pepy.tech/badge/agentscope-runtime)](https://pepy.tech/project/agentscope-runtime)
[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg?logo=python&label=Python)](https://python.org)
[![License](https://img.shields.io/badge/license-Apache%202.0-red.svg?logo=apache&label=License)](LICENSE)
[![Code Style](https://img.shields.io/badge/code%20style-black-black.svg?logo=python&label=CodeStyle)](https://github.com/psf/black)
[![GitHub Stars](https://img.shields.io/github/stars/agentscope-ai/agentscope-runtime?style=flat&logo=github&color=yellow&label=Stars)](https://github.com/agentscope-ai/agentscope-runtime/stargazers)
[![GitHub Forks](https://img.shields.io/github/forks/agentscope-ai/agentscope-runtime?style=flat&logo=github&color=purple&label=Forks)](https://github.com/agentscope-ai/agentscope-runtime/network)
[![Build Status](https://img.shields.io/badge/build-passing-brightgreen.svg?logo=githubactions&label=Build)](https://github.com/agentscope-ai/agentscope-runtime/actions)
[![Cookbook](https://img.shields.io/badge/📚_Cookbook-English|中文-teal.svg)](https://runtime.agentscope.io)
[![DeepWiki](https://img.shields.io/badge/DeepWiki-agentscope--runtime-navy.svg?logo=data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACwAAAAyCAYAAAAnWDnqAAAAAXNSR0IArs4c6QAAA05JREFUaEPtmUtyEzEQhtWTQyQLHNak2AB7ZnyXZMEjXMGeK/AIi+QuHrMnbChYY7MIh8g01fJoopFb0uhhEqqcbWTp06/uv1saEDv4O3n3dV60RfP947Mm9/SQc0ICFQgzfc4CYZoTPAswgSJCCUJUnAAoRHOAUOcATwbmVLWdGoH//PB8mnKqScAhsD0kYP3j/Yt5LPQe2KvcXmGvRHcDnpxfL2zOYJ1mFwrryWTz0advv1Ut4CJgf5uhDuDj5eUcAUoahrdY/56ebRWeraTjMt/00Sh3UDtjgHtQNHwcRGOC98BJEAEymycmYcWwOprTgcB6VZ5JK5TAJ+fXGLBm3FDAmn6oPPjR4rKCAoJCal2eAiQp2x0vxTPB3ALO2CRkwmDy5WohzBDwSEFKRwPbknEggCPB/imwrycgxX2NzoMCHhPkDwqYMr9tRcP5qNrMZHkVnOjRMWwLCcr8ohBVb1OMjxLwGCvjTikrsBOiA6fNyCrm8V1rP93iVPpwaE+gO0SsWmPiXB+jikdf6SizrT5qKasx5j8ABbHpFTx+vFXp9EnYQmLx02h1QTTrl6eDqxLnGjporxl3NL3agEvXdT0WmEost648sQOYAeJS9Q7bfUVoMGnjo4AZdUMQku50McDcMWcBPvr0SzbTAFDfvJqwLzgxwATnCgnp4wDl6Aa+Ax283gghmj+vj7feE2KBBRMW3FzOpLOADl0Isb5587h/U4gGvkt5v60Z1VLG8BhYjbzRwyQZemwAd6cCR5/XFWLYZRIMpX39AR0tjaGGiGzLVyhse5C9RKC6ai42ppWPKiBagOvaYk8lO7DajerabOZP46Lby5wKjw1HCRx7p9sVMOWGzb/vA1hwiWc6jm3MvQDTogQkiqIhJV0nBQBTU+3okKCFDy9WwferkHjtxib7t3xIUQtHxnIwtx4mpg26/HfwVNVDb4oI9RHmx5WGelRVlrtiw43zboCLaxv46AZeB3IlTkwouebTr1y2NjSpHz68WNFjHvupy3q8TFn3Hos2IAk4Ju5dCo8B3wP7VPr/FGaKiG+T+v+TQqIrOqMTL1VdWV1DdmcbO8KXBz6esmYWYKPwDL5b5FA1a0hwapHiom0r/cKaoqr+27/XcrS5UwSMbQAAAABJRU5ErkJggg==)](https://deepwiki.com/agentscope-ai/agentscope-runtime)
[![A2A](https://img.shields.io/badge/A2A-Agent_to_Agent-blue.svg?label=A2A)](https://a2a-protocol.org/)
[![MCP](https://img.shields.io/badge/MCP-Model_Context_Protocol-purple.svg?logo=plug&label=MCP)](https://modelcontextprotocol.io/)
[![Discord](https://img.shields.io/badge/Discord-Join_Us-blueviolet.svg?logo=discord)](https://discord.gg/eYMpfnkG8h)
[![DingTalk](https://img.shields.io/badge/DingTalk-Join_Us-orange.svg)](https://qr.dingtalk.com/action/joingroup?code=v1,k1,OmDlBXpjW+I2vWjKDsjvI9dhcXjGZi3bQiojOq3dlDw=&_dt_no_comment=1&origin=11)

[[Cookbook]](https://runtime.agentscope.io/)
[[中文README]](README_zh.md)

**A Production-Ready Runtime Framework for Intelligent Agent Applications**

*AgentScope Runtime tackles two critical challenges in agent development: secure sandboxed tool execution and scalable agent deployment. Built with a dual-core architecture, it provides framework-agnostic infrastructure for deploying agents with full observability and safe tool interactions.*

</div>

---

## ✨ Key Features

- **🏗️ Deployment Infrastructure**: Built-in services for session management, memory, and sandbox environment control
- **🔒 Sandboxed Tool Execution**: Isolated sandboxes ensure safe tool execution without system compromise

- **🔧 Framework Agnostic**: Not tied to any specific framework. Works seamlessly with popular open-source agent frameworks and custom implementations

- ⚡ **Developer Friendly**: Simple deployment with powerful customization options

- **📊 Observability**: Comprehensive tracing and monitoring for runtime operations

---

## 💬 Contact

Welcome to join our community on

| [Discord](https://discord.gg/eYMpfnkG8h)                     | DingTalk                                                     |
| ------------------------------------------------------------ | ------------------------------------------------------------ |
| <img src="https://gw.alicdn.com/imgextra/i1/O1CN01hhD1mu1Dd3BWVUvxN_!!6000000000238-2-tps-400-400.png" width="100" height="100"> | <img src="https://img.alicdn.com/imgextra/i1/O1CN01LxzZha1thpIN2cc2E_!!6000000005934-2-tps-497-477.png" width="100" height="100"> |

---

## 📋 Table of Contents

- [🚀 Quick Start](#-quick-start)
- [📚 Cookbook](#-cookbook)
- [🔌 Agent Framework Integration](#-agent-framework-integration)
- [🏗️ Deployment](#️-deployment)
- [🤝 Contributing](#-contributing)
- [📄 License](#-license)

---

## 🚀 Quick Start

### Prerequisites
- Python 3.10 or higher
- pip or uv package manager

### Installation

From PyPI:

```bash
# Install core dependencies
pip install agentscope-runtime

# Install sandbox dependencies
pip install "agentscope-runtime[sandbox]"
```

(Optional) From source:

```bash
# Pull the source code from GitHub
git clone -b main https://github.com/agentscope-ai/agentscope-runtime.git
cd agentscope-runtime

# Install core dependencies
pip install -e .

# Install sandbox dependencies
pip install -e ".[sandbox]"
```

### Basic Agent Usage Example

This example demonstrates how to create a simple LLM agent using AgentScope Runtime and stream responses from the Qwen model.

```python
import asyncio
import os
from agentscope_runtime.engine import Runner
from agentscope_runtime.engine.agents.llm_agent import LLMAgent
from agentscope_runtime.engine.llms import QwenLLM
from agentscope_runtime.engine.schemas.agent_schemas import AgentRequest
from agentscope_runtime.engine.services.context_manager import ContextManager


async def main():
    # Set up the language model and agent
    model = QwenLLM(
        model_name="qwen-turbo",
        api_key=os.getenv("DASHSCOPE_API_KEY"),
    )
    llm_agent = LLMAgent(model=model, name="llm_agent")

    async with ContextManager() as context_manager:
        runner = Runner(agent=llm_agent, context_manager=context_manager)

        # Create a request and stream the response
        request = AgentRequest(
            input=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "What is the capital of France?",
                        },
                    ],
                },
            ],
        )

        async for message in runner.stream_query(request=request):
            if hasattr(message, "text"):
                print(f"Streamed Answer: {message.text}")


asyncio.run(main())
```

### Basic Sandbox Usage Example

This example demonstrates how to create sandboxed and execute tool within the sandbox.

```python
from agentscope_runtime.sandbox import BaseSandbox

with BaseSandbox() as box:
    print(box.run_ipython_cell(code="print('hi')"))
    print(box.run_shell_command(command="echo hello"))
```

> [!NOTE]
>
> Current version requires Docker or Kubernetes to be installed and running on your system. Please refer to [this tutorial](https://runtime.agentscope.io/en/sandbox.html) for more details.
>
> If pulling the Docker image fails, try setting:
> `export RUNTIME_SANDBOX_REGISTRY="agentscope-registry.ap-southeast-1.cr.aliyuncs.com"`

---

## 📚 Cookbook

- **[📖 Cookbook](https://runtime.agentscope.io/en/intro.html)**: Comprehensive tutorials
- **[💡 Concept](https://runtime.agentscope.io/en/concept.html)**: Core concepts and architecture overview
- **[🚀 Quick Start](https://runtime.agentscope.io/en/quickstart.html)**: Quick start tutorial
- **[🏠 Demo House](https://runtime.agentscope.io/en/demohouse.html)**: Rich example projects
- **[📋 API Reference](https://runtime.agentscope.io/en/api/index.html)**: Complete API documentation

---

## 🔌 Agent Framework Integration

### AgentScope Integration

```python
# pip install "agentscope-runtime[agentscope]"
import os

from agentscope.agent import ReActAgent
from agentscope.model import OpenAIChatModel
from agentscope_runtime.engine.agents.agentscope_agent import AgentScopeAgent

agent = AgentScopeAgent(
    name="Friday",
    model=OpenAIChatModel(
        "gpt-4",
        api_key=os.getenv("OPENAI_API_KEY"),
    ),
    agent_config={
        "sys_prompt": "You're a helpful assistant named Friday.",
    },
    agent_builder=ReActAgent,
)
```

### Agno Integration

```python
# pip install "agentscope-runtime[agno]"
from agno.agent import Agent
from agno.models.openai import OpenAIChat
from agentscope_runtime.engine.agents.agno_agent import AgnoAgent

agent = AgnoAgent(
    name="Friday",
    model=OpenAIChat(
        id="gpt-4",
    ),
    agent_config={
        "instructions": "You're a helpful assistant.",
    },
    agent_builder=Agent,
)
```

### AutoGen Integration

```python
# pip install "agentscope-runtime[autogen]"
from autogen_agentchat.agents import AssistantAgent
from autogen_ext.models.openai import OpenAIChatCompletionClient
from agentscope_runtime.engine.agents.autogen_agent import AutogenAgent

agent = AutogenAgent(
    name="Friday",
    model=OpenAIChatCompletionClient(
        model="gpt-4",
    ),
    agent_config={
        "system_message": "You're a helpful assistant",
    },
    agent_builder=AssistantAgent,
)
```

### LangGraph Integration

```python
# pip install "agentscope-runtime[langgraph]"
from typing import TypedDict
from langgraph import graph, types
from agentscope_runtime.engine.agents.langgraph_agent import LangGraphAgent


# define the state
class State(TypedDict, total=False):
    id: str


# define the node functions
async def set_id(state: State):
    new_id = state.get("id")
    assert new_id is not None, "must set ID"
    return types.Command(update=State(id=new_id), goto="REVERSE_ID")


async def reverse_id(state: State):
    new_id = state.get("id")
    assert new_id is not None, "ID must be set before reversing"
    return types.Command(update=State(id=new_id[::-1]))


state_graph = graph.StateGraph(state_schema=State)
state_graph.add_node("SET_ID", set_id)
state_graph.add_node("REVERSE_ID", reverse_id)
state_graph.set_entry_point("SET_ID")
compiled_graph = state_graph.compile(name="ID Reversal")
agent = LangGraphAgent(graph=compiled_graph)
```

> [!NOTE]
>
> More agent framework interations are comming soon!

---

## 🏗️ Deployment

The agent runner exposes a `deploy` method that takes a `DeployManager` instance and deploys the agent. The service port is set as the parameter `port` when creating the `LocalDeployManager`. The service endpoint path is set as the parameter `endpoint_path` when deploying the agent. In this example, we set the endpoint path to `/process`. After deployment, you can access the service at `http://localhost:8090/process`.

```python
from agentscope_runtime.engine.deployers import LocalDeployManager

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
```

---

## 🤝 Contributing

We welcome contributions from the community! Here's how you can help:

### 🐛 Bug Reports
- Use GitHub Issues to report bugs
- Include detailed reproduction steps
- Provide system information and logs

### 💡 Feature Requests
- Discuss new ideas in GitHub Discussions
- Follow the feature request template
- Consider implementation feasibility

### 🔧 Code Contributions
1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

For detailed contributing guidelines, please see  [CONTRIBUTE](cookbook/en/contribute.md).

---

## 📄 License

AgentScope Runtime is released under the [Apache License 2.0](LICENSE).

```
Copyright 2025 Tongyi Lab

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
```

## Contributors ✨
<!-- ALL-CONTRIBUTORS-BADGE:START - Do not remove or modify this section -->
[![All Contributors](https://img.shields.io/badge/all_contributors-12-orange.svg?style=flat-square)](#contributors-)
<!-- ALL-CONTRIBUTORS-BADGE:END -->

Thanks goes to these wonderful people ([emoji key](https://allcontributors.org/docs/en/emoji-key)):

<!-- ALL-CONTRIBUTORS-LIST:START - Do not remove or modify this section -->
<!-- prettier-ignore-start -->
<!-- markdownlint-disable -->
<table>
  <tbody>
    <tr>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/rayrayraykk"><img src="https://avatars.githubusercontent.com/u/39145382?v=4?s=100" width="100px;" alt="Weirui Kuang"/><br /><sub><b>Weirui Kuang</b></sub></a><br /><a href="https://github.com/agentscope-ai/agentscope-runtime/commits?author=rayrayraykk" title="Code">💻</a> <a href="https://github.com/agentscope-ai/agentscope-runtime/pulls?q=is%3Apr+reviewed-by%3Arayrayraykk" title="Reviewed Pull Requests">👀</a> <a href="#maintenance-rayrayraykk" title="Maintenance">🚧</a> <a href="#projectManagement-rayrayraykk" title="Project Management">📆</a></td>
      <td align="center" valign="top" width="14.28%"><a href="http://www.bruceluo.net/"><img src="https://avatars.githubusercontent.com/u/7297307?v=4?s=100" width="100px;" alt="Bruce Luo"/><br /><sub><b>Bruce Luo</b></sub></a><br /><a href="https://github.com/agentscope-ai/agentscope-runtime/commits?author=zhilingluo" title="Code">💻</a> <a href="https://github.com/agentscope-ai/agentscope-runtime/pulls?q=is%3Apr+reviewed-by%3Azhilingluo" title="Reviewed Pull Requests">👀</a> <a href="#example-zhilingluo" title="Examples">💡</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/zzhangpurdue"><img src="https://avatars.githubusercontent.com/u/5746653?v=4?s=100" width="100px;" alt="Zhicheng Zhang"/><br /><sub><b>Zhicheng Zhang</b></sub></a><br /><a href="https://github.com/agentscope-ai/agentscope-runtime/commits?author=zzhangpurdue" title="Code">💻</a> <a href="https://github.com/agentscope-ai/agentscope-runtime/pulls?q=is%3Apr+reviewed-by%3Azzhangpurdue" title="Reviewed Pull Requests">👀</a> <a href="https://github.com/agentscope-ai/agentscope-runtime/commits?author=zzhangpurdue" title="Documentation">📖</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/ericczq"><img src="https://avatars.githubusercontent.com/u/116273607?v=4?s=100" width="100px;" alt="ericczq"/><br /><sub><b>ericczq</b></sub></a><br /><a href="https://github.com/agentscope-ai/agentscope-runtime/commits?author=ericczq" title="Code">💻</a> <a href="https://github.com/agentscope-ai/agentscope-runtime/commits?author=ericczq" title="Documentation">📖</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/qbc2016"><img src="https://avatars.githubusercontent.com/u/22984042?v=4?s=100" width="100px;" alt="qbc"/><br /><sub><b>qbc</b></sub></a><br /><a href="https://github.com/agentscope-ai/agentscope-runtime/pulls?q=is%3Apr+reviewed-by%3Aqbc2016" title="Reviewed Pull Requests">👀</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/rankesterc"><img src="https://avatars.githubusercontent.com/u/114560457?v=4?s=100" width="100px;" alt="Ran Chen"/><br /><sub><b>Ran Chen</b></sub></a><br /><a href="https://github.com/agentscope-ai/agentscope-runtime/commits?author=rankesterc" title="Code">💻</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/jinliyl"><img src="https://avatars.githubusercontent.com/u/6469360?v=4?s=100" width="100px;" alt="jinliyl"/><br /><sub><b>jinliyl</b></sub></a><br /><a href="https://github.com/agentscope-ai/agentscope-runtime/commits?author=jinliyl" title="Code">💻</a> <a href="https://github.com/agentscope-ai/agentscope-runtime/commits?author=jinliyl" title="Documentation">📖</a></td>
    </tr>
    <tr>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/Osier-Yi"><img src="https://avatars.githubusercontent.com/u/8287381?v=4?s=100" width="100px;" alt="Osier-Yi"/><br /><sub><b>Osier-Yi</b></sub></a><br /><a href="https://github.com/agentscope-ai/agentscope-runtime/commits?author=Osier-Yi" title="Code">💻</a> <a href="https://github.com/agentscope-ai/agentscope-runtime/commits?author=Osier-Yi" title="Documentation">📖</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/kevinlin09"><img src="https://avatars.githubusercontent.com/u/26913335?v=4?s=100" width="100px;" alt="Kevin Lin"/><br /><sub><b>Kevin Lin</b></sub></a><br /><a href="https://github.com/agentscope-ai/agentscope-runtime/commits?author=kevinlin09" title="Code">💻</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://davdgao.github.io/"><img src="https://avatars.githubusercontent.com/u/102287034?v=4?s=100" width="100px;" alt="DavdGao"/><br /><sub><b>DavdGao</b></sub></a><br /><a href="https://github.com/agentscope-ai/agentscope-runtime/pulls?q=is%3Apr+reviewed-by%3ADavdGao" title="Reviewed Pull Requests">👀</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/FLyLeaf-coder"><img src="https://avatars.githubusercontent.com/u/122603493?v=4?s=100" width="100px;" alt="FlyLeaf"/><br /><sub><b>FlyLeaf</b></sub></a><br /><a href="https://github.com/agentscope-ai/agentscope-runtime/commits?author=FLyLeaf-coder" title="Code">💻</a> <a href="https://github.com/agentscope-ai/agentscope-runtime/commits?author=FLyLeaf-coder" title="Documentation">📖</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/jinghuan-Chen"><img src="https://avatars.githubusercontent.com/u/42742857?v=4?s=100" width="100px;" alt="jinghuan-Chen"/><br /><sub><b>jinghuan-Chen</b></sub></a><br /><a href="https://github.com/agentscope-ai/agentscope-runtime/commits?author=jinghuan-Chen" title="Code">💻</a></td>
    </tr>
  </tbody>
  <tfoot>
    <tr>
      <td align="center" size="13px" colspan="7">
        <img src="https://raw.githubusercontent.com/all-contributors/all-contributors-cli/1b8533af435da9854653492b1327a23a4dbd0a10/assets/logo-small.svg">
          <a href="https://all-contributors.js.org/docs/en/bot/usage">Add your contributions</a>
        </img>
      </td>
    </tr>
  </tfoot>
</table>

<!-- markdownlint-restore -->
<!-- prettier-ignore-end -->

<!-- ALL-CONTRIBUTORS-LIST:END -->

This project follows the [all-contributors](https://github.com/all-contributors/all-contributors) specification. Contributions of any kind welcome!