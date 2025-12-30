# 记忆组件 (Modelstudio Memory Components)

本示例包含Modelstudio Memory相关组件，提供对话记忆存储、检索和用户画像管理功能。

## 📋 组件列表

### 1. AddMemory - 添加对话记忆
核心组件，用于将对话历史存储为结构化的记忆节点，并自动提取用户画像信息。

**前置使用条件：**
- DashScope API-KEY
- 配置记忆服务Endpoint (可选)
- 用户画像 Schema（可选，用于画像提取场景）

**输入参数 (AddMemoryInput)：**
- `user_id` (str): 唯一用户标识符
- `messages` (List[Message]): 对话消息列表
  - `role`: 消息角色（user/assistant）
  - `content`: 消息内容
- `timestamp` (int, 可选): 对话时间戳（10位），默认为当前时间
- `profile_schema` (str, 可选): 用户画像 Schema ID，通过CreateProfileSchema接口创建
- `meta_data` (Dict, 可选): 附加元数据（位置、上下文等）

**输出参数 (AddMemoryOutput)：**
- `memory_nodes` (List[MemoryNode]): 创建的记忆节点  - `memory_node_id`: 唯一记忆节点 ID
  - `content`: 记忆内容
  - `event`: 记忆事件类型
  - `old_content`: 旧内容（仅在更新记忆场景时出现）
- `request_id` : 唯一的request_id

**核心功能：**
- **自动提取**: 自动从对话中提取关键信息
- **画像学习**: 从对话中学习用户特征（年龄、兴趣等）
- **结构化存储**: 将对话存储为结构化的可搜索记忆节点
- **元数据支持**: 支持自定义元数据（时间、位置、上下文）
- **更新跟踪**: 跟踪记忆的更新和变化

### 2. SearchMemory - 搜索相关记忆
基于语义相似度搜索相关历史对话的组件。

**前置使用条件：**
- 用户已有记忆数据
- 有效的搜索查询

**输入参数 (SearchMemoryInput)：**
- `user_id` (str): 用户标识符
- `messages` (List[Message]): 当前对话上下文
- `top_k` (int, 可选): 返回结果数量（默认: 5）
- `min_score` (float, 可选): 最小相似度分数（建议值0.03）
- `filters` (Dict, 可选): 额外的过滤条件

**输出参数 (SearchMemoryOutput)：**
- `memory_nodes` (List[MemoryNode]): 检索到的记忆节点
- `request_id` (str): 请求标识符

**核心功能：**
- **语义搜索**: 基于语义相似度检索，而非仅关键词匹配
- **上下文感知**: 考虑对话上下文以获得更好结果
- **分数排序**: 按相关性分数排序返回结果
- **灵活过滤**: 支持时间范围、事件类型等多种过滤器

### 3. ListMemory - 列出记忆节点
支持分页的用户记忆节点列表组件。

**输入参数 (ListMemoryInput)：**
- `user_id` (str): 用户标识符
- `page_num` (int): 页码（从 1 开始）
- `page_size` (int): 每页条目数

**输出参数 (ListMemoryOutput)：**
- `memory_nodes` (List[MemoryNode]): 当前页的记忆列表
- `total` (int): 总记忆节点数
- `page_num` (int): 当前页码
- `page_size` (int): 页面大小
- `request_id` (str): 请求标识符

### 4. DeleteMemory - 删除记忆节点
删除指定记忆节点的组件。

**输入参数 (DeleteMemoryInput)：**
- `user_id` (str): 用户标识符
- `memory_node_id` (str): 要删除的记忆节点 ID

**输出参数 (DeleteMemoryOutput)：**
- `success` (bool): 删除是否成功
- `request_id` (str): 请求标识符

### 5. CreateProfileSchema - 创建用户画像 Schema
定义用户画像字段结构的组件。

**输入参数 (CreateProfileSchemaInput)：**
- `name` (str): Schema 名称
- `description` (str): Schema 描述
- `attributes` (List[ProfileAttribute]): 画像属性定义
  - `name`: 属性名称（如"年龄"、"爱好"）
  - `description`: 属性描述

**输出参数 (CreateProfileSchemaOutput)：**
- `profile_schema_id` (str): 创建的 Schema ID
- `request_id` (str): 请求标识符

### 6. GetUserProfile - 获取用户画像
获取自动提取的用户画像信息的组件。

**输入参数 (GetUserProfileInput)：**
- `schema_id` (str): 画像 Schema ID
- `user_id` (str): 用户标识符

**输出参数 (GetUserProfileOutput)：**
- `profile` (UserProfile): 用户画像信息
  - `schema_name`: Schema 名称
  - `schema_description`: Schema 描述
  - `attributes`: 包含提取值的画像属性
- `request_id` (str): 请求标识符

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

## 🏗️ 记忆架构特点

### 记忆存储策略

- **对话结构化**: 自动将对话结构化为记忆
- **自动摘要**: 从冗长对话中提取关键信息
- **时间序列组织**: 按时间线组织记忆
- **事件分类**: 按事件类型分类记忆（提醒、事实、偏好等）

### 检索策略

- **语义搜索**: 基于语义相似度检索
- **时间过滤**: 支持按时间范围过滤（最近、特定时期）
- **相关性排序**: 按语义相似度和时效性排序结果
- **上下文感知**: 考虑对话上下文以获得更好的检索效果

### 画像提取

- **基于 NLP 的提取**: 使用自然语言处理提取用户信息
- **渐进式更新**: 随时间逐步构建和完善用户画像
- **冲突解决**: 智能处理冲突信息
- **多属性支持**: 同时支持多个画像属性


