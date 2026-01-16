---
jupytext:
  formats: md:myst
  text_representation:
    extension: .md
    format_name: myst
    format_version: 0.13
    jupytext_version: 1.11.5
kernelspec:
  display_name: Python 3
  language: python
  name: python3
---

# 参考: Agent API 协议规范

## 概述

本文档描述了与AI智能体通信的结构化JSON协议。该协议定义了支持以下功能的消息、请求和响应：

+ 流式内容传输
+ 工具/函数调用
+ 多模态内容（文本、图像、数据）
+ 全生命周期的状态跟踪
+ 错误处理

## 协议结构

### 1. 核心枚举

**角色**：

```{code-cell}
class Role:
    ASSISTANT = "assistant"
    USER = "user"
    SYSTEM = "system"
    TOOL = "tool"  # 新增：工具角色
```

**消息类型**：

```{code-cell}
class MessageType:
    MESSAGE = "message"
    FUNCTION_CALL = "function_call"
    FUNCTION_CALL_OUTPUT = "function_call_output"
    PLUGIN_CALL = "plugin_call"
    PLUGIN_CALL_OUTPUT = "plugin_call_output"
    COMPONENT_CALL = "component_call"
    COMPONENT_CALL_OUTPUT = "component_call_output"
    MCP_LIST_TOOLS = "mcp_list_tools"
    MCP_APPROVAL_REQUEST = "mcp_approval_request"
    MCP_TOOL_CALL = "mcp_call"
    MCP_APPROVAL_RESPONSE = "mcp_approval_response"
    MCP_TOOL_CALL_OUTPUT = "mcp_call_output"
    REASONING = "reasoning"
    HEARTBEAT = "heartbeat"
    ERROR = "error"

    @classmethod
    def all_values(cls):
        """返回MessageType中所有常量值"""
        return [
            value
            for name, value in vars(cls).items()
            if not name.startswith("_") and isinstance(value, str)
        ]
```

**运行状态**：

```{code-cell}
class RunStatus:
    Created = "created"
    InProgress = "in_progress"
    Completed = "completed"
    Canceled = "canceled"
    Failed = "failed"
    Rejected = "rejected"
    Unknown = "unknown"
    Queued = "queued"      # 新增：排队状态
    Incomplete = "incomplete"  # 新增：未完成状态
```

### 2. 工具定义

**函数参数**：

```{code-cell}
class FunctionParameters(BaseModel):
    type: str  # 必须为 "object"
    properties: Dict[str, Any]
    required: Optional[List[str]]
```

**函数工具**：

```{code-cell}
class FunctionTool(BaseModel):
    name: str
    description: str
    parameters: Union[Dict[str, Any], FunctionParameters]
```

**工具**：

```{code-cell}
class Tool(BaseModel):
    type: Optional[str] = None  # 目前仅支持 "function"
    function: Optional[FunctionTool] = None
```

**函数调用**：
```{code-cell}
class FunctionCall(BaseModel):
    """
    助手提示消息工具调用函数的模型类
    """

    call_id: Optional[str] = None
    """工具调用的ID"""

    name: Optional[str] = None
    """要调用的函数名称"""

    arguments: Optional[str] = None
    """调用函数的参数，由模型生成的JSON格式

    注意：模型生成的JSON不一定有效，可能产生未定义的参数。
    在调用函数前请验证参数有效性
    """
```

**函数调用输出**：
```{code-cell}
class FunctionCallOutput(BaseModel):
    """
    助手提示消息工具调用函数的模型类
    """

    call_id: str
    """工具调用的ID"""

    output: str
    """函数执行结果"""
```

### 3. 内容模型

**基础内容模型**：

```{code-cell}
class Content(Event):
    type: str
    """内容部分的类型"""

    object: str = "content"
    """内容部分的标识"""

    index: Optional[int] = None
    """在消息内容列表中的索引位置"""

    delta: Optional[bool] = False
    """是否为增量内容"""

    msg_id: str = None
    """消息唯一ID"""
```

**专用内容类型**：

