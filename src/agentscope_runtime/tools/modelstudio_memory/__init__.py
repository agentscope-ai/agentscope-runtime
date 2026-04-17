# -*- coding: utf-8 -*-
"""
ModelStudio Memory Components.

This package provides components for interacting with the ModelStudio Memory
service.

Components:
    - AddMemory: Store conversation messages as memory nodes
    - SearchMemory: Search for relevant memories
    - ListMemory: List memory nodes with pagination
    - DeleteMemory: Delete a specific memory node
    - UpdateMemory: Update a memory node's content
    - DeleteEntity: Delete an entity and all its associated data
    - CreateProfileSchema: Create a user profile schema
    - GetProfileSchema: Retrieve profile schema details
    - ListProfileSchemas: List profile schemas with pagination
    - UpdateProfileSchema: Update a profile schema
    - DeleteProfileSchema: Delete a profile schema
    - GetUserProfile: Retrieve a user profile

Schemas:
    All Pydantic schemas for input/output are available in the schemas
    submodule.

Exceptions:
    Custom exceptions for better error handling are available in the
    exceptions submodule.

Configuration:
    Configuration can be managed through environment variables or by
    providing a MemoryServiceConfig instance.
"""

# Configuration
from .config import MemoryServiceConfig

# Exceptions
from .exceptions import (
    MemoryAPIError,
    MemoryAuthenticationError,
    MemoryNetworkError,
    MemoryNotFoundError,
    MemoryValidationError,
)

# Components
from .core import (
    AddMemory,
    SearchMemory,
    ListMemory,
    DeleteMemory,
    CreateProfileSchema,
    GetUserProfile,
    GetProfileSchema,
    ListProfileSchemas,
    DeleteProfileSchema,
    UpdateProfileSchema,
    UpdateMemory,
    DeleteEntity,
)

# Schemas - Import commonly used schemas for convenience
from .schemas import (
    AddMemoryInput,
    AddMemoryOutput,
    AttributeOperation,
    CreateProfileSchemaInput,
    CreateProfileSchemaOutput,
    DeleteMemoryInput,
    DeleteMemoryOutput,
    DeleteProfileSchemaInput,
    DeleteProfileSchemaOutput,
    GetProfileSchemaInput,
    GetProfileSchemaOutput,
    GetUserProfileInput,
    GetUserProfileOutput,
    ListMemoryInput,
    ListMemoryOutput,
    ListProfileSchemasInput,
    ListProfileSchemasOutput,
    MemoryNode,
    Message,
    ProfileAttribute,
    ProfileSchemaAttribute,
    ProfileSchemaSummary,
    SearchMemoryInput,
    SearchMemoryOutput,
    UpdateMemoryInput,
    UpdateMemoryOutput,
    UpdateProfileSchemaInput,
    UpdateProfileSchemaOutput,
    DeleteEntityInput,
    DeleteEntityOutput,
    UserProfile,
    UserProfileAttribute,
)

__all__ = [
    # Core Components
    "AddMemory",
    "SearchMemory",
    "ListMemory",
    "DeleteMemory",
    "CreateProfileSchema",
    "GetUserProfile",
    "GetProfileSchema",
    "ListProfileSchemas",
    "DeleteProfileSchema",
    "UpdateProfileSchema",
    "UpdateMemory",
    "DeleteEntity",
    # Configuration
    "MemoryServiceConfig",
    # Exceptions
    "MemoryAPIError",
    "MemoryAuthenticationError",
    "MemoryNetworkError",
    "MemoryNotFoundError",
    "MemoryValidationError",
    # Schemas
    "Message",
    "MemoryNode",
    "AddMemoryInput",
    "AddMemoryOutput",
    "SearchMemoryInput",
    "SearchMemoryOutput",
    "ListMemoryInput",
    "ListMemoryOutput",
    "DeleteMemoryInput",
    "DeleteMemoryOutput",
    "ProfileAttribute",
    "ProfileSchemaAttribute",
    "ProfileSchemaSummary",
    "AttributeOperation",
    "CreateProfileSchemaInput",
    "CreateProfileSchemaOutput",
    "GetProfileSchemaInput",
    "GetProfileSchemaOutput",
    "ListProfileSchemasInput",
    "ListProfileSchemasOutput",
    "DeleteProfileSchemaInput",
    "DeleteProfileSchemaOutput",
    "UpdateProfileSchemaInput",
    "UpdateProfileSchemaOutput",
    "UpdateMemoryInput",
    "UpdateMemoryOutput",
    "DeleteEntityInput",
    "DeleteEntityOutput",
    "UserProfileAttribute",
    "UserProfile",
    "GetUserProfileInput",
    "GetUserProfileOutput",
]
