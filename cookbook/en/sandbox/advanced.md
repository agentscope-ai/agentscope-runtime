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

# Advanced Usage of Tool Sandbox

```{note}
This section covers advanced sandbox usage. Complete the basic tutorial in the previous section ({doc}`sandbox`) first.
```

## Remote Sandbox Server

Remote sandbox servers let you deploy isolated, standalone services. This section explains the setup and configuration of a sandbox server. After setup, connect using the sandbox SDK.

### Quick Start with Default Configuration

The simplest way to start a sandbox server is by using the default configuration:

```bash
runtime-sandbox-server
```

The above command will start the server with default settings:

- Host: `127.0.0.1` (localhost), change to `0.0.0.0` to provide external access
- Port: `8000`
- Single worker process
- Base sandbox type in pool
- Local file system storage
- No Redis caching

For advanced configurations, you can use the `--config` option to specify a different environment setup. For instance, you can use:

```bash
# This command will load the settings defined in the `custom.env` file
runtime-sandbox-server --config custom.env
```

```{note}
If you plan to use the sandbox at scale in production, we recommend deploying it directly on Alibaba Cloud for managed hosting.

[One-click deploy sandbox on Alibaba Cloud](https://computenest.console.aliyun.com/service/instance/create/default?ServiceName=AgentScope%20Runtime%20%E6%B2%99%E7%AE%B1%E7%8E%AF%E5%A2%83)
```

### Custom Configuration

For custom deployments or specific requirements, you can customise the server configuration by creating a `.env` file in your working directory:

```bash
# .env
# Service settings
HOST="0.0.0.0"
PORT=8000
WORKERS=4
DEBUG=False
BEARER_TOKEN=your-secret-token

# Sandbox Manager settings
DEFAULT_SANDBOX_TYPE=base
POOL_SIZE=10
AUTO_CLEANUP=True
CONTAINER_PREFIX_KEY=agent-runtime-container-
CONTAINER_DEPLOYMENT=docker
DEFAULT_MOUNT_DIR=sessions_mount_dir
PORT_RANGE=[49152,59152]

# Redis settings
REDIS_ENABLED=True
REDIS_SERVER=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_USER=your-redis-user
REDIS_PASSWORD=your-redis-password
REDIS_PORT_KEY=_agent_runtime_container_occupied_ports
REDIS_CONTAINER_POOL_KEY=_agent_runtime_container_container_pool

# OSS settings
FILE_SYSTEM=oss
OSS_ENDPOINT=http://oss-cn-hangzhou.aliyuncs.com
OSS_ACCESS_KEY_ID=your-access-key-id
OSS_ACCESS_KEY_SECRET=your-access-key-secret
OSS_BUCKET_NAME=your-bucket-name

# K8S settings
K8S_NAMESPACE=default
KUBECONFIG_PATH=
```

### Configuration Reference

#### Service Settings

| Parameter      | Description                | Default     | Example                             |
| -------------- | -------------------------- | ----------- | ----------------------------------- |
| `HOST`         | Server bind address        | `127.0.0.1` | `0.0.0.0` for external access       |
| `PORT`         | Server port                | `8000`      | `8080`, `8008`                      |
| `WORKERS`      | Number of worker processes | `1`         | `4`                                 |
| `DEBUG`        | Enable debug mode          | `False`     | `False` or `True` for `Fastapi` app |
| `BEARER_TOKEN` | Authentication token       | Empty       | `your-secret-token`                 |

#### Runtime Manager Settings

