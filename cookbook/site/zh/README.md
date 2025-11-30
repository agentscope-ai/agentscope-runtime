# 参与贡献Cookbook

感谢您对 AgentScope Runtime Cookbook 的兴趣！

AgentScope Runtime Cookbook 提供了使用 AgentScope Runtime 构建智能体应用程序的实用示例、教程和最佳实践。我们拥有一个友好的开发者、研究人员和从业者社区，他们热衷于帮助新的贡献者。我们欢迎各种类型的贡献，从添加新的教程和示例到改进现有文档和修复问题。

## 前提条件

在开始之前，请确保您已安装以下软件：

- Python 3.10+
- Git
- Markdown/Jupyter Notebooks 的基础知识

## 安装

克隆仓库并安装必要的开发依赖项：

```bash
git clone https://github.com/agentscope-ai/agentscope-runtime.git
cd agentscope-runtime
pip install -e ".[dev]"
```

## 管理文档

- **添加文档**：在适当的目录中创建新的 Markdown (`.md`) 或 Jupyter Notebook (`.ipynb`) 文件。更新 `_toc.yml` 文件以将其包含在目录中。
- **删除文档**：删除相关文件，并从 `_toc.yml` 文件中移除其条目。

## 构建 Jupyter Book

使用提供的 bash 脚本来清理、构建并可选择预览 Jupyter Book。

```bash
bash ./build.sh -p
```

- **`-p`** 选项将打开一个本地服务器，以在浏览器中预览Cookbook。

## （可选）手动构建步骤

如果您更喜欢手动构建，请按照以下步骤操作：

1. **清理以前的构建：**

   ```bash
   jupyter-book clean .
   ```

2. **构建Cookbook：**

   ```bash
   jupyter-book build .
   ```

   输出的 HTML 文件将生成在 `_build/html` 目录中。

3. **本地预览：**

   在浏览器中打开控制台所输出的文件路径，或使用简单的 HTTP 服务器：

   ```bash
   python -m http.server --directory _build/html 8000
   ```

   访问 [http://localhost:8000](http://localhost:8000)。