```{code-cell}
class ImageContent(Content):
    type: str = ContentType.IMAGE
    """内容部分的类型"""

    image_url: Optional[str] = None
    """图片URL详情"""


class TextContent(Content):
    type: str = ContentType.TEXT
    """内容部分的类型"""

    text: Optional[str] = None
    """文本内容"""


class DataContent(Content):
    type: str = ContentType.DATA
    """内容部分的类型"""

    data: Optional[Dict] = None
    """数据内容"""


class AudioContent(Content):
    type: str = ContentType.AUDIO
    """内容部分的类型"""

    data: Optional[str] = None
    """音频数据详情"""

    format: Optional[str] = None
    """音频数据格式"""


class FileContent(Content):
    type: str = ContentType.FILE
    """内容部分的类型"""

    file_url: Optional[str] = None
    """文件URL详情"""

    file_id: Optional[str] = None
    """文件ID详情"""

    filename: Optional[str] = None
    """文件名详情"""

    file_data: Optional[str] = None
    """文件数据详情"""


class RefusalContent(Content):
    type: str = ContentType.REFUSAL
    """内容部分的类型"""

    refusal: Optional[str] = None
    """拒绝内容"""
```

### 4. 消息模型

```{code-cell}
class Message(Event):
    id: str = Field(default_factory=lambda: "msg_" + str(uuid4()))
    """消息唯一ID"""

    object: str = "message"
    """消息标识"""

    type: str = "message"
    """消息类型"""

    status: str = RunStatus.Created
    """消息状态：in_progress, completed 或 incomplete"""

    role: Optional[str] = None
    """消息作者角色，应为 `user`,`system`, 'assistant'"""

    content: Optional[
        List[Union[TextContent, ImageContent, DataContent]]
    ] = None
    """消息内容"""

    code: Optional[str] = None
    """消息错误代码"""

    message: Optional[str] = None
    """消息错误描述"""
```

**关键方法**：

+ `add_delta_content()`: 向现有消息追加部分内容
+ `content_completed()`: 标记内容片段为完成状态
+ `add_content()`: 添加完整的内容片段

### 5. 请求模型

**基础请求**：

```{code-cell}
class BaseRequest(BaseModel):
    input: List[Message]
    stream: bool = True
    id: Optional[str] = None
```

**智能体请求**：

```{code-cell}
class AgentRequest(BaseRequest):
    model: Optional[str] = None
    top_p: Optional[float] = None
    temperature: Optional[float] = None
    frequency_penalty: Optional[float] = None
    presence_penalty: Optional[float] = None
    max_tokens: Optional[int] = None
    stop: Optional[Union[Optional[str], List[str]]] = None
    n: Optional[int] = Field(default=1, ge=1, le=5)
    seed: Optional[int] = None
    tools: Optional[List[Union[Tool, Dict]]] = None
    session_id: Optional[str] = None
```

### 6. 响应模型

**基础响应**：

```{code-cell}
class BaseResponse(Event):
    sequence_number: str = None
    id: str = Field(default_factory=lambda: "response_" + str(uuid4()))
    object: str = "response"
    created_at: int = int(datetime.now().timestamp())
    completed_at: Optional[int] = None
    error: Optional[Error] = None
    output: Optional[List[Message]] = None
    usage: Optional[Dict] = None
```

**智能体响应**：

```{code-cell}
class AgentResponse(BaseResponse):
    session_id: Optional[str] = None
```

### 7. 错误模型

```{code-cell}
class Error(BaseModel):
    code: str
    message: str
```

## 协议流程

### 请求/响应生命周期

1. 客户端发送 `AgentRequest`，包含：
   - 输入消息
   - 生成参数
   - 工具定义
   - 会话上下文
2. 服务端响应 `AgentResponse` 对象流，包含：
   - 状态更新 (`created` → `in_progress` → `completed`)
   - 带内容片段的输出消息
   - 最终使用指标

### 内容流式传输

当请求中 `stream=True` 时：

+ 文本内容以 `delta=true` 片段增量发送
+ 每个片段包含指向目标内容槽的 `index`
+ 最终片段通过 `status=completed` 标记完成

**流式传输示例**：

```bash
{"status":"created","id":"response_...","object":"response"}
{"status":"created","id":"msg_...","object":"message","type":"assistant"}
{"status":"in_progress","type":"text","index":0,"delta":true,"text":"Hello","object":"content"}
{"status":"in_progress","type":"text","index":0,"delta":true,"text":", ","object":"content"}
{"status":"in_progress","type":"text","index":0,"delta":true,"text":"world","object":"content"}
{"status":"completed","type":"text","index":0,"delta":false,"text":"Hello, world!","object":"content"}
{"status":"completed","id":"msg_...","object":"message", ...}
{"status":"completed","id":"response_...","object":"response", ...}
```

### 状态转换

| 状态         | 描述                       |
| ------------- | -------------------------- |
| `created`     | 对象创建时的初始状态       |
| `in_progress` | 操作正在处理中             |
| `completed`   | 操作成功完成               |
| `failed`      | 操作因错误终止             |
| `rejected`    | 操作被系统拒绝             |
| `canceled`    | 操作被用户取消             |


## 最佳实践

