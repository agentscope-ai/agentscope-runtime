# -*- coding: utf-8 -*-
import asyncio
import logging
import os
import sys
import time
import uuid
from datetime import datetime
from typing import List
from openai import AsyncOpenAI

from agentscope_runtime.tools.modelstudio_memory import (
    AddMemory,
    SearchMemory,
    ListMemory,
    DeleteMemory,
    CreateProfileSchema,
    GetUserProfile,
    GetUserProfileInput,
    Message,
    AddMemoryInput,
    SearchMemoryInput,
    ListMemoryInput,
    DeleteMemoryInput,
    CreateProfileSchemaInput,
    ProfileAttribute,
    MemoryAPIError,
    MemoryAuthenticationError,
    MemoryNotFoundError,
    MemoryValidationError,
)

# ===== Configure logging to filter out verbose debug messages =====
# Read log level from environment variable, default to WARNING
LOG_LEVEL = os.getenv("LOG_LEVEL", "WARNING").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.WARNING),
    format=(
        "%(levelname)s: %(message)s"
        if LOG_LEVEL == "WARNING"
        else "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    ),
)

# Disable verbose logging for certain components
# (unless explicitly set to DEBUG)
if LOG_LEVEL != "DEBUG":
    logging.getLogger("agentscope_runtime").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        print(
            f"[ERROR] Required environment variable not set: {name}",
            file=sys.stderr,
        )
        sys.exit(1)
    return value


def get_env(name: str, default: str) -> str:
    value = os.getenv(name, default)
    return value


def truncate(text: str, length: int = 120) -> str:
    if text is None:
        return ""
    if len(text) <= length:
        return text
    return text[: length - 3] + "..."


def print_section(title: str) -> None:
    bar_str = "=" * 70
    print(f"\n{bar_str}\n{title}\n{bar_str}")


def print_info(message: str) -> None:
    print(f"[system_info] {message}")


def print_warn(message: str) -> None:
    print(f"[warn] {message}")


def print_success(message: str) -> None:
    print(f"[success] {message}")


def print_error(message: str) -> None:
    print(f"[ERROR] {message}")


def format_api_error(error: MemoryAPIError) -> str:
    """Format API error information for display"""
    parts = []

    # Extract error message body (excluding extra info added by __str__ method)
    error_message = str(error).split(" | ", maxsplit=1)[0]
    parts.append(f"Error: {error_message}")

    if error.error_code:
        parts.append(f"Error Code: {error.error_code}")

    if error.status_code:
        parts.append(f"HTTP Status: {error.status_code}")

    if error.request_id:
        parts.append(f"Request ID: {error.request_id}")

    return "\n          ".join(parts)


async def step_create_profile_schema(
    create_profile_schema: CreateProfileSchema,
) -> str:
    """Create user profile schema"""
    print_info(
        "User profile schema defines user attributes (e.g., age, hobbies).",
    )
    print("")

    payload = CreateProfileSchemaInput(
        name="User Profile (Demo)",
        description="Demo user profile schema",
        attributes=[
            ProfileAttribute(name="Age", description="User's age"),
            ProfileAttribute(
                name="Hobbies",
                description="User's interests and preferences",
            ),
        ],
    )

    # Display example parameters
    print_info("Request parameters:")
    print_info(f"  · Schema name: {payload.name}")
    print_info(f"  · Schema description: {payload.description}")
    print_info("  · Attributes:")
    for idx, attr in enumerate(payload.attributes, start=1):
        print_info(f"      [{idx}] {attr.name} - {attr.description}")
    print("")

    result = await create_profile_schema.arun(payload)
    print_success("✓ Profile schema created")
    print_info(f"  Schema ID: {result.profile_schema_id}")
    print_info(f"  Request ID: {result.request_id}")
    print("")

    return result.profile_schema_id


