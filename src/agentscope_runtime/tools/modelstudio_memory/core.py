# -*- coding: utf-8 -*-
"""
ModelStudio Memory Components.

This module provides components for interacting with the ModelStudio Memory
service, enabling:
- Adding conversation memories
- Searching for relevant memories
- Listing and managing memory nodes
- Creating and retrieving user profiles

All components support async operations and follow the Component pattern.
"""
import logging
from typing import Any, Optional

from ..base import Tool
from .base import ModelStudioMemoryBase
from .config import MemoryServiceConfig
from .schemas import (
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
    SearchMemoryInput,
    SearchMemoryOutput,
    UserProfile,
    UserProfileAttribute,
)

logger = logging.getLogger(__name__)


class AddMemory(
    Tool[AddMemoryInput, AddMemoryOutput],
    ModelStudioMemoryBase,
):
    """
    Component for storing conversation history as memory nodes.

    This component sends conversation messages to the ModelStudio Memory
    to be processed and stored as searchable memory nodes. The service
    automatically extracts and structures relevant information.

    Environment Variables:
        DASHSCOPE_API_KEY: Required. API key for authentication
        MODELSTUDIO_SERVICE_ID: Optional. Service identifier
            (default: "memory_service")
        MEMORY_SERVICE_ENDPOINT: Optional. API endpoint URL
            (default: https://dashscope.aliyuncs.com/api/v2/apps/memory)

    Raises:
        ValueError: If DASHSCOPE_API_KEY is not set
        MemoryAPIError: If the API request fails
        MemoryAuthenticationError: If authentication fails
        MemoryNetworkError: If network communication fails
    """

    name = "add_memory"
    description = "Store conversation messages as memory nodes"

    def __init__(self, config: Optional[MemoryServiceConfig] = None) -> None:
        """
        Initialize the AddMemory component.

        Args:
            config: Optional configuration. If not provided, will be loaded
                   from environment variables.
        """
        Tool.__init__(self)
        ModelStudioMemoryBase.__init__(self, config)

    async def _arun(
        self,
        args: AddMemoryInput,
        **kwargs: Any,
    ) -> AddMemoryOutput:
        """
        Add memory nodes for the given conversation.

        Args:
            args: Input containing user_id, messages, timestamp, and optional
                 metadata
            **kwargs: Additional parameters (currently unused)

        Returns:
            AddMemoryOutput containing the created memory nodes and request_id

        Raises:
            MemoryAPIError: If the API request fails
        """
        logger.info(f"Adding memory for user {args.user_id}")

        try:
            # Build request payload
            payload = args.model_dump(exclude_none=True)

            # Send request
            result = await self._request(
                "POST",
                self.config.get_add_memory_url(),
                json=payload,
            )

            # Debug: print API response structure
            logger.debug(f"API Response: {result}")
            logger.debug(
                f"memory_nodes type: {type(result.get('memory_nodes'))}",
            )
            logger.debug(f"memory_nodes value: {result.get('memory_nodes')}")

            # Parse response - handle both list and dict formats
            memory_nodes_raw = result.get("memory_nodes", [])
            if isinstance(memory_nodes_raw, dict):
                # If it's a dict (single node), wrap it in a list
                memory_nodes_list = [memory_nodes_raw]
            elif isinstance(memory_nodes_raw, list):
                memory_nodes_list = memory_nodes_raw
            else:
                memory_nodes_list = []

            output = AddMemoryOutput(
                memory_nodes=[
                    MemoryNode(**node) for node in memory_nodes_list
                ],
                request_id=result.get("request_id", ""),
            )

            logger.info(
                f"Successfully added {len(output.memory_nodes)} memory nodes",
            )
            return output

        except Exception:
            logger.exception(f"Failed to add memory for user {args.user_id}")
            raise


class SearchMemory(
    Tool[SearchMemoryInput, SearchMemoryOutput],
    ModelStudioMemoryBase,
):
    """
    Component for searching relevant memories based on conversation context.

    This component searches the memory database for relevant past conversations
    and information based on the current conversation context.

    Environment Variables:
        DASHSCOPE_API_KEY: Required. API key for authentication
        MODELSTUDIO_SERVICE_ID: Optional. Service identifier
        MEMORY_SERVICE_ENDPOINT: Optional. API endpoint URL

    Raises:
        ValueError: If DASHSCOPE_API_KEY is not set
        MemoryAPIError: If the API request fails
    """

    name = "search_memory"
    description = "Search for relevant memories based on conversation context"

    def __init__(self, config: Optional[MemoryServiceConfig] = None) -> None:
        """
        Initialize the SearchMemory component.

        Args:
            config: Optional configuration. If not provided, will be loaded
                   from environment variables.
        """
        Tool.__init__(self)
        ModelStudioMemoryBase.__init__(self, config)

    async def _arun(
        self,
        args: SearchMemoryInput,
        **kwargs: Any,
    ) -> SearchMemoryOutput:
        """
        Search for relevant memory nodes.

        Args:
            args: Input containing user_id, messages, top_k, and min_score
            **kwargs: Additional parameters (currently unused)

        Returns:
            SearchMemoryOutput containing retrieved memory nodes and request_id

        Raises:
            MemoryAPIError: If the API request fails
        """
        logger.info(
            f"Searching memory for user {args.user_id} "
            f"(top_k={args.top_k}, min_score={args.min_score})",
        )

        try:
            # Build request payload
            payload = args.model_dump(exclude_none=True)

            # Send request
            result = await self._request(
                "POST",
                self.config.get_search_memory_url(),
                json=payload,
            )

            # Parse response
            output = SearchMemoryOutput(
                memory_nodes=[
                    MemoryNode(**node)
                    for node in result.get("memory_nodes", [])
                ],
                request_id=result.get("request_id", ""),
            )

            logger.info(
                f"Found {len(output.memory_nodes)} memory nodes for "
                f"user {args.user_id}",
            )
            return output

        except Exception:
            logger.exception(
                f"Failed to search memory for user {args.user_id}",
            )
            raise