1. **流处理**：
   - 缓冲增量片段直到收到 `status=completed`
   - 使用 `msg_id` 关联内容与父消息
   - 尊重多片段消息的 `index` 顺序
2. **错误处理**：
   - 检查响应中的 `error` 字段
   - 监控 `failed` 状态转换
   - 对可恢复错误实施重试逻辑
3. **状态管理**：
   - 使用 `session_id` 保持会话连续性
   - 跟踪 `created_at`/`completed_at` 监控延迟
   - 使用 `sequence_number` 排序（如已实现）

## 使用示例

**用户查询**：

```json
{
  "input": [{
    "role": "user",
    "content": [{"type": "text", "text": "描述这张图片"}],
    "type": "message"
  }],
  "stream": true,
  "model": "gpt-4-vision"
}
```

**智能体响应流**：

```bash
{"id":"response_123","object":"response","status":"created"}
{"id":"msg_abc","object":"message","type":"assistant","status":"created"}
{"status":"in_progress","type":"text","index":0,"delta":true,"text":"这张","object":"content","msg_id":"msg_abc"}
{"status":"in_progress","type":"text","index":0,"delta":true,"text":"图片显示...","object":"content","msg_id":"msg_abc"}
{"status":"completed","type":"text","index":0,"delta":false,"text":"这张图片显示...","object":"content","msg_id":"msg_abc"}
{"id":"msg_abc","status":"completed","object":"message"}
{"id":"response_123","status":"completed","object":"response"}
```

## Agent API 协议构建方式

Agent API 协议提供了分层Builder模式来生成符合协议规范的流式响应数据。通过使用 `agent_api_builder` 模块，开发者可以轻松构建复杂的流式响应序列。

### 1. 构建器架构

Agent API 构建器采用三层架构设计：

- **ResponseBuilder**: 响应构建器，负责管理整个响应流程
- **MessageBuilder**: 消息构建器，负责构建和管理单个消息对象
- **ContentBuilder**: 内容构建器，负责构建和管理单个内容对象

### 2. 核心类说明

#### ResponseBuilder（响应构建器）

```python
from agentscope_runtime.engine.helpers.agent_api_builder import ResponseBuilder

# 创建响应构建器
response_builder = ResponseBuilder(session_id="session_123")

# 设置响应状态
response_builder.created()      # 创建状态
response_builder.in_progress()  # 进行中状态
response_builder.completed()    # 完成状态

# 创建消息构建器
message_builder = response_builder.create_message_builder(
    role="assistant",
    message_type="message"
)
```

#### MessageBuilder（消息构建器）

```python
# 创建内容构建器
content_builder = message_builder.create_content_builder(
    content_type="text",
    index=0
)

# 添加内容到消息
message_builder.add_content(content)

# 完成消息构建
message_builder.complete()
```

#### ContentBuilder（内容构建器）

```python
# 添加文本增量
content_builder.add_text_delta("Hello")
content_builder.add_text_delta(" World")

# 设置完整文本内容
content_builder.set_text("Hello World")

# 设置图片内容
content_builder.set_image_url("https://example.com/image.jpg")

# 设置数据内容
content_builder.set_data({"key": "value"})

# 完成内容构建
content_builder.complete()
```

### 3. 完整使用示例

以下示例展示如何使用Agent API构建器生成完整的流式响应序列：

```python
from agentscope_runtime.engine.helpers.agent_api_builder import ResponseBuilder

def generate_streaming_response(text_tokens):
    """生成流式响应序列"""
    # 创建响应构建器
    response_builder = ResponseBuilder(session_id="session_123")

    # 生成完整的流式响应序列
    for event in response_builder.generate_streaming_response(
        text_tokens=["Hello", " ", "World", "!"],
        role="assistant"
    ):
        yield event

# 使用示例
for event in generate_streaming_response(["Hello", " ", "World", "!"]):
    print(event)
```

### 4. 流式响应序列

使用 `generate_streaming_response` 方法可以生成标准的流式响应序列：

1. **响应创建** (`response.created`)
2. **响应开始** (`response.in_progress`)
3. **消息创建** (`message.created`)
4. **内容流式输出** (`content.delta` 事件)
5. **内容完成** (`content.completed`)
6. **消息完成** (`message.completed`)
7. **响应完成** (`response.completed`)

### 5. 支持的内容类型

ContentBuilder 支持多种内容类型：

- **TextContent**: 文本内容，支持增量输出
- **ImageContent**: 图片内容，支持URL和base64格式
- **DataContent**: 数据内容，支持任意JSON数据
- **AudioContent**: 音频内容，支持多种音频格式
- **FileContent**: 文件内容，支持文件URL和文件数据
- **RefusalContent**: 拒绝内容，用于表示拒绝执行

