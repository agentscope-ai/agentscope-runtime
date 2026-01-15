## Custom Built Sandbox

While the built-in sandbox types cover common use cases, you may encounter scenarios requiring specialized environments or unique tool combinations. Creating custom sandboxes allows you to tailor the execution environment to your specific needs. This section demonstrates how to build and register your own sandbox types.

### Install from Source (Required for Custom Sandbox)

To create custom sandboxes, you need to install AgentScope Runtime from source in editable mode, which allows you to modify the code and see changes immediately:

```bash
git clone https://github.com/agentscope-ai/agentscope-runtime.git
cd agentscope-runtime
git submodule update --init --recursive
pip install -e .
```

```{note}
The `-e` (editable) flag is important when creating custom sandboxes because it allows you to:
- Modify sandbox code and see changes immediately without reinstalling
- Add your custom sandbox classes to the registry
- Develop and test custom tools iteratively
```

### Creating Custom Sandbox Class

You can define your own sandbox type and register it in the system to meet special requirements. Just inherit from `Sandbox` and decorate with `SandboxRegistry.register`, then put the file in `src/agentscope_runtime/sandbox/custom` (e.g., `src/agentscope_runtime/sandbox/custom/custom_sandbox.py`):

```python
# src/agentscope_runtime/sandbox/custom/custom_sandbox.py
# -*- coding: utf-8 -*-
import os

from typing import Optional

from ..version import __version__
from ..registry import SandboxRegistry
from ..enums import SandboxType
from ..box.sandbox import Sandbox

SANDBOXTYPE = "custom_sandbox"


@SandboxRegistry.register(
    f"agentscope/runtime-sandbox-{SANDBOXTYPE}:{__version__}",
    sandbox_type=SANDBOXTYPE,
    security_level="medium",
    timeout=60,
    description="my sandbox",
    environment={
        "TAVILY_API_KEY": os.getenv("TAVILY_API_KEY", ""),
        "AMAP_MAPS_API_KEY": os.getenv("AMAP_MAPS_API_KEY", ""),
    },
)
class CustomSandbox(Sandbox):
    def __init__(
        self,
        sandbox_id: Optional[str] = None,
        timeout: int = 3000,
        base_url: Optional[str] = None,
        bearer_token: Optional[str] = None,
    ):
        super().__init__(
            sandbox_id,
            timeout,
            base_url,
            bearer_token,
            SandboxType(SANDBOXTYPE),
        )

```

### Preparing Docker Image

Creating a custom sandbox also requires preparing the corresponding Docker image. The image should include all the necessary dependencies, tools, and configurations for your specific use case.

```{note}
**Configuration Options:**
- **Simple MCP Server Changes**: For simply changing the initial MCP Server in Sandbox, just modify the `mcp_server_configs.json` file
- **Advanced Customization**: For more advanced usage and customization, you must be very familiar with Dockerfile syntax and Docker best practices
```

Here's an example Dockerfile for a custom sandbox with filesystem, browser and some useful MCP tools in one sandbox:

```dockerfile
FROM node:22-slim

# Set ENV variables
ENV NODE_ENV=production
ENV WORKSPACE_DIR=/workspace

ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --fix-missing \
    curl \
    python3 \
    python3-pip \
    python3-venv \
    build-essential \
    libssl-dev \
    git \
    supervisor \
    vim \
    nginx \
    gettext-base

WORKDIR /agentscope_runtime
RUN python3 -m venv venv
ENV PATH="/agentscope_runtime/venv/bin:$PATH"

# Copy application files
COPY src/agentscope_runtime/sandbox/box/shared/app.py ./
COPY src/agentscope_runtime/sandbox/box/shared/routers/ ./routers/
COPY src/agentscope_runtime/sandbox/box/shared/dependencies/ ./dependencies/
COPY src/agentscope_runtime/sandbox/box/shared/artifacts/ ./ext_services/artifacts/
COPY src/agentscope_runtime/sandbox/box/shared/third_party/markdownify-mcp/ ./mcp_project/markdownify-mcp/
COPY src/agentscope_runtime/sandbox/box/shared/third_party/steel-browser/ ./ext_services/steel-browser/
COPY examples/custom_sandbox/box/ ./

RUN pip install -r requirements.txt

# Install Google Chrome & fonts
RUN curl -fsSL https://dl.google.com/linux/linux_signing_key.pub | apt-key add - && \
    echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list && \
    apt-get update && apt-get install -y --fix-missing google-chrome-stable \
    google-chrome-stable \
    fonts-wqy-zenhei \
    fonts-wqy-microhei

# Install steel browser
WORKDIR /agentscope_runtime/ext_services/steel-browser
RUN npm ci --omit=dev \
    && npm install -g webpack webpack-cli \
    && npm run build -w api \
    && rm -rf node_modules/.cache

# Install artifacts backend
WORKDIR /agentscope_runtime/ext_services/artifacts
RUN npm install \
    && rm -rf node_modules/.cache

# Install mcp_project/markdownify-mcp
WORKDIR /agentscope_runtime/mcp_project/markdownify-mcp
RUN npm install -g pnpm \
    && pnpm install \
    && pnpm run build \
    && rm -rf node_modules/.cache

WORKDIR ${WORKSPACE_DIR}
RUN mv /agentscope_runtime/config/supervisord.conf /etc/supervisor/conf.d/supervisord.conf
RUN mv /agentscope_runtime/config/nginx.conf.template /etc/nginx/nginx.conf.template
RUN git init \
    && chmod +x /agentscope_runtime/scripts/start.sh

COPY .gitignore ${WORKSPACE_DIR}

# MCP required environment variables
ENV TAVILY_API_KEY=123
ENV AMAP_MAPS_API_KEY=123

# Cleanup to reduce image size
RUN pip cache purge \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /tmp/* \
    && rm -rf /var/tmp/* \
    && npm cache clean --force \
    && rm -rf ~/.npm/_cacache

CMD ["/bin/sh", "-c", "envsubst '$SECRET_TOKEN' < /etc/nginx/nginx.conf.template > /etc/nginx/nginx.conf && /usr/bin/supervisord -c /etc/supervisor/conf.d/supervisord.conf"]
```

### Building Your Custom Image

After preparing your Dockerfile and custom sandbox class, use the built-in builder tool to build your custom sandbox image:

```bash
runtime-sandbox-builder custom_sandbox --dockerfile_path examples/custom_sandbox/Dockerfile
```

**Command Parameters:**

- `custom_sandbox`: The name/tag for your custom sandbox image
- `--dockerfile_path`: Path to your custom Dockerfile

Once built, your custom sandbox image will be ready to use with the corresponding sandbox class you defined.