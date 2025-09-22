# Detached Local Deploy Example

This example demonstrates how to deploy an Agent as a detached process service using AgentScope Runtime.

## File Description

- `agent_run.py` - Agent definition using QwenLLM
- `quick_deploy.py` - Quick deployment script for simple testing

## Features of Detached Process Deployment

1. **Independent Execution**: Service runs in a separate process, main program can exit
2. **Process Management**: Supports process status queries and remote shutdown
3. **Configurable Services**: Supports InMemory and Redis service configurations
4. **Unified API**: Uses the same FastAPI architecture as other deployment modes

## Environment Setup

```bash
# Set API Key
export DASHSCOPE_API_KEY="your_qwen_api_key"

# Optional: Use Redis service
export USE_REDIS=true
export REDIS_HOST=localhost
export REDIS_PORT=6379
```

## Usage

### 1. Complete Example (Recommended)

```bash
python deploy_detached.py
```

This script provides complete deployment lifecycle management:
- Automatically deploy Agent to detached process
- Test service functionality
- Interactive management interface
- Graceful service shutdown

### 2. Quick Testing

```bash
python quick_deploy.py
```

For quick deployment testing, suitable for development and debugging.

## API Endpoints

After successful deployment, the service will provide the following endpoints:

### Basic Endpoints
- `GET /` - Service information
- `GET /health` - Health check
- `POST /process` - Standard conversation interface
- `POST /process/stream` - Streaming conversation interface

### Detached Process Management Endpoints
- `GET /admin/status` - Process status information
- `POST /admin/shutdown` - Remote service shutdown

## Test Commands

### Health Check
```bash
curl http://127.0.0.1:8080/health
```

### Streaming Request
```bash
curl -X POST http://127.0.0.1:8080/process \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  --no-buffer \
  -d '{
    "input": [
      {
        "role": "user",
        "content": [
          {
            "type": "text",
            "text": "Tell me about Hangzhou city"
          }
        ]
      }
    ]
  }'
```

### Process Management
```bash
# Check process status
curl http://127.0.0.1:8080/admin/status

# Stop service
curl -X POST http://127.0.0.1:8080/admin/shutdown
```

## Configuration Options

### Service Configuration
You can configure different service providers through environment variables:

```bash
# Use Redis
export MEMORY_PROVIDER=redis
export SESSION_HISTORY_PROVIDER=redis
export REDIS_HOST=localhost
export REDIS_PORT=6379

# Use configuration file
export AGENTSCOPE_SERVICES_CONFIG=/path/to/services_config.json
```

### Service Configuration File Example
```json
{
  "memory": {
    "provider": "redis",
    "config": {
      "host": "localhost",
      "port": 6379,
      "db": 0
    }
  },
  "session_history": {
    "provider": "redis",
    "config": {
      "host": "localhost",
      "port": 6379,
      "db": 1
    }
  }
}
```

## Important Notes

1. **Process Management**: Detached processes need to be stopped manually or using management interface
2. **Monitoring**: Production environments should configure appropriate process monitoring and logging
3. **Security**: Management interfaces should have restricted access permissions
4. **Resources**: Detached processes consume additional memory and CPU resources

## Troubleshooting

### Port Already in Use
```bash
# Check port usage
lsof -i :8080

# Or change port
python deploy_detached.py  # Modify port parameter in script
```

### Process Cleanup
If service exits abnormally, manual cleanup may be needed:
```bash
# Find process
ps aux | grep "agentscope"

# Terminate process
kill -TERM <pid>
```

### Log Viewing
Log output in detached process mode is redirected, you can view it through:
- Check `/tmp/agentscope_runtime_*.log` (if log files exist)
- Use process status interface to check running status
- Check system logs