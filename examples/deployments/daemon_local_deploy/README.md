# Daemon Local Deploy Example

This example demonstrates how to deploy an Agent as a local daemon service using AgentScope Runtime.

## File Description

- `app_deploy.py` - Main deployment script using AgentApp with full endpoint configuration

## Features of Daemon Deployment

1. **Persistent Service**: Service runs in the main process, blocking until manually stopped
2. **Interactive Control**: Direct process management with Ctrl+C to stop
3. **Simple Setup**: Minimal configuration required for quick deployment
4. **Development Friendly**: Easy debugging and direct resource sharing

## Environment Setup

```bash
# Set API Key
export DASHSCOPE_API_KEY="your_qwen_api_key"
```

## Usage

### 1. Complete Example with AgentApp (Recommended)

```bash
python app_deploy.py
```

This script provides complete deployment with multiple endpoints:
- Automatically creates and configures an AgentScopeAgent
- Defines multiple endpoints (sync, async, streaming, tasks)
- Deploys using LocalDeployManager
- Keeps service running until manually stopped
- Provides detailed usage examples

### 2. Simple Deployment with Runner

```bash
python local_deploy.py
```

For basic deployment using Runner directly, suitable for simple scenarios.

## API Endpoints

After successful deployment, the service will provide the following endpoints:

### Basic Endpoints
- `GET /` - Service information
- `GET /health` - Health check
- `POST /sync` - Synchronous conversation interface
- `POST /async` - Asynchronous conversation interface
- `POST /stream_async` - Streaming conversation interface (async)
- `POST /stream_sync` - Streaming conversation interface (sync)

### Task Endpoints (Celery)
- `POST /task` - Celery task endpoint (queue: celery1)
- `POST /atask` - Async Celery task endpoint

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

### Asynchronous Request
```bash
curl -X POST http://127.0.0.1:8080/async \
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

### Streaming Request (Async)
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

### Streaming Request (Sync)
```bash
curl -X POST http://127.0.0.1:8080/stream_sync \
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
            "text": "Tell me a story"
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

## Configuration Options

### Service Host and Port
You can customize the host and port in the deployment scripts:

```python
deploy_manager = LocalDeployManager(
    host="0.0.0.0",  # Listen on all interfaces
    port=8080,       # Custom port
)
```

### Celery Configuration
If you need to use Celery tasks, make sure Redis is running:

```bash
# Start Redis (required for Celery)
redis-server

# Or using Docker
docker run -d -p 6379:6379 redis:latest
```

Configure Celery in your AgentApp:

```python
app = AgentApp(
    agent=agent,
    broker_url="redis://localhost:6379/0",   # Redis database 0 for broker
    backend_url="redis://localhost:6379/1",  # Redis database 1 for backend
)
```

## Important Notes

1. **Blocking Process**: Daemon deployment runs in the main process and blocks until stopped
2. **Manual Management**: Service must be stopped manually with Ctrl+C or by terminating the process
3. **Development Use**: Best suited for development and testing environments
4. **No Background Execution**: Unlike detached process mode, the script must remain running

## Troubleshooting

### Port Already in Use
```bash
# Check port usage
lsof -i :8080

# Or change port in the script
# Modify the port parameter in LocalDeployManager
```

### Redis Connection Error
If Celery tasks fail, ensure Redis is running:
```bash
# Check Redis status
redis-cli ping

# Should return: PONG
```

### Process Termination
To stop the service:
- Press `Ctrl+C` in the terminal
- Or send SIGTERM: `kill -TERM <pid>`

## Comparison with Other Deployment Methods

| Feature | Daemon | Detached Process | Kubernetes | ModelStudio |
|---------|--------|------------------|------------|-------------|
| Process Control | Blocking | Independent | Container | Cloud-managed |
| Complexity | Simple | Medium | Complex | Medium |
| Scalability | Single | Single Node | Multi-node | Cloud-scale |
| Best For | Development | Production (single) | Enterprise | Cloud users |

## Files Structure

- `app_deploy.py`: Main deployment script using AgentApp with multiple endpoints
- `local_deploy.py`: Simple deployment using Runner

This example provides a straightforward way to deploy AgentScope Runtime agents as daemon services for development and testing purposes.

