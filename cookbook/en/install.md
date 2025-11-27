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

To install the stable release of Agentscope Runtime via PyPI, use:

```bash
pip install agentscope-runtime
```

### (Optional) Install preview version (Beta/RC)

If you want to try features that have not been officially released yet, you can install the latest preview version:

```bash
pip install --pre agentscope-runtime
```

```{note}
Note: Preview versions may contain features or interface changes that are not fully stable yet. It is recommended to use them in a testing environment.
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

You should see the version number printed out.


## Installation Options Explained

The core runtime (`agentscope-runtime`) includes AgentScope Framework and Sandbox dependencies. See details about all installation options at [pyproject.toml](https://github.com/agentscope-ai/agentscope-runtime/blob/main/pyproject.toml).

| **Component**         | **Package**          | **Use-Case**  | **Dependencies**                                             |
| --------------------- | -------------------- | ------------- | ------------------------------------------------------------ |
| Core Runtime          | `agentscope-runtime` | Core runtime  | Minimal including AgentScope Framework and Sandbox Dependencies |
| Development Tools     | `dev`                | Dev utilities | Testing, Linting, Docs                                       |