class ListMemory(
    Tool[ListMemoryInput, ListMemoryOutput],
    ModelStudioMemoryBase,
):
    """
    Component for listing memory nodes with pagination.

    This component retrieves a paginated list of all memory nodes for a
    specific user.

    Environment Variables:
        DASHSCOPE_API_KEY: Required. API key for authentication
        MODELSTUDIO_SERVICE_ID: Optional. Service identifier
        MEMORY_SERVICE_ENDPOINT: Optional. API endpoint URL

    Raises:
        ValueError: If DASHSCOPE_API_KEY is not set
        MemoryAPIError: If the API request fails
    """

    name = "list_memory"
    description = "List memory nodes for a user with pagination"

    def __init__(self, config: Optional[MemoryServiceConfig] = None) -> None:
        """
        Initialize the ListMemory component.

        Args:
            config: Optional configuration. If not provided, will be loaded
                   from environment variables.
        """
        Tool.__init__(self)
        ModelStudioMemoryBase.__init__(self, config)

    async def _arun(
        self,
        args: ListMemoryInput,
        **kwargs: Any,
    ) -> ListMemoryOutput:
        """
        List memory nodes for a user with pagination.

        Args:
            args: Input containing user_id, page_num, and page_size
            **kwargs: Additional parameters (currently unused)

        Returns:
            ListMemoryOutput containing memory nodes, pagination info,
            and request_id

        Raises:
            MemoryAPIError: If the API request fails
        """
        logger.info(
            f"Listing memory for user {args.user_id} "
            f"(page {args.page_num}, size {args.page_size})",
        )

        try:
            # Build request params
            params = args.model_dump(exclude_none=True)

            # Send request (GET with query parameters)
            result = await self._request(
                "GET",
                self.config.get_list_memory_url(),
                params=params,
            )

            # Parse response
            output = ListMemoryOutput(
                memory_nodes=[
                    MemoryNode(**node)
                    for node in result.get("memory_nodes", [])
                ],
                page_size=result.get("page_size", args.page_size or 10),
                page_num=result.get("page_num", args.page_num or 1),
                total=result.get("total", 0),
                request_id=result.get("request_id", ""),
            )

            logger.info(
                f"Retrieved {len(output.memory_nodes)} memory nodes "
                f"(total: {output.total})",
            )
            return output

        except Exception:
            logger.exception(f"Failed to list memory for user {args.user_id}")
            raise


class DeleteMemory(
    Tool[DeleteMemoryInput, DeleteMemoryOutput],
    ModelStudioMemoryBase,
):
    """
    Component for deleting a specific memory node.

    This component deletes a memory node by its ID.

    Environment Variables:
        DASHSCOPE_API_KEY: Required. API key for authentication
        MODELSTUDIO_SERVICE_ID: Optional. Service identifier
        MEMORY_SERVICE_ENDPOINT: Optional. API endpoint URL

    Raises:
        ValueError: If DASHSCOPE_API_KEY is not set
        MemoryAPIError: If the API request fails
        MemoryNotFoundError: If the memory node is not found
    """

    name = "delete_memory"
    description = "Delete a specific memory node"

    def __init__(self, config: Optional[MemoryServiceConfig] = None) -> None:
        """
        Initialize the DeleteMemory component.

        Args:
            config: Optional configuration. If not provided, will be loaded
                   from environment variables.
        """
        Tool.__init__(self)
        ModelStudioMemoryBase.__init__(self, config)

    async def _arun(
        self,
        args: DeleteMemoryInput,
        **kwargs: Any,
    ) -> DeleteMemoryOutput:
        """
        Delete a memory node.

        Args:
            args: Input containing user_id and memory_node_id
            **kwargs: Additional parameters (currently unused)

        Returns:
            DeleteMemoryOutput containing the request_id

        Raises:
            MemoryAPIError: If the API request fails
            MemoryNotFoundError: If the memory node is not found
        """
        logger.info(
            f"Deleting memory node {args.memory_node_id} "
            f"for user {args.user_id}",
        )

        try:
            # Build URL with path parameter
            url = self.config.get_delete_memory_url(args.memory_node_id)

            # Send request
            result = await self._request("DELETE", url)

            # Parse response
            output = DeleteMemoryOutput(
                request_id=result.get("request_id", ""),
            )

            logger.info(
                f"Successfully deleted memory node {args.memory_node_id}",
            )
            return output

        except Exception:
            logger.exception(
                f"Failed to delete memory node {args.memory_node_id}",
            )
            raise