| Parameter | Description | Default                    | Notes |
| --- | --- |----------------------------| --- |
| `DEFAULT_SANDBOX_TYPE` | Default sandbox type(s) | `base`                     | Can be a single type or a list of types, enabling multiple independent sandbox pools. Valid values include base, filesystem, browser, etc.<br/>Supported formats:<br/>• Single type: `DEFAULT_SANDBOX_TYPE=base`<br/>• Multiple types (comma-separated): `DEFAULT_SANDBOX_TYPE=base,gui`<br/>• Multiple types (JSON list): `DEFAULT_SANDBOX_TYPE=["base","gui"]`<br/>Each type will have its own separate pre-warmed pool. |
| `POOL_SIZE` | Pre-warmed container pool size | `1`                        | Cached containers for faster startup. The `POOL_SIZE` parameter controls how many containers are pre-created and cached in a ready-to-use state. When users request a new sandbox, the system will first try to allocate from this pre-warmed pool, significantly reducing startup time compared to creating containers from scratch. For example, with `POOL_SIZE=10`, the system maintains 10 ready containers that can be instantly assigned to new requests. |
| `AUTO_CLEANUP` | Automatic container cleanup | `True`                     | All sandboxes will be released after the server is closed if set to `True`. |
| `CONTAINER_PREFIX_KEY` | Container name prefix | `agent-runtime-container-` | For identification |
| `CONTAINER_DEPLOYMENT` | Container runtime | `docker`                   | Currently, `docker`, `k8s`, `agentrun`, `fc`, `gvisor` are supported |
| `DEFAULT_MOUNT_DIR` | Default mount directory | `sessions_mount_dir`       | For persistent storage path where the `/workspace` file is stored |
| `READONLY_MOUNTS` | Read-only directory mounts | `None` | A dictionary mapping **host paths** to **container paths**, mounted in **read-only** mode. Used to share files/configurations without allowing container writes. Example:<br/>`{"\/Users\/alice\/data": "\/data"}` mounts the host's `/Users/alice/data` to `/data` inside the container as read-only. |
| `PORT_RANGE` | Available port range | `[49152,59152]`            | For service port allocation |
| `HEARTBEAT_TIMEOUT` | Session heartbeat timeout (seconds) | `300` | If a `session_ctx_id` has no “touch” activities (e.g., list_tools/call_tool/check_health/add_mcp_servers) within this period, it is considered idle and can be reaped by the scanner. |
| `HEARTBEAT_SCAN_INTERVAL` | Heartbeat scan interval (seconds) | `0` | Interval for the background watcher to run the heartbeat scan. Set to `0` to disable the watcher (you may run `scan_heartbeat_once()` via an external cron instead). |
| `HEARTBEAT_LOCK_TTL` | Distributed lock TTL for scan/reap (seconds) | `120` | In multi-instance deployments, used to ensure only one instance reaps a given `session_ctx_id` at a time. Should be larger than the typical reap duration; too small may cause duplicate reaping after lock expiry. |
| `MAX_SANDBOX_INSTANCES` | Maximum sandbox instances (total container cap) | `0` | Limits the total number of sandbox instances (containers) the SandboxManager can create/keep. When the current container count reaches or exceeds this value, new creation requests are denied (e.g., returning `None` or raising an exception, depending on implementation). Values: • `0`: unlimited • `N>0`: at most `N` instances Examples: • `MAX_SANDBOX_INSTANCES=20` |

##### Backend Comparison

The sandbox supports multiple backends, selectable via `CONTAINER_DEPLOYMENT`. The table below compares local isolation options and remote/managed deployment backends.

| Property             | Docker (`docker`)         | gVisor (`gvisor`)                    | BoxLite (`boxlite`)                                         | Kubernetes (`k8s`)                                       | AgentRun (`agentrun`)                    | Function Compute (`fc`)                  | ACK (Managed K8s)                                        | Firecracker (Not supported)          |
| -------------------- | ------------------------- | ------------------------------------ | ----------------------------------------------------------- | -------------------------------------------------------- | ---------------------------------------- | ---------------------------------------- | -------------------------------------------------------- | ------------------------------------ |
| Category             | Local containers          | Local containers (user-space kernel) | Local lightweight VM                                        | Remote/cluster container orchestration                   | Cloud managed / serverless               | Cloud serverless                         | Cloud managed Kubernetes                                 | MicroVM (local/cloud)                |
| Isolation            | Kernel namespaces         | User-space kernel                    | Hardware VM                                                 | Kernel namespaces (pods/containers)                      | Platform-isolated (cloud)                | Platform-isolated (cloud)                | Kernel namespaces (managed K8s)                          | Hardware VM                          |
| Escape risk          | Container escape possible | Very low                             | Near zero                                                   | Container escape possible (depends on hardening/runtime) | Mitigated by platform                    | Mitigated by platform                    | Container escape possible (depends on hardening/runtime) | Near zero                            |
| Typical startup time | < 100 ms                  | < 200 ms                             | < 200 ms                                                    | Seconds (scheduling/pull dependent)                      | Seconds (cold start dependent)           | Seconds (cold start dependent)           | Seconds (scheduling/pull dependent)                      | < 125 ms                             |
| Requires daemon      | Yes                       | Yes (`runsc`)                        | No                                                          | Yes (cluster control plane/node agents)                  | No (managed)                             | No (managed)                             | Yes (managed; users don’t run control plane)             | Yes                                  |
| OCI image support    | Native                    | Via Docker                           | Native                                                      | Native                                                   | Typically supported (platform-dependent) | Typically supported (platform-dependent) | Native                                                   | Extra setup required                 |
| Embeddable           | No (CLI/API)              | No                                   | Yes (library)                                               | No (control-plane APIs)                                  | No (platform APIs)                       | No (platform APIs)                       | No (control-plane APIs)                                  | Partial                              |
| OS support           | Linux/macOS/Windows       | Linux/macOS                          | macOS (Apple Silicon), Linux (x86_64/ARM64), Windows (WLS2) | Linux (cluster nodes)                                    | Managed (cloud)                          | Managed (cloud)                          | Managed (cloud)                                          | Linux (x86_64/ARM64)                 |
| Best for             | Local dev/test            | Higher-security local runs           | High isolation + embeddable local runtime                   | Large-scale production scheduling                        | Managed hosting + elasticity             | Managed hosting + elasticity             | Alibaba Cloud managed K8s production                     | High isolation + fast boot (planned) |

