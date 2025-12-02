# AgentScope Runtime CLI (`as-runtime`)

The unified command-line interface for managing your agent development, deployment, and runtime operations.

## Quick Start

### Installation

```bash
pip install agentscope-runtime
```

### Verify Installation

```bash
as-runtime --version
as-runtime --help
```

## Core Commands

### 1. Development: `as-runtime run`

Run your agent interactively or execute single queries for testing during development.

**Interactive Mode:**
```bash
# Start interactive session
as-runtime run agent.py

# Load from project directory
as-runtime run ./my-agent-project

# Use existing deployment
as-runtime run local_20250101_120000_abc123
```

**Single Query Mode:**
```bash
# Execute one query and exit
as-runtime run agent.py --query "What is the weather today?"

# With custom session
as-runtime run agent.py --query "Hello" --session-id my-session --user-id user123
```

**Agent File Requirements:**

Your agent file must export one of:
- Variable named `agent_app` or `app` of type `AgentApp`
- Function named `create_app()` or `create_agent_app()` returning `AgentApp`

Example `agent.py`:
```python
from agentscope_runtime.engine.app import AgentApp

agent_app = AgentApp(
    app_name="MyAgent",
    app_description="A helpful assistant",
)

@agent_app.query(framework="agentscope")
async def query_func(self, msgs, request=None, **kwargs):
    # Your agent logic here
    yield {"content": "Hello!"}, True
```

### 2. Web UI: `as-runtime web`

Launch your agent with a browser-based web interface for testing.

```bash
# Default host and port (127.0.0.1:8090)
as-runtime web agent.py

# Custom host and port
as-runtime web agent.py --host 0.0.0.0 --port 8000

# From project directory
as-runtime web ./my-agent-project
```

**Note:** First launch may take longer as web UI dependencies are installed via npm.

### 3. Deployment Management

#### List Deployments

```bash
# List all deployments
as-runtime list

# Filter by status
as-runtime list --status running

# Filter by platform
as-runtime list --platform k8s

# JSON output
as-runtime list --format json
```

#### Check Deployment Status

```bash
# Show detailed deployment info
as-runtime status local_20250101_120000_abc123

# JSON format
as-runtime status local_20250101_120000_abc123 --format json
```

#### Stop Deployment

```bash
# Stop with confirmation prompt
as-runtime stop local_20250101_120000_abc123

# Skip confirmation
as-runtime stop local_20250101_120000_abc123 --yes
```

**Note:** Currently updates local state only. Platform-specific cleanup may be needed separately.

#### Invoke Deployed Agent

```bash
# Interactive mode with deployed agent
as-runtime invoke local_20250101_120000_abc123

# Single query
as-runtime invoke local_20250101_120000_abc123 --query "Hello"
```

### 4. Deployment: `as-runtime deploy`

Deploy agents to various platforms (coming in future releases).

```bash
# Deploy to ModelStudio (planned)
as-runtime deploy modelstudio agent.py --name my-agent

# Deploy to AgentRun (planned)
as-runtime deploy agentrun agent.py

# Deploy to Kubernetes (planned)
as-runtime deploy k8s agent.py --namespace production

# Local detached deployment (planned)
as-runtime deploy local agent.py --port 8090
```

### 5. Sandbox Management: `as-runtime sandbox`

Consolidated sandbox commands under unified CLI.

```bash
# Start MCP server
as-runtime sandbox mcp

# Start sandbox manager server
as-runtime sandbox server

# Build sandbox environments
as-runtime sandbox build
```

**Legacy Commands:** The old `runtime-sandbox-*` commands still work but are recommended to migrate to `as-runtime sandbox *`.

## Agent Loading

The CLI supports three ways to specify agents:

1. **Python File:** Direct path to `.py` file
   ```bash
   as-runtime run /path/to/agent.py
   ```

2. **Project Directory:** Directory containing `app.py`, `agent.py`, or `main.py`
   ```bash
   as-runtime run ./my-agent-project
   ```

3. **Deployment ID:** Use previously deployed agent
   ```bash
   as-runtime run local_20250101_120000_abc123
   ```

## State Management

Deployment metadata is stored in `~/.as-runtime/deployments.json` with automatic:
- Atomic file writes
- Backup before modifications (keeps last 5)
- Schema validation and migration
- Corruption recovery

You can manually edit this file or share it with team members.

## Common Workflows

### Development Workflow

```bash
# 1. Develop your agent locally
as-runtime run agent.py

# 2. Test with web UI
as-runtime web agent.py

# 3. Deploy when ready (future)
as-runtime deploy k8s agent.py

# 4. Check deployment status
as-runtime list
as-runtime status <deployment-id>
```

### Testing Workflow

```bash
# Quick test with single query
as-runtime run agent.py --query "test query"

# Interactive testing with conversation history
as-runtime run agent.py --session-id test-session

# Test with web UI
as-runtime web agent.py --port 8080
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

## Advanced Usage

### Session Management

```bash
# Continue previous session
as-runtime run agent.py --session-id my-session

# Multiple users, same agent
as-runtime run agent.py --user-id alice --session-id session1
as-runtime run agent.py --user-id bob --session-id session2
```

### Output Formats

```bash
# Human-readable table (default)
as-runtime list

# JSON for scripting
as-runtime list --format json | jq '.[] | .id'
```

## Next Steps

- See [examples/](../../examples/) for complete agent implementations
- Read [design.md](../../../openspec/changes/add-unified-cli-system/design.md) for architecture details
- Check [API documentation](../api/) for programmatic usage
- Join community on Discord/DingTalk for support

## Feedback

Found a bug or have a feature request? Please open an issue on GitHub.
