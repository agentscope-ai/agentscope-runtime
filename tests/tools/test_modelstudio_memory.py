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
    AttributeOperation,
    CreateProfileSchema,
    CreateProfileSchemaInput,
    CreateProfileSchemaOutput,
    DeleteEntity,
    DeleteEntityInput,
    DeleteEntityOutput,
    DeleteMemory,
    DeleteMemoryInput,
    DeleteMemoryOutput,
    DeleteProfileSchema,
    DeleteProfileSchemaInput,
    DeleteProfileSchemaOutput,
    GetProfileSchema,
    GetProfileSchemaInput,
    GetProfileSchemaOutput,
    GetUserProfile,
    GetUserProfileInput,
    GetUserProfileOutput,
    ListMemory,
    ListMemoryInput,
    ListMemoryOutput,
    ListProfileSchemas,
    ListProfileSchemasInput,
    ListProfileSchemasOutput,
    Message,
    MemoryNode,
    ProfileAttribute,
    SearchMemory,
    SearchMemoryInput,
    SearchMemoryOutput,
    UpdateMemory,
    UpdateMemoryInput,
    UpdateMemoryOutput,
    UpdateProfileSchema,
    UpdateProfileSchemaInput,
    UpdateProfileSchemaOutput,
)

NO_DASHSCOPE_KEY = os.getenv("DASHSCOPE_API_KEY", "") == ""


# ==================== Helpers ====================


def _generate_user_id() -> str:
    """Generate a unique test user ID."""
    short_uuid = str(uuid.uuid4())[:8]
    return f"test_user_{short_uuid}"


def _generate_schema_name(prefix: str = "s") -> str:
    """Generate a unique schema name (max 32 chars)."""
    ts = datetime.now().strftime("%m%d%H%M%S")
    short_uuid = str(uuid.uuid4())[:4]
    return f"{prefix}_{ts}_{short_uuid}"


# ==================== Fixtures ====================


@pytest.fixture
async def test_user_id():
    """Fixture that generates a user ID and deletes the entity on teardown."""
    user_id = _generate_user_id()
    yield user_id

    # Cleanup: delete the entity after test
    delete_entity = DeleteEntity()
    try:
        await delete_entity.arun(
            DeleteEntityInput(
                entity_type="user",
                entity_id=user_id,
            ),
        )
    except Exception:
        pass
    await delete_entity.close()


@pytest.fixture
async def add_memory_component():
    """Fixture for AddMemory component."""
    component = AddMemory()
    yield component
    await component.close()


@pytest.fixture
async def search_memory_component():
    """Fixture for SearchMemory component."""
    component = SearchMemory()
    yield component
    await component.close()


@pytest.fixture
async def list_memory_component():
    """Fixture for ListMemory component."""
    component = ListMemory()
    yield component
    await component.close()


@pytest.fixture
async def delete_memory_component():
    """Fixture for DeleteMemory component."""
    component = DeleteMemory()
    yield component
    await component.close()


@pytest.fixture
async def create_profile_schema_component():
    """Fixture for CreateProfileSchema component."""
    component = CreateProfileSchema()
    yield component
    await component.close()


@pytest.fixture
async def get_user_profile_component():
    """Fixture for GetUserProfile component."""
    component = GetUserProfile()
    yield component
    await component.close()


@pytest.fixture
async def get_profile_schema_component():
    """Fixture for GetProfileSchema component."""
    component = GetProfileSchema()
    yield component
    await component.close()


@pytest.fixture
async def list_profile_schemas_component():
    """Fixture for ListProfileSchemas component."""
    component = ListProfileSchemas()
    yield component
    await component.close()


@pytest.fixture
async def delete_profile_schema_component():
    """Fixture for DeleteProfileSchema component."""
    component = DeleteProfileSchema()
    yield component
    await component.close()


@pytest.fixture
async def update_profile_schema_component():
    """Fixture for UpdateProfileSchema component."""
    component = UpdateProfileSchema()
    yield component
    await component.close()