def example_messages() -> List[Message]:
    return [
        Message(
            role="user",
            content="Remind me to drink water at "
            "9am and review my notes at 3pm every day.",
        ),
        Message(role="assistant", content="Got it, I've noted that down."),
        Message(
            role="user",
            content=(
                "Also, remind me to buy a birthday gift "
                "for Mr. Smith tomorrow. Mr. Smith is turning "
                "30 this year, three years older than me. "
                "We share the same hobbies and "
                "often play soccer together, so I plan to "
                "buy him a nice soccer ball."
            ),
        ),
        Message(role="assistant", content="Sure, I'll remind you tomorrow."),
    ]


async def step_add_memory(
    add_memory: AddMemory,
    end_user_id: str,
    profile_schema_id: str,
) -> List[str]:
    """Add conversation memory to the memory service"""
    print_info(
        "We'll submit a conversation to the memory service.",
    )
    print_info("  1️⃣  Extract and save memory nodes")
    print_info("  2️⃣  Extract user profile information (age, hobbies, etc.)")
    print("")

    now_ts = int(time.time())
    msgs = example_messages()
    payload = AddMemoryInput(
        user_id=end_user_id,
        messages=msgs,
        timestamp=now_ts,
        profile_schema=profile_schema_id,
        meta_data={
            "location_name": "Hangzhou",
            "geo_coordinate": "120.1551,30.2741",
            "customized_key": "customized_value",
        },
    )

    # Display example parameters
    print_info("📥 Request parameters:")
    print_info(f"  · User ID: {payload.user_id}")
    print_info(f"  · Profile Schema ID: {truncate(profile_schema_id, 50)}")

    # Format timestamp
    timestamp_str = time.strftime(
        "%Y-%m-%d %H:%M:%S",
        time.localtime(payload.timestamp),
    )
    print_info(f"  · Timestamp: {timestamp_str}")
    print_info(f"  · Message count: {len(payload.messages)}")
    print("")

    print_info("💬 Conversation content (note profile information):")
    for idx, m in enumerate(payload.messages, start=1):
        role_icon = "👤" if m.role == "user" else "🤖"
        content_str = str(m.content)
        print(f"  {role_icon} [{m.role}] {truncate(content_str, 100)}")
    print("")
    print_info("  🎯 = Contains extractable profile information (age, hobbies)")
    print("")

    add_result = await add_memory.arun(payload)

    # Debug: Print return result type
    print_info(
        f"🔍 Debug info: memory_nodes type = {type(add_result.memory_nodes)}",
    )

    # Compatibility handling: convert memory_nodes to list if not already
    if isinstance(add_result.memory_nodes, list):
        memory_nodes_list = add_result.memory_nodes
    else:
        # If single object, wrap in list
        memory_nodes_list = (
            [add_result.memory_nodes] if add_result.memory_nodes else []
        )

    node_ids = [
        n.memory_node_id for n in memory_nodes_list if n.memory_node_id
    ]

    if node_ids:
        print_success(f"✓ Successfully added {len(node_ids)} memory nodes")
        print_info(f"  Request ID: {add_result.request_id}")
        print("")
        print_info("📝 Generated memory nodes:")
        print("")
        for idx, node in enumerate(memory_nodes_list, start=1):
            print(f"  [{idx}] Content: {truncate(node.content, 100)}")
            print(f"      ID: {node.memory_node_id}")
            print(f"      Event: {node.event}")
            if node.old_content:
                print(f"      Old content: {truncate(node.old_content, 100)}")

            if idx < len(memory_nodes_list):
                print("")
        print("")
    else:
        print_warn(
            "⚠ No memory node IDs returned, deletion step will be skipped.",
        )

    return node_ids


