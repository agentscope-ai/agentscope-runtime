# Welcome to AgentScope Runtime Cookbook

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
[![DeepWiki](https://img.shields.io/badge/DeepWiki-agentscope--runtime-navy.svg?logo=data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACwAAAAyCAYAAAAnWDnqAAAAAXNSR0IArs4c6QAAA05JREFUaEPtmUtyEzEQhtWTQyQLHNak2AB7ZnyXZMEjXMGeK/AIi+QuHrMnbChYY7MIh8g01fJoopFb0uhhEqqcbWTp06/uv1saEDv4O3n3dV60RfP947Mm9/SQc0ICFQgzfc4CYZoTPAswgSJCCUJUnAAoRHOAUOcATwbmVLWdGoH//PB8mnKqScAhsD0kYP3j/Yt5LPQe2KvcXmGvRHcDnpxfL2zOYJ1mFwrryWTz0advv1Ut4CJgf5uhDuDj5eUcAUoahrdY/56ebRWeraTjMt/00Sh3UDtjgHtQNHwcRGOC98BJEAEymycmYcWwOprTgcB6VZ5JK5TAJ+fXGLBm3FDAmn6oPPjR4rKCAoJCal2eAiQp2x0vxTPB3ALO2CRkwmDy5WohzBDwSEFKRwPbknEggCPB/imwrycgxX2NzoMCHhPkDwqYMr9tRcP5qNrMZHkVnOjRMWwLCcr8ohBVb1OMjxLwGCvjTikrsBOiA6fNyCrm8V1rP93iVPpwaE+gO0SsWmPiXB+jikdf6SizrT5qKasx5j8ABbHpFTx+vFXp9EnYQmLx02h1QTTrl6eDqxLnGjporxl3NL3agEvXdT0WmEost648sQOYAeJS9Q7bfUVoMGnjo4AZdUMQku50McDcMWcBPvr0SzbTAFDfvJqwLzgxwATnCgnp4wDl6Aa+Ax283gghmj+vj7feE2KBBRMW3FzOpLOADl0Isb5587h/U4gGvkt5v60Z1VLG8BhYjbzRwyQZemwAd6cCR5/XFWLYZRIMpX39AR0tjaGGiGzLVyhse5C9RKC6ai42ppWPKiBagOvaYk8lO7DajerabOZP46Lby5wKjw1HCRx7p9sVMOWGzb/vA1hwiWc6jm3MvQDTogQkiqIhJV0nBQBTU+3okKCFDy9WwferkHjtxib7t3xIUQtHxnIwtx4mpg26/HfwVNVDb4oI9RHmx5WGelRVlrtiw43zboCLaxv46AZeB3IlTkwouebTr1y2NjSpHz68WNFjHvupy3q8TFn3Hos2IAk4Ju5dCo8B3wP7VPr/FGaKiG+T+v+TQqIrOqMTL1VdWV1DdmcbO8KXBz6esmYWYKPwDL5b5FA1a0hwapHiom0r/cKaoqr+27/XcrS5UwSMbQAAAABJRU5ErkJggg==)](https://deepwiki.com/agentscope-ai/agentscope-runtime)
[![A2A](https://img.shields.io/badge/A2A-Agent_to_Agent-blue.svg?label=A2A)](https://a2a-protocol.org/)
[![MCP](https://img.shields.io/badge/MCP-Model_Context_Protocol-purple.svg?logo=plug&label=MCP)](https://modelcontextprotocol.io/)
[![Discord](https://img.shields.io/badge/Discord-Join_Us-blueviolet.svg?logo=discord)](https://discord.gg/eYMpfnkG8h)
[![DingTalk](https://img.shields.io/badge/DingTalk-Join_Us-orange.svg)](https://qr.dingtalk.com/action/joingroup?code=v1,k1,OmDlBXpjW+I2vWjKDsjvI9dhcXjGZi3bQiojOq3dlDw=&_dt_no_comment=1&origin=11)

## AgentScope Runtime V1.0 Release

AgentScope Runtime V1.0 builds upon the solid foundation of efficient agent deployment and secure sandbox execution, now offering **a unified “Agent as API” experience** across the full agent development lifecycle — from local development to production deployment — with expanded sandbox types, protocol compatibility, and a richer set of built‑in tools.

At the same time, the way agents integrate with runtime services has evolved from **black‑box module replacement** to a ***white‑box adapter pattern*** — enabling developers to preserve the native interfaces and behaviors of their existing agent frameworks, while embedding runtime capabilities such as state management, session history, and tool registration directly into the application lifecycle. This provides greater flexibility and seamless cross‑framework integration.

**Key improvements in V1.0:**

- **Unified dev/prod paradigm** — Consistent Agent Functional in both development and production environments.
- **Native multi-agent support** — Full compatibility with AgentScope’s multi-agent paradigms
- **Mainstream SDK & protocol integration** — OpenAI SDK support and Google A2A protocol compatibility
- **Visual Web UI** — Ready-to-use web chat interface immediately available after deployment
- **Expanded sandbox types** — GUI, Browser, FileSystem, Mobile, Cloud (most visualized via VNC)
- **Richer built-in tools** — Production-ready modules for Search, RAG, AIGC, Payment, and more
- **Flexible deployment modes** — Local threads/processes, Docker, Kubernetes, or hosted cloud

For more detailed change descriptions and the migration guide, please refer to: {doc}`CHANGELOG`

## What is AgentScope Runtime?

**AgentScope Runtime** is a full-stack agent runtime that tackles two core challenges: **efficient agent deployment** and **secure sandbox execution**. It ships with foundational services such as short- and long-term memory plus agent-state persistence, along with hardened sandbox infrastructure. Whether you need to orchestrate production-grade agents or guarantee safe tool interactions, AgentScope Runtime provides developer-friendly workflows with complete observability.

In V1.0, these services are exposed via an **adapter pattern**, enabling seamless integration with the native modules of different agent frameworks while preserving their native interfaces and behaviors, ensuring both compatibility and flexibility.

This cookbook walks you through building service-ready agent applications with **AgentScope Runtime**.

## Core Architecture

**⚙️ Agent Deployment Runtime (Engine)**

Provides `AgentApp` as the main entry point for agent applications, along with production‑grade infrastructure for deploying, managing, and training agents. It also includes built‑in services such as session history, long‑term memory, and agent state management.

**🔒 Sandbox Execution Runtime (Sandbox)**

Secure, isolated environments that let agents execute code, control browsers, manipulate files, and integrate MCP tools—without exposing your host system.

**🛠️ Production‑Grade Tool Services (Tool)**

Built on trusted third‑party API capabilities (such as Search, RAG, AIGC, Payment, etc.), these services are exposed through a unified SDK that provides standardized call interfaces, enabling agents to integrate and utilize these capabilities in a consistent way without worrying about differences or complexities in the underlying APIs.

**🔌 Adapter Pattern (Adapter)**

Adapts various runtime service modules (state management, session history, tool execution, etc.) to the native module interfaces of agent frameworks, allowing developers to directly invoke these capabilities while preserving native behaviors — enabling seamless integration and flexible extension.

## Why AgentScope Runtime?

* 🤖 **AS Native Runtime Framework** — Officially built and maintained by AgentScope, deeply integrated with its multi‑agent paradigms, adapter pattern, and tool usage to ensure optimal compatibility and performance.
* **🏗️ Deployment Infrastructure**: Built-in long memory, session, agent state, and sandbox control services
* **🔒 Sandbox Execution**: Isolated sandboxes keep browser, file, and MCP tooling safe
* ⚡ **Developer Friendly**: Simple deployment flows plus rich customization endpoints
* **📊 Observability**: End-to-end tracing and monitoring for runtime behavior

Start deploying agents and experimenting with the sandbox today!
