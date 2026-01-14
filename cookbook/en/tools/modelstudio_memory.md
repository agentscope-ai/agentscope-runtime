# ModelStudio Memory - Conversation Memory & User Profiles

## 📖 What is ModelStudio Memory?

ModelStudio Memory is a **conversation memory tool** that enables
your AI applications to "remember" user conversation history and automatically extract user profiles.

**Core Capabilities:**
- 💾 **Memory Storage**: Automatically converts conversations into structured memories with semantic search support
- 🔍 **Smart Retrieval**: Context-aware semantic search of relevant historical conversations
- 👤 **Profile Extraction**: Automatically extracts user attributes (age, interests, occupation, etc.) from conversations
- 🎯 **Personalized Conversations**: Provides more personalized responses by leveraging memory

**Typical Scenario:**
```
First conversation:
  User: "I'm 28 years old, a software engineer, and I love playing basketball on weekends"
  System: Auto-record → Extract profile (age=28, occupation=software engineer, hobby=basketball)

One week later:
  User: "Recommend some weekend activities"
  System: Retrieve memory → Finds basketball interest → Recommends basketball events and courts
```

## 📋 Core Components

### 1. AddMemory - Add Memory
Stores user conversations as memories and automatically extracts key information and user profiles.

**Main Parameters:**
- `user_id`: Unique user identifier
- `messages`: List of conversation messages (user/assistant)
- `timestamp`: Conversation timestamp (optional)
- `profile_schema`: User profile schema ID (optional, for profile extraction)
- `meta_data`: Additional metadata such as location, category, etc. (optional)

**Returns:**
- `memory_nodes`: List of created memory nodes, including memory ID, content, and event type

### 2. SearchMemory - Search Memory
Searches relevant historical conversations based on semantic similarity.

**Main Parameters:**
- `user_id`: User identifier
- `messages`: Current conversation context
- `top_k`: Number of results to return (default: 5)
- `min_score`: Minimum similarity score (default: 0.0)

**Returns:**
- `memory_nodes`: List of memory nodes sorted by relevance

### 3. ListMemory - List Memory
Paginated view of all user memories.

**Main Parameters:**
- `user_id`: User identifier
- `page_num`: Page number (starts from 1)
- `page_size`: Number of entries per page

### 4. DeleteMemory - Delete Memory
Deletes specified memory nodes.

**Main Parameters:**
- `user_id`: User identifier
- `memory_node_id`: ID of the memory node to delete

### 5. CreateProfileSchema - Create Profile Schema
Defines the structure of user profile fields to extract.

**Main Parameters:**
- `name`: Schema name
- `description`: Schema description
- `attributes`: List of profile attributes (e.g., age, hobbies, occupation)

**Returns:**
- `profile_schema_id`: ID of the created schema

### 6. GetUserProfile - Get User Profile
Retrieves automatically extracted user profile information.

**Main Parameters:**
- `schema_id`: Profile schema ID
- `user_id`: User identifier

**Returns:**
- `profile`: User profile containing extracted values for each attribute

## 🔧 Environment Configuration

| Environment Variable | Required | Default | Description |
|---------------------|----------|---------|-------------|
| `DASHSCOPE_API_KEY` | YES | - | DashScope API key |
| `MEMORY_SERVICE_ENDPOINT` | NO | https://dashscope.aliyuncs.com/api/v2/apps/memory | Memory service API endpoint |

## 🚀 Usage Examples

### Basic Memory Operations

Demonstrates the basic flow of adding, searching, and listing memories:

```python
from agentscope_runtime.tools.modelstudio_memory import (
    AddMemory, SearchMemory, Message, AddMemoryInput, SearchMemoryInput,
)
import asyncio

async def basic_example():
    add_memory = AddMemory()
    search_memory = SearchMemory()

    try:
        # Add memory
        await add_memory.arun(AddMemoryInput(
            user_id="user_001",
            messages=[
                Message(role="user", content="Remind me to drink water at 9 AM every day"),
                Message(role="assistant", content="Okay, recorded"),
            ]
        ))

        await asyncio.sleep(2)  # Wait for memory processing

        # Search memory
        result = await search_memory.arun(SearchMemoryInput(
            user_id="user_001",
            messages=[Message(role="user", content="What do I need to do?")],
            top_k=5
        ))

        for node in result.memory_nodes:
            print(f"Memory: {node.content}")

    finally:
        await add_memory.close()
        await search_memory.close()

asyncio.run(basic_example())
```

