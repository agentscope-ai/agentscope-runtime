# Detached Local Deploy Example

This example demonstrates how to deploy an Agent as a detached process service using AgentScope Runtime.

## File Description

- `app_deploy.py` - Main deployment script using AgentApp with full endpoint configuration

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

### Complete Example

```bash
python app_deploy.py
```

This script provides complete deployment lifecycle management:
- Automatically creates and configures an AgentScopeAgent
- Deploys Agent to detached process
- Configured with multiple endpoints (sync, async, streaming, tasks)
- Service continues running after script exits
- Provides remote management capabilities
- Detailed usage examples

## API Endpoints

After successful deployment, the service will provide the following endpoints:

### Basic Endpoints
- `GET /` - Service information
- `GET /health` - Health check
- `POST /sync` - Synchronous conversation interface
- `POST /async` - Asynchronous conversation interface
- `POST /stream_async` - Streaming conversation interface
- `POST /stream_sync` - Streaming conversation interface

### Task Endpoints (Celery)
- `POST /task` - Celery task endpoint (queue: celery1)
- `POST /atask` - Async Celery task endpoint

### Management Endpoints
- `POST /admin/shutdown` - Remote service shutdown

## Test Commands

### Health Check
```bash
curl http://127.0.0.1:8080/health
```

### Synchronous Request
```bash
curl -X POST http://127.0.0.1:8080/sync \
  -H "Content-Type: application/json" \
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

### Streaming Request
```bash
curl -X POST http://127.0.0.1:8080/stream_async \
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
    ],
    "session_id": "123"
  }'
```

### Celery Task Request
```bash
curl -X POST http://127.0.0.1:8080/task \
  -H "Content-Type: application/json" \
  -d '{
    "input": [
      {
        "role": "user",
        "content": [
          {
            "type": "text",
            "text": "Process this task"
          }
        ]
      }
    ],
    "session_id": "123"
  }'
```

### Service Management
```bash
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
python app_deploy.py  # Modify port parameter in script
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
- Use service endpoints to check running status
- Check system logs

## Key Differences from Daemon Mode

| Feature | Daemon Mode | Detached Process Mode |
|---------|-------------|----------------------|
| Process Execution | Blocking (main process) | Independent process |
| Script Behavior | Blocks until stopped | Exits after deployment |
| Service Lifecycle | Tied to script | Independent |
| Remote Management | Manual (Ctrl+C) | API-based shutdown |
| Use Case | Development/Testing | Production (single node) |

## Files Structure

- `app_deploy.py`: Main deployment script using AgentApp with complete endpoint configuration

This example provides a complete workflow for deploying AgentScope Runtime agents as detached processes with production-ready configurations.