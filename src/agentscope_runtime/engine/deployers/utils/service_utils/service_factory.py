# -*- coding: utf-8 -*-
# pylint:disable=line-too-long

from typing import Dict, Type, Any
from .service_config import (
    ServiceType,
    ServiceProvider,
    ServiceConfig,
    ServicesConfig,
)


class ServiceFactory:
    """Factory for creating service instances based on configuration."""

    # Service registry mapping service types and providers to
    # implementation classes
    _service_registry: Dict[str, Dict[str, Type]] = {}

    @classmethod
    def _populate_registry(cls):
        """Populate the service registry with available implementations."""
        if cls._service_registry:
            return  # Already populated

        try:
            # Import service implementations
            from agentscope_runtime.engine.services.memory_service import (
                InMemoryMemoryService,
            )
            from agentscope_runtime.engine.services.session_history_service import (  # noqa E501
                InMemorySessionHistoryService,
            )

            # Register memory services
            cls._service_registry[ServiceType.MEMORY] = {
                ServiceProvider.IN_MEMORY: InMemoryMemoryService,
            }

            # Register session history services
            cls._service_registry[ServiceType.SESSION_HISTORY] = {
                ServiceProvider.IN_MEMORY: InMemorySessionHistoryService,
            }

            # Try to register Redis services if available

            from agentscope_runtime.engine.services.redis_memory_service import (  # noqa E501
                RedisMemoryService,
            )
            from agentscope_runtime.engine.services.redis_session_history_service import (  # noqa E501
                RedisSessionHistoryService,
            )

            cls._service_registry[ServiceType.MEMORY][
                ServiceProvider.REDIS
            ] = RedisMemoryService
            cls._service_registry[ServiceType.SESSION_HISTORY][
                ServiceProvider.REDIS
            ] = RedisSessionHistoryService

            # Try to register other services if available
            from agentscope_runtime.engine.services.sandbox_service import (
                SandboxService,
            )

            # Assuming default implementation
            cls._service_registry[ServiceType.SANDBOX] = {
                ServiceProvider.IN_MEMORY: SandboxService,
            }

            from agentscope_runtime.engine.services.rag_service import (
                RAGService,
            )

            # Assuming default implementation
            cls._service_registry[ServiceType.RAG] = {
                ServiceProvider.IN_MEMORY: RAGService,
            }

        except ImportError as e:
            raise RuntimeError(
                f"Failed to import required service classes: {e}",
            ) from e

    @classmethod
    def create_service(
        cls,
        service_type: ServiceType,
        config: ServiceConfig,
    ) -> Any:
        """Create a service instance based on type and configuration.

        Args:
            service_type: Type of service to create
            config: Configuration for the service

        Returns:
            Service instance

        Raises:
            ValueError: If service type or provider is unknown
            RuntimeError: If service creation fails
        """
        cls._populate_registry()

        if service_type not in cls._service_registry:
            raise ValueError(f"Unknown service type: {service_type}")

        providers = cls._service_registry[service_type]
        if config.provider not in providers:
            available_providers = list(providers.keys())
            raise ValueError(
                f"Unknown provider '{config.provider}' for service '"
                f"{service_type}'. Available providers: {available_providers}",
            )

        service_class = providers[config.provider]

        try:
            # Create service instance with configuration parameters
            return service_class(**config.config)
        except Exception as e:
            raise RuntimeError(
                f"Failed to create {service_type} service with provider "
                f"'{config.provider}': {e}",
            ) from e

    @classmethod
    def register_service(
        cls,
        service_type: ServiceType,
        provider: ServiceProvider,
        service_class: Type,
    ):
        """Register a new service implementation.

        Args:
            service_type: Type of service
            provider: Service provider
            service_class: Implementation class
        """
        cls._populate_registry()

        if service_type not in cls._service_registry:
            cls._service_registry[service_type] = {}

        cls._service_registry[service_type][provider] = service_class

    @classmethod
    def create_services_from_config(
        cls,
        config: ServicesConfig,
    ) -> Dict[str, Any]:
        """Create all services from a services configuration.

        Args:
            config: Services configuration

        Returns:
            Dict mapping service names to service instances

        Raises:
            RuntimeError: If any required service creation fails
        """
        services = {}

        # Create required services
        try:
            services["memory"] = cls.create_service(
                ServiceType.MEMORY,
                config.memory,
            )
            services["session_history"] = cls.create_service(
                ServiceType.SESSION_HISTORY,
                config.session_history,
            )
        except Exception as e:
            raise RuntimeError(
                f"Failed to create required services: {e}",
            ) from e

        # Create optional services
        if config.sandbox:
            try:
                services["sandbox"] = cls.create_service(
                    ServiceType.SANDBOX,
                    config.sandbox,
                )
            except Exception as e:
                # Log warning but don't fail
                print(f"Warning: Failed to create sandbox service: {e}")

        if config.rag:
            try:
                services["rag"] = cls.create_service(
                    ServiceType.RAG,
                    config.rag,
                )
            except Exception as e:
                # Log warning but don't fail
                print(f"Warning: Failed to create RAG service: {e}")

        return services

    @classmethod
    def get_available_providers(cls, service_type: ServiceType) -> list:
        """Get list of available providers for a service type.

        Args:
            service_type: Type of service

        Returns:
            List of available provider names
        """
        cls._populate_registry()

        if service_type not in cls._service_registry:
            return []

        return list(cls._service_registry[service_type].keys())
