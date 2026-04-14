# -*- coding: utf-8 -*-
"""
Pydantic models for ModelStudio Memory API.
"""
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, model_validator


# ==================== Message ====================
class Message(BaseModel):
    """Message in a conversation."""

    role: str = Field(..., description="Role of the message sender")
    content: Any = Field(..., description="Content of the message")


# ==================== Memory Node ====================
class MemoryNode(BaseModel):
    """A memory node stored in the system."""

    memory_node_id: Optional[str] = Field(
        None,
        description="Unique identifier for the memory node",
    )
    content: str = Field(..., description="Content of the memory node")
    event: Optional[str] = Field(
        None,
        description="Events associated with the memory node. "
        "e.g. ADD, DELETE, UPDATE",
    )
    old_content: Optional[str] = Field(
        None,
        description="Old content of the memory node",
    )
    created_at: Optional[int] = Field(
        None,
        description="Creation timestamp in seconds",
    )
    updated_at: Optional[int] = Field(
        None,
        description="Last update timestamp in seconds",
    )
    meta_data: Optional[Dict[str, Any]] = Field(
        None,
        description="Custom metadata",
    )


# ==================== Add Memory ====================
class AddMemoryInput(BaseModel):
    """Input for adding memory."""

    user_id: str = Field(..., description="End user id")
    messages: List[Message] = Field(
        ...,
        description="Conversation messages to be stored as memory",
    )
    meta_data: Optional[Dict[str, Any]] = Field(
        None,
        description="Optional metadata",
    )
    memory_library_id: Optional[str] = Field(
        None,
        description="Memory library ID. Uses default library if not provided",
    )
    project_id: Optional[str] = Field(
        None,
        description="Project ID within the memory library",
    )
    profile_schema: Optional[str] = Field(
        None,
        description="Profile schema ID for user profile extraction",
    )
    custom_instructions: Optional[str] = Field(
        None,
        description="Custom memory extraction instructions (max 512 chars)",
    )
    expired_in_days: Optional[int] = Field(
        None,
        description="Memory expiration in days (7/30/180 or -1 for never)",
    )

    class Config:
        extra = "allow"  # Allow extra fields


class AddMemoryOutput(BaseModel):
    """Output from adding memory."""

    memory_nodes: List[MemoryNode] = Field(
        ...,
        description="Generated memory nodes",
    )
    request_id: str = Field(..., description="Request id")


# ==================== Search Memory ====================
class SearchMemoryInput(BaseModel):
    """Input for searching memory."""

    user_id: str = Field(..., description="End user id")
    messages: List[Message] = Field(
        ...,
        description="Conversation messages for context",
    )
    top_k: Optional[int] = Field(
        None,
        description="Maximum number of results to return (server default: 10)",
    )
    min_score: Optional[float] = Field(
        None,
        description="Minimum similarity score threshold (server default: 0.3)",
    )
    memory_library_id: Optional[str] = Field(
        None,
        description="Memory library ID. Uses default library if not provided",
    )
    project_ids: Optional[List[str]] = Field(
        None,
        description="Project IDs to search in",
    )
    source: Optional[str] = Field(
        None,
        description="Source identifier filter",
    )
    enable_rewrite: Optional[bool] = Field(
        None,
        description="Enable query rewrite",
    )
    enable_judge: Optional[bool] = Field(
        None,
        description="Enable relevance judgment",
    )
    enable_rerank: Optional[bool] = Field(
        None,
        description="Enable result reranking",
    )

    class Config:
        extra = "allow"  # Allow extra fields


class SearchMemoryOutput(BaseModel):
    """Output from searching memory."""

    memory_nodes: List[MemoryNode] = Field(
        ...,
        description="Retrieved memory nodes",
    )
    request_id: str = Field(..., description="Request id")


# ==================== List Memory ====================
class ListMemoryInput(BaseModel):
    """Input for listing memory nodes."""

    user_id: str = Field(..., description="End user id")
    page_num: Optional[int] = Field(1, description="Page number (1-based)")
    page_size: Optional[int] = Field(
        10,
        description="Number of items per page",
    )
    memory_library_id: Optional[str] = Field(
        None,
        description="Memory library ID. Uses default library if not provided",
    )
    project_id: Optional[str] = Field(
        None,
        description="Project ID to list from",
    )

    class Config:
        extra = "allow"  # Allow extra fields


