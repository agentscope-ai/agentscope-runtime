# AgentScope Runtime CLI (`agentscope`)

The unified command-line interface for managing your agent development, deployment, and runtime operations.

## Table of Contents

- [Quick Start](#quick-start)
- [Complete Example](#complete-example)
- [Core Commands](#core-commands)
  - [Development: `agentscope chat`](#1-development-agentscope-chat)
  - [Web UI: `agentscope web`](#2-web-ui-agentscope-web)
  - [Run Agent Service: `agentscope run`](#3-run-agent-service-agentscope-run)
  - [Deployment: `agentscope deploy`](#4-deployment-agentscope-deploy)
  - [Deployment Management](#5-deployment-management)
  - [Sandbox Management: `agentscope sandbox`](#6-sandbox-management-as-runtime-sandbox)
- [API Reference](#api-reference)
- [Common Workflows](#common-workflows)
- [Troubleshooting](#troubleshooting)

## Quick Start

### Installation

```bash
pip install agentscope-runtime
```

### Verify Installation

```bash
agentscope --version
agentscope --help
```

## Complete Example

This section provides a complete walkthrough of creating, running, and deploying an agent.

### Step 1: Create Your Agent Project

Create a project directory structure:

```
my-agent-project/
├── app_agent.py          # Main agent file
├── requirements.txt      # Python dependencies (optional)
└── .env                  # Environment variables (optional)
```

### Step 2: Write Your Agent Code

Create `app_agent.py`:

```python
# -*- coding: utf-8 -*-
import os

from agentscope.agent import ReActAgent
from agentscope.formatter import DashScopeChatFormatter
from agentscope.model import DashScopeChatModel
from agentscope.pipeline import stream_printing_messages
from agentscope.tool import Toolkit, execute_python_code
from agentscope.memory import InMemoryMemory

from agentscope_runtime.engine.app import AgentApp
from agentscope_runtime.engine.schemas.agent_schemas import AgentRequest
from agentscope_runtime.engine.services.agent_state import (
    InMemoryStateService,
)

# Create AgentApp instance
agent_app = AgentApp(
    app_name="MyAssistant",
    app_description="A helpful assistant agent",
)


@agent_app.init
async def init_func(self):
    """Initialize services."""
    self.state_service = InMemoryStateService()
    await self.state_service.start()


@agent_app.shutdown
async def shutdown_func(self):
    """Cleanup services."""
    await self.state_service.stop()


@agent_app.query(framework="agentscope")
async def query_func(
    self,
    msgs,
    request: AgentRequest = None,
    **kwargs,
):
    """Process user queries."""
    session_id = request.session_id
    user_id = request.user_id

    # Load state if exists
    state = await self.state_service.export_state(
        session_id=session_id,
        user_id=user_id,
    )

    # Create toolkit with Python execution
    toolkit = Toolkit()
    toolkit.register_tool_function(execute_python_code)

    # Create agent
    agent = ReActAgent(
        name="MyAssistant",
        model=DashScopeChatModel(
            "qwen-turbo",
            api_key=os.getenv("DASHSCOPE_API_KEY"),
            enable_thinking=True,
            stream=True,
        ),
        sys_prompt="You're a helpful assistant.",
        toolkit=toolkit,
        memory=InMemoryMemory(),
        formatter=DashScopeChatFormatter(),
    )
    agent.set_console_output_enabled(False)

    # Load state if available
    if state:
        agent.load_state_dict(state)

    # Process query and stream response
    async for msg, last in stream_printing_messages(
        agents=[agent],
        coroutine_task=agent(msgs),
    ):
        yield msg, last

    # Save state
    state = agent.state_dict()
    await self.state_service.save_state(
        user_id=user_id,
        session_id=session_id,
        state=state,
    )


if __name__ == "__main__":
    agent_app.run()
```

### Step 3: Run Your Agent Locally

**Interactive mode (multi-turn conversation):**

```bash
cd my-agent-project
export DASHSCOPE_API_KEY=sk-your-api-key
agentscope chat app_agent.py
```

**Single query mode:**

```bash
agentscope chat app_agent.py --query "Hello, how are you?"
```

**With custom session:**

```bash
agentscope chat app_agent.py --query "Hello" --session-id my-session --user-id user123
```

### Step 4: Test with Web UI

```bash
agentscope web app_agent.py
```
An backend service will be started at `http://127.0.0.1:8090` on default and
a web server on `http://localhost:5173/`.
Open it in your browser.

### Step 5: Deploy Your Agent

**Local deployment:**

```bash
agentscope deploy local app_agent.py --env DASHSCOPE_API_KEY=sk-your-api-key
```

After deployment, you'll receive:
- **Deployment ID**: `local_20250101_120000_abc123`
- **URL**: `http://127.0.0.1:8080`

**Query deployed agent via curl:**

```bash
curl -i -X POST "http://127.0.0.1:8080/process" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer 8ddcc903-b75b-40b8-ba7f-1501e05cb3f2" \
  -d '{
    "input": [
      {
        "role": "user",
        "content": [
          {
            "type": "text",
            "text": "Hello, how are you?"
          }
        ]
      }
    ],
    "session_id": "123"
  }'
```

**Or use CLI:**

```bash
agentscope chat local_20250101_120000_abc123 --query "Hello"
```

### Step 6: Stop Deployment

```bash
agentscope stop local_20250101_120000_abc123
```

## Core Commands

### 1. Development: `agentscope chat`

Run your agent interactively or execute single queries for testing during development.

#### Command Syntax

```bash
agentscope chat SOURCE [OPTIONS]
```

#### Arguments

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `SOURCE` | string | Yes | Path to Python file, project directory, or deployment ID |

#### Options

| Option | Short | Type | Default | Description |
|--------|-------|------|---------|-------------|
| `--query` | `-q` | string | `None` | Single query to execute (non-interactive mode). If provided, executes query and exits |
| `--session-id` | - | string | `None` | Session ID for conversation continuity. If not provided, a random session ID is generated |
| `--user-id` | - | string | `"default_user"` | User ID for the session |
| `--verbose` | `-v` | flag | `False` | Show verbose output including logs and reasoning |
| `--entrypoint` | `-e` | string | `None` | Entrypoint file name for directory sources (e.g., 'app.py', 'main.py'). Only used when SOURCE is a directory |

#### Examples

**Interactive mode (multi-turn conversation):**

```bash
# Start interactive session
agentscope chat app_agent.py

# Load from project directory
agentscope chat ./my-agent-project

# Use existing deployment
agentscope chat local_20250101_120000_abc123
```

**Single query mode:**

```bash
# Execute one query and exit
agentscope chat app_agent.py --query "What is the weather today?"

# With custom session and user
agentscope chat app_agent.py --query "Hello" --session-id my-session --user-id user123

# Verbose mode (show reasoning and logs)
agentscope chat app_agent.py --query "Hello" --verbose
```

**Project directory with custom entrypoint:**

```bash
agentscope chat ./my-project --entrypoint custom_app.py
```

#### Agent File Requirements

Your agent file **must** run the `agent_app.run()` as main method.

### 2. Web UI: `agentscope web`

Launch your agent with a browser-based web interface for testing.

#### Command Syntax

```bash
agentscope web SOURCE [OPTIONS]
```

#### Arguments

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `SOURCE` | string | Yes | Path to Python file or project directory |

#### Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--host` | string | `"127.0.0.1"` | Host to bind the web server to |
| `--port` | integer | `8090` | Port to bind the web server to |
| `--entrypoint` | string | `None` | Entrypoint file name for directory sources |

#### Examples

```bash
# Default host and port (127.0.0.1:8090)
agentscope web app_agent.py

# Custom host and port
agentscope web app_agent.py --host 0.0.0.0 --port 8000

# From project directory
agentscope web ./my-agent-project
```

**Note:** First launch may take longer as web UI dependencies are installed via npm.

### 3. Run Agent Service: `agentscope run`

Start agent service and run continuously, exposing HTTP API endpoints for programmatic access.

#### Command Syntax

```bash
agentscope run SOURCE [OPTIONS]
```

#### Arguments

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `SOURCE` | string | Yes | Path to Python file, project directory, or deployment ID |

#### Options

| Option | Short | Type | Default | Description |
|--------|-------|------|---------|-------------|
| `--host` | `-h` | string | `"0.0.0.0"` | Host address to bind to |
| `--port` | `-p` | integer | `8080` | Port number to serve the application on |
| `--verbose` | `-v` | flag | `False` | Show verbose output including logs |
| `--entrypoint` | `-e` | string | `None` | Entrypoint file name for directory sources (e.g., 'app.py', 'main.py') |

#### Examples

```bash
# Run agent service with defaults (0.0.0.0:8080)
agentscope run app_agent.py

# Specify custom host and port
agentscope run app_agent.py --host 127.0.0.1 --port 8090

# Run with verbose logging
agentscope run app_agent.py --verbose

# Use custom entrypoint for directory source
agentscope run ./my-project --entrypoint custom_app.py

```

#### Use Cases

The `run` command is ideal for:
- Running agent as a background service
- Providing HTTP API access without interactive CLI
- Integration with other applications via HTTP
- Production-like local testing

#### Accessing the Service

Once the service is running, you can access it via HTTP API:

```bash
curl -X POST "http://127.0.0.1:8080/process" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "input": [
      {
        "role": "user",
        "content": [{"type": "text", "text": "Hello!"}]
      }
    ],
    "session_id": "my-session"
  }'
```

**Note:** Press Ctrl+C to stop the service.

### 4. Deployment: `agentscope deploy`

Deploy agents to various platforms for production use.

#### Command Syntax

```bash
agentscope deploy PLATFORM SOURCE [OPTIONS]
```

#### Platforms

- `modelstudio`: Alibaba Cloud ModelStudio
- `agentrun`: Alibaba Cloud AgentRun
- `k8s`: Kubernetes/ACK

#### Common Options (All Platforms)

| Option | Short | Type | Default | Description |
|--------|-------|------|---------|-------------|
| `--name` | - | string | `None` | Deployment name. If not provided, auto-generated |
| `--entrypoint` | `-e` | string | `None` | Entrypoint file name for directory sources (e.g., 'app.py', 'main.py') |
| `--env` | `-E` | string (multiple) | - | Environment variable in `KEY=VALUE` format. Can be repeated multiple times |
| `--env-file` | - | path | `None` | Path to `.env` file with environment variables |
| `--config` | `-c` | path | `None` | Path to deployment config file (`.json`, `.yaml`, or `.yml`) |

#### 4.1. ModelStudio Deployment

Deploy to Alibaba Cloud ModelStudio.

##### Command Syntax

```bash
agentscope deploy modelstudio SOURCE [OPTIONS]
```

##### Platform-Specific Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--skip-upload` | flag | `False` | Build package without uploading to ModelStudio |

##### Prerequisites

- Alibaba Cloud account
- ModelStudio access configured
- Environment variables: `DASHSCOPE_API_KEY` (or other required credentials)

##### Examples

```bash
# Basic deployment
export USE_LOCAL_RUNTIME=True
agentscope deploy modelstudio app_agent.py --name my-agent --env DASHSCOPE_API_KEY=sk-xxx

# Build without uploading
agentscope deploy modelstudio app_agent.py --skip-upload
```

**Note:** `USE_LOCAL_RUNTIME=True` uses local agentscope runtime instead of PyPI version.

##### Querying Deployed Agent

**Using curl:**

```bash
curl -i -X POST "http://127.0.0.1:8080/process" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "input": [
      {
        "role": "user",
        "content": [
          {
            "type": "text",
            "text": "Hello, how are you?"
          }
        ]
      }
    ],
    "session_id": "123"
  }'
```

**Using chat cli :**

```bash
agentscope chat [DEPLOYMENT_ID] --query "Hello"
```

#### 4.2. AgentRun Deployment

Deploy to Alibaba Cloud AgentRun.

##### Command Syntax

```bash
agentscope deploy agentrun SOURCE [OPTIONS]
```

##### Platform-Specific Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--region` | string | `"cn-hangzhou"` | Alibaba Cloud region |
| `--cpu` | float | `2.0` | CPU allocation in cores |
| `--memory` | integer | `2048` | Memory allocation in MB |
| `--skip-upload` | flag | `False` | Build package without uploading |

##### Prerequisites

- Alibaba Cloud account
- Required environment variables:
  - `ALIBABA_CLOUD_ACCESS_KEY_ID`
  - `ALIBABA_CLOUD_ACCESS_KEY_SECRET`

##### Examples

```bash
# Basic deployment
agentscope deploy agentrun app_agent.py --name my-agent

# Custom region and resources
agentscope deploy agentrun app_agent.py \
  --region cn-beijing \
  --cpu 4.0 \
  --memory 4096 \
  --env DASHSCOPE_API_KEY=sk-xxx
```

#### 4.3. Kubernetes Deployment

Deploy to Kubernetes/ACK cluster.

##### Command Syntax

```bash
agentscope deploy k8s SOURCE [OPTIONS]
```

##### Platform-Specific Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--namespace` | string | `"agentscope-runtime"` | Kubernetes namespace |
| `--kube-config-path` | `-c` | path | `None` | Path to kubeconfig file |
| `--replicas` | integer | `1` | Number of pod replicas |
| `--port` | integer | `8080` | Container port |
| `--image-name` | string | `"agent_app"` | Docker image name |
| `--image-tag` | string | `"linux-amd64"` | Docker image tag |
| `--registry-url` | string | `"localhost"` | Remote registry URL |
| `--registry-namespace` | string | `"agentscope-runtime"` | Remote registry namespace |
| `--push` | flag | `False` | Push image to registry |
| `--base-image` | string | `"python:3.10-slim-bookworm"` | Base Docker image |
| `--requirements` | string | `None` | Python requirements (comma-separated or file path) |
| `--cpu-request` | string | `"200m"` | CPU resource request (e.g., '200m', '1') |
| `--cpu-limit` | string | `"1000m"` | CPU resource limit (e.g., '1000m', '2') |
| `--memory-request` | string | `"512Mi"` | Memory resource request (e.g., '512Mi', '1Gi') |
| `--memory-limit` | string | `"2Gi"` | Memory resource limit (e.g., '2Gi', '4Gi') |
| `--image-pull-policy` | choice | `"IfNotPresent"` | Image pull policy: `Always`, `IfNotPresent`, `Never` |
| `--deploy-timeout` | integer | `300` | Deployment timeout in seconds |
| `--health-check` | flag | `None` | Enable/disable health check |
| `--platform` | string | `"linux/amd64"` | Target platform (e.g., 'linux/amd64', 'linux/arm64') |
| `--pypi-mirror` | string | `None` | PyPI mirror URL for pip package installation (e.g., 'https://pypi.tuna.tsinghua.edu.cn/simple'). If not specified, uses pip default |

##### Prerequisites

- Kubernetes cluster access
- Docker installed (for building images)
- `kubectl` configured

##### Examples

```bash
# Basic deployment
export USE_LOCAL_RUNTIME=True
agentscope deploy k8s app_agent.py \
  --image-name agent_app \
  --env DASHSCOPE_API_KEY=sk-xxx \
  --image-tag linux-amd64-4 \
  --registry-url your-registry.com \
  --push

# Custom namespace and resources
agentscope deploy k8s app_agent.py \
  --namespace production \
  --replicas 3 \
  --cpu-limit 2 \
  --memory-limit 4Gi \
  --env DASHSCOPE_API_KEY=sk-xxx
```

**Note:** `USE_LOCAL_RUNTIME=True` uses local agentscope runtime instead of PyPI version.

#### 4.4. Knative Deployment

Deploy to Knative/ACK Knative cluster.

##### Command Syntax

```bash
agentscope deploy knative SOURCE [OPTIONS]
```

##### Platform-Specific Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--namespace` | string | `"agentscope-runtime"` | Kubernetes namespace |
| `--kube-config-path` | `-c` | path | `None` | Path to kubeconfig file |
| `--port` | integer | `8080` | Container port |
| `--image-name` | string | `"agent_app"` | Docker image name |
| `--image-tag` | string | `"linux-amd64"` | Docker image tag |
| `--registry-url` | string | `"localhost"` | Remote registry URL |
| `--registry-namespace` | string | `"agentscope-runtime"` | Remote registry namespace |
| `--push` | flag | `False` | Push image to registry |
| `--base-image` | string | `"python:3.10-slim-bookworm"` | Base Docker image |
| `--requirements` | string | `None` | Python requirements (comma-separated or file path) |
| `--cpu-request` | string | `"200m"` | CPU resource request (e.g., '200m', '1') |
| `--cpu-limit` | string | `"1000m"` | CPU resource limit (e.g., '1000m', '2') |
| `--memory-request` | string | `"512Mi"` | Memory resource request (e.g., '512Mi', '1Gi') |
| `--memory-limit` | string | `"2Gi"` | Memory resource limit (e.g., '2Gi', '4Gi') |
| `--image-pull-policy` | choice | `"IfNotPresent"` | Image pull policy: `Always`, `IfNotPresent`, `Never` |
| `--deploy-timeout` | integer | `300` | Deployment timeout in seconds |
| `--health-check` | flag | `None` | Enable/disable health check |
| `--platform` | string | `"linux/amd64"` | Target platform (e.g., 'linux/amd64', 'linux/arm64') |
| `--pypi-mirror` | string | `None` | PyPI mirror URL for pip package installation (e.g., 'https://pypi.tuna.tsinghua.edu.cn/simple'). If not specified, uses pip default |

##### Prerequisites

- Kubernetes cluster access
- Docker installed (for building images)
- `kubectl` configured
- Knative installed

##### Examples

```bash
# Basic deployment
export USE_LOCAL_RUNTIME=True
agentscope deploy knative app_agent.py \
  --image-name agent_app \
  --env DASHSCOPE_API_KEY=sk-xxx \
  --image-tag linux-amd64-4 \
  --registry-url your-registry.com \
  --push

# Custom namespace and resources
agentscope deploy knative app_agent.py \
  --namespace production \
  --cpu-limit 2 \
  --memory-limit 4Gi \
  --env DASHSCOPE_API_KEY=sk-xxx
```

**Note:** `USE_LOCAL_RUNTIME=True` uses local agentscope runtime instead of PyPI version.

### 5. Deployment Management

#### 5.1. List Deployments

List all deployments and their status.

##### Command Syntax

```bash
agentscope list [OPTIONS]
```

##### Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--status` | string | `None` | Filter by status (e.g., 'running', 'stopped') |
| `--platform` | string | `None` | Filter by platform (e.g., 'local', 'k8s', 'modelstudio') |
| `--format` | choice | `"table"` | Output format: `table` or `json` |

##### Examples

```bash
# List all deployments
agentscope list

# Filter by status
agentscope list --status running

# Filter by platform
agentscope list --platform k8s

# JSON output
agentscope list --format json
```

#### 5.2. Check Deployment Status

Show detailed information about a specific deployment.

##### Command Syntax

```bash
agentscope status DEPLOY_ID [OPTIONS]
```

##### Arguments

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `DEPLOY_ID` | string | Yes | Deployment ID (e.g., `local_20250101_120000_abc123`) |

##### Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--format` | choice | `"table"` | Output format: `table` or `json` |

##### Examples

```bash
# Show detailed deployment info
agentscope status local_20250101_120000_abc123

# JSON format
agentscope status local_20250101_120000_abc123 --format json
```

#### 5.3. Stop Deployment

Stop a running deployment.

##### Command Syntax

```bash
agentscope stop DEPLOY_ID [OPTIONS]
```

##### Arguments

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `DEPLOY_ID` | string | Yes | Deployment ID |

##### Options

| Option | Short | Type | Default | Description |
|--------|-------|------|---------|-------------|
| `--yes` | `-y` | flag | `False` | Skip confirmation prompt |

##### Examples

```bash
# Stop with confirmation prompt
agentscope stop local_20250101_120000_abc123

# Skip confirmation
agentscope stop local_20250101_120000_abc123 --yes
```

**Note:** Currently updates local state only. Platform-specific cleanup may be needed separately.

#### 5.4. Invoke Deployed Agent

Interact with a deployed agent using CLI.

##### Command Syntax

```bash
agentscope invoke DEPLOY_ID [OPTIONS]
```

##### Arguments

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `DEPLOY_ID` | string | Yes | Deployment ID |

##### Options

| Option | Short | Type | Default | Description |
|--------|-------|------|---------|-------------|
| `--query` | `-q` | string | `None` | Single query to execute (non-interactive mode) |
| `--session-id` | - | string | `None` | Session ID for conversation continuity |
| `--user-id` | - | string | `"default_user"` | User ID for the session |

##### Examples

```bash
# Interactive mode with deployed agent
agentscope invoke local_20250101_120000_abc123

# Single query
agentscope invoke local_20250101_120000_abc123 --query "Hello"
```

### 6. Sandbox Management: `agentscope sandbox`

Consolidated sandbox commands under unified CLI.

#### Commands

```bash
# Start MCP server
agentscope sandbox mcp

# Start sandbox manager server
agentscope sandbox server

# Build sandbox environments
agentscope sandbox build
```

**Legacy Commands:** The old `runtime-sandbox-*` commands still work but are recommended to migrate to `agentscope sandbox *`.

## API Reference

This section provides reference information for programmatic access to deployed agents.

### HTTP API (Deployed Agents)

When you deploy an agent, it exposes an HTTP API endpoint that you can call programmatically.

#### Endpoint

```
POST /process
```

#### Base URL

The base URL depends on your deployment:
- **Local deployment**: `http://127.0.0.1:8080` (or your custom host:port)
- **Kubernetes deployment**: Your service URL
- **ModelStudio/AgentRun**: Platform-provided endpoint

#### Headers

| Header | Type | Required | Description |
|--------|------|----------|-------------|
| `Content-Type` | string | Yes | Must be `application/json` |
| `Authorization` | string | Yes | Bearer token: `Bearer YOUR_TOKEN` |

#### Request Body

```json
{
  "input": [
    {
      "role": "user",
      "content": [
        {
          "type": "text",
          "text": "Your message here"
        }
      ]
    }
  ],
  "session_id": "string"
}
```

**Fields:**
- `input`: Array of message objects with `role` and `content` fields
- `session_id`: Session identifier for conversation continuity

#### Response

Streaming response with agent output. The response format depends on your agent implementation.

#### Example: Python Client

```python
import requests

url = "http://127.0.0.1:8080/process"
headers = {
    "Content-Type": "application/json",
    "Authorization": "Bearer YOUR_TOKEN"
}
data = {
    "input": [
        {
            "role": "user",
            "content": [{"type": "text", "text": "Hello!"}]
        }
    ],
    "session_id": "my-session-123"
}

response = requests.post(url, json=data, headers=headers, stream=True)
for line in response.iter_lines():
    if line:
        print(line.decode('utf-8'))
```

## File System and Workspace

### Workspace Directory: `.agentscope_runtime`

During deployment, the deployer creates temporary files and build artifacts in your
workspace directory under `.agentscope_runtime/`. This directory is created automatically
in your current working directory.

#### Directory Structure

```
<workspace>/
└── .agentscope_runtime/
    ├── builds/                          # Build artifacts cache
    │   ├── k8s_20251205_1430_a3f9e2/   # Kubernetes build
    │   │   ├── deployment.zip
    │   │   ├── Dockerfile
    │   │   ├── requirements.txt
    │   │   └── ...
    │   ├── modelstudio_20251205_1445_b7c4d1/  # ModelStudio build
    │   │   └── *.whl
    │   └── local_20251205_1500_abc123/  # Local deployment bundle
    │       └── ...
    └── deployments.json                 # Workspace-level deployment metadata
```

#### Build Artifacts

Build artifacts are stored in `builds/` with platform-specific subdirectories:
- **Format**: `{platform}_{YYYYMMDD_HHMM}_{hash}/`
- **Contents**: Deployment packages, Dockerfiles, requirements files, etc.
- **Purpose**: Cached for reuse when code hasn't changed

#### Managing Build Artifacts

You can safely:
- **View**: Inspect build artifacts to understand what's being deployed
- **Test**: Use artifacts for debugging deployment issues
- **Delete**: Remove old builds to free up disk space
- **Ignore**: Add `.agentscope_runtime/` to `.gitignore` (it's not meant to be committed)

**Example: Clean up old builds**

   ```bash
# List build directories
ls -la .agentscope_runtime/builds/

# Remove specific build
rm -rf .agentscope_runtime/builds/k8s_20251205_1430_a3f9e2

# Remove all builds (keeps directory structure)
rm -rf .agentscope_runtime/builds/*
   ```

**Note:** The CLI uses content-aware caching, so deleting builds will cause them to be regenerated on next deployment if needed.

### Global State Directory: `~/.agentscope-runtime`

Deployment metadata and state are stored in your home directory:

```
~/.agentscope-runtime/
├── deployments.json              # Global deployment registry
└── deployments.backup.YYYYMMDD.json  # Daily backups (keeps last 30 days)
```

**Features:**
- Atomic file writes
- Automatic backups before modifications
- Schema validation and migration
- Corruption recovery

You can manually edit `deployments.json` or share it with team members for deployment state synchronization.

## Common Workflows

### Development Workflow

```bash
# 1. Develop your agent locally
agentscope chat app_agent.py

# 2. Test with web UI
agentscope web app_agent.py

# 3. Deploy when ready
agentscope deploy local app_agent.py --env DASHSCOPE_API_KEY=sk-xxx

# 4. Check deployment status
agentscope list
agentscope status <deployment-id>

# 5. Test deployed agent
agentscope invoke <deployment-id> --query "test query"

# 6. Stop when done
agentscope stop <deployment-id>
```

### Testing Workflow

```bash
# Quick test with single query
agentscope chat app_agent.py --query "test query"

# Interactive testing with conversation history
agentscope chat app_agent.py --session-id test-session

# Test with web UI
agentscope web app_agent.py --port 8080
```

### Production Deployment Workflow

```bash
# 1. Deploy to Kubernetes
agentscope deploy k8s app_agent.py \
  --image-name my-agent \
  --registry-url registry.example.com \
  --push \
  --replicas 3 \
  --env DASHSCOPE_API_KEY=sk-xxx

# 2. Monitor deployments
agentscope list --platform k8s

# 3. Check specific deployment
agentscope status <deployment-id>

# 4. Scale or update as needed
# (Re-run deploy command with updated parameters)

# 5. Stop when no longer needed
agentscope stop <deployment-id>
```

## Troubleshooting

### Agent Loading Fails

**Error:** "No AgentApp found in agent.py"

**Solution:** Ensure your file exports `agent_app` or `app` variable, or `create_app()` function.

### Multiple AgentApp Instances

**Error:** "Multiple AgentApp instances found"

**Solution:** Export only one AgentApp instance. Comment out or remove extras.

### Import Errors

**Error:** Module import failures

**Solution:** Ensure all dependencies are installed and the agent file is valid Python.

### Port Already in Use

**Error:** "Address already in use"

**Solution:** Use a different port with `--port` flag or stop the conflicting process.

### Deployment Fails

**Error:** Deployment timeout or connection errors

**Solution:**
- Check network connectivity
- Verify credentials and environment variables
- Check platform-specific requirements (Docker, Kubernetes, etc.)
- Review deployment logs: `agentscope status <deployment-id>`

### Session Not Persisting

**Error:** Session history not maintained between queries

**Solution:** Ensure you're using the same `--session-id` for related queries, or let the CLI generate one automatically.

## Advanced Usage

### Session Management

```bash
# Continue previous session
agentscope chat app_agent.py --session-id my-session

# Multiple users, same agent
agentscope chat app_agent.py --user-id alice --session-id session1
agentscope chat app_agent.py --user-id bob --session-id session2
```

### Output Formats

```bash
# Human-readable table (default)
agentscope list

# JSON for scripting
agentscope list --format json | jq '.[] | .id'
```

### Environment Variables

You can provide environment variables in multiple ways:

```bash
# Via CLI (highest priority)
agentscope deploy local app_agent.py --env KEY1=value1 --env KEY2=value2

# Via env file
agentscope deploy local app_agent.py --env-file .env

# Via config file
agentscope deploy local app_agent.py --config deploy-config.yaml
```

Priority order: CLI > env-file > config file

### Configuration Files

You can use JSON or YAML configuration files:

**deploy-config.yaml:**
```yaml
name: my-agent
host: 0.0.0.0
port: 8080
environment:
  DASHSCOPE_API_KEY: sk-xxx
  OTHER_VAR: value
```

**deploy-config.json:**
```json
{
  "name": "my-agent",
  "host": "0.0.0.0",
  "port": 8080,
  "environment": {
    "DASHSCOPE_API_KEY": "sk-xxx",
    "OTHER_VAR": "value"
  }
}
```

## Next Steps

- See [examples/](../../examples/) for complete agent implementations
- Check [API documentation](../api/) for programmatic usage
- Join community on Discord/DingTalk for support

## Feedback

Found a bug or have a feature request? Please open an issue on GitHub.
