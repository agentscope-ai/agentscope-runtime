# -*- coding: utf-8 -*-

import os
import inspect

from typing import Callable, Dict, Any, Optional, TypeVar, Generic

from .base import ServiceWithLifecycleManager

T = TypeVar("T", bound=ServiceWithLifecycleManager)


class ServiceFactory(Generic[T]):
    """
    Generic Service Factory base class that supports environment variables
    and kwargs.

    This base class provides a generic factory pattern that supports:
    - Loading configuration from environment variables
    - Overriding environment variables with kwargs
    - Registering custom backends
    """

    _registry: Dict[str, Callable[..., T]] = {}
    _env_prefix: str = ""
    _default_backend: str = "in_memory"

    @classmethod
    def register_backend(
        cls,
        backend_type: str,
        constructor: Callable[..., T],
    ) -> None:
        """Register a constructor function for a backend type.

        Args:
            backend_type: Backend type name (case-insensitive)
            constructor: Constructor function used to create the service
                instance
        """
        cls._registry[backend_type.lower()] = constructor

    @classmethod
    def _load_env_kwargs(cls, backend_type: str) -> Dict[str, Any]:
        """Load backend-specific kwargs from environment variables.

        Args:
            backend_type: Backend type name

        Returns:
            A dictionary of parameters loaded from environment variables
        """
        result = {}
        prefix = f"{cls._env_prefix}{backend_type.upper()}_"

        for key, value in os.environ.items():
            if key.startswith(prefix):
                # env var: SERVICE_TYPE_BACKEND_PARAM -> param
                param_name = key[len(prefix) :].lower()
                result[param_name] = value

        return result

    @classmethod
    async def create(
        cls,
        backend_type: Optional[str] = None,
        **kwargs: Any,
    ) -> T:
        """
        Create and start a service instance, supporting environment
        variables and kwargs.

        Args:
            backend_type: Backend type, if None will read from environment
                variables
            **kwargs: Additional parameters, having higher priority than
                environment variables

        Returns:
            A started service instance

        Raises:
            ValueError: If the backend_type is unsupported
        """
        if backend_type is None:
            backend_type = os.getenv(
                f"{cls._env_prefix}BACKEND",
                cls._default_backend,
            )
        backend_type = backend_type.lower()

        constructor = cls._registry.get(backend_type)
        if constructor is None:
            raise ValueError(f"Unsupported backend type: {backend_type}")

        # 1. Load kwargs for this backend from environment variables
        env_kwargs = cls._load_env_kwargs(backend_type)

        # 2. Merge priority: kwargs > environment variables
        final_kwargs = {**env_kwargs, **kwargs}

        # 3. Filter out kwargs that are not accepted by the constructor
        sig = inspect.signature(constructor)

        has_var_kwargs = any(
            p.kind == inspect.Parameter.VAR_KEYWORD
            for p in sig.parameters.values()
        )

        if not has_var_kwargs:
            accepted_keys = sig.parameters.keys()
            final_kwargs = {
                k: v for k, v in final_kwargs.items() if k in accepted_keys
            }

        # 4. Create instance
        service = constructor(**final_kwargs)
        return service
