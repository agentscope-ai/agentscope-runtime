# -*- coding: utf-8 -*-

import os

import pytest
import pytest_asyncio
from dotenv import load_dotenv

from agentscope_runtime.engine.schemas.agent_schemas import (
    Message,
    MessageType,
    TextContent,
    ContentType,
    Role,
)
from agentscope_runtime.engine.services.reme_task_memory_service import (
    ReMeTaskMemoryService,
)


def create_message(role: str, content: str) -> Message:
    """Helper function to create a proper Message object."""
    return Message(
        type=MessageType.MESSAGE,
        role=role,
        content=[TextContent(type=ContentType.TEXT, text=content)],
    )


def load_test_env():
    """Load environment variables for testing."""
    # Load from .env file if exists
    load_dotenv()

    # Set required environment variables for ReMeTaskMemoryService
    required_env_vars = [
        "FLOW_EMBEDDING_API_KEY",
        "FLOW_EMBEDDING_BASE_URL",
        "FLOW_LLM_API_KEY",
        "FLOW_LLM_BASE_URL"
    ]

    # Set default values if not already set
    env_defaults = {
        "FLOW_EMBEDDING_API_KEY": "sk-test-key",
        "FLOW_EMBEDDING_BASE_URL": "https://api.test.com/v1",
        "FLOW_LLM_API_KEY": "sk-test-key",
        "FLOW_LLM_BASE_URL": "https://api.test.com/v1"
    }

    for var in required_env_vars:
        print(f"Checking environment variable: {os.getenv(var)}")
        if not os.getenv(var):
            os.environ[var] = env_defaults[var]


@pytest_asyncio.fixture
async def memory_service():
    """Create and setup ReMeTaskMemoryService for testing."""
    # Load environment variables
    load_test_env()

    service = None
    try:
        print("Creating ReMeTaskMemoryService...")
        service = ReMeTaskMemoryService()
        print("Starting service...")
        await service.start()

        # Check if service is healthy
        print("Checking service health...")
        healthy = await service.health()
        if not healthy:
            pytest.skip("ReMeTaskMemoryService is not available")

        print("Service is ready!")
        yield service

    except ImportError as e:
        print(f"ImportError details: {e}")
        import traceback
        traceback.print_exc()
        pytest.skip(f"Missing dependencies for ReMeTaskMemoryService: {e}")

    except FileNotFoundError as e:
        if ".env not found" in str(e):
            pytest.skip("ReMeTaskMemoryService requires .env file")
        else:
            pytest.skip(f"Missing file for ReMeTaskMemoryService: {e}")

    except Exception as e:
        print(f"General error details: {e}")
        import traceback
        traceback.print_exc()
        pytest.skip(f"Failed to initialize ReMeTaskMemoryService: {e}")

    finally:
        try:
            if service is not None:
                await service.stop()
        except Exception as e:
            print(f"Cleanup error: {e}")


@pytest.mark.asyncio
async def test_service_lifecycle(memory_service: ReMeTaskMemoryService):
    """Test service start/stop lifecycle."""
    assert await memory_service.health() is True
    await memory_service.stop()
    # Note: ReMeTaskMemoryService.health() always returns True
    # so we can't test the stopped state like Redis


@pytest.mark.asyncio
async def test_add_and_search_task_memory_no_session(
        memory_service: ReMeTaskMemoryService,
):
    """Test adding and searching task memory without session ID."""
    user_id = "test_user1"
    messages = [create_message(Role.USER, "I need to complete a web search task for financial news")]

    # Add memory
    await memory_service.add_memory(user_id, messages)

    # Search memory
    search_query = [create_message(Role.USER, "What tasks do I need to complete?")]
    retrieved = await memory_service.search_memory(user_id, search_query)

    # ReMeTaskMemoryService returns different format than Redis
    assert retrieved is not None
    assert len(retrieved) > 0


@pytest.mark.asyncio
async def test_add_and_search_task_memory_with_session(
        memory_service: ReMeTaskMemoryService,
):
    """Test adding and searching task memory with session ID."""
    user_id = "test_user2"
    session_id = "session1"
    messages = [create_message(Role.USER, "I need to analyze market trends using data analysis tools")]

    # Add memory with session
    await memory_service.add_memory(user_id, messages, session_id)

    # Search memory
    search_query = [create_message(Role.USER, "What analysis tasks do I have?")]
    retrieved = await memory_service.search_memory(user_id, search_query)

    assert retrieved is not None
    assert len(retrieved) > 0


@pytest.mark.asyncio
async def test_search_task_memory_with_filters(
        memory_service: ReMeTaskMemoryService,
):
    """Test searching task memory with filters like top_k."""
    user_id = "test_user3"
    messages = [
        create_message(Role.USER, "I need to use web search tool for news"),
        create_message(Role.USER, "I need to use code execution tool for analysis"),
        create_message(Role.USER, "I need to use file management tool for organization")
    ]

    # Add multiple task memories
    for i, msg in enumerate(messages):
        await memory_service.add_memory(user_id, [msg], f"session_{i}")

    # Search with top_k filter
    search_query = [create_message(Role.USER, "What tools do I need to use?")]
    retrieved = await memory_service.search_memory(
        user_id,
        search_query,
        filters={"top_k": 2}
    )

    assert retrieved is not None
    # Note: ReMeTaskMemoryService may return different number than requested
    # due to its internal implementation


