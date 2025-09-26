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
[[English README]](README.md)

**智能体应用的生产就绪运行时框架**

*AgentScope Runtime 解决了智能体开发中的两个关键挑战：安全的沙盒工具执行和可扩展的智能体服务化部署。凭借双核架构，AgentScope Runtime提供了与智能体框架无关的基础设施，以实现智能体部署的可观察性和安全工具调用。*

</div>

---

## ✨ 关键特性

- **🏗️ 部署基础设施**：内置服务用于历史会话管理、长期记忆和沙盒环境生命周期控制
- **🔒 沙盒工具执行**：隔离的沙盒确保安全工具执行，不会影响系统
- **🔧 框架无关**：不绑定任何特定智能体框架，与流行的开源智能体框架和自定义实现无缝集成
- ⚡ **对开发者友好**：简单部署并提供强大的自定义选项
- **📊 可观察性**：对运行时操作进行全面跟踪和监控

---

## 💬 联系我们

欢迎加入我们的社区，获取最新的更新和支持！

| [Discord](https://discord.gg/eYMpfnkG8h)                     | 钉钉群                                                       |
| ------------------------------------------------------------ | ------------------------------------------------------------ |
| <img src="https://gw.alicdn.com/imgextra/i1/O1CN01hhD1mu1Dd3BWVUvxN_!!6000000000238-2-tps-400-400.png" width="100" height="100"> | <img src="https://img.alicdn.com/imgextra/i1/O1CN01LxzZha1thpIN2cc2E_!!6000000005934-2-tps-497-477.png" width="100" height="100"> |

---

## 📋 目录

- [🚀 快速开始](#-快速开始)
- [📚 指南](#-指南)
- [🔌 智能体框架集成](#-智能体框架集成)
- [🏗️ 部署](#️-部署)
- [🤝 贡献](#-贡献)
- [📄 许可证](#-许可证)

---

## 🚀 快速开始

### 前提条件
- Python 3.10 或更高版本
- pip 或 uv 包管理器

### 安装

从PyPI安装：

```bash
# 安装核心依赖
pip install agentscope-runtime

# 安装沙盒依赖
pip install "agentscope-runtime[sandbox]"
```

（可选）从源码安装：

```bash
# 从 GitHub 拉取源码
git clone -b main https://github.com/agentscope-ai/agentscope-runtime.git
cd agentscope-runtime

# 安装核心依赖
pip install -e .

# 安装沙盒依赖
pip install -e ".[sandbox]"
```

### 基本智能体使用示例

此示例演示如何使用 AgentScope Runtime 创建简单的 LLM 智能体并从 Qwen 模型流式传输响应。

```python
import asyncio
import os
from agentscope_runtime.engine import Runner
from agentscope_runtime.engine.agents.llm_agent import LLMAgent
from agentscope_runtime.engine.llms import QwenLLM
from agentscope_runtime.engine.schemas.agent_schemas import AgentRequest
from agentscope_runtime.engine.services.context_manager import ContextManager


async def main():
    # 设置语言模型和智能体
    model = QwenLLM(
        model_name="qwen-turbo",
        api_key=os.getenv("DASHSCOPE_API_KEY"),
    )
    llm_agent = LLMAgent(model=model, name="llm_agent")

    async with ContextManager() as context_manager:
        runner = Runner(agent=llm_agent, context_manager=context_manager)

        # 创建请求并流式传输响应
        request = AgentRequest(
            input=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "法国的首都是什么？",
                        },
                    ],
                },
            ],
        )

        async for message in runner.stream_query(request=request):
            if hasattr(message, "text"):
                print(f"流式答案: {message.text}")


asyncio.run(main())
```

### 基本沙盒使用示例

此示例演示如何创建沙盒并在沙盒中执行工具。

```python
from agentscope_runtime.sandbox import BaseSandbox

with BaseSandbox() as box:
    print(box.run_ipython_cell(code="print('你好')"))
    print(box.run_shell_command(command="echo hello"))
```

> [!NOTE]
>
> 当前版本需要安装并运行Docker或者Kubernetes，未来我们将提供更多公有云部署选项。请参考[此教程](https://runtime.agentscope.io/zh/sandbox.html)了解更多详情。
>
> 如果镜像拉取失败，可以尝试设置：
> `export RUNTIME_SANDBOX_REGISTRY="agentscope-registry.ap-southeast-1.cr.aliyuncs.com"`

---

## 📚 指南

- **[📖 Cookbook](https://runtime.agentscope.io/zh/intro.html)**: 全面教程
- **[💡 概念](https://runtime.agentscope.io/zh/concept.html)**: 核心概念和架构概述
- **[🚀 快速开始](https://runtime.agentscope.io/zh/quickstart.html)**: 快速入门教程
- **[🏠 展示厅](https://runtime.agentscope.io/zh/demohouse.html)**: 丰富的示例项目
- **[📋 API 参考](https://runtime.agentscope.io/zh/api/index.html)**: 完整的API文档

---

## 🔌 智能体框架集成

### AgentScope 集成

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

### Agno集成

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

### AutoGen集成

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

### LangGraph集成

```python
# pip install "agentscope-runtime[langgraph]"
from typing import TypedDict
from langgraph import graph, types
from agentscope_runtime.engine.agents.langgraph_agent import LangGraphAgent


# 定义状态
class State(TypedDict, total=False):
    id: str


# 定义节点函数
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
> 更多智能体框架集成即将推出！

---

## 🏗️ 部署

智能体运行器使用了`deploy` 方法，该方法采用一个 `DeployManager` 实例并部署智能体。服务端口在创建 `LocalDeployManager` 时设置为参数 `port`。服务端点路径在部署智能体时设置为参数 `endpoint_path`。在此示例中，我们将端点路径设置为 `/process`。部署后，您可以通过 [http://localhost:8090/process](http://localhost:8090/process) 访问该服务。

```python
from agentscope_runtime.engine.deployers import LocalDeployManager

# 创建部署管理器
deploy_manager = LocalDeployManager(
    host="localhost",
    port=8090,
)

# 将智能体部署为流式服务
deploy_result = await runner.deploy(
    deploy_manager=deploy_manager,
    endpoint_path="/process",
    stream=True,  # 启用流式响应
)
```

---

## 🤝 贡献

我们欢迎来自社区的贡献！您可以提供以下帮助：

### 🐛 错误报告

- 使用 GitHub Issues 报告错误
- 包含详细的重现步骤
- 提供系统信息和日志

### 💡 特性请求

- 在 GitHub Discussions 中讨论新想法
- 遵循特性请求模板
- 考虑实施的可行性

### 🔧 代码贡献

1. Fork 这个仓库
2. 创建一个功能分支 (git checkout -b feature/amazing-feature)
3. 提交更改 (git commit -m 'Add amazing feature')
4. 推送到分支 (git push origin feature/amazing-feature)
5. 打开一个 Pull Request

有关如何贡献的详细指南，请查看 [如何贡献](cookbook/zh/contribute.md).

---

## 📄 许可证

AgentScope Runtime 根据 [Apache License 2.0](LICENSE) 发布。

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

## 贡献者 ✨
<!-- ALL-CONTRIBUTORS-BADGE:START - Do not remove or modify this section -->
[![All Contributors](https://img.shields.io/badge/all_contributors-10-orange.svg?style=flat-square)](#contributors-)
<!-- ALL-CONTRIBUTORS-BADGE:END -->


感谢这些优秀的贡献者们 ([表情符号说明](https://allcontributors.org/docs/en/emoji-key)):

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

本项目遵循 [all-contributors](https://github.com/all-contributors/all-contributors) 规范。欢迎任何形式的贡献！