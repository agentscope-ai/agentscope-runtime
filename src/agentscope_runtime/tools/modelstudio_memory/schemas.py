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
class SearchFilters(BaseModel):
    """Filters for memory search."""

    tags: Optional[List[str]] = Field(
        None,
        description="Filter results by tags",
    )


class SearchMemoryInput(BaseModel):
    """Input for searching memory."""

    user_id: str = Field(..., description="End user id")
    messages: List[Message] = Field(
        ...,
        description="Conversation messages for context",
    )
    top_k: Optional[int] = Field(
        100,
        description="Maximum number of results to return",
    )
    min_score: Optional[float] = Field(
        0.0,
        description="Minimum similarity score threshold",
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
    immutable: Optional[bool] = Field(
        False,
        description="Whether the attribute is immutable",
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


class GetUserProfileOutput(BaseModel):
    """Output from getting a user profile."""

    request_id: str = Field(..., description="Request id", alias="requestId")
    profile: UserProfile = Field(..., description="User profile")

    class Config:
        populate_by_name = True  # Allow both field names and aliases
