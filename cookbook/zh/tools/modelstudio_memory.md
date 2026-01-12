# ModelStudio Memory - 对话记忆与用户画像

## 📖 什么是 ModelStudio Memory？

ModelStudio Memory 是来自阿里云百炼大模型平台官方提供的**对话记忆管理工具**，让你的 AI
应用能够"记住"用户的对话历史，并从中自动提取用户画像。

**核心能力：**
- 💾 **记忆存储**：自动将对话转换为结构化记忆，支持语义搜索
- 🔍 **智能检索**：基于上下文语义检索相关历史对话
- 👤 **画像提取**：自动从对话中提取用户属性（年龄、兴趣、职业等）
- 🎯 **个性化对话**：结合记忆为用户提供更个性化的回复

**典型场景：**
```
用户首次对话：
  用户："我今年28岁，是一名软件工程师，周末喜欢打篮球"
  系统：自动记录 → 提取画像（年龄=28，职业=软件工程师，爱好=篮球）

一周后再次对话：
  用户："推荐一些周末活动"
  系统：检索记忆 → 发现喜欢篮球 → 推荐篮球赛事和球馆
```

## 📋 核心组件

### 1. AddMemory - 添加记忆
将用户对话存储为记忆，自动提取关键信息和用户画像。

**主要参数：**
- `user_id`: 用户唯一标识
- `messages`: 对话消息列表（user/assistant）
- `timestamp`: 对话时间戳（可选）
- `profile_schema`: 用户画像 Schema ID（可选，用于画像提取）
- `meta_data`: 附加元数据，如位置、类别等（可选）

**返回结果：**
- `memory_nodes`: 创建的记忆节点列表，包含记忆ID、内容、事件类型

### 2. SearchMemory - 搜索记忆
基于语义相似度搜索相关历史对话。

**主要参数：**
- `user_id`: 用户标识
- `messages`: 当前对话上下文
- `top_k`: 返回结果数量（默认 5）
- `min_score`: 最小相似度分数（默认 0.0）

**返回结果：**
- `memory_nodes`: 按相关性排序的记忆节点列表

### 3. ListMemory - 列出记忆
分页查看用户的所有记忆。

**主要参数：**
- `user_id`: 用户标识
- `page_num`: 页码（从 1 开始）
- `page_size`: 每页条目数

### 4. DeleteMemory - 删除记忆
删除指定的记忆节点。

**主要参数：**
- `user_id`: 用户标识
- `memory_node_id`: 要删除的记忆节点 ID

### 5. CreateProfileSchema - 创建画像模板
定义要提取的用户画像字段结构。

**主要参数：**
- `name`: 模板名称
- `description`: 模板描述
- `attributes`: 画像属性列表（如：年龄、爱好、职业）

**返回结果：**
- `profile_schema_id`: 创建的模板 ID

### 6. GetUserProfile - 获取用户画像
获取系统自动提取的用户画像信息。

**主要参数：**
- `schema_id`: 画像模板 ID
- `user_id`: 用户标识

**返回结果：**
- `profile`: 用户画像，包含各属性的提取值

## 🔧 环境变量配置

| 环境变量 | 必需 | 默认值 | 说明 |
|---------|---|--------|------|
| `DASHSCOPE_API_KEY` | YES | - | DashScope API 密钥 |
| `MEMORY_SERVICE_ENDPOINT` | NO| https://dashscope.aliyuncs.com/api/v2/apps/memory | 记忆服务 API 端点 |

## 🚀 使用示例

### 基础记忆操作示例

演示添加、搜索和列出记忆的基本流程：

```python
from agentscope_runtime.tools.modelstudio_memory import (
    AddMemory, SearchMemory, Message, AddMemoryInput, SearchMemoryInput,
)
import asyncio

async def basic_example():
    add_memory = AddMemory()
    search_memory = SearchMemory()

    try:
        # 添加记忆
        await add_memory.arun(AddMemoryInput(
            user_id="user_001",
            messages=[
                Message(role="user", content="每天上午9点提醒我喝水"),
                Message(role="assistant", content="好的，已记录"),
            ]
        ))

        await asyncio.sleep(2)  # 等待记忆处理

        # 搜索记忆
        result = await search_memory.arun(SearchMemoryInput(
            user_id="user_001",
            messages=[Message(role="user", content="我需要做什么？")],
            top_k=5
        ))

        for node in result.memory_nodes:
            print(f"记忆: {node.content}")

    finally:
        await add_memory.close()
        await search_memory.close()

asyncio.run(basic_example())
```

### 用户画像提取示例

演示如何从对话中自动提取用户画像：

