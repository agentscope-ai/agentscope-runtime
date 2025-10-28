# AgentBay Integration with AgentScope Runtime

This document demonstrates how to use the AgentBay cloud sandbox integration with AgentScope Runtime.

## Overview

AgentBay is now integrated as a new sandbox type (`SandboxType.AGENTBAY`) in AgentScope Runtime. This integration provides:

- **Cloud-native sandbox environment** - No local container dependencies
- **Multiple image types** - Linux, Windows, Browser, CodeSpace, Mobile
- **Unified API** - Compatible with existing sandbox service interface
- **Direct cloud communication** - Uses AgentBay SDK for API calls

## Prerequisites

1. **Install AgentBay SDK**:

   ```bash
   pip install agentbay
   ```

2. **Set up API Key**:
   ```bash
   export AGENTBAY_API_KEY="your_agentbay_api_key"
   ```

## Usage Examples

### 1. Direct AgentBay Sandbox Usage

```python
import os
from agentscope_runtime.sandbox.box.agentbay.agentbay_sandbox import AgentbaySandbox

# Create AgentBay sandbox
sandbox = AgentbaySandbox(
    api_key=os.getenv("AGENTBAY_API_KEY"),
    image_id="linux_latest"  # or "windows_latest", "browser_latest", etc.
)

# Execute shell commands
result = sandbox.call_tool("run_shell_command", {"command": "echo 'Hello World'"})
print(result["output"])

# File operations
sandbox.call_tool("write_file", {
    "path": "/tmp/test.txt",
    "content": "Hello from AgentBay!"
})

content = sandbox.call_tool("read_file", {"path": "/tmp/test.txt"})
print(content["content"])

# Cleanup
sandbox._cleanup()
```

### 2. Using AgentBay through Sandbox Service

```python
import asyncio
from agentscope_runtime.sandbox.enums import SandboxType
from agentscope_runtime.engine.services.sandbox_service import SandboxService
from agentscope_runtime.engine.services.environment_manager import create_environment_manager

async def main():
    # Create sandbox service with AgentBay API key
    sandbox_service = SandboxService(bearer_token=os.getenv("AGENTBAY_API_KEY"))

    async with create_environment_manager(sandbox_service=sandbox_service) as manager:
        # Connect to AgentBay sandbox
        sandboxes = manager.connect_sandbox(
            session_id="my_session",
            user_id="my_user",
            env_types=[SandboxType.AGENTBAY.value]
        )

        sandbox = sandboxes[0]

        # Use sandbox
        result = sandbox.call_tool("run_shell_command", {"command": "python --version"})
        print(result)

        # Release resources
        manager.release_sandbox("my_session", "my_user")

asyncio.run(main())
```

### 3. Different Image Types

```python
# Linux environment (default)
sandbox = AgentbaySandbox(image_id="linux_latest")

# Windows environment
sandbox = AgentbaySandbox(image_id="windows_latest")

# Browser environment
sandbox = AgentbaySandbox(image_id="browser_latest")

# CodeSpace environment
sandbox = AgentbaySandbox(image_id="code_latest")

# Mobile environment
sandbox = AgentbaySandbox(image_id="mobile_latest")
```

### 4. Browser Automation Example

```python
# Create browser environment
sandbox = AgentbaySandbox(image_id="browser_latest")

# Initialize browser
sandbox.call_tool("browser_navigate", {"url": "https://www.example.com"})

# Take screenshot
result = sandbox.call_tool("screenshot", {})
print(f"Screenshot URL: {result['screenshot_url']}")

# Click element
sandbox.call_tool("browser_click", {"selector": "button#submit"})

# Input text
sandbox.call_tool("browser_input", {
    "selector": "input[name='email']",
    "text": "user@example.com"
})
```

### 5. Session Management

```python
# Get session information
session_info = sandbox.get_session_info()
print(f"Session ID: {session_info['session_id']}")
print(f"Resource URL: {session_info['resource_url']}")

# List all sessions
sessions = sandbox.list_sessions()
print(f"Total sessions: {sessions['total_count']}")

# List sessions with specific labels
sessions = sandbox.list_sessions(labels={"project": "demo"})
```

## Available Tools

The AgentBay sandbox supports the following tools:

### Basic Operations

- `run_shell_command` - Execute shell commands
- `run_ipython_cell` - Execute Python code
- `screenshot` - Take screenshots

### File Operations

- `read_file` - Read file contents
- `write_file` - Write file contents
- `list_directory` - List directory contents
- `create_directory` - Create directories
- `move_file` - Move/rename files
- `delete_file` - Delete files

### Browser Operations (browser_latest image)

- `browser_navigate` - Navigate to URL
- `browser_click` - Click elements
- `browser_input` - Input text

## Configuration

### Environment Variables

- `AGENTBAY_API_KEY` - Your AgentBay API key (required)

### Sandbox Parameters

- `api_key` - AgentBay API key
- `image_id` - Environment type (linux_latest, windows_latest, etc.)
- `labels` - Session labels for organization
- `timeout` - Operation timeout in seconds

## Error Handling

```python
try:
    sandbox = AgentbaySandbox(api_key="invalid_key")
except ValueError as e:
    print(f"Configuration error: {e}")

try:
    result = sandbox.call_tool("run_shell_command", {"command": "invalid_command"})
    if not result["success"]:
        print(f"Command failed: {result['error']}")
except Exception as e:
    print(f"Tool call error: {e}")
```

## Best Practices

1. **Always cleanup**: Call `sandbox._cleanup()` or use context managers
2. **Handle errors**: Check `result["success"]` for tool call results
3. **Use appropriate images**: Choose the right image type for your use case
4. **Set labels**: Use labels to organize sessions
5. **Monitor resources**: Be aware of session timeouts and costs

## Troubleshooting

### Common Issues

1. **API Key Not Set**:

   ```
   ValueError: AgentBay API key is required
   ```

   Solution: Set `AGENTBAY_API_KEY` environment variable

2. **AgentBay SDK Not Installed**:

   ```
   ImportError: AgentBay SDK is not installed
   ```

   Solution: `pip install agentbay`

3. **Session Creation Failed**:
   ```
   RuntimeError: Failed to create cloud session
   ```
   Solution: Check API key validity and network connectivity

### Debug Information

Enable debug logging to see detailed information:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Migration from Existing Sandboxes

If you're migrating from existing sandbox types to AgentBay:

1. **Change sandbox type**: Use `SandboxType.AGENTBAY` instead of other types
2. **Update initialization**: Pass `api_key` parameter
3. **Tool calls remain the same**: The `call_tool` interface is compatible
4. **No local containers**: AgentBay runs entirely in the cloud

## Support

For issues related to:

- **AgentBay SDK**: [GitHub Issues](https://github.com/aliyun/wuying-agentbay-sdk/issues)
- **AgentScope Runtime**: Check the main project documentation
- **Integration**: This integration follows AgentScope Runtime patterns