@pytest.fixture
async def update_memory_component():
    """Fixture for UpdateMemory component."""
    component = UpdateMemory()
    yield component
    await component.close()


@pytest.fixture
async def delete_entity_component():
    """Fixture for DeleteEntity component."""
    component = DeleteEntity()
    yield component
    await component.close()


# ==================== Memory Tests ====================


@pytest.mark.asyncio
@pytest.mark.skipif(NO_DASHSCOPE_KEY, reason="DASHSCOPE_API_KEY not set")
async def test_add_memory_success(add_memory_component, test_user_id):
    """Test adding a memory node."""
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

    assert isinstance(result, AddMemoryOutput)
    assert isinstance(result.memory_nodes, list)
    if result.memory_nodes:
        for node in result.memory_nodes:
            assert isinstance(node, MemoryNode)


@pytest.mark.asyncio
@pytest.mark.skipif(NO_DASHSCOPE_KEY, reason="DASHSCOPE_API_KEY not set")
async def test_add_memory_with_library_and_project_id(
    add_memory_component,
    test_user_id,
):
    """Test adding a memory node with optional parameters."""
    messages = [
        Message(role="user", content="I prefer dark mode in all apps"),
        Message(role="assistant", content="Noted, you prefer dark mode."),
    ]

    input_data = AddMemoryInput(
        user_id=test_user_id,
        messages=messages,
        custom_instructions="Extract user preferences",
        expired_in_days=30,
    )

    result = await add_memory_component.arun(input_data)

    assert isinstance(result, AddMemoryOutput)
    assert isinstance(result.memory_nodes, list)


@pytest.mark.asyncio
@pytest.mark.skipif(NO_DASHSCOPE_KEY, reason="DASHSCOPE_API_KEY not set")
async def test_search_memory_success(search_memory_component, test_user_id):
    """Test searching memory nodes."""
    messages = [
        Message(role="user", content="basketball"),
    ]

    input_data = SearchMemoryInput(
        user_id=test_user_id,
        messages=messages,
        top_k=5,
    )

    result = await search_memory_component.arun(input_data)

    assert isinstance(result, SearchMemoryOutput)
    assert isinstance(result.memory_nodes, list)
    if result.memory_nodes:
        for node in result.memory_nodes:
            assert isinstance(node, MemoryNode)


@pytest.mark.asyncio
@pytest.mark.skipif(NO_DASHSCOPE_KEY, reason="DASHSCOPE_API_KEY not set")
async def test_search_memory_with_project_ids(
    search_memory_component,
    test_user_id,
):
    """Test searching memory nodes with project_ids."""
    messages = [
        Message(role="user", content="basketball"),
    ]

    input_data = SearchMemoryInput(
        user_id=test_user_id,
        messages=messages,
        top_k=5,
        enable_rerank=True,
    )

    result = await search_memory_component.arun(input_data)

    assert isinstance(result, SearchMemoryOutput)
    assert isinstance(result.memory_nodes, list)


@pytest.mark.asyncio
@pytest.mark.skipif(NO_DASHSCOPE_KEY, reason="DASHSCOPE_API_KEY not set")
async def test_list_memory_success(list_memory_component, test_user_id):
    """Test listing memory nodes with pagination."""
    input_data = ListMemoryInput(
        user_id=test_user_id,
        page_size=10,
        page_num=1,
    )

    result = await list_memory_component.arun(input_data)

    assert isinstance(result, ListMemoryOutput)
    assert isinstance(result.memory_nodes, list)
    assert isinstance(result.total, int)
    if result.total >= 0:
        for node in result.memory_nodes:
            assert isinstance(node, MemoryNode)


@pytest.mark.asyncio
@pytest.mark.skipif(NO_DASHSCOPE_KEY, reason="DASHSCOPE_API_KEY not set")
async def test_delete_memory_success(
    add_memory_component,
    delete_memory_component,
    test_user_id,
):
    """Test deleting a memory node."""
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

    await asyncio.sleep(3)
    if add_result.memory_nodes:
        memory_node_id = add_result.memory_nodes[0].memory_node_id

        delete_input = DeleteMemoryInput(
            user_id=test_user_id,
            memory_node_id=memory_node_id,
        )

        result = await delete_memory_component.arun(delete_input)

        assert isinstance(result, DeleteMemoryOutput)
        assert result.request_id is not None