class CreateProfileSchema(
    Tool[CreateProfileSchemaInput, CreateProfileSchemaOutput],
    ModelStudioMemoryBase,
):
    """
    Component for creating a user profile schema.

    This component creates a schema that defines the structure of user profiles
    including attribute definitions.

    Environment Variables:
        DASHSCOPE_API_KEY: Required. API key for authentication
        MODELSTUDIO_SERVICE_ID: Optional. Service identifier
        MEMORY_SERVICE_ENDPOINT: Optional. API endpoint URL

    Raises:
        ValueError: If DASHSCOPE_API_KEY is not set or if attributes list
                   is empty
        MemoryAPIError: If the API request fails
    """

    name = "create_profile_schema"
    description = "Create a profile schema with attribute definitions"

    def __init__(self, config: Optional[MemoryServiceConfig] = None) -> None:
        """
        Initialize the CreateProfileSchema component.

        Args:
            config: Optional configuration. If not provided, will be loaded
                   from environment variables.
        """
        Tool.__init__(self)
        ModelStudioMemoryBase.__init__(self, config)

    async def _arun(
        self,
        args: CreateProfileSchemaInput,
        **kwargs: Any,
    ) -> CreateProfileSchemaOutput:
        """
        Create a profile schema.

        Args:
            args: Input containing name, description, and attributes
            **kwargs: Additional parameters (currently unused)

        Returns:
            CreateProfileSchemaOutput containing profile_schema_id and
            request_id

        Raises:
            MemoryAPIError: If the API request fails
        """
        logger.info(f"Creating profile schema: {args.name}")

        try:
            # Build request payload
            payload = args.model_dump(exclude_none=True)

            # Send request
            result = await self._request(
                "POST",
                self.config.get_create_profile_schema_url(),
                json=payload,
            )

            # Parse response
            output = CreateProfileSchemaOutput(
                profile_schema_id=result.get("profile_schema_id", ""),
                request_id=result.get("request_id", ""),
            )

            logger.info(
                f"Successfully created profile schema: "
                f"{output.profile_schema_id}",
            )
            return output

        except Exception:
            logger.exception(f"Failed to create profile schema: {args.name}")
            raise


class GetUserProfile(
    Tool[GetUserProfileInput, GetUserProfileOutput],
    ModelStudioMemoryBase,
):
    """
    Component for retrieving a user profile.

    This component retrieves a user's profile based on a schema ID and user ID.

    Environment Variables:
        DASHSCOPE_API_KEY: Required. API key for authentication
        MODELSTUDIO_SERVICE_ID: Optional. Service identifier
        MEMORY_SERVICE_ENDPOINT: Optional. API endpoint URL

    Raises:
        ValueError: If DASHSCOPE_API_KEY is not set
        MemoryAPIError: If the API request fails
        MemoryNotFoundError: If the profile is not found
    """

    name = "get_user_profile"
    description = "Get user profile by schema id and user id"

    def __init__(self, config: Optional[MemoryServiceConfig] = None) -> None:
        """
        Initialize the GetUserProfile component.

        Args:
            config: Optional configuration. If not provided, will be loaded
                   from environment variables.
        """
        Tool.__init__(self)
        ModelStudioMemoryBase.__init__(self, config)

    async def _arun(
        self,
        args: GetUserProfileInput,
        **kwargs: Any,
    ) -> GetUserProfileOutput:
        """
        Get a user profile.

        Args:
            args: Input containing schema_id and user_id
            **kwargs: Additional parameters (currently unused)

        Returns:
            GetUserProfileOutput containing the profile and request_id

        Raises:
            MemoryAPIError: If the API request fails
            MemoryNotFoundError: If the profile is not found
        """
        logger.info(
            f"Getting user profile for user {args.user_id} "
            f"with schema {args.schema_id}",
        )

        try:
            # Build URL with path parameter
            url = self.config.get_user_profile_url(args.schema_id)

            # Send request with user_id as query parameter
            result = await self._request(
                "GET",
                url,
                params={"user_id": args.user_id},
            )

            # Parse response - handle API's camelCase field names
            profile_raw = result.get("profile", {})
            attributes = [
                UserProfileAttribute(
                    name=item.get("name", ""),
                    id=item.get("id", ""),
                    value=item.get("value"),
                )
                for item in profile_raw.get("attributes", [])
            ]

            profile = UserProfile(
                schema_description=profile_raw.get("schemaDescription"),
                schema_name=profile_raw.get("schemaName"),
                attributes=attributes,
            )

            output = GetUserProfileOutput(
                profile=profile,
                request_id=result.get("requestId", ""),
            )

            logger.info(
                f"Successfully retrieved profile for user {args.user_id}",
            )
            return output

        except Exception:
            logger.exception(
                f"Failed to get profile for user {args.user_id}",
            )
            raise
