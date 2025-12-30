# 记忆组件 (Modelstudio Memory Components)

本目录包含Modelstudio Memory相关组件，提供对话记忆存储、检索和用户画像管理功能。

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

```python
from agentscope_runtime.tools.modelstudio_memory import (
    AddMemory,
    SearchMemory,
    ListMemory,
    DeleteMemory,
    Message,
    AddMemoryInput,
    SearchMemoryInput,
    ListMemoryInput,
    DeleteMemoryInput,
)
import asyncio
import time

# 初始化组件
add_memory = AddMemory()
search_memory = SearchMemory()
list_memory = ListMemory()
delete_memory = DeleteMemory()


async def basic_memory_example():
    user_id = "user_001"
    
    # 1. 添加对话记忆
    add_result = await add_memory.arun(
        AddMemoryInput(
            user_id=user_id,
            messages=[
                Message(role="user", content="每天上午9点提醒我喝水。"),
                Message(role="assistant", content="好的，我已经记录下来。"),
            ],
            timestamp=int(time.time()),
            meta_data={
                "location_name": "家里",
                "context": "日常事务"
            }
        )
    )
    
    print(f"添加了 {len(add_result.memory_nodes)} 条记忆节点")
    memory_ids = [node.memory_node_id for node in add_result.memory_nodes]
    
    # 等待记忆处理完成
    await asyncio.sleep(2)
    
    # 2. 搜索相关记忆
    search_result = await search_memory.arun(
        SearchMemoryInput(
            user_id=user_id,
            messages=[
                Message(role="user", content="今天我需要做什么？")
            ],
            top_k=5,
            min_score=0
        )
    )
    
    print(f"找到 {len(search_result.memory_nodes)} 条相关记忆：")
    for node in search_result.memory_nodes:
        print(f"  - {node.content}")
    
    # 3. 列出所有记忆
    list_result = await list_memory.arun(
        ListMemoryInput(
            user_id=user_id,
            page_num=1,
            page_size=10
        )
    )
    
    print(f"总记忆数：{list_result.total}")
    
    # 4. 删除记忆
    for memory_id in memory_ids:
        await delete_memory.arun(
            DeleteMemoryInput(
                user_id=user_id,
                memory_node_id=memory_id
            )
        )
    
    print("清理完成")


asyncio.run(basic_memory_example())
```

### 用户画像提取示例

```python
from agentscope_runtime.tools.modelstudio_memory import (
    CreateProfileSchema,
    GetUserProfile,
    AddMemory,
    ProfileAttribute,
    CreateProfileSchemaInput,
    GetUserProfileInput,
    AddMemoryInput,
    Message,
)
import asyncio
import time


async def profile_extraction_example():
    create_schema = CreateProfileSchema()
    get_profile = GetUserProfile()
    add_memory = AddMemory()
    
    user_id = "user_002"
    
    # 1. 创建用户画像 Schema
    schema_result = await create_schema.arun(
        CreateProfileSchemaInput(
            name="用户基础画像",
            description="包含年龄和兴趣的基础用户信息",
            attributes=[
                ProfileAttribute(name="年龄", description="用户年龄"),
                ProfileAttribute(name="爱好", description="用户的兴趣爱好"),
                ProfileAttribute(name="职业", description="用户职业"),
            ]
        )
    )
    
    schema_id = schema_result.profile_schema_id
    print(f"创建画像 Schema：{schema_id}")
    
    # 2. 添加包含画像信息的对话
    await add_memory.arun(
        AddMemoryInput(
            user_id=user_id,
            messages=[
                Message(
                    role="user",
                    content="我今年28岁，是一名软件工程师。周末喜欢踢足球。"
                ),
                Message(role="assistant", content="很高兴认识你！我已经记下你的信息了。"),
            ],
            timestamp=int(time.time()),
            profile_schema=schema_id
        )
    )
    
    # 等待画像提取
    await asyncio.sleep(3)
    
    # 3. 获取提取的画像
    profile_result = await get_profile.arun(
        GetUserProfileInput(
            schema_id=schema_id,
            user_id=user_id
        )
    )
    
    print(f"\n📋 用户画像：")
    print(f"Schema：{profile_result.profile.schema_name}")
    print(f"\n提取的属性：")
    for attr in profile_result.profile.attributes:
        value = attr.value if attr.value else "（暂未提取）"
        print(f"  - {attr.name}：{value}")


asyncio.run(profile_extraction_example())
```

### 记忆增强的 LLM 对话示例

