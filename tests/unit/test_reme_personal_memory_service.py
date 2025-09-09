# -*- coding: utf-8 -*-
# pylint: disable=redefined-outer-name, protected-access
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
from agentscope_runtime.engine.services.reme_personal_memory_service import (
    ReMePersonalMemoryService,
)

mock_mode: bool = True


def create_message(role: str, content: str) -> Message:
    """Helper function to create a proper Message object."""
    return Message(
        type=MessageType.MESSAGE,
        role=role,
        content=[TextContent(type=ContentType.TEXT, text=content)],
    )


@pytest_asyncio.fixture
async def memory_service():
    """Create and setup ReMePersonalMemoryService for testing."""
    service = None
    try:
        if not mock_mode:
            load_dotenv()

        service = ReMePersonalMemoryService(mock_mode=mock_mode)
        await service.start()

        # Check if service is healthy
        healthy = await service.health()
        if not healthy:
            pytest.skip("ReMePersonalMemoryService is not available")

        yield service

    except ImportError as e:
        import traceback

        traceback.print_exc()
        pytest.skip(f"Missing dependencies for ReMePersonalMemoryService: {e}")

    except FileNotFoundError as e:
        if ".env not found" in str(e):
            pytest.skip("ReMePersonalMemoryService requires .env file")
        else:
            pytest.skip(f"Missing file for ReMePersonalMemoryService: {e}")

    except Exception as e:
        import traceback

        traceback.print_exc()
        pytest.skip(f"Failed to initialize ReMePersonalMemoryService: {e}")

    finally:
        if service is not None:
            await service.stop()


@pytest.mark.asyncio
async def test_service_lifecycle(memory_service: ReMePersonalMemoryService):
    """Test service start/stop lifecycle."""
    assert await memory_service.health() is True
    await memory_service.stop()
    # Note: ReMePersonalMemoryService.health() always returns True
    # so we can't test the stopped state like Redis


@pytest.mark.asyncio
async def test_add_and_search_memory_no_session(
    memory_service: ReMePersonalMemoryService,
):
    """Test adding and searching memory without session ID."""
    user_id = "test_user1"
    messages = [create_message(Role.USER, "I love playing basketball")]

    # Add memory
    await memory_service.add_memory(user_id, messages)

    # Search memory
    search_query = [create_message(Role.USER, "What sports do I like?")]
    retrieved = await memory_service.search_memory(user_id, search_query)

    # ReMePersonalMemoryService returns different format than Redis
    assert retrieved is not None
    assert len(retrieved) > 0


@pytest.mark.asyncio
async def test_add_and_search_memory_with_session(
    memory_service: ReMePersonalMemoryService,
):
    """Test adding and searching memory with session ID."""
    user_id = "test_user2"
    session_id = "session1"
    messages = [
        create_message(Role.USER, "I enjoy reading science fiction books"),
    ]

    # Add memory with session
    await memory_service.add_memory(user_id, messages, session_id)

    # Search memory
    search_query = [create_message(Role.USER, "What books do I like?")]
    retrieved = await memory_service.search_memory(user_id, search_query)

    assert retrieved is not None
    assert len(retrieved) > 0


@pytest.mark.asyncio
async def test_search_memory_with_filters(
    memory_service: ReMePersonalMemoryService,
):
    """Test searching memory with filters like top_k."""
    user_id = "test_user3"
    messages = [
        create_message(Role.USER, "I like swimming"),
        create_message(Role.USER, "I enjoy running"),
        create_message(Role.USER, "I love cycling"),
    ]

    # Add multiple memories
    for i, msg in enumerate(messages):
        await memory_service.add_memory(user_id, [msg], f"session_{i}")

    # Search with top_k filter
    search_query = [create_message(Role.USER, "What activities do I like?")]
    retrieved = await memory_service.search_memory(
        user_id,
        search_query,
        filters={"top_k": 2},
    )

    assert retrieved is not None


@pytest.mark.asyncio
async def test_list_memory(memory_service: ReMePersonalMemoryService):
    """Test listing memory for a user."""
    user_id = "test_user4"
    messages = [
        create_message(Role.USER, "I work as a software engineer"),
        create_message(Role.USER, "I live in San Francisco"),
    ]

    # Add memories
    for i, msg in enumerate(messages):
        await memory_service.add_memory(user_id, [msg], f"session_{i}")

    # List memory
    listed = await memory_service.list_memory(user_id)

    assert listed is not None
    assert isinstance(listed, list)


@pytest.mark.asyncio
async def test_list_memory_with_filters(
    memory_service: ReMePersonalMemoryService,
):
    """Test listing memory with filters."""
    user_id = "test_user5"
    messages = [
        create_message(Role.USER, f"Memory item {i}") for i in range(5)
    ]

    # Add multiple memories
    for i, msg in enumerate(messages):
        await memory_service.add_memory(user_id, [msg], f"session_{i}")

    listed = await memory_service.list_memory(
        user_id,
        filters={"page_size": 3, "page_num": 1},
    )

    assert listed is not None
    assert isinstance(listed, list)


@pytest.mark.asyncio
async def test_delete_memory_session(
    memory_service: ReMePersonalMemoryService,
):
    """Test deleting memory by session ID."""
    user_id = "test_user6"
    session_id = "session_to_delete"

    # Add memory
    msg1 = create_message(Role.USER, "This should be deleted")
    msg2 = create_message(Role.USER, "This should remain")

    await memory_service.add_memory(user_id, [msg1], session_id)
    await memory_service.add_memory(user_id, [msg2], "another_session")

    # Delete specific session
    await memory_service.delete_memory(user_id, session_id)

    # Verify deletion (note: ReMePersonalMemoryService implementation may vary)
    # This is mainly to test that the method doesn't raise errors


@pytest.mark.asyncio
async def test_delete_memory_user(
    memory_service: ReMePersonalMemoryService,
):
    """Test deleting all memory for a user."""
    user_id = "test_user_to_delete"

    # Add some memory
    await memory_service.add_memory(
        user_id,
        [create_message(Role.USER, "Some memory to delete")],
    )

    # Delete all user memory
    await memory_service.delete_memory(user_id)

    # This mainly tests that the method doesn't raise errors


@pytest.mark.asyncio
async def test_operations_on_non_existent_user(
    memory_service: ReMePersonalMemoryService,
):
    """Test operations on non-existent user."""
    user_id = "non_existent_user"

    # Search on non-existent user should not raise errors
    retrieved = await memory_service.search_memory(
        user_id,
        [create_message(Role.USER, "any query")],
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
async def test_message_format_compatibility(
    memory_service: ReMePersonalMemoryService,
):
    """Test that the service handles different message formats."""
    user_id = "test_user_formats"

    # Test with Message objects
    message_obj = create_message(Role.USER, "Message as object")
    await memory_service.add_memory(user_id, [message_obj])

    # Test with dict format (if supported)
    try:
        message_dict = {"content": "Message as dict", "role": "user"}
        await memory_service.add_memory(user_id, [message_dict])
    except Exception:
        # If dict format is not supported, that's okay
        pass

    # Search should work
    search_query = [create_message(Role.USER, "What messages do I have?")]
    retrieved = await memory_service.search_memory(user_id, search_query)

    assert retrieved is not None