@pytest.mark.asyncio
@pytest.mark.skipif(NO_DASHSCOPE_KEY, reason="DASHSCOPE_API_KEY not set")
async def test_update_memory_success(
    add_memory_component,
    update_memory_component,
    test_user_id,
):
    """Test updating a memory node."""
    messages = [
        Message(role="user", content="I like reading science fiction books"),
        Message(role="assistant", content="Great taste in books!"),
    ]

    add_input = AddMemoryInput(
        user_id=test_user_id,
        messages=messages,
    )

    add_result = await add_memory_component.arun(add_input)

    await asyncio.sleep(3)
    if add_result.memory_nodes:
        memory_node_id = add_result.memory_nodes[0].memory_node_id

        update_input = UpdateMemoryInput(
            memory_node_id=memory_node_id,
            custom_content="I like reading fantasy books instead",
        )

        result = await update_memory_component.arun(update_input)

        assert isinstance(result, UpdateMemoryOutput)
        assert result.request_id is not None


@pytest.mark.asyncio
@pytest.mark.skipif(NO_DASHSCOPE_KEY, reason="DASHSCOPE_API_KEY not set")
async def test_delete_entity_success(
    add_memory_component,
    delete_entity_component,
    test_user_id,
):
    """Test deleting an entity and all its associated data."""
    messages = [
        Message(role="user", content="Test message for entity deletion"),
        Message(role="assistant", content="Understood"),
    ]

    add_input = AddMemoryInput(
        user_id=test_user_id,
        messages=messages,
    )

    await add_memory_component.arun(add_input)
    await asyncio.sleep(3)

    delete_input = DeleteEntityInput(
        entity_type="user",
        entity_id=test_user_id,
    )

    result = await delete_entity_component.arun(delete_input)

    assert isinstance(result, DeleteEntityOutput)
    assert result.request_id is not None


# ==================== Profile Schema Tests ====================


@pytest.mark.asyncio
@pytest.mark.skipif(NO_DASHSCOPE_KEY, reason="DASHSCOPE_API_KEY not set")
async def test_create_profile_schema_success(
    create_profile_schema_component,
    delete_profile_schema_component,
):
    """Test creating a user profile schema."""
    schema_name = _generate_schema_name("ts")

    attributes = [
        ProfileAttribute(name="age", description="User's age"),
        ProfileAttribute(name="occupation", description="User's occupation"),
        ProfileAttribute(name="hobbies", description="User's hobbies"),
    ]

    input_data = CreateProfileSchemaInput(
        name=schema_name,
        description="Test profile schema for pytest",
        attributes=attributes,
    )

    result = await create_profile_schema_component.arun(input_data)

    assert isinstance(result, CreateProfileSchemaOutput)
    assert result.profile_schema_id is not None

    # Cleanup
    await delete_profile_schema_component.arun(
        DeleteProfileSchemaInput(schema_id=result.profile_schema_id),
    )


@pytest.mark.asyncio
@pytest.mark.skipif(NO_DASHSCOPE_KEY, reason="DASHSCOPE_API_KEY not set")
async def test_get_profile_schema_success(
    create_profile_schema_component,
    get_profile_schema_component,
    delete_profile_schema_component,
):
    """Test getting profile schema details."""
    schema_name = _generate_schema_name("tg")

    attributes = [
        ProfileAttribute(name="favorite_color", description="Favorite color"),
    ]

    create_input = CreateProfileSchemaInput(
        name=schema_name,
        description="Schema for get test",
        attributes=attributes,
    )
    create_result = await create_profile_schema_component.arun(create_input)
    schema_id = create_result.profile_schema_id

    get_input = GetProfileSchemaInput(schema_id=schema_id)
    result = await get_profile_schema_component.arun(get_input)

    assert isinstance(result, GetProfileSchemaOutput)
    assert result.name == schema_name
    assert len(result.attributes) >= 1

    # Cleanup
    await delete_profile_schema_component.arun(
        DeleteProfileSchemaInput(schema_id=schema_id),
    )


