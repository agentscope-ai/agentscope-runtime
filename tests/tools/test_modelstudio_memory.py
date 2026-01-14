# -*- coding: utf-8 -*-
# pylint:disable=redefined-outer-name

import asyncio
import os
import uuid
from datetime import datetime

import pytest

from agentscope_runtime.tools.modelstudio_memory import (
    AddMemory,
    AddMemoryInput,
    AddMemoryOutput,
    CreateProfileSchema,
    CreateProfileSchemaInput,
    CreateProfileSchemaOutput,
    DeleteMemory,
    DeleteMemoryInput,
    DeleteMemoryOutput,
    GetUserProfile,
    GetUserProfileInput,
    GetUserProfileOutput,
    ListMemory,
    ListMemoryInput,
    ListMemoryOutput,
    Message,
    MemoryNode,
    ProfileAttribute,
    SearchMemory,
    SearchMemoryInput,
    SearchMemoryOutput,
)

NO_DASHSCOPE_KEY = os.getenv("DASHSCOPE_API_KEY", "") == ""


def generate_test_user_id() -> str:
    """Generate a unique test user ID for each test run."""
    mmdd = datetime.now().strftime("%m%d")
    user_uuid = str(uuid.uuid4())[:8]
    return f"test_memory_user_{mmdd}_{user_uuid}"


@pytest.fixture
def add_memory_component():
    """Fixture for AddMemory component."""
    component = AddMemory()
    yield component


@pytest.fixture
def search_memory_component():
    """Fixture for SearchMemory component."""
    component = SearchMemory()
    yield component


@pytest.fixture
def list_memory_component():
    """Fixture for ListMemory component."""
    component = ListMemory()
    yield component


@pytest.fixture
def delete_memory_component():
    """Fixture for DeleteMemory component."""
    component = DeleteMemory()
    yield component


@pytest.fixture
def create_profile_schema_component():
    """Fixture for CreateProfileSchema component."""
    component = CreateProfileSchema()
    yield component


@pytest.fixture
def get_user_profile_component():
    """Fixture for GetUserProfile component."""
    component = GetUserProfile()
    yield component


@pytest.mark.asyncio
@pytest.mark.skipif(
    NO_DASHSCOPE_KEY,
    reason="DASHSCOPE_API_KEY not set",
)
async def test_add_memory_success(add_memory_component):
    """Test adding a memory node."""
    test_user_id = generate_test_user_id()

    # Prepare test data
    messages = [
        Message(role="user", content="I love playing basketball on weekends"),
        Message(
            role="assistant",
            content="That's great! Basketball is a fun and healthy activity.",
        ),
    ]

    input_data = AddMemoryInput(
        user_id=test_user_id,
        messages=messages,
        meta_data={"source": "pytest", "test": "add_memory"},
    )

    result = await add_memory_component.arun(input_data)

    # Assertions
    assert isinstance(result, AddMemoryOutput)
    assert isinstance(result.memory_nodes, list)
    if result.memory_nodes:
        for node in result.memory_nodes:
            assert isinstance(node, MemoryNode)


@pytest.mark.asyncio
@pytest.mark.skipif(
    NO_DASHSCOPE_KEY,
    reason="DASHSCOPE_API_KEY not set",
)
async def test_search_memory_success(search_memory_component):
    """Test searching memory nodes."""
    test_user_id = generate_test_user_id()

    # SearchMemoryInput requires messages for context
    messages = [
        Message(role="user", content="basketball"),
    ]

    input_data = SearchMemoryInput(
        user_id=test_user_id,
        messages=messages,
        top_k=5,
    )

    result = await search_memory_component.arun(input_data)

    # Assertions
    assert isinstance(result, SearchMemoryOutput)
    assert isinstance(result.memory_nodes, list)
    if result.memory_nodes:
        for node in result.memory_nodes:
            assert isinstance(node, MemoryNode)


