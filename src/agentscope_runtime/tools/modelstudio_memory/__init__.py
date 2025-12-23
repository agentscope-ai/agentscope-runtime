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
    - CreateProfileSchema: Create a user profile schema
    - GetUserProfile: Retrieve a user profile

Models:
    All Pydantic models for input/output are available in the models submodule.

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
)

# Models - Import commonly used models for convenience
from .models import (
    AddMemoryInput,
    AddMemoryOutput,
    CreateProfileSchemaInput,
    CreateProfileSchemaOutput,
    DeleteMemoryInput,
    DeleteMemoryOutput,
    GetUserProfileInput,
    GetUserProfileOutput,
    ListMemoryInput,
    ListMemoryOutput,
    MemoryNode,
    Message,
    ProfileAttribute,
    SearchMemoryInput,
    SearchMemoryOutput,
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
    # Configuration
    "MemoryServiceConfig",
    # Exceptions
    "MemoryAPIError",
    "MemoryAuthenticationError",
    "MemoryNetworkError",
    "MemoryNotFoundError",
    "MemoryValidationError",
    # Models
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
    "CreateProfileSchemaInput",
    "CreateProfileSchemaOutput",
    "UserProfileAttribute",
    "UserProfile",
    "GetUserProfileInput",
    "GetUserProfileOutput",
]