### 6. 最佳实践

1. **状态管理**: 确保按正确顺序调用状态方法（created → in_progress → completed）
2. **内容索引**: 为多内容消息正确设置index值
3. **增量输出**: 使用add_delta方法实现流式文本输出
4. **错误处理**: 在构建过程中适当处理异常情况
5. **资源清理**: 及时调用complete方法完成构建

### 7. 高级用法

#### 多内容消息构建

```python
# 创建包含文本和图片的消息
message_builder = response_builder.create_message_builder()

# 添加文本内容
text_builder = message_builder.create_content_builder("text", index=0)
text_builder.set_text("这是一张图片：")
text_builder.complete()

# 添加图片内容
image_builder = message_builder.create_content_builder("image", index=1)
image_builder.set_image_url("https://example.com/image.jpg")
image_builder.complete()

# 完成消息
message_builder.complete()
```

#### 数据内容构建

```python
# 创建包含结构化数据的消息
data_builder = message_builder.create_content_builder("data", index=0)

# 设置数据内容
data_builder.set_data({
    "type": "function_call",
    "name": "get_weather",
    "arguments": '{"city": "Beijing"}'
})

# 添加数据增量
data_builder.add_data_delta({"status": "processing"})
data_builder.add_data_delta({"result": "sunny"})

data_builder.complete()
```

通过使用Agent API构建器，开发者可以轻松构建符合协议规范的复杂流式响应，实现更好的用户体验和更灵活的响应控制。

## 协议适配器

协议适配器（Protocol Adapter）用于在不同协议之间进行转换，使 AgentScope Runtime 能够支持多种 API 协议。

### 适配器架构

AgentScope Runtime 提供了三种内置协议适配器：

- **A2A 协议适配器**（`A2AFastAPIDefaultAdapter`）：支持 Agent-to-Agent 协议
- **Response API 协议适配器**（`ResponseAPIDefaultAdapter`）：支持 OpenAI Responses API 协议
- **AG-UI 协议适配器**（`AGUIDefaultAdapter`）：支持 AG-UI 前端框架协议

### 使用内置适配器

AgentApp 默认会自动注册内置适配器：

```{code-cell}
from agentscope_runtime.engine import AgentApp
from agentscope_runtime.engine.deployers.adapter.a2a import A2AFastAPIDefaultAdapter
from agentscope_runtime.engine.deployers.adapter.responses import ResponseAPIDefaultAdapter
from agentscope_runtime.engine.deployers.adapter.agui import AGUIDefaultAdapter

app = AgentApp(agent=agent)

# AgentApp 会自动注册内置适配器
# 您也可以通过 protocol_adapters 参数自定义
app = AgentApp(
    agent=agent,
    protocol_adapters=[
        A2AFastAPIDefaultAdapter(
            agent_name="Friday",
            agent_description="A helpful assistant",
        ),
        ResponseAPIDefaultAdapter(),
        AGUIDefaultAdapter(),
    ],
)
```

### 创建自定义适配器

您可以通过继承 `ProtocolAdapter` 基类来创建自定义适配器：

```{code-cell}
from agentscope_runtime.engine.deployers.adapter.protocol_adapter import ProtocolAdapter
from typing import Any, Callable

class CustomProtocolAdapter(ProtocolAdapter):
    """自定义协议适配器示例"""

    def add_endpoint(self, app, func: Callable, **kwargs) -> Any:
        """添加端点到适配器

        Args:
            app: FastAPI 应用实例
            func: 处理函数
            **kwargs: 其他参数

        Returns:
            端点对象
        """
        # 实现自定义端点添加逻辑
        @app.post("/custom-endpoint")
        async def custom_handler(request):
            # 转换请求格式
            converted_request = self._convert_request(request)
            # 调用处理函数
            result = await func(converted_request)
            # 转换响应格式
            return self._convert_response(result)

        return custom_handler

    def _convert_request(self, request):
        """将外部协议请求转换为内部格式"""
        # 实现请求转换逻辑
        pass

    def _convert_response(self, response):
        """将内部响应转换为外部协议格式"""
        # 实现响应转换逻辑
        pass
```

### 适配器使用场景

1. **多协议支持**：使同一个 Agent 能够同时支持多种 API 协议
2. **协议转换**：在不同协议之间进行无缝转换
3. **向后兼容**：支持旧版本协议的同时支持新协议
4. **自定义协议**：实现特定业务场景的协议适配

更多详细信息，请参考 API 文档中的适配器模块说明。
