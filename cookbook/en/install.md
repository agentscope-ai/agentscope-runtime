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

# Installation

Ready to get started with AgentScope Runtime? This guide will help you get up and running with **AgentScope Runtime** in just a few minutes.

## Installation Methods

Agentscope Runtime supports two installation methods: **PyPI** and **from source**. Both methods require Python 3.10 or higher.

### Install via PyPI

```{warning}
This project is under rapid development and iteration. We recommend installing from source to get the latest features and bug fixes.
```

To install the stable release of Agentscope Runtime via PyPI, use:

```bash
pip install agentscope-runtime
```

For the whole experience, including sandbox capabilities and other agent framework integrations:

```bash
pip install "agentscope-runtime[langgraph,agno,autogen]"
```

### (Optional) Install from Source

If you want to use the latest development version or contribute to the project, you can install from source:

```bash
git clone https://github.com/agentscope-ai/agentscope-runtime.git

cd agentscope-runtime

pip install .
```

For development, you may want to install with development dependencies:

```bash
pip install ".[dev]"
```

## Check Your Installation

To verify your installation and check the current version, run the following in Python:

```{code-cell}
import agentscope_runtime

print(f"AgentScope Runtime {agentscope_runtime.__version__} is ready!")
```

You should see the version number printed out. The expected output should look like: `AgentScope Runtime 0.1.0 is ready!`

### Check AgentScope Agent

```{code-cell}
try:
    from agentscope_runtime.engine.agents.agentscope_agent import AgentScopeAgent
    print(f"✅ {AgentScopeAgent.__name__} - Successfully imported")
except ImportError as e:
    print(f"❌ AgentScopeAgent - Import failed: {e}")
    print('💡 Try installing via: pip install "agentscope-runtime[agentscope]"')
```

### Check Agno Agent

```{code-cell}
try:
    from agentscope_runtime.engine.agents.agno_agent import AgnoAgent
    print(f"✅ {AgnoAgent.__name__} - Successfully imported")
except ImportError as e:
    print(f"❌ AgnoAgent - Import failed: {e}")
    print('💡 Try installing via: pip install "agentscope-runtime[agno]"')
```

### Check LangGraph Agent

```{code-cell}
try:
    from agentscope_runtime.engine.agents.langgraph_agent import LangGraphAgent
    print(f"✅ {LangGraphAgent.__name__} - Successfully imported")
except ImportError as e:
    print(f"❌ LangGraphAgent - Import failed: {e}")
    print('💡 Try installing via: pip install "agentscope-runtime[langgraph]"')
```

## Installation Options Explained

This diagram visualizes installation options as a layered architecture, starting with the core runtime (agentscope-runtime) — which **includes AgentScope Framework and Sandbox dependencies** — at the base. Optional modules (e.g., LangGraph, Agno, AutoGen) stack atop the core, each adding specific functionality (e.g., tool execution, framework integrations) and requiring corresponding dependencies. See details about all installation options at [pyproject.toml](https://github.com/agentscope-ai/agentscope-runtime/blob/main/pyproject.toml).

| **Component**         | **Package**          | **Use-Case**  | **Dependencies**                                             |
| --------------------- | -------------------- | ------------- | ------------------------------------------------------------ |
| Core Runtime          | `agentscope-runtime` | Core runtime  | Minimal including AgentScope Framework and Sandbox Dependencies |
| Development Tools     | `dev`                | Dev utilities | Testing, Linting, Docs                                       |
| Agno Integration      | `agno`               | Agno          | Agno Framework                                               |
| LangGraph Integration | `langgraph`          | LangGraph     | LangGraph Framework                                          |
| AutoGen Integration   | `autogen`            | AutoGen       | AutoGen Framework                                            |