#### (Optional) Redis Settings

```{note}
**When to use Redis:**
- **Single Worker (`WORKERS=1`)**: Redis is optional. The system can use in-memory caching for sandbox status, which is simpler and has lower latency.
- **Multiple Workers (`WORKERS>1`)**: Redis is required to share sandbox state across worker processes and ensure consistency.
```

Redis provides caching for sandbox status and state management. You can use an in-memory cache if only one worker exists:

| Parameter | Description | Default | Notes |
| --- | --- | --- | --- |
| `REDIS_ENABLED` | Enable Redis support | `False` | Required for scaling or when the number of workers is larger than `1` |
| `REDIS_SERVER` | Redis server address | localhost | Redis host |
| `REDIS_PORT` | Redis port | 6379 | Standard Redis port |
| `REDIS_DB` | Redis database number | `0` | 0-15 |
| `REDIS_USER` | Redis username | Empty | For Redis6+ ACL |
| `REDIS_PASSWORD` | Redis password | Empty | Authentication |
| `REDIS_PORT_KEY` | Port tracking key | `_agent_runtime_container_occupied_ports` | Internal use |
| `REDIS_CONTAINER_POOL_KEY` | Container pool key | `_agent_runtime_container_container_pool` | Internal use |

#### (Optional) OSS Settings

