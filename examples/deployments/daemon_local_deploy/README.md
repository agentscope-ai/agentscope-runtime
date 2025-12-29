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

### Agent Configuration
User could define their own `init`, `shutdown` and `process` method to call an agent or workflow during runtime.
Then deploy the runtime to any platform.
The following example show a suggested method define an agent in runtime.

```python
agent_app = AgentApp(
    app_name="Friday",
    app_description="A helpful assistant",
)


@agent_app.init
async def init_func(self):
    self.state_service = InMemoryStateService()
    self.session_service = InMemorySessionHistoryService()

    await self.state_service.start()
    await self.session_service.start()


@agent_app.shutdown
async def shutdown_func(self):
    await self.state_service.stop()
    await self.session_service.stop()


@agent_app.query(framework="agentscope")
async def query_func(
    self,
    msgs,
    request: AgentRequest = None,
):
    session_id = request.session_id
    user_id = request.user_id

    state = await self.state_service.export_state(
        session_id=session_id,
        user_id=user_id,
    )

    toolkit = Toolkit()
    toolkit.register_tool_function(execute_python_code)

    agent = ReActAgent(
        name="Friday",
        model=DashScopeChatModel(
            "qwen-turbo",
            api_key=os.getenv("DASHSCOPE_API_KEY"),
            enable_thinking=True,
            stream=True,
        ),
        sys_prompt="You're a helpful assistant named Friday.",
        toolkit=toolkit,
        memory=AgentScopeSessionHistoryMemory(
            service=self.session_service,
            session_id=session_id,
            user_id=user_id,
        ),
        formatter=DashScopeChatFormatter(),
    )

    if state:
        agent.load_state_dict(state)

    async for msg, last in stream_printing_messages(
        agents=[agent],
        coroutine_task=agent(msgs),
    ):
        yield msg, last

    state = agent.state_dict()

    await self.state_service.save_state(
        user_id=user_id,
        session_id=session_id,
        state=state,
    )

```

Then we could run the runtime by:

```python
agent_app.run(host="0.0.0.0", port=8080)
```

or deploy runtime by

```python

async def main():
    await agent_app.deploy(deploy_manager)


if __name__ == "__main__":
    asyncio.run(main())
    input("Press Enter to stop the server...")
```

both function will start an app that provide responses api, or agentic api service.
The difference is the deploy_manger could be different manager such as `k8s`, `modelstudio`, `detached process`.


## Important Notes

1. **Blocking Process**: Daemon deployment runs in the main process and blocks until stopped
2. **Manual Management**: Service must be stopped manually with Ctrl+C or by terminating the process
3. **Development Use**: Best suited for development and testing environments
4. **No Background Execution**: Unlike detached process mode, the script must remain running

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

This example provides a straightforward way to deploy AgentScope Runtime agents as daemon services for development and testing purposes.

