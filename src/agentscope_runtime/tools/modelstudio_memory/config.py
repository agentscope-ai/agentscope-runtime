# -*- coding: utf-8 -*-
"""
Configuration management for ModelStudio Memory service.
"""
import os
from dataclasses import dataclass


# Default endpoint
DEFAULT_MEMORY_SERVICE_ENDPOINT = (
    "https://dashscope.aliyuncs.com/api/v2/apps/memory"
)


@dataclass
class MemoryServiceConfig:
    """
    Configuration for ModelStudio Memory Service.

    Attributes:
        api_key: DashScope API key for authentication
        service_endpoint: Base URL for the memory service API
        service_id: Service identifier
    """

    api_key: str
    service_endpoint: str = DEFAULT_MEMORY_SERVICE_ENDPOINT
    service_id: str = "memory_service"

    @classmethod
    def from_env(cls) -> "MemoryServiceConfig":
        """
        Create configuration from environment variables.

        Environment Variables:
            DASHSCOPE_API_KEY: Required. API key for authentication
            MEMORY_SERVICE_ENDPOINT: Optional. API endpoint URL
            MODELSTUDIO_SERVICE_ID: Optional. Service identifier

        Returns:
            MemoryServiceConfig: Configuration instance

        Raises:
            ValueError: If DASHSCOPE_API_KEY is not set
        """
        api_key = os.getenv("DASHSCOPE_API_KEY")
        if not api_key:
            raise ValueError(
                "DASHSCOPE_API_KEY environment variable is required. "
                "Please set it before using ModelStudio Memory components.",
            )

        return cls(
            api_key=api_key,
            service_endpoint=os.getenv(
                "MEMORY_SERVICE_ENDPOINT",
                DEFAULT_MEMORY_SERVICE_ENDPOINT,
            ),
            service_id=os.getenv("MODELSTUDIO_SERVICE_ID", "memory_service"),
        )

    def get_add_memory_url(self) -> str:
        """Get URL for adding memory."""
        return f"{self.service_endpoint}/add"

    def get_search_memory_url(self) -> str:
        """Get URL for searching memory."""
        return f"{self.service_endpoint}/memory_nodes/search"

    def get_list_memory_url(self) -> str:
        """Get URL for listing memory."""
        return f"{self.service_endpoint}/memory_nodes"

    def get_user_profile_url(self, schema_id: str) -> str:
        """Get URL for getting user profile."""
        return (
            f"{self.service_endpoint}/profile_schemas/{schema_id}/user_profile"
        )

    def get_profile_schema_url(self, schema_id: str) -> str:
        """Get URL for a specific profile schema (GET/PATCH/DELETE)."""
        return f"{self.service_endpoint}/profile_schemas/{schema_id}"

    def get_profile_schemas_url(self) -> str:
        """Get URL for profile schemas collection (POST/GET list)."""
        return f"{self.service_endpoint}/profile_schemas"

    def get_memory_node_url(self, memory_node_id: str) -> str:
        """Get URL for a specific memory node (DELETE/PATCH)."""
        return f"{self.service_endpoint}/memory_nodes/{memory_node_id}"

    def get_delete_entity_url(
        self,
        entity_type: str,
        entity_id: str,
    ) -> str:
        """Get URL for deleting an entity."""
        return f"{self.service_endpoint}/entities/{entity_type}/{entity_id}"
