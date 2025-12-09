# -*- coding: utf-8 -*-

from typing import Callable, Dict

from ..service_factory import ServiceFactory
from .state_service import StateService, InMemoryStateService
from .redis_state_service import RedisStateService


class StateServiceFactory(ServiceFactory[StateService]):
    """
    Factory for StateService, supports both environment variables and kwargs
    parameters.

    Usage examples:
        1. Start with environment variables only:
            export STATE_BACKEND=redis
            export STATE_REDIS_REDIS_URL="redis://localhost:6379/5"
            service = await StateServiceFactory.create()

        2. Override environment variables with arguments:
            export STATE_BACKEND=redis
            export STATE_REDIS_REDIS_URL="redis://localhost:6379/5"
            service = await StateServiceFactory.create(
                redis_url="redis://otherhost:6379/1"
            )

        3. User-defined backend:
            from my_backend import PostgresStateService
            StateServiceFactory.register_backend(
                "postgres",
                PostgresStateService,
            )
            export STATE_BACKEND=postgres
            export STATE_POSTGRES_DSN="postgresql://user:pass@localhost/db"
            service = await StateServiceFactory.create()
    """

    _registry: Dict[str, Callable[..., StateService]] = {}
    _env_prefix = "STATE_"
    _default_backend = "in_memory"


StateServiceFactory.register_backend(
    "in_memory",
    lambda **kwargs: InMemoryStateService(),
)

StateServiceFactory.register_backend(
    "redis",
    lambda **kwargs: RedisStateService(
        redis_url=kwargs.get("redis_url", "redis://localhost:6379/0"),
        redis_client=kwargs.get("redis_client"),
    ),
)