@pytest.mark.asyncio
@pytest.mark.skipif(
    NO_DASHSCOPE_KEY,
    reason="DASHSCOPE_API_KEY not set",
)
async def test_list_memory_success(list_memory_component):
    """Test listing memory nodes with pagination."""
    test_user_id = generate_test_user_id()

    input_data = ListMemoryInput(
        user_id=test_user_id,
        page_size=10,
        page_num=1,
    )

    result = await list_memory_component.arun(input_data)

    # Assertions
    assert isinstance(result, ListMemoryOutput)
    assert isinstance(result.memory_nodes, list)
    assert isinstance(result.total, int)
    if result.total >= 0:
        for node in result.memory_nodes:
            assert isinstance(node, MemoryNode)


@pytest.mark.asyncio
@pytest.mark.skipif(
    NO_DASHSCOPE_KEY,
    reason="DASHSCOPE_API_KEY not set",
)
async def test_delete_memory_success(
    add_memory_component,
    delete_memory_component,
):
    """Test deleting a memory node."""
    test_user_id = generate_test_user_id()

    # First, add a memory node
    messages = [
        Message(role="user", content="Remember that I like playing football"),
        Message(role="assistant", content="Understood, test message received"),
    ]

    add_input = AddMemoryInput(
        user_id=test_user_id,
        messages=messages,
        meta_data={"test": "delete_memory"},
    )

    add_result = await add_memory_component.arun(add_input)

    # Wait for several seconds for the memory to be processed
    await asyncio.sleep(3)
    if add_result.memory_nodes:
        memory_node_id = add_result.memory_nodes[0].memory_node_id

        # Now delete it
        delete_input = DeleteMemoryInput(
            user_id=test_user_id,
            memory_node_id=memory_node_id,
        )

        result = await delete_memory_component.arun(delete_input)

        # Assertions
        assert isinstance(result, DeleteMemoryOutput)
        assert result.request_id is not None


@pytest.mark.asyncio
@pytest.mark.skipif(
    NO_DASHSCOPE_KEY,
    reason="DASHSCOPE_API_KEY not set",
)
async def test_create_profile_schema_success(create_profile_schema_component):
    """Test creating a user profile schema."""
    # Generate unique schema name
    mmdd = datetime.now().strftime("%m%d%H%M%S")
    schema_name = f"test_schema_{mmdd}"

    # Define profile attributes
    attributes = [
        ProfileAttribute(
            name="age",
            description="User's age",
        ),
        ProfileAttribute(
            name="occupation",
            description="User's occupation or job title",
        ),
        ProfileAttribute(
            name="hobbies",
            description="User's hobbies and interests",
        ),
    ]

    input_data = CreateProfileSchemaInput(
        name=schema_name,
        description="Test profile schema for pytest",
        attributes=attributes,
    )

    # Call the async run method
    result = await create_profile_schema_component.arun(input_data)

    # Assertions
    assert isinstance(result, CreateProfileSchemaOutput)
    assert result.profile_schema_id is not None


@pytest.mark.asyncio
@pytest.mark.skipif(
    NO_DASHSCOPE_KEY,
    reason="DASHSCOPE_API_KEY not set",
)
async def test_get_user_profile_success(
    create_profile_schema_component,
    get_user_profile_component,
):
    """Test retrieving a user profile."""
    test_user_id = generate_test_user_id()

    # First, create a profile schema
    mmdd = datetime.now().strftime("%m%d%H%M%S")
    schema_name = f"test_profile_schema_{mmdd}"

    attributes = [
        ProfileAttribute(
            name="test_field",
            description="Test field",
        ),
    ]

    schema_input = CreateProfileSchemaInput(
        name=schema_name,
        attributes=attributes,
    )

    schema_result = await create_profile_schema_component.arun(schema_input)
    schema_id = schema_result.profile_schema_id

    # Now get the user profile
    input_data = GetUserProfileInput(
        schema_id=schema_id,
        user_id=test_user_id,
    )

    result = await get_user_profile_component.arun(input_data)

    # Assertions
    assert isinstance(result, GetUserProfileOutput)
    if result.profile is not None:
        assert isinstance(result.profile.attributes, list)