async def step_list_memory(
    list_memory: ListMemory,
    end_user_id: str,
    page_num: int = 1,
    page_size: int = 10,
) -> List[str]:
    """List all memory nodes for a user (paginated)"""
    print_info(
        "List all memory nodes currently saved for this user.",
    )
    print("")

    payload = ListMemoryInput(
        user_id=end_user_id,
        page_num=page_num,
        page_size=page_size,
    )

    # Display example parameters
    print_info("Request parameters:")
    print_info(f"  · User ID: {payload.user_id}")
    print_info(f"  · Page number: {payload.page_num}")
    print_info(f"  · Page size: {payload.page_size}")
    print("")

    result = await list_memory.arun(payload)
    total_pages = (
        (result.total + result.page_size - 1) // result.page_size
        if result.page_size
        else 1
    )

    print_success(
        f"✓ List retrieved successfully (Request ID: {result.request_id})",
    )
    print_info(
        f"📊 Pagination: Page {result.page_num}/{total_pages}, "
        f"{result.page_size} per page, {result.total} total",
    )
    print("")

    if not result.memory_nodes:
        print_info("(No memory nodes on this page)")
        return []

    print_info(
        f"📝 Memory node list ({len(result.memory_nodes)} on this page):",
    )
    print("")

    existing_ids = []
    for idx, node in enumerate(result.memory_nodes, start=1):
        existing_ids.append(node.memory_node_id or "")
        print(f"  [{idx}] {truncate(node.content, 100)}")
        print(f"      ID: {node.memory_node_id}")
        if idx < len(result.memory_nodes):
            print("")

    print("")
    return [nid for nid in existing_ids if nid]


async def step_search_memory_with_llm(
    search_memory: SearchMemory,
    llm_client: AsyncOpenAI,
    end_user_id: str,
):
    """Search memories and generate personalized response using LLM"""
    user_query = "What do I need to be reminded of today and tomorrow?"

    print_info(
        "We'll use a natural language query to search relevant memories, "
        "then let the LLM generate a personalized answer "
        "based on these memories.",
    )
    print("")

    # 1. Search memories
    print_info("🔍 Step 1: Search relevant memories")
    payload = SearchMemoryInput(
        user_id=end_user_id,
        messages=[Message(role="user", content=user_query)],
        top_k=5,
        min_score=0,
    )

    print_info("Search parameters:")
    print_info(f"  · User ID: {payload.user_id}")
    print_info(f"  · User query: {user_query}")
    print_info(f"  · Top K: {payload.top_k}")
    print_info(f"  · Min score: {payload.min_score}")
    print("")

    search_result = await search_memory.arun(payload)
    print_success(
        f"✓ Search completed (Request ID: {search_result.request_id})",
    )

    if not search_result.memory_nodes:
        print_warn("No relevant memory nodes found")
        return

    print_info(f"Found {len(search_result.memory_nodes)} relevant memories:")
    print("")

    hit_ids = []
    for idx, node in enumerate(search_result.memory_nodes, start=1):
        hit_ids.append(node.memory_node_id or "")
        print(f"  [{idx}] {truncate(node.content, 100)}")
        print(f"      ID: {node.memory_node_id}")

    print("")
    print("─" * 70)
    print("")

    # 2. Generate response using LLM
    print_info(
        "🤖 Step 2: Generate personalized answer using LLM "
        "based on retrieved memories",
    )
    print("")

    context_lines = [
        f"- {node.content}" for node in search_result.memory_nodes
    ]
    system_prompt = (
        "You are an assistant. "
        "Answer the user's question based on the "
        "following retrieved memories.\n\n"
        + "Memory content:\n"
        + ("\n".join(context_lines) if context_lines else "(No results)")
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_query},
    ]

    model_name = "qwen-max"

    print_info(f"Model: {model_name} (streaming)")
    print_info(f"Query: {user_query}")
    print("")
    print_success("Model response:")
    print("")
    print("  ", end="")

    stream = await llm_client.chat.completions.create(
        model=model_name,
        messages=messages,
        stream=True,
        stream_options={"include_usage": True},
    )

    async for chunk in stream:
        if chunk.choices:
            delta = chunk.choices[0].delta
            if delta.content:
                print(delta.content, end="", flush=True)

    print("")
    print("")

    return


