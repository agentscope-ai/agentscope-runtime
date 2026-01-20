# 欢迎来到AgentScope Runtime Cookbook

[![GitHub Repo](https://img.shields.io/badge/GitHub-Repo-black.svg?logo=github)](https://github.com/agentscope-ai/agentscope-runtime)
[![WebUI](https://img.shields.io/badge/Try_WebUI-Online-green.svg?logo=googlechrome)](http://webui.runtime.agentscope.io/)
[![PyPI](https://img.shields.io/pypi/v/agentscope-runtime?label=PyPI&color=brightgreen&logo=python)](https://pypi.org/project/agentscope-runtime/)
[![Downloads](https://static.pepy.tech/badge/agentscope-runtime)](https://pepy.tech/project/agentscope-runtime)
[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg?logo=python&label=Python)](https://python.org)
[![Last Commit](https://img.shields.io/github/last-commit/agentscope-ai/agentscope-runtime)](https://github.com/agentscope-ai/agentscope-runtime)
[![License](https://img.shields.io/badge/license-Apache%202.0-red.svg?logo=apache&label=License)](LICENSE)
[![Code Style](https://img.shields.io/badge/code%20style-black-black.svg?logo=python&label=CodeStyle)](https://github.com/psf/black)
[![GitHub Stars](https://img.shields.io/github/stars/agentscope-ai/agentscope-runtime?style=flat&logo=github&color=yellow&label=Stars)](https://github.com/agentscope-ai/agentscope-runtime/stargazers)
[![GitHub Forks](https://img.shields.io/github/forks/agentscope-ai/agentscope-runtime?style=flat&logo=github&color=purple&label=Forks)](https://github.com/agentscope-ai/agentscope-runtime/network)
[![Build Status](https://img.shields.io/badge/build-passing-brightgreen.svg?logo=githubactions&label=Build)](https://github.com/agentscope-ai/agentscope-runtime/actions)
[![Cookbook](https://img.shields.io/badge/📚_Cookbook-English|中文-teal.svg)](https://runtime.agentscope.io)
[![DeepWiki](https://img.shields.io/badge/DeepWiki-agentscope--runtime-navy.svg?logo=data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACwAAAAyCAYAAAAnWDnqAAAAAXNSR0IArs4c6QAAA05JREFUaEPtmUtyEzEQhtWTQyQLHNak2AB7ZnyXZMEjXMGeK/AIi+QuHrMnbChYY7MIh8g01fJoopFb0uhhEqqcbWTp06/uv1saEDv4O3n3dV60RfP947Mm9/SQc0ICFQgzfc4CYZoTPAswgSJCCUJUnAAoRHOAUOcATwbmVLWdGoH//PB8mnKqScAhsD0kYP3j/Yt5LPQe2KvcXmGvRHcDnpxfL2zOYJ1mFwrryWTz0advv1Ut4CJgf5uhDuDj5eUcAUoahrdY/56ebRWeraTjMt/00Sh3UDtjgHtQNHwcRGOC98BJEAEymycmYcWwOprTgcB6VZ5JK5TAJ+fXGLBm3FDAmn6oPPjR4rKCAoJCal2eAiQp2x0vxTPB3ALO2CRkwmDy5WohzBDwSEFKRwPbknEggCPB/imwrycgxX2NzoMCHhPkDwqYMr9tRcP5qNrMZHkVnOjRMWwLCcr8ohBVb1OMjxLwGCvjTikrsBOiA6fNyCrm8V1rP93iVPpwaE+gO0SsWmPiXB+jikdf6SizrT5qKasx5j8ABbHpFTx+vFXp9EnYQmLx02h1QTTrl6eDqxLnGjporxl3NL3agEvXdT0WmEost648sQOYAeJS9Q7bfUVoMGnjo4AZdUMQku50McDcMWcBPvr0SzbTAFDfvJqwLzgxwATnCgnp4wDl6Aa+Ax283gghmj+vj7feE2KBBRMW3FzOpLOADl0Isb5587h/U4gGvkt5v60Z1VLG8BhYjbzRwyQZemwAd6cCR5/XFWLYZRIMpX39AR0tjaGGiGzLVyhse5C9RKC6ai42ppWPKiBagOvaYk8lO7DajerabOZP46Lby5wKjw1HCRx7p9sVMOWGzb/vA1hwiWc6jm3MvQDTogQkiqIhJV0nBQBTU+3okKCFDy9WwferkHjtxib7t3xIUQtHxnIwtx4mpg26/HfwVNVDb4oI9RHmx5WGelRVlrtiw43zboCLaxv46AZeB3IlTkwouebTr1y2NjSpHz68WNFjHvupy3q8TFn3Hos2IAk4Ju5dCo8B3wP7VPr/FGaKiG+T+v+TQqIrOqMTL1VdWV1DdmcbO8KXBz6esmYWYKPwDL5b5FA1a0hwapHiom0r/cKaoqr+27/XcrS5UwSMbQAAAABJRU5ErkJggg==)](https://deepwiki.com/agentscope-ai/agentscope-runtime)[![A2A](https://img.shields.io/badge/A2A-Agent_to_Agent-blue.svg?label=A2A)](https://a2a-protocol.org/)
[![MCP](https://img.shields.io/badge/MCP-Model_Context_Protocol-purple.svg?logo=plug&label=MCP)](https://modelcontextprotocol.io/)
[![Discord](https://img.shields.io/badge/Discord-Join_Us-blueviolet.svg?logo=discord)](https://discord.gg/eYMpfnkG8h)
[![DingTalk](https://img.shields.io/badge/DingTalk-Join_Us-orange.svg)](https://qr.dingtalk.com/action/joingroup?code=v1,k1,OmDlBXpjW+I2vWjKDsjvI9dhcXjGZi3bQiojOq3dlDw=&_dt_no_comment=1&origin=11)

## AgentScope Runtime V1.0 发布

AgentScope Runtime V1.0 在高效智能体部署与安全沙箱执行的坚实基础上，推出了 **统一的 “Agent 作为 API” 开发体验**，覆盖完整智能体从本地开发到生产部署的生命周期，并扩展了更多沙箱类型、协议兼容性与更丰富的内置工具集。

同时，智能体服务的接入方式从过去的 **黑盒化模块替换** 升级为 ***白盒化适配器模式*** —— 开发者可以在保留原有智能体框架接口与行为的前提下，将状态管理、会话记录、工具注册等运行时能力按需嵌入应用生命周期，实现更灵活的定制与跨框架无缝集成。

**V1.0 主要改进：**

- **统一的开发/生产范式** —— 在开发环境与生产环境中 智能体功能性保持一致
- **原生多智能体支持** —— 完全兼容 AgentScope 的多智能体范式
- **主流 SDK 与协议集成** —— 支持 OpenAI SDK 与 Google A2A 协议
- **可视化 Web UI** —— 部署后即可立即体验的开箱即用 Web 聊天界面
- **扩展沙箱类型** —— GUI、浏览器、文件系统、移动端、云端（大部分可通过 VNC 可视化）
- **更丰富的内置工具** —— 面向生产的搜索、RAG、AIGC、支付等模块
- **灵活的部署模式** —— 本地线程/进程、Docker、Kubernetes、或托管云端

更详细的变更说明，以及迁移指南请参考：{doc}`CHANGELOG`

## 什么是AgentScope Runtime？

**AgentScope Runtime** 是一个面向 AI Agent 的全栈运行时，旨在解决两大核心挑战：**高效部署与服务化**以及**安全的沙箱化执行**。

简而言之：
$$
\begin{aligned}
\textbf{AgentScope Runtime}
=&\ \textbf{工具沙箱隔离}
+\ \textbf{AaaS API（Agent 即服务）}
+\ \textbf{可扩展部署} \\
&+\ \textbf{全栈可观测性（日志/链路追踪）}
+\ \textbf{框架兼容性}
\end{aligned}
$$
本 cookbook 将引导你使用 **AgentScope Runtime** 构建**可服务化**、面向生产环境的高质量 Agent 应用。

## 核心架构

**⚙️ 智能体部署运行时 (Engine)**

提供`AgentApp`作为智能体应用主入口，同时配备部署、管理和监控智能体应用的生产级基础设施，并内置了会话历史、长期记忆以及智能体状态等服务。

**🔒 沙箱执行运行时 (Sandbox)**

安全隔离的环境，让您的智能体能够安全地执行代码、控制浏览器、管理文件并集成MCP 工具——所有这些都不会危及您的系统安全。

**🛠️ 生产级工具服务 (Tool)**

基于可信第三方 API 能力（如搜索、RAG、AIGC、支付等），通过统一的 SDK 封装对外提供标准化调用接口，使智能体能够以一致的方式集成和使用这些服务，而无需关心底层 API 的差异与复杂性。

## 为什么选择 AgentScope Runtime？

- 🤖 **AS原生运行时框架**：由 AgentScope 官方构建和维护，与其多智能体范式、适配器模式及工具使用深度集成，确保最佳兼容性与性能
- **🏗️ 部署基础设施**：内置长短期记忆、智能体状态和沙箱环境控制服务
- **🔒 沙箱执行**：隔离的沙箱确保工具安全执行，不会危及系统
- ⚡ **开发者友好**：简单部署，功能强大的自定义选项
- **📊 可观测性**：针对运行时操作的全面追踪和监控

立即开始使用 AgentScope Runtime 部署你的智能体并尝试工具沙箱吧！