@pytest.mark.asyncio
@pytest.mark.skipif(NO_DASHSCOPE_KEY, reason="DASHSCOPE_API_KEY not set")
async def test_list_profile_schemas_success(list_profile_schemas_component):
    """Test listing profile schemas."""
    input_data = ListProfileSchemasInput(
        page_num=1,
        page_size=10,
    )

    result = await list_profile_schemas_component.arun(input_data)

    assert isinstance(result, ListProfileSchemasOutput)
    assert isinstance(result.profile_schemas, list)
    assert isinstance(result.total, int)


@pytest.mark.asyncio
@pytest.mark.skipif(NO_DASHSCOPE_KEY, reason="DASHSCOPE_API_KEY not set")
async def test_update_profile_schema_success(
    create_profile_schema_component,
    update_profile_schema_component,
    delete_profile_schema_component,
):
    """Test updating a profile schema."""
    schema_name = _generate_schema_name("tu")

    attributes = [
        ProfileAttribute(name="field_a", description="Field A"),
    ]

    create_input = CreateProfileSchemaInput(
        name=schema_name,
        attributes=attributes,
    )
    create_result = await create_profile_schema_component.arun(create_input)
    schema_id = create_result.profile_schema_id

    update_input = UpdateProfileSchemaInput(
        schema_id=schema_id,
        name=f"u_{schema_name}",
        attributes_operations=[
            AttributeOperation(
                op="add",
                name="field_b",
                description="Field B added via update",
            ),
        ],
    )

    result = await update_profile_schema_component.arun(update_input)

    assert isinstance(result, UpdateProfileSchemaOutput)
    assert result.request_id is not None

    # Cleanup
    await delete_profile_schema_component.arun(
        DeleteProfileSchemaInput(schema_id=schema_id),
    )


@pytest.mark.asyncio
@pytest.mark.skipif(NO_DASHSCOPE_KEY, reason="DASHSCOPE_API_KEY not set")
async def test_delete_profile_schema_success(
    create_profile_schema_component,
    delete_profile_schema_component,
):
    """Test deleting a profile schema."""
    schema_name = _generate_schema_name("td")

    attributes = [
        ProfileAttribute(name="temp_field", description="Temporary field"),
    ]

    create_input = CreateProfileSchemaInput(
        name=schema_name,
        attributes=attributes,
    )
    create_result = await create_profile_schema_component.arun(create_input)
    schema_id = create_result.profile_schema_id

    delete_input = DeleteProfileSchemaInput(schema_id=schema_id)
    result = await delete_profile_schema_component.arun(delete_input)

    assert isinstance(result, DeleteProfileSchemaOutput)
    assert result.request_id is not None


# ==================== User Profile Tests ====================


@pytest.mark.asyncio
@pytest.mark.skipif(NO_DASHSCOPE_KEY, reason="DASHSCOPE_API_KEY not set")
async def test_get_user_profile_success(
    create_profile_schema_component,
    get_user_profile_component,
    delete_profile_schema_component,
    test_user_id,
):
    """Test retrieving a user profile."""
    schema_name = _generate_schema_name("tp")

    attributes = [
        ProfileAttribute(name="test_field", description="Test field"),
    ]

    schema_input = CreateProfileSchemaInput(
        name=schema_name,
        attributes=attributes,
    )

    schema_result = await create_profile_schema_component.arun(schema_input)
    schema_id = schema_result.profile_schema_id

    input_data = GetUserProfileInput(
        schema_id=schema_id,
        user_id=test_user_id,
    )

    result = await get_user_profile_component.arun(input_data)

    assert isinstance(result, GetUserProfileOutput)
    if result.profile is not None:
        assert isinstance(result.profile.attributes, list)

    # Cleanup schema
    await delete_profile_schema_component.arun(
        DeleteProfileSchemaInput(schema_id=schema_id),
    )