async def step_get_user_profile(
    get_user_profile: GetUserProfile,
    schema_id: str,
    end_user_id: str,
) -> None:
    """Retrieve and display user profile information"""
    print_info("🎯 User Profile Feature Demo")
    print("")
    print_info(
        "💡 Note: The memory service automatically extracts "
        "user information from conversations and populates profile fields.",
    )
    print_info(
        "    For example: From 'Mr. Smith is turning 30, "
        "three years older than me' we can infer the user is 27",
    )
    print_info(
        "    From 'We often play soccer together' "
        "we can infer the user's hobby is soccer",
    )
    print("")

    payload = GetUserProfileInput(schema_id=schema_id, user_id=end_user_id)

    # Display example parameters
    print_info("📥 Request parameters:")
    print_info(f"  · Schema ID: {truncate(payload.schema_id, 50)}")
    print_info(f"  · User ID: {payload.user_id}")
    print("")

    result = await get_user_profile.arun(payload)
    print_success(
        f"✓ User profile retrieved (Request ID: {result.request_id})",
    )
    print("")

    # Display schema information
    print_info("📋 Schema information:")
    schema_name = result.profile.schema_name or "(Not set)"
    schema_desc = result.profile.schema_description or "(Not set)"
    print_info(f"  Name: {schema_name}")
    print_info(f"  Description: {schema_desc}")
    print("")

    # Display user profile
    if result.profile.attributes:
        print_info(
            f"👤 User profile ({len(result.profile.attributes)} fields):",
        )
        print("")

        for idx, attr in enumerate(result.profile.attributes, start=1):
            value_display = attr.value if attr.value else "(Not extracted yet)"

            print_info(f"  [{idx}] {attr.name}")
            print_info(f"      Value: {value_display}")
            print_info(f"      ID: {attr.id}")

            # Separator (except for last item)
            if idx < len(result.profile.attributes):
                print("")

        print("")

        # If any fields are filled, add note
        has_values = any(attr.value for attr in result.profile.attributes)
        if has_values:
            print_success(
                "💡 Tip: The above profile information was automatically "
                "extracted from conversations by the memory service!",
            )
        else:
            print_info(
                "💡 Tip: Profile fields not yet populated. "
                "They will be filled as more conversations accumulate.",
            )
        print("")
    else:
        print_info("(No profile fields)")
        print("")


async def step_delete_memory(
    delete_memory: DeleteMemory,
    end_user_id: str,
    node_ids: List[str],
) -> None:
    """Delete specified memory nodes"""
    print_info(
        "Delete the memory nodes we just added to demonstrate data cleanup.",
    )
    print("")

    if not node_ids:
        print_warn("⚠ No nodes to delete, skipping this step.")
        return

    # Display example parameters
    print_info("Request parameters:")
    print_info(f"  · User ID: {end_user_id}")
    print_info(f"  · Nodes to delete: {len(node_ids)}")
    print("")

    print_info(f"🗑️  Deleting {len(node_ids)} memory nodes...")
    print("")

    for idx, node_id in enumerate(node_ids, start=1):
        result = await delete_memory.arun(
            DeleteMemoryInput(user_id=end_user_id, memory_node_id=node_id),
        )
        print_success(
            f"  ✓ [{idx}/{len(node_ids)}] Deleted: {truncate(node_id, 50)}",
        )
        print_info(f"      Request ID: {result.request_id}")

    print("")
    print_success(f"✓ All deletions completed, {len(node_ids)} nodes deleted")


