# AG-UI Protocol 示例

本示例展示如何使用 AgentScope Runtime 构建一个兼容 AG-UI 协议的 ReAct Agent 服务。该服务支持流式响应、工具调用、会话历史管理和状态持久化。

## 示例特性

- **AG-UI 协议支持**: 支持AG-UI protocol
- **ReAct Agent**: 使用 AgentScope 的 ReAct Agent 实现推理和行动循环
- **工具调用**: 集成了 `get_weather` 和 `execute_python_code` 两个示例工具
- **会话管理**: 支持多会话历史记录的管理和持久化
- **状态管理**: Agent 状态可以跨请求保存和恢复

## 准备工作

### 1. 安装依赖

确保已经安装了 agentscope-runtime 及相关依赖：

```bash
pip install --upgrade agentscope-runtime
```

### 2. 配置 DashScope API Key

本示例使用 DashScope 的 qwen-max 模型，需要配置 API Key：

```bash
export DASHSCOPE_API_KEY="your-api-key-here"
```

你也可以在 `agent.py` 中直接修改 API Key 或更换其他模型。

## 运行 Agent 服务

使用`agentscope`命令行启动服务

```bash
# 在当前目录下运行：
agentscope run .

# 或者在项目根目录下执行

agentscope run examples/ag-ui
```

服务将在 `http://localhost:8080` 启动，AG-UI 协议端点为 `/ag-ui`。

## 请求服务

使用 curl 发送 POST 请求，以下请求会触发工具调用

```bash
uuid=$(python -c "import uuid; print(uuid.uuid4(), end='')")

curl -X POST http://localhost:8080/ag-ui \
  --header "Content-Type: application/json" \
  --data '{
    "context": [],
    "messages": [
      {
        "content": "北京今天的天气如何？",
        "id": "'$uuid'",
        "role": "user"
      }
    ],
    "runId": "run_456",
    "threadId": "thread_123",
    "context": [],
    "tools": [],
    "forwardedProps": {},
    "state": null
  }'
```

### 请求参数说明

- **threadId**: 线程/会话 ID，用于标识不同的对话会话
- **runId**: 运行 ID，每次请求的唯一标识
- **messages**: 消息列表，包含用户输入和历史对话
- **state**: (可选) Agent 的状态数据，用于恢复 Agent 的状态
- **context**: 上下文信息
- **tools**: 工具列表
- **forwardedProps**: 转发的属性

### 响应格式

服务返回 Server-Sent Events (SSE) 格式的流式响应：

```plain
data: {"type": "RUN_STARTED", "threadId": "thread_123", "runId": "run_456"}

data: {"type": "TOOL_CALL_START", "toolCallId": "call_51529f037f2641ddba53cd", "toolCallName": "get_weather", "message_id": "msg_7fb52b7b-4037-4868-907e-125d18828992_0"}

data: {"type": "TOOL_CALL_ARGS", "toolCallId": "call_51529f037f2641ddba53cd", "delta": "{\"location\": \"北京\"}"}

data: {"type": "TOOL_CALL_END", "toolCallId": "call_51529f037f2641ddba53cd"}

data: {"type": "TOOL_CALL_RESULT", "messageId": "msg_012a1e31-af54-4bb1-99db-4ebe2020c89e_0", "toolCallId": "call_51529f037f2641ddba53cd", "content": "[{\"type\": \"text\", \"text\": \"The weather in 北京 is sunny with a temperature of 25°C.\"}]", "role": "tool"}

data: {"type": "TEXT_MESSAGE_START", "messageId": "msg_a6dec420-0631-473f-854c-e4c42cf283f0_0", "role": "assistant"}

data: {"type": "TEXT_MESSAGE_CONTENT", "messageId": "msg_a6dec420-0631-473f-854c-e4c42cf283f0_0", "delta": "北京"}

data: {"type": "TEXT_MESSAGE_CONTENT", "messageId": "msg_a6dec420-0631-473f-854c-e4c42cf283f0_0", "delta": "今天的天气是"}

data: {"type": "TEXT_MESSAGE_CONTENT", "messageId": "msg_a6dec420-0631-473f-854c-e4c42cf283f0_0", "delta": "晴朗，"}

data: {"type": "TEXT_MESSAGE_CONTENT", "messageId": "msg_a6dec420-0631-473f-854c-e4c42cf283f0_0", "delta": "气温为25°C。"}

data: {"type": "TEXT_MESSAGE_END", "messageId": "msg_a6dec420-0631-473f-854c-e4c42cf283f0_0"}

data: {"type": "RUN_FINISHED", "threadId": "thread_123", "runId": "run_456"}
```

### 事件类型说明

| 事件类型 | 说明 |
|---------|------|
| `RUN_STARTED` | 运行开始 |
| `TOOL_CALL_START` | 工具调用开始 |
| `TOOL_CALL_ARGS` | 工具调用参数（流式） |
| `TOOL_CALL_END` | 工具调用结束 |
| `TOOL_CALL_RESULT` | 工具调用结果 |
| `TEXT_MESSAGE_START` | 文本消息开始 |
| `TEXT_MESSAGE_CONTENT` | 文本消息内容（流式） |
| `TEXT_MESSAGE_END` | 文本消息结束 |
| `RUN_FINISHED` | 运行完成 |

## 常见问题

### 问题：无法连接到服务

- 确认服务已启动：检查终端输出
- 确认端口没有被占用：`lsof -i :8080`

### 问题：API Key 错误

- 检查环境变量 `DASHSCOPE_API_KEY` 是否正确设置
- 确认 DashScope API Key 有效且有足够的额度

### 添加自定义工具

在 `agent.py` 中定义新的工具函数并注册：

```python
async def your_custom_tool(param: str) -> ToolResponse:
    """Your tool description."""
    # 实现工具逻辑
    return ToolResponse(content=[TextBlock(type="text", text="result")])

# 在 create_stateful_agent 中注册
toolkit.register_tool_function(your_custom_tool)
```