For distributed file storage using [Alibaba Cloud Object Storage Service](https://www.aliyun.com/product/oss):

| Parameter | Description | Default | Notes |
| --- | --- | --- | --- |
| `FILE_SYSTEM` | File system type | `local` | `local`, or `oss` |
| `OSS_ENDPOINT` | OSS endpoint URL | Empty | Regional endpoint |
| `OSS_ACCESS_KEY_ID` | OSS access key ID | Empty | From the OSS console |
| `OSS_ACCESS_KEY_SECRET` | OSS access key secret | Empty | Keep secure |
| `OSS_BUCKET_NAME` | OSS bucket name | Empty | Pre-created bucket |

#### (Optional) K8S Settings

To configure settings specific to Kubernetes in your sandbox server, ensure you set `CONTAINER_DEPLOYMENT=k8s` to activate this feature. Consider adjusting the following parameters:

| Parameter         | Description                     | Default   | Notes                                                |
| ----------------- | ------------------------------- | --------- | ---------------------------------------------------- |
| `K8S_NAMESPACE`   | Kubernetes namespace to be used | `default` | Set the namespace for resource deployment            |
| `KUBECONFIG_PATH` | Path to the kubeconfig file     | `None`    | Specifies the kubeconfig location for cluster access |

### (Optional) AgentRun Settings

[AgentRun](https://functionai.console.aliyun.com/cn-hangzhou/agent/) is a serverless intelligent Agent development framework launched by Alibaba Cloud. It provides a complete set of tools to help developers quickly build, deploy, and manage AI Agent applications. You can deploy the sandbox servers on AgentRun.

To configure settings specific to [AgentRun](https://functionai.console.aliyun.com/cn-hangzhou/agent/) in your sandbox server, ensure you set `CONTAINER_DEPLOYMENT=agentrun`. Consider adjusting the following parameters:

| Parameter                     | Description              | Default                          | Notes                                                                                     |
|-------------------------------| ------------------------ |----------------------------------|-------------------------------------------------------------------------------------------|
| `AGENT_RUN_ACCOUNT_ID`        | Alibaba Cloud Account ID             | Empty                           | Alibaba Cloud main account ID. Log in to the [RAM console](https://ram.console.aliyun.com/profile/access-keys) to get the Alibaba Cloud account ID and AK/SK |
| `AGENT_RUN_ACCESS_KEY_ID`     | Access Key ID               | Empty             | Alibaba Cloud AccessKey ID, requires `AliyunAgentRunFullAccess` permission                                           |
| `AGENT_RUN_ACCESS_KEY_SECRET` | Access Key Secret           | Empty         | Alibaba Cloud AccessKey Secret                                                                       |
| `AGENT_RUN_REGION_ID`         | Deployment Region ID               | Empty | AgentRun deployment region ID                                                                            |
| `AGENT_RUN_CPU`               | CPU Specification                  | `2.0`                            | vCPU specification                                                                                    |
| `AGENT_RUN_MEMORY`            | Memory Specification                 | `2048`                           | Memory specification(MB)                                                                                  |
| `AGENT_RUN_VPC_ID`            | VPC ID                   | `None`                           | VPC network ID (optional)                                                                               |
| `AGENT_RUN_VSWITCH_IDS`       | Switch ID List             | `None`                           | VSwitch ID list (optional)                                                                          |
| `AGENT_RUN_SECURITY_GROUP_ID` | Security Group ID                 | `None`                           | Security group ID (optional)                                                                                 |
| `AGENT_RUN_PREFIX`            | Resource Name Prefix             | `agentscope-sandbox`             | Prefix for created resource names                                                                                 |
| `AGENT_RUN_LOG_PROJECT`       | SLS Log Project              | `None`                           | SLS log project name (optional)                                                                             |
| `AGENT_RUN_LOG_STORE`         | SLS Log Store                | `None`                           | SLS log store name (optional)                                                                              |

#### (Optional) Function Compute (FC) Settings

[Function Compute](https://fcnext.console.aliyun.com/) (FC) is a serverless computing service that allows you to run your code without managing infrastructure. You can deploy sandbox servers on FC.

To configure settings specific to [FC](https://fcnext.console.aliyun.com/) in your sandbox server, ensure you set `CONTAINER_DEPLOYMENT=fc`. Consider adjusting the following parameters:

| Parameter                     | Description              | Default                          | Notes                                                                                                                                                        |
|-------------------------------| ------------------------ |----------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `FC_ACCOUNT_ID`               | Alibaba Cloud Account ID             | Empty                           | Alibaba Cloud main account ID. Log in to the [RAM console](https://ram.console.aliyun.com/profile/access-keys) to get the Alibaba Cloud account ID and AK/SK |
| `FC_ACCESS_KEY_ID`     | Access Key ID               | Empty             | Alibaba Cloud AccessKey ID, requires `AliyunFCFullAccess` permission                                                                                         |
| `FC_ACCESS_KEY_SECRET` | Access Key Secret           | Empty         | Alibaba Cloud AccessKey Secret                                                                                                                               |
| `FC_REGION_ID`         | Deployment Region ID               | Empty | FC deployment region ID                                                                                                                                      |
| `FC_CPU`               | CPU Specification                  | `2.0`                            | vCPU specification                                                                                                                                           |
| `FC_MEMORY`            | Memory Specification                 | `2048`                           | Memory specification (MB)                                                                                                                                    |
| `FC_VPC_ID`            | VPC ID                   | `None`                           | VPC network ID (optional)                                                                                                                                    |
| `FC_VSWITCH_IDS`       | Switch ID List             | `None`                           | VSwitch ID list (optional)                                                                                                                                   |
| `FC_SECURITY_GROUP_ID` | Security Group ID                 | `None`                           | Security group ID (optional)                                                                                                                                 |
| `FC_PREFIX`            | Resource Name Prefix             | `agentscope-sandbox`             | Prefix for created resource names                                                                                                                            |
| `FC_LOG_PROJECT`       | SLS Log Project              | `None`                           | SLS log project name (optional)                                                                                                                              |
| `FC_LOG_STORE`         | SLS Log Store                | `None`                           | SLS log store name (optional)                                                                                                                                |

### Loading Custom Sandbox

In addition to the default basic sandbox types, you can implement a custom sandbox by writing an extension module and loading it with the `--extension` parameter.
This allows you to modify the security level, add environment variables, define custom timeouts, and more.

#### Writing a custom sandbox extension (e.g. `custom_sandbox.py`)

See {ref}`Custom Sandbox Class <custom_sandbox>`

> - `@SandboxRegistry.register` will register the class into the sandbox manager, so it can be recognised and used at startup.
> - The `environment` field can inject external API keys or other necessary configurations into the sandbox.
> - The class inherits from `Sandbox` and can override its methods to implement more customised logic.

#### Loading the extension at startup

Place `custom_sandbox.py` in the project directory or in a Python module path where it can be imported, then start the server specifying the `--extension` parameter:

```bash
runtime-sandbox-server --extension custom_sandbox.py
```

If you have multiple sandbox extensions, you can add multiple `--extension` options, for example:

```bash
runtime-sandbox-server \
    --extension custom_sandbox1.py \
    --extension custom_sandbox2.py
```

### Starting the Server

You can also start the server directly without using startup options after configuring the `.env` file.

```bash
runtime-sandbox-server
```

The server will automatically load the configuration from the `.env` file and start with your custom settings.

### Connecting to Remote Server

From your client application, connect to the remote server:

```python
from agentscope_runtime.sandbox import BaseSandbox

# Connect to remote server (replace with your actual server address and port)
with BaseSandbox(
    base_url="http://127.0.0.1:8000",
    bearer_token="your-bearer-token",
) as sandbox:
    # Use the sandbox normally
    result = sandbox.run_shell_command(command="echo 'Hello from remote!'")
    print(result)
```

## Custom Built Sandbox

While the built-in sandbox types cover common use cases, you may encounter scenarios requiring specialised environments or unique tool combinations. Creating custom sandboxes allows you to tailor the execution environment to your specific needs. This section demonstrates how to build and register your custom sandbox types.

### Install from Source (Required for Custom Sandbox)

To create custom sandboxes, you need to install AgentScope Runtime from source in editable mode, which allows you to modify the code and see changes immediately:

```bash
git clone https://github.com/agentscope-ai/agentscope-runtime.git
cd agentscope-runtime
git submodule update --init --recursive
pip install -e .
```

```{note}
The `-e` (editable) flag is essential when creating custom sandboxes because it allows you to:
- Modify sandbox code and see changes immediately without reinstalling
- Add your custom sandbox classes to the registry
- Develop and test custom tools iteratively
```

(custom_sandbox)=

### Creating a Custom Sandbox Class

You can define your custom sandbox type and register it in the system to meet special requirements. Just inherit from `Sandbox` and decorate with `SandboxRegistry.register`, then put the file in `src/agentscope_runtime/sandbox/custom` (e.g., `src/agentscope_runtime/sandbox/custom/custom_sandbox.py`):

```python
# -*- coding: utf-8 -*-
import os

from typing import Optional

from agentscope_runtime.sandbox.utils import build_image_uri
from agentscope_runtime.sandbox.registry import SandboxRegistry
from agentscope_runtime.sandbox.enums import SandboxType
from agentscope_runtime.sandbox.box.sandbox import Sandbox

SANDBOXTYPE = "my_custom_sandbox"


@SandboxRegistry.register(
    build_image_uri(f"runtime-sandbox-{SANDBOXTYPE}"),
    sandbox_type=SANDBOXTYPE,
    security_level="medium",
    timeout=60,
    description="my sandbox",
    environment={
        "TAVILY_API_KEY": os.getenv("TAVILY_API_KEY", ""),
        "AMAP_MAPS_API_KEY": os.getenv("AMAP_MAPS_API_KEY", ""),
    },
)
class MyCustomSandbox(Sandbox):
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
- **Simple MCP Server Changes**: For simply changing the initial MCP Server in Sandbox, modify the `mcp_server_configs.json` file
- **Advanced Customization**: For more advanced usage and customization, you must be very familiar with Dockerfile syntax and Docker best practices
```

Here's an example Dockerfile for a custom sandbox with a filesystem, a browser, and some useful MCP tools in one sandbox:


```dockerfile
FROM node:22-slim

# ENV variables
ENV NODE_ENV=production
ENV WORKSPACE_DIR=/workspace

ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --fix-missing \
    curl  \
    python3  \
    python3-pip  \
    python3-venv \
    build-essential  \
    libssl-dev  \
    git  \
    supervisor  \
    vim  \
    nginx \
    gettext-base \
    xfce4 \
    xfce4-terminal \
    x11vnc \
    xvfb \
    novnc \
    websockify \
    dbus-x11 \
    fonts-wqy-zenhei \
    fonts-wqy-microhei

RUN apt-get update && apt-get install -y --fix-missing \
    chromium \
    chromium-sandbox \
    libx11-xcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxi6 \
    libxtst6 \
    libnss3 \
    libglib2.0-0 \
    libdrm2 \
    libgbm1 \
    libasound2 \
    fonts-liberation \
    libu2f-udev

RUN sed -i 's/^CHROMIUM_FLAGS=""/CHROMIUM_FLAGS="--no-sandbox"/' /usr/bin/chromium

WORKDIR /agentscope_runtime
RUN python3 -m venv venv
ENV PATH="/agentscope_runtime/venv/bin:$PATH"

COPY src/agentscope_runtime/sandbox/box/shared/app.py ./
COPY src/agentscope_runtime/sandbox/box/shared/routers/ ./routers/
COPY src/agentscope_runtime/sandbox/box/shared/dependencies/ ./dependencies/
COPY examples/sandbox/custom_sandbox/box/ ./

RUN pip install -r requirements.txt

WORKDIR ${WORKSPACE_DIR}
RUN mv /agentscope_runtime/config/supervisord.conf /etc/supervisor/conf.d/supervisord.conf
RUN mv /agentscope_runtime/config/nginx.conf.template /etc/nginx/nginx.conf.template
RUN mv /agentscope_runtime/vnc_relay.html /usr/share/novnc/vnc_relay.html
RUN git init \
    && chmod +x /agentscope_runtime/scripts/start.sh

COPY .gitignore ${WORKSPACE_DIR}

# MCP required environment variables
ENV TAVILY_API_KEY=123
ENV AMAP_MAPS_API_KEY=123

# Cleanup
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
runtime-sandbox-builder my_custom_sandbox --dockerfile_path examples/sandbox/custom_sandbox/Dockerfile --extension PATH_TO_YOUR_SANDBOX_MODULE
```

**Command Parameters:**

- `custom_sandbox`: The name/tag for your custom sandbox image
- `--dockerfile_path`: Path to your custom Dockerfile
- `--extension`: Path to your custom sandbox Python module

Once built, your custom sandbox image will be ready to use with the corresponding sandbox class you defined.

#### Building Built-in Images Locally

You can also use the builder to build the built-in sandbox images locally:

```bash
# Build all built-in images
runtime-sandbox-builder all

# Build base image (~1Gb)
runtime-sandbox-builder base

# Build GUI image (~2Gb)
runtime-sandbox-builder gui

# Build browser image (~2Gb)
runtime-sandbox-builder browser

# Build filesystem image (~2Gb)
runtime-sandbox-builder filesystem

# Build mobile image (~3Gb)
runtime-sandbox-builder mobile
```
The above commands are useful when you want to:

- Build images locally instead of pulling from the registry
- Customise the base images before building your own
- Ensure you have the latest version of the built-in images
- Work in air-gapped environments

### Change Sandbox Image Configuration

The Docker image used by the Sandbox module is determined by the following three environment variables.
You can modify any of them as needed to change the image source or version.

| Environment Variable              | Purpose                                                      | Default Value  | Example Modification                                         |
| --------------------------------- | ------------------------------------------------------------ | -------------- | ------------------------------------------------------------ |
| `RUNTIME_SANDBOX_REGISTRY`        | Docker registry address. An empty value means Docker Hub will be used. | `""`           | `export RUNTIME_SANDBOX_REGISTRY="agentscope-registry.ap-southeast-1.cr.aliyuncs.com"` |
| `RUNTIME_SANDBOX_IMAGE_NAMESPACE` | Image namespace, similar to an account name.                 | `"agentscope"` | `export RUNTIME_SANDBOX_IMAGE_NAMESPACE="my_namespace"`      |
| `RUNTIME_SANDBOX_IMAGE_TAG`       | Image version tag.                                           | `"latest"`     | `export RUNTIME_SANDBOX_IMAGE_TAG="my_custom"`               |