async def main() -> None:  # pylint: disable=too-many-statements
    # Required envs
    dashscope_api_key = require_env("DASHSCOPE_API_KEY")

    # Generate random user ID if not set
    end_user_id = get_env("END_USER_ID", "")
    if not end_user_id:
        mmdd = datetime.now().strftime("%m%d")
        user_uuid = str(uuid.uuid4())[:8]
        end_user_id = f"modelstudio_memory_user_{mmdd}_{user_uuid}"
        print_info(f"User ID: {end_user_id}")
        print("")

    llm_base_url = get_env(
        "LLM_BASE_URL",
        "https://dashscope.aliyuncs.com/compatible-mode/v1",
    )

    # Initialize components
    add_memory = AddMemory()
    search_memory = SearchMemory()
    list_memory = ListMemory()
    delete_memory = DeleteMemory()
    create_profile_schema = CreateProfileSchema()
    get_user_profile = GetUserProfile()

    # Initialize OpenAI client
    llm_client = AsyncOpenAI(
        api_key=dashscope_api_key,
        base_url=llm_base_url,
    )

    try:
        print_section("Demo 0: Create Profile Schema")
        try:
            schema_id = await step_create_profile_schema(create_profile_schema)
        except (
            MemoryAPIError,
            MemoryAuthenticationError,
            MemoryValidationError,
        ) as e:
            print_error("❌ Failed to create profile schema:")
            print_error(f"    {format_api_error(e)}")
            print_error(
                "\n💡 Tip: Please check if your API Key is correct, "
                "or contact support with the Request ID",
            )
            return

        print_section("Demo 1: Add Memory")
        try:
            node_ids = await step_add_memory(
                add_memory,
                end_user_id,
                schema_id,
            )
        except (
            MemoryAPIError,
            MemoryAuthenticationError,
            MemoryValidationError,
        ) as e:
            print_error("❌ Failed to add memory:")
            print_error(f"    {format_api_error(e)}")
            print_error(
                "\n💡 Tip: Please check if your parameters are correct, "
                "or contact support with the Request ID",
            )
            return

        # Wait for consistency
        print("")
        print_info("⏳ Waiting for memory generation (3 seconds)...")
        await asyncio.sleep(3)
        print("")

        # 2. List memory
        print_section("Demo 2: List Memory")
        try:
            await step_list_memory(list_memory, end_user_id)
        except (
            MemoryAPIError,
            MemoryAuthenticationError,
            MemoryValidationError,
        ) as e:
            print_error("❌ Failed to list memory:")
            print_error(f"    {format_api_error(e)}")
            # Non-critical step, can continue

        print_section("Demo 3: Search Memory + LLM Answer")
        try:
            await step_search_memory_with_llm(
                search_memory,
                llm_client,
                end_user_id,
            )
        except (
            MemoryAPIError,
            MemoryAuthenticationError,
            MemoryValidationError,
        ) as e:
            print_error("❌ Failed to search memory:")
            print_error(f"    {format_api_error(e)}")
            # Non-critical step, can continue

        # Wait for profile extraction to complete
        print("")
        print_info(
            "⏳ Waiting for profile extraction to complete (2 seconds)...",
        )
        print_info(
            "   Memory service is extracting user info "
            "from conversations (age, hobbies, etc.)...",
        )
        await asyncio.sleep(2)
        print("")

        print_section("Demo 4: Get User Profile (show auto-extracted profile)")
        try:
            await step_get_user_profile(
                get_user_profile,
                schema_id,
                end_user_id,
            )
        except (
            MemoryAPIError,
            MemoryAuthenticationError,
            MemoryValidationError,
            MemoryNotFoundError,
        ) as e:
            print_error("❌ Failed to get user profile:")
            print_error(f"    {format_api_error(e)}")
            # Non-critical step, can continue

        print_section("Demo 5: Delete Memory")
        try:
            await step_delete_memory(delete_memory, end_user_id, node_ids)
        except (
            MemoryAPIError,
            MemoryAuthenticationError,
            MemoryValidationError,
        ) as e:
            print_error("❌ Failed to delete memory:")
            print_error(f"    {format_api_error(e)}")
            # Non-critical step, can continue

        # Wait for consistency
        print("")
        print_info("⏳ Waiting for deletion to take effect (2 seconds)...")
        await asyncio.sleep(2)
        print("")

        print_section("Demo 6: List Memory Again (verify deletion)")
        try:
            await step_list_memory(list_memory, end_user_id)
        except (
            MemoryAPIError,
            MemoryAuthenticationError,
            MemoryValidationError,
        ) as e:
            print_error("❌ Failed to list memory:")
            print_error(f"    {format_api_error(e)}")

        print("")
        print("=" * 70)
        print_success("🎉 All demo steps completed!")
        print("=" * 70)

    finally:
        # Cleanup: close all HTTP connections
        print("")
        print_info("🔄 Cleaning up resources...")
        await add_memory.close()
        await search_memory.close()
        await list_memory.close()
        await delete_memory.close()
        await create_profile_schema.close()
        await get_user_profile.close()
        await llm_client.close()
        print_info("✓ Resource cleanup completed")


if __name__ == "__main__":
    asyncio.run(main())
