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

### 通过 PyPI 安装

要通过 PyPI 安装Agentscope Runtime的稳定版本，请使用：

```bash
pip install agentscope-runtime

# 若需额外扩展，请使用 extras 安装：
pip install "agentscope-runtime[ext]"
```

### （可选）安装预览版本（Beta/RC）

如果您想体验尚未正式发布的功能，可以安装最新的预览版本：

```bash
pip install --pre agentscope-runtime
```

```{note}
提示： 预发布版本可能含有尚未完全稳定的功能或接口变动，请在测试环境中使用。
```

### （可选）从源码安装

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


## 安装选项说明

核心运行时（`agentscope-runtime`）包含 AgentScope 框架和 Sandbox 依赖。查看所有安装选项的详细信息，请参见 [pyproject.toml](https://github.com/agentscope-ai/agentscope-runtime/blob/main/pyproject.toml)。

| **组件**   | **软件包**           | **用途**     | **依赖项**                                                   |
| ---------- | -------------------- | ------------ | ------------------------------------------------------------ |
| 核心运行时 | `agentscope-runtime` | 核心运行环境 | 最小依赖，包括 AgentScope 框架 和 Sandbox 依赖               |
| 开发工具   | `dev`                | 开发工具集   | 测试、代码检查（Linting）、文档                              |
| Extension  | `ext`                | 部署扩展     | REME AI、Mem0、阿里云服务、表格存储、LangChain、Azure 语音、对象存储、身份认证、构建工具 |