### User Profile Extraction

Demonstrates how to automatically extract user profiles from conversations:

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
        # Create profile schema
        schema_result = await create_schema.arun(CreateProfileSchemaInput(
            name="Basic User Profile",
            description="User information including age and interests",
            attributes=[
                ProfileAttribute(name="Age", description="User's age"),
                ProfileAttribute(name="Hobbies", description="User's interests and hobbies"),
                ProfileAttribute(name="Occupation", description="User's occupation"),
            ]
        ))

        schema_id = schema_result.profile_schema_id

        # Add conversation with profile information
        await add_memory.arun(AddMemoryInput(
            user_id="user_002",
            messages=[
                Message(role="user", content="I'm 28 years old and a software engineer. I like playing soccer on weekends."),
                Message(role="assistant", content="Nice to meet you!"),
            ],
            profile_schema=schema_id
        ))

        await asyncio.sleep(3)  # Wait for profile extraction

        # Get extracted profile
        profile = await get_profile.arun(GetUserProfileInput(
            schema_id=schema_id, user_id="user_002"
        ))

        for attr in profile.profile.attributes:
            print(f"{attr.name}: {attr.value or 'Not extracted'}")

    finally:
        await create_schema.close()
        await get_profile.close()
        await add_memory.close()

asyncio.run(profile_example())
```

### Memory-Enhanced LLM Conversation

Demonstrates how to combine memory with LLM for personalized conversations:

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

        # Store conversation history
        await add_memory.arun(AddMemoryInput(
            user_id=user_id,
            messages=[
                Message(role="user", content="My favorite programming language is Python"),
                Message(role="assistant", content="Great! Python is very powerful"),
            ]
        ))

        await asyncio.sleep(2)

        # Search relevant memories
        query = "What technologies am I interested in?"
        result = await search_memory.arun(SearchMemoryInput(
            user_id=user_id,
            messages=[Message(role="user", content=query)],
            top_k=5
        ))

        # Build prompt with memory context
        memory_ctx = "\n".join([f"- {n.content}" for n in result.memory_nodes])
        system_prompt = f"Use the following user memories to provide personalized responses:\n{memory_ctx}"

        # Call LLM
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

### Memory Management with Metadata

Demonstrates how to use metadata and timestamps for memory management:

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

        # Add memory with metadata
        await add_memory.arun(AddMemoryInput(
            user_id=user_id,
            messages=[
                Message(role="user", content="Meeting with design team tomorrow at 2 PM"),
                Message(role="assistant", content="Meeting recorded"),
            ],
            timestamp=int(time.time()),
            meta_data={"category": "work", "priority": "high"}
        ))

        await asyncio.sleep(2)

        # Query memories
        result = await search_memory.arun(SearchMemoryInput(
            user_id=user_id,
            messages=[Message(role="user", content="What meetings do I have?")],
            top_k=3
        ))

        for node in result.memory_nodes:
            print(f"Memory: {node.content}")

    finally:
        await add_memory.close()
        await search_memory.close()

asyncio.run(metadata_example())
```

## 🏗️ Core Features

### 🔍 Smart Retrieval
- **Semantic Understanding**: Goes beyond simple keyword matching to understand conversation meaning
- **Context Awareness**: Combines current conversation context to find the most relevant historical memories
- **Time Filtering**: Can filter memories from specific time periods

### 💾 Automatic Memory Management
- **Structured Storage**: Automatically converts conversations into structured memory nodes
- **Event Classification**: Automatically identifies memory types (reminders, facts, preferences, etc.)
- **Metadata Support**: Supports adding additional information like location, category, etc.

### 👤 User Profile Extraction
- **Automatic Learning**: Automatically extracts user attributes from conversations (age, occupation, hobbies, etc.)
- **Progressive Updates**: Profile gradually improves as conversations accumulate
- **Multi-Attribute Support**: Can define and extract multiple profile fields simultaneously

## 💡 Best Practices

### Memory Management
1. **Timely Storage**: Call AddMemory promptly after each conversation round to save memories
2. **Reasonable top_k**: Set `top_k=3~10` for searches to balance performance and effectiveness
3. **Add Metadata**: Add custom metadata to memories for easier custom management

### User Profile
1. **Clear Schema Definition**: Profile fields and descriptions should be clear and specific, avoid being too abstract
2. **Progressive Collection**: Don't expect to extract all information from a single conversation