@pytest.mark.asyncio
async def test_list_task_memory(memory_service: ReMeTaskMemoryService):
    """Test listing task memory for a user."""
    user_id = "test_user4"
    messages = [
        create_message(Role.USER, "I need to complete a data processing task"),
        create_message(Role.USER, "I need to generate a report using visualization tools")
    ]

    # Add task memories
    for i, msg in enumerate(messages):
        await memory_service.add_memory(user_id, [msg], f"session_{i}")

    # List memory
    listed = await memory_service.list_memory(user_id)

    assert listed is not None
    assert isinstance(listed, list)


@pytest.mark.asyncio
async def test_list_task_memory_with_filters(
        memory_service: ReMeTaskMemoryService,
):
    """Test listing task memory with filters."""
    user_id = "test_user5"
    messages = [create_message(Role.USER, f"Task memory item {i}") for i in range(2)]

    # Add multiple task memories
    for i, msg in enumerate(messages):
        await memory_service.add_memory(user_id, [msg], f"session_{i}")

    # List with filters (though ReMeTaskMemoryService may not support pagination)
    listed = await memory_service.list_memory(
        user_id,
        filters={"page_size": 3, "page_num": 1}
    )

    assert listed is not None
    assert isinstance(listed, list)


@pytest.mark.asyncio
async def test_delete_task_memory_session(
        memory_service: ReMeTaskMemoryService,
):
    """Test deleting task memory by session ID."""
    user_id = "test_user6"
    session_id = "session_to_delete"

    # Add task memory
    msg1 = create_message(Role.USER, "This task should be deleted")
    msg2 = create_message(Role.USER, "This task should remain")

    await memory_service.add_memory(user_id, [msg1], session_id)
    await memory_service.add_memory(user_id, [msg2], "another_session")

    # Delete specific session
    await memory_service.delete_memory(user_id, session_id)

    # Verify deletion (note: ReMeTaskMemoryService implementation may vary)
    # This is mainly to test that the method doesn't raise errors


@pytest.mark.asyncio
async def test_delete_task_memory_user(
        memory_service: ReMeTaskMemoryService,
):
    """Test deleting all task memory for a user."""
    user_id = "test_user_to_delete"

    # Add some task memory
    await memory_service.add_memory(
        user_id,
        [create_message(Role.USER, "Some task memory to delete")]
    )

    # Delete all user memory
    await memory_service.delete_memory(user_id)

    # This mainly tests that the method doesn't raise errors


@pytest.mark.asyncio
async def test_operations_on_non_existent_user(
        memory_service: ReMeTaskMemoryService,
):
    """Test operations on non-existent user."""
    user_id = "non_existent_user"

    # Search on non-existent user should not raise errors
    retrieved = await memory_service.search_memory(
        user_id,
        [create_message(Role.USER, "any task query")]
    )

    # Should return something (empty or error message)
    assert retrieved is not None

    # List on non-existent user
    listed = await memory_service.list_memory(user_id)
    assert listed is not None

    # Delete operations should not raise errors
    await memory_service.delete_memory(user_id)
    await memory_service.delete_memory(user_id, "some_session")


@pytest.mark.asyncio
async def test_task_message_format_compatibility(
        memory_service: ReMeTaskMemoryService,
):
    """Test that the service handles different message formats for tasks."""
    user_id = "test_user_formats"

    # Test with Message objects
    message_obj = create_message(Role.USER, "Task message as object")
    await memory_service.add_memory(user_id, [message_obj])

    # Test with dict format (if supported)
    try:
        message_dict = {"content": "Task message as dict", "role": "user"}
        await memory_service.add_memory(user_id, [message_dict])
    except Exception:
        # If dict format is not supported, that's okay
        pass

    # Search should work
    search_query = [create_message(Role.USER, "What task messages do I have?")]
    retrieved = await memory_service.search_memory(user_id, search_query)

    assert retrieved is not None


@pytest.mark.asyncio
async def test_task_specific_scenarios(
        memory_service: ReMeTaskMemoryService,
):
    """Test task-specific scenarios that differ from personal memory."""
    user_id = "test_task_user"
    
    # Test task-oriented messages
    task_messages = [
        create_message(Role.USER, "please use web search tool to search financial news"),
        create_message(Role.USER, "execute python code to analyze the data"),
        create_message(Role.USER, "use file management tool to organize results")
    ]

    # Add task memories
    for i, msg in enumerate(task_messages):
        await memory_service.add_memory(user_id, [msg], f"task_session_{i}")

    # Search for tool-related tasks
    tool_query = [create_message(Role.USER, "What tools should I use?")]
    tool_results = await memory_service.search_memory(user_id, tool_query)
    
    assert tool_results is not None
    assert len(tool_results) > 0

    # Search for specific task types
    search_query = [create_message(Role.USER, "What search tasks do I have?")]
    search_results = await memory_service.search_memory(user_id, search_query)
    
    assert search_results is not None

    # List all task memories
    all_tasks = await memory_service.list_memory(user_id)
    assert all_tasks is not None
    assert isinstance(all_tasks, list)