```python
from agentscope_runtime.tools.modelstudio_memory import (
    AddMemory,
    SearchMemory,
    Message,
    AddMemoryInput,
    SearchMemoryInput,
)
from openai import AsyncOpenAI
import asyncio
import time
import os


async def memory_enhanced_conversation():
    add_memory = AddMemory()
    search_memory = SearchMemory()
    
    # 初始化 OpenAI 客户端（DashScope 兼容）
    llm_client = AsyncOpenAI(
        api_key=os.getenv("DASHSCOPE_API_KEY"),
        base_url=os.getenv(
            "LLM_BASE_URL",
            "https://dashscope.aliyuncs.com/compatible-mode/v1"
        )
    )
    
    user_id = "user_003"
    
    # 1. 将初始对话存入记忆
    initial_messages = [
        Message(role="user", content="我最喜欢的编程语言是 Python。"),
        Message(role="assistant", content="很好！Python 非常强大和灵活。"),
        Message(role="user", content="我目前在学习机器学习。"),
        Message(role="assistant", content="很棒的选择！机器学习是个迷人的领域。"),
    ]
    
    await add_memory.arun(
        AddMemoryInput(
            user_id=user_id,
            messages=initial_messages,
            timestamp=int(time.time())
        )
    )
    
    await asyncio.sleep(2)
    
    # 2. 新查询 - 搜索相关记忆
    user_query = "我对哪些技术感兴趣？"
    
    search_result = await search_memory.arun(
        SearchMemoryInput(
            user_id=user_id,
            messages=[Message(role="user", content=user_query)],
            top_k=5
        )
    )
    
    # 3. 从检索的记忆构建上下文
    memory_context = "\n".join([
        f"- {node.content}" for node in search_result.memory_nodes
    ])
    
    # 4. 使用带记忆上下文的 LLM 生成回答
    system_prompt = (
        "你是一个有帮助的助手。使用以下关于用户的记忆来提供个性化的回答。\n\n"
        f"用户的记忆：\n{memory_context}"
    )
    
    stream = await llm_client.chat.completions.create(
        model="qwen-max",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_query}
        ],
        stream=True
    )
    
    print(f"用户：{user_query}\n")
    print("助手：", end="")
    
    full_response = ""
    async for chunk in stream:
        if chunk.choices and chunk.choices[0].delta.content:
            content = chunk.choices[0].delta.content
            print(content, end="", flush=True)
            full_response += content
    
    print("\n")
    
    # 5. 存储新对话
    await add_memory.arun(
        AddMemoryInput(
            user_id=user_id,
            messages=[
                Message(role="user", content=user_query),
                Message(role="assistant", content=full_response)
            ],
            timestamp=int(time.time())
        )
    )
    
    await llm_client.close()


asyncio.run(memory_enhanced_conversation())
```

### 长期记忆管理示例

```python
from agentscope_runtime.tools.modelstudio_memory import (
    AddMemory,
    SearchMemory,
    ListMemory,
    Message,
    AddMemoryInput,
    SearchMemoryInput,
    ListMemoryInput,
)
import asyncio
import time
from datetime import datetime, timedelta


async def long_term_memory_management():
    add_memory = AddMemory()
    search_memory = SearchMemory()
    list_memory = ListMemory()
    
    user_id = "user_004"
    
    # 模拟不同时间的对话
    conversations = [
        {
            "time_offset": 0,  # 今天
            "messages": [
                Message(role="user", content="明天下午2点和设计团队开会。"),
                Message(role="assistant", content="我已经记下您明天下午2点的会议。"),
            ],
            "meta_data": {"category": "工作", "priority": "高"}
        },
        {
            "time_offset": -86400,  # 昨天
            "messages": [
                Message(role="user", content="完成了第四季度项目报告。"),
                Message(role="assistant", content="太棒了，恭喜完成报告！"),
            ],
            "meta_data": {"category": "工作", "status": "已完成"}
        },
        {
            "time_offset": -604800,  # 上周
            "messages": [
                Message(role="user", content="开始学习 React 来做新项目。"),
                Message(role="assistant", content="React 是个很棒的框架！"),
            ],
            "meta_data": {"category": "学习", "topic": "React"}
        }
    ]
    
    # 存储不同时间戳的对话
    print("📝 存储对话...")
    for conv in conversations:
        timestamp = int(time.time()) + conv["time_offset"]
        await add_memory.arun(
            AddMemoryInput(
                user_id=user_id,
                messages=conv["messages"],
                timestamp=timestamp,
                meta_data=conv["meta_data"]
            )
        )
    
    await asyncio.sleep(2)
    
    # 查询记忆
    queries = [
        "我有什么会议安排？",
        "我最近完成了什么？",
        "我正在学习什么？"
    ]
    
    print("\n🔍 查询记忆：\n")
    for query in queries:
        print(f"问：{query}")
        search_result = await search_memory.arun(
            SearchMemoryInput(
                user_id=user_id,
                messages=[Message(role="user", content=query)],
                top_k=3
            )
        )
        
        if search_result.memory_nodes:
            print(f"相关记忆：")
            for node in search_result.memory_nodes:
                print(f"  - {node.content}")
        else:
            print("  未找到相关记忆")
        print()
    
    # 分页列出所有记忆
    print("📊 所有存储的记忆：")
    list_result = await list_memory.arun(
        ListMemoryInput(
            user_id=user_id,
            page_num=1,
            page_size=10
        )
    )
    
    print(f"总计：{list_result.total} 条记忆")
    for i, node in enumerate(list_result.memory_nodes, 1):
        print(f"  [{i}] {node.content}")


asyncio.run(long_term_memory_management())
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