class ListMemoryOutput(BaseModel):
    """Output from listing memory nodes."""

    memory_nodes: List[MemoryNode] = Field(
        ...,
        description="Retrieved memory nodes",
    )
    page_size: int = Field(..., description="Number of items per page")
    page_num: int = Field(..., description="Current page number")
    total: int = Field(..., description="Total number of memory nodes")
    request_id: str = Field(..., description="Request id")


# ==================== Delete Memory ====================
class DeleteMemoryInput(BaseModel):
    """Input for deleting a memory node."""

    user_id: str = Field(..., description="End user id")
    memory_node_id: str = Field(
        ...,
        description="Memory node id to delete",
    )
    memory_library_id: Optional[str] = Field(
        None,
        description="Memory library ID. Uses default library if not provided",
    )

    class Config:
        extra = "allow"  # Allow extra fields


class DeleteMemoryOutput(BaseModel):
    """Output from deleting a memory node."""

    request_id: str = Field(..., description="Request id")


# ==================== Profile Schema ====================
class ProfileAttribute(BaseModel):
    """Attribute definition in a profile schema."""

    name: str = Field(..., description="Attribute name")
    description: Optional[str] = Field(
        None,
        description="Attribute description",
    )
    default_value: Optional[Any] = Field(
        None,
        description="Default value for the attribute",
    )


class CreateProfileSchemaInput(BaseModel):
    """Input for creating a profile schema."""

    name: str = Field(..., description="Profile schema name")
    description: Optional[str] = Field(
        None,
        description="Profile schema description",
    )
    attributes: List[ProfileAttribute] = Field(
        ...,
        description="List of attribute definitions (must have at least 1)",
    )
    memory_library_id: Optional[str] = Field(
        None,
        description="Memory library ID. Uses default library if not provided",
    )

    @model_validator(mode="after")
    def validate_attributes(self) -> "CreateProfileSchemaInput":
        """Validate that at least one attribute is provided."""
        if not self.attributes:
            raise ValueError("attributes must contain at least one item")
        return self

    class Config:
        extra = "allow"


class CreateProfileSchemaOutput(BaseModel):
    """Output from creating a profile schema."""

    profile_schema_id: str = Field(
        ...,
        description="Created profile schema id",
    )
    request_id: str = Field(..., description="Request id")


# ==================== User Profile ====================
class UserProfileAttribute(BaseModel):
    """Attribute in a user profile."""

    name: str = Field(..., description="Attribute name")
    id: str = Field(..., description="Attribute id")
    value: Optional[Any] = Field(None, description="Attribute value")


class UserProfile(BaseModel):
    """User profile with attributes."""

    schema_description: Optional[str] = Field(
        None,
        alias="schemaDescription",
        description="Schema description",
    )
    schema_name: Optional[str] = Field(
        None,
        alias="schemaName",
        description="Schema name",
    )
    attributes: List[UserProfileAttribute] = Field(
        default_factory=list,
        description="User attributes",
    )

    class Config:
        populate_by_name = True  # Allow both field names and aliases


class GetUserProfileInput(BaseModel):
    """Input for getting a user profile."""

    schema_id: str = Field(..., description="Profile schema id")
    user_id: str = Field(..., description="End user id")
    memory_library_id: Optional[str] = Field(
        None,
        description="Memory library ID. Uses default library if not provided",
    )


class GetUserProfileOutput(BaseModel):
    """Output from getting a user profile."""

    request_id: str = Field(..., description="Request id", alias="requestId")
    profile: UserProfile = Field(..., description="User profile")

    class Config:
        populate_by_name = True  # Allow both field names and aliases


# ==================== Profile Schema CRUD ====================
class ProfileSchemaAttribute(BaseModel):
    """Attribute in a profile schema response (includes attribute_id)."""

    attribute_id: str = Field(..., description="Attribute ID")
    name: str = Field(..., description="Attribute name")
    description: Optional[str] = Field(
        None,
        description="Attribute description",
    )
    default_value: Optional[Any] = Field(
        None,
        description="Default value for the attribute",
    )


class GetProfileSchemaInput(BaseModel):
    """Input for getting profile schema details."""

    schema_id: str = Field(..., description="Profile schema id")
    memory_library_id: Optional[str] = Field(
        None,
        description="Memory library ID. Uses default library if not provided",
    )


