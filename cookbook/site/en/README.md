# Contribute to Cookbook

Thanks for your interest in the AgentScope Runtime Cookbook!

AgentScope Runtime Cookbook provides practical examples, tutorials, and best practices for building agent applications with AgentScope Runtime. We have a friendly community of developers, researchers, and practitioners who are eager to help new contributors. We welcome contributions of all types, from adding new tutorials and examples to improving existing documentation and fixing issues.

## Prerequisites

Before you begin, ensure you have the following installed:

- Python 3.10+
- Git
- Basic knowledge of Markdown/Jupyter Notebooks

## Installation

Clone the repository and install the necessary development dependencies:

```bash
git clone https://github.com/agentscope-ai/agentscope-runtime.git
cd agentscope-runtime
pip install -e ".[dev]"
```

## Managing Documentation

- **Add Documentation**: Create a new Markdown (`.md`) or Jupyter Notebook (`.ipynb`) in the appropriate directory. Update the `_toc.yml` file to include it in the table of contents.
- **Remove Documentation**: Delete the relevant file and remove its entry from the `_toc.yml` file.

## Building the Jupyter Book

Use the provided bash script to clean, build, and optionally preview the Jupyter Book.

```bash
bash ./build.sh -p
```

- The **`-p`** option will open a local server to preview the book in your browser.

## (Optional) Manual Build Steps

If you prefer building manually, follow these steps:

1. **Clean Previous Builds:**

   ```bash
   jupyter-book clean .
   ```

2. **Build the Book:**

   ```bash
   jupyter-book build .
   ```

   Output HTML files will be generated in the `_build/html` directory.

3. **Preview Locally:**

   Open the output in your browser or use a simple HTTP server:

   ```bash
   python -m http.server --directory _build/html 8000
   ```

   Visit [http://localhost:8000](http://localhost:8000/).
