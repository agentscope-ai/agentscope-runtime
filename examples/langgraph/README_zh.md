# LangGraph 集成示例

此目录包含演示如何将 LangGraph 与 AgentScope Runtime 集成以构建复杂智能体工作流的示例。

## 概述

LangGraph 是一个用于构建具有 LLM 的有状态、多参与者应用程序的库，用于创建智能体和多智能体工作流。这些示例展示了如何在 AgentScope Runtime 框架内利用 LangGraph 强大的工作流功能。

## 示例

### 1. 基本 LLM 交互 (`run_langgraph_llm.py`)

演示在 AgentScope Runtime 中使用 LangGraph 进行基本 LLM 交互的简单示例：

- 使用来自 DashScope 的 Qwen-Plus 模型
- 实现带有单个节点的基本状态图工作流
- 展示如何从 LLM 流式传输响应
- 包含对话历史记录的内存管理
- 演示 `StateGraph` 与 `START` 和 `call_model` 节点的使用

### 2. 带工具的高级智能体 (`run_langgraph_agent.py`)

演示具有工具调用功能的更复杂智能体的示例：

- 集成在 `my_tools.py` 中定义的自定义工具
- 实现短期（对话）和长期（持久化）内存
- 使用检查点在会话间维护状态
- 提供 API 端点以检查内存状态
- 演示工具调用和结果处理
- 包含用于演示目的的自定义天气工具
- 使用带有 user_id 和 session_id 字段的自定义 `AgentState` 扩展
- 为工具调用结果实现长期内存存储

### 3. 自定义工具 (`my_tools.py`)

可由 LangGraph 智能体使用的自定义工具集合：

- 文件操作：读取和更新计划文件
- 支持范围的文本文件查看
- 使用阿里云 IQS API 进行网络搜索
- 内存管理实用程序

关键工具包括：
- `read_plan_file(file_path)`：读取计划文件的内容
- `update_plan_file(file_path, content, adjust_plan=False, adjustment_reason="")`：更新或创建带内容的计划文件，支持可选的计划调整
- `iqs_generic_search(query, category=None, limit=5)`：使用阿里云 IQS API 进行网络搜索，支持类别过滤
- `_view_text_file(file_path, ranges=None)`：用于读取带可选范围支持的文本文件的内部实用程序

## 先决条件

1. **安装依赖**：
   ```bash
   pip install agentscope-runtime[langgraph]
   ```

2. **设置环境变量**：
   ```bash
   # 必需：DashScope API 密钥用于 Qwen 模型
   export DASHSCOPE_API_KEY="your-dashscope-api-key"

   # 可选：Alibaba Cloud IQS API 密钥用于网络搜索（在 my_tools.py 中使用）
   export IQS_API_KEY="your-iqs-api-key"
   ```

## 运行示例

### 基本 LLM 交互

```bash
python examples/langgraph/run_langgraph_llm.py
```

### 带工具的高级智能体

```bash
python examples/langgraph/run_langgraph_agent.py
```

启动服务器后，您可以通过查询接口与智能体交互，并通过提供的 API 端点检查内存状态。

### 与智能体交互

服务器运行后，您可以使用 `/query` 端点向智能体发送查询：

```bash
curl -X POST http://localhost:8090/query \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "北京的天气怎么样？"}],
    "user_id": "user123",
    "session_id": "session456"
  }'
```

## 展示的关键特性

### LangGraph 集成
- 使用 `AgentState` 进行状态管理
- 使用 `StateGraph` 定义工作流
- 用于持久状态的检查点
- 用于实时交互的流式响应

### 内存管理
- 用于对话历史记录的短期内存
- 用于持久存储的长期内存
- 用于检查内存状态的 API 端点
- 基于会话的内存隔离

### 工具集成
- 使用 LangChain 的 `@tool` 装饰器定义自定义工具
- 工具调用和结果处理
- 文件系统操作
- 网络搜索功能

## API 端点

运行高级智能体示例时，以下 API 端点可用：

- `POST /query` - 向智能体发送查询
- `GET /api/memory/short-term/{session_id}` - 获取会话的短期内存
- `GET /api/memory/short-term` - 列出所有短期内存
- `GET /api/memory/long-term/{user_id}` - 获取用户的长期内存

## 自定义

您可以通过以下方式自定义这些示例：

1. **添加新工具**：使用 `@tool` 装饰的附加函数扩展 `my_tools.py`
2. **更改 LLM**：修改 `ChatOpenAI` 初始化以使用不同的模型
3. **扩展工作流**：向状态图添加新节点和边
4. **自定义内存**：实现不同的内存存储后端

## 相关文档

- [LangGraph 文档](https://langchain-ai.github.io/langgraph/)
- [AgentScope Runtime 文档](https://runtime.agentscope.io/)