class GetProfileSchemaOutput(BaseModel):
    """Output from getting profile schema details."""

    request_id: str = Field(..., description="Request id")
    name: str = Field(..., description="Schema name")
    description: Optional[str] = Field(
        None,
        description="Schema description",
    )
    attributes: List[ProfileSchemaAttribute] = Field(
        default_factory=list,
        description="Schema attributes with IDs",
    )


class ProfileSchemaSummary(BaseModel):
    """Summary of a profile schema in list results."""

    profile_schema_id: str = Field(
        ...,
        description="Profile schema ID",
    )
    name: str = Field(..., description="Schema name")
    description: Optional[str] = Field(
        None,
        description="Schema description",
    )


class ListProfileSchemasInput(BaseModel):
    """Input for listing profile schemas."""

    page_num: Optional[int] = Field(1, description="Page number (1-based)")
    page_size: Optional[int] = Field(
        10,
        description="Number of items per page",
    )
    memory_library_id: Optional[str] = Field(
        None,
        description="Memory library ID. Uses default library if not provided",
    )


class ListProfileSchemasOutput(BaseModel):
    """Output from listing profile schemas."""

    request_id: str = Field(..., description="Request id")
    profile_schemas: List[ProfileSchemaSummary] = Field(
        default_factory=list,
        description="List of profile schemas",
    )
    total: int = Field(..., description="Total number of schemas")


class DeleteProfileSchemaInput(BaseModel):
    """Input for deleting a profile schema."""

    schema_id: str = Field(..., description="Profile schema id")
    memory_library_id: Optional[str] = Field(
        None,
        description="Memory library ID. Uses default library if not provided",
    )


class DeleteProfileSchemaOutput(BaseModel):
    """Output from deleting a profile schema."""

    request_id: str = Field(..., description="Request id")


class AttributeOperation(BaseModel):
    """An operation on a profile schema attribute."""

    op: str = Field(
        ...,
        description="Operation type: add, update, or delete",
    )
    attribute_id: Optional[str] = Field(
        None,
        description="Attribute ID (required for update/delete)",
    )
    name: Optional[str] = Field(
        None,
        description="Attribute name (required for add)",
    )
    description: Optional[str] = Field(
        None,
        description="Attribute description",
    )
    default_value: Optional[Any] = Field(
        None,
        description="Default value for the attribute",
    )


class UpdateProfileSchemaInput(BaseModel):
    """Input for updating a profile schema."""

    schema_id: str = Field(..., description="Profile schema id")
    name: Optional[str] = Field(
        None,
        description="New schema name",
    )
    description: Optional[str] = Field(
        None,
        description="New schema description",
    )
    attributes_operations: Optional[List[AttributeOperation]] = Field(
        None,
        description="List of attribute operations (add/update/delete)",
    )
    memory_library_id: Optional[str] = Field(
        None,
        description="Memory library ID. Uses default library if not provided",
    )


class UpdateProfileSchemaOutput(BaseModel):
    """Output from updating a profile schema."""

    request_id: str = Field(..., description="Request id")


# ==================== Update Memory Node ====================
class UpdateMemoryNodeInput(BaseModel):
    """Input for updating a memory node."""

    memory_node_id: str = Field(
        ...,
        description="Memory node ID to update",
    )
    custom_content: str = Field(
        ...,
        description="New content for the memory node",
    )
    timestamp: Optional[int] = Field(
        None,
        description="Timestamp in seconds",
    )
    meta_data: Optional[Dict[str, Any]] = Field(
        None,
        description="Custom metadata",
    )
    memory_library_id: Optional[str] = Field(
        None,
        description="Memory library ID. Uses default library if not provided",
    )


class UpdateMemoryNodeOutput(BaseModel):
    """Output from updating a memory node."""

    request_id: str = Field(..., description="Request id")


# ==================== Delete Entity ====================
class DeleteEntityInput(BaseModel):
    """Input for deleting an entity and all its associated data."""

    entity_type: str = Field(
        ...,
        description="Entity type (e.g. user)",
    )
    entity_id: str = Field(
        ...,
        description="Entity ID to delete",
    )
    memory_library_id: Optional[str] = Field(
        None,
        description="Memory library ID. Uses default library if not provided",
    )


class DeleteEntityOutput(BaseModel):
    """Output from deleting an entity."""

    request_id: str = Field(..., description="Request id")
