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

# 安装

准备好开始使用 AgentScope Runtime 了吗？本指南将帮助您在几分钟内快速搭建和运行**AgentScope Runtime**。

## 安装方式

### 1. 通过 PyPI 安装

```{warning}
本项目正在快速开发和迭代中。我们建议从源码安装以获取最新功能和Bug修复。
```

要通过 PyPI 安装Agentscope Runtime的稳定版本，请使用：

```bash
pip install agentscope-runtime
```

如需完整功能，包括沙箱功能和其他智能体框架集成：

```bash
pip install "agentscope-runtime[langgraph,agno,autogen]"
```

### 2. （可选）从源码安装

如果您想要使用最新的开发版本或为项目做贡献，可以从源码安装：

```bash
git clone https://github.com/agentscope-ai/agentscope-runtime.git

cd agentscope-runtime

pip install .
```

对于开发用途，您需要安装包含开发依赖的版本：

```bash
pip install ".[dev]"
```

## 检查您的安装

要验证安装并查看当前版本，请在 Python 中运行以下代码：

```{code-cell}
import agentscope_runtime

print(f"AgentScope Runtime {agentscope_runtime.__version__} is ready!")
```

执行代码后，您应该会看到版本号输出。

### 检查 AgentScope Agent

```{code-cell}
try:
    from agentscope_runtime.engine.agents.agentscope_agent import AgentScopeAgent
    print(f"✅ {AgentScopeAgent.__name__} - 导入成功")
except ImportError as e:
    print(f"❌ AgentScopeAgent - 导入失败：{e}")
    print('💡 尝试通过以下命令安装：pip install "agentscope-runtime[agentscope]"')
```

### 检查 Agno Agent

```{code-cell}
try:
    from agentscope_runtime.engine.agents.agno_agent import AgnoAgent
    print(f"✅ {AgnoAgent.__name__} - 导入成功")
except ImportError as e:
    print(f"❌ AgnoAgent - 导入失败：{e}")
    print('💡尝试通过以下命令安装：pip install "agentscope-runtime[agno]"')
```

### 检查 LangGraph Agent

```{code-cell}
try:
    from agentscope_runtime.engine.agents.langgraph_agent import LangGraphAgent
    print(f"✅ {LangGraphAgent.__name__} - 导入成功")
except ImportError as e:
    print(f"❌ LangGraphAgent -导入失败：{e}")
    print('💡尝试通过以下命令安装：pip install "agentscope-runtime[langgraph]"')
```

## 安装选项说明

这个图展示了安装选项的层次结构，从底层核心运行时（agentscope-runtime）开始——其中 **包含 AgentScope 框架 和 Sandbox 依赖**。可选模块（例如 LangGraph、Agno、AutoGen）堆叠在核心之上，每个模块都增加了特定的功能（如工具执行、框架集成），并需要相应的依赖项。查看所有安装选项的详细信息，请参见 [pyproject.toml](https://github.com/agentscope-ai/agentscope-runtime/blob/main/pyproject.toml)。

| **组件**       | **软件包**           | **用途**     | **依赖项**                                     |
| -------------- | -------------------- | ------------ | ---------------------------------------------- |
| 核心运行时     | `agentscope-runtime` | 核心运行环境 | 最小依赖，包括 AgentScope 框架 和 Sandbox 依赖 |
| 开发工具       | `dev`                | 开发工具集   | 测试、代码检查（Linting）、文档                |
| Agno 集成      | `agno`               | Agno         | Agno 框架                                      |
| LangGraph 集成 | `langgraph`          | LangGraph    | LangGraph 框架                                 |
| AutoGen 集成   | `autogen`            | AutoGen      | AutoGen 框架                                   |
