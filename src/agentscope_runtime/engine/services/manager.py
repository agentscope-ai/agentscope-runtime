# -*- coding: utf-8 -*-
import logging
from contextlib import AsyncExitStack
from typing import Dict, Any, Type, List
from abc import ABC, abstractmethod

from agentscope_runtime.engine import Service

logger = logging.getLogger(__name__)


class ServiceManager(ABC):
    """
    Abstract base class for service managers.
    Provides common functionality for service registration and lifecycle
    management.
    """

    def __init__(self):
        self.services = []
        self.service_instances = {}
        self._exit_stack = AsyncExitStack()

        # Initialize default services
        self._register_default_services()

    @abstractmethod
    def _register_default_services(self):
        """
        Register default services for this manager. Override in
        subclasses.
        """

    def register(self, service_class: Type, *args, name: str = None, **kwargs):
        """
        Register a service.

        Args:
            service_class: The class of the service to register.
            *args: Positional arguments for service initialization.
            name: Optional service name. Defaults to class name without
                'Service' suffix and converted to lowercase.
            **kwargs: Keyword arguments for service initialization.

        Returns:
            self: For method chaining
        """
        if name is None:
            name = service_class.__name__.replace("Service", "").lower()

        # Check if service name already exists
        if any(service[3] == name for service in self.services):
            raise ValueError(
                f"Service with name '{name}' is already registered",
            )

        self.services.append((service_class, args, kwargs, name))
        logger.debug(f"Registered service: {name} ({service_class.__name__})")
        return self

    def register_service(self, name: str, service: Service):
        """Register an already instantiated service.

        Args:
            name: Service name
            service: Service instance

        Returns:
            self: For method chaining
        """
        if name in self.service_instances:
            raise ValueError(
                f"Service with name '{name}' is already registered",
            )

        self.service_instances[name] = service
        logger.debug(f"Registered service instance: {name}")
        return self

    async def __aenter__(self):
        """Start all registered services using AsyncExitStack."""
        try:
            # Track services that were registered with register() to avoid
            # duplicate processing
            registered_names = set()

            # Start services that were registered with register()
            for service_class, args, kwargs, name in self.services:
                logger.debug(f"Starting service: {name}")
                instance = service_class(*args, **kwargs)

                # Use AsyncExitStack to manage the context
                await self._exit_stack.enter_async_context(instance)
                self.service_instances[name] = instance
                registered_names.add(name)  # Track this service as processed
                logger.debug(f"Successfully started service: {name}")

            # Start services that were registered with register_service()
            # These services are already instantiated, just need to enter
            # their context
            for name, service in list(self.service_instances.items()):
                if (
                    name not in registered_names
                ):  # Only process services not from register() method
                    logger.debug(f"Starting pre-instantiated service: {name}")
                    await self._exit_stack.enter_async_context(service)
                    logger.debug(
                        f"Successfully started pre-instantiated service:"
                        f" {name}",
                    )

            return self

        except Exception as e:
            logger.error(f"Failed to start services: {e}")
            # Ensure proper cleanup if initialization fails
            await self._exit_stack.aclose()
            raise

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Close all services using AsyncExitStack."""
        logger.debug("Stopping all services")
        await self._exit_stack.aclose()
        self.service_instances.clear()
        logger.debug("All services stopped")
        return False

    def __getattr__(self, name: str):
        """
        Enable attribute access for services, e.g., manager.env,
        manager.session.
        """
        if name in self.service_instances:
            return self.service_instances[name]
        raise AttributeError(f"Service '{name}' not found")

    def __getitem__(self, name: str):
        """Enable dictionary-style access for services."""
        if name in self.service_instances:
            return self.service_instances[name]
        raise KeyError(f"Service '{name}' not found")

    def get(self, name: str, default=None):
        """Explicitly retrieve a service instance with optional default."""
        return self.service_instances.get(name, default)

    def has_service(self, name: str) -> bool:
        """Check if a service exists."""
        return name in self.service_instances

    def list_services(self) -> List[str]:
        """List all registered service names."""
        return list(self.service_instances.keys())

    @property
    def all_services(self) -> Dict[str, Any]:
        """Retrieve all service instances."""
        return self.service_instances.copy()

    async def health_check(self) -> Dict[str, bool]:
        """Check health of all services."""
        health_status = {}
        for name, service in self.service_instances.items():
            try:
                if hasattr(service, "health"):
                    health_status[name] = await service.health()
                else:
                    health_status[
                        name
                    ] = True  # Assume healthy if no health method
            except Exception as e:
                logger.error(f"Health check failed for service {name}: {e}")
                health_status[name] = False
        return health_status