```python
from agentscope_runtime.tools.modelstudio_memory import (
    CreateProfileSchema, GetUserProfile, AddMemory,
    ProfileAttribute, CreateProfileSchemaInput,
    GetUserProfileInput, AddMemoryInput, Message,
)
import asyncio

async def profile_example():
    create_schema = CreateProfileSchema()
    get_profile = GetUserProfile()
    add_memory = AddMemory()

    try:
        # 创建画像 Schema
        schema_result = await create_schema.arun(CreateProfileSchemaInput(
            name="用户基础画像",
            description="包含年龄和兴趣的用户信息",
            attributes=[
                ProfileAttribute(name="年龄", description="用户年龄"),
                ProfileAttribute(name="爱好", description="用户的兴趣爱好"),
                ProfileAttribute(name="职业", description="用户职业"),
            ]
        ))

        schema_id = schema_result.profile_schema_id

        # 添加包含画像信息的对话
        await add_memory.arun(AddMemoryInput(
            user_id="user_002",
            messages=[
                Message(role="user", content="我今年28岁，是一名软件工程师。周末喜欢踢足球。"),
                Message(role="assistant", content="很高兴认识你！"),
            ],
            profile_schema=schema_id
        ))

        await asyncio.sleep(3)  # 等待画像提取

        # 获取提取的画像
        profile = await get_profile.arun(GetUserProfileInput(
            schema_id=schema_id, user_id="user_002"
        ))

        for attr in profile.profile.attributes:
            print(f"{attr.name}: {attr.value or '未提取'}")

    finally:
        await create_schema.close()
        await get_profile.close()
        await add_memory.close()

asyncio.run(profile_example())
```

### 记忆增强的 LLM 对话示例

演示如何结合记忆和大模型实现个性化对话：

```python
from agentscope_runtime.tools.modelstudio_memory import (
    AddMemory, SearchMemory, Message, AddMemoryInput, SearchMemoryInput,
)
from openai import AsyncOpenAI
import asyncio
import os

async def llm_with_memory():
    add_memory = AddMemory()
    search_memory = SearchMemory()
    llm_client = AsyncOpenAI(
        api_key=os.getenv("DASHSCOPE_API_KEY"),
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
    )

    try:
        user_id = "user_003"

        # 存储历史对话
        await add_memory.arun(AddMemoryInput(
            user_id=user_id,
            messages=[
                Message(role="user", content="我最喜欢的编程语言是 Python"),
                Message(role="assistant", content="很好！Python 非常强大"),
            ]
        ))

        await asyncio.sleep(2)

        # 搜索相关记忆
        query = "我对哪些技术感兴趣？"
        result = await search_memory.arun(SearchMemoryInput(
            user_id=user_id,
            messages=[Message(role="user", content=query)],
            top_k=5
        ))

        # 构建带记忆的提示词
        memory_ctx = "\n".join([f"- {n.content}" for n in result.memory_nodes])
        system_prompt = f"使用以下用户记忆提供个性化回答：\n{memory_ctx}"

        # 调用大模型
        response = await llm_client.chat.completions.create(
            model="qwen-max",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query}
            ]
        )

        print(response.choices[0].message.content)

    finally:
        await add_memory.close()
        await search_memory.close()
        await llm_client.close()

asyncio.run(llm_with_memory())
```

### 记忆管理示例

演示如何使用元数据和时间戳管理记忆：

```python
from agentscope_runtime.tools.modelstudio_memory import (
    AddMemory, SearchMemory, Message, AddMemoryInput, SearchMemoryInput,
)
import asyncio
import time

async def metadata_example():
    add_memory = AddMemory()
    search_memory = SearchMemory()

    try:
        user_id = "user_004"

        # 添加带元数据的记忆
        await add_memory.arun(AddMemoryInput(
            user_id=user_id,
            messages=[
                Message(role="user", content="明天下午2点和设计团队开会"),
                Message(role="assistant", content="已记录会议安排"),
            ],
            timestamp=int(time.time()),
            meta_data={"category": "工作", "priority": "高"}
        ))

        await asyncio.sleep(2)

        # 查询记忆
        result = await search_memory.arun(SearchMemoryInput(
            user_id=user_id,
            messages=[Message(role="user", content="我有什么会议安排？")],
            top_k=3
        ))

        for node in result.memory_nodes:
            print(f"记忆: {node.content}")

    finally:
        await add_memory.close()
        await search_memory.close()

asyncio.run(metadata_example())
```

## 🏗️ 核心特性

### 🔍 智能检索
- **语义理解**：不是简单的关键词匹配，而是理解对话含义
- **上下文感知**：结合当前对话内容找到最相关的历史记忆
- **时间过滤**：可以筛选特定时间段的记忆

### 💾 自动记忆管理
- **结构化存储**：自动将对话转为结构化记忆节点
- **事件分类**：自动识别记忆类型（提醒、事实、偏好等）
- **元数据支持**：支持添加位置、类别等附加信息

### 👤 用户画像提取
- **自动学习**：从对话中自动提取用户属性（年龄、职业、爱好等）
- **渐进式更新**：随着对话积累，画像逐步完善
- **多属性支持**：可定义多个画像字段同时提取

## 💡 最佳实践

### 记忆管理建议
1. **及时存储**：在每轮对话结束后及时调用 AddMemory 保存记忆
2. **合理使用 top_k**：搜索时建议设置 `top_k=3~10`，平衡性能和效果
3. **添加meta信息**：为记忆添加自定义信息，便于自定义管理

### 用户画像建议
1. **明确定义 Schema**：画像字段及描述应该清晰、具体，避免过于抽象
2. **渐进式收集**：不要期望一次对话就能提取所有信息