# -*- coding: utf-8 -*-

from typing import Callable, Dict

from ..service_factory import ServiceFactory
from .session_history_service import (
    SessionHistoryService,
    InMemorySessionHistoryService,
)
from .redis_session_history_service import RedisSessionHistoryService

try:
    from .tablestore_session_history_service import (
        TablestoreSessionHistoryService,
    )

    TABLESTORE_AVAILABLE = True
except ImportError:
    TABLESTORE_AVAILABLE = False


class SessionHistoryServiceFactory(ServiceFactory[SessionHistoryService]):
    """
    Factory for SessionHistoryService, supporting both environment variables
    and keyword arguments.

    Usage examples:
        1. Start with only environment variables:
            export SESSION_HISTORY_BACKEND=redis
            export SESSION_HISTORY_REDIS_REDIS_URL="redis://localhost:6379/5"
            service = await SessionHistoryServiceFactory.create()

        2. Override environment variables with arguments:
            export SESSION_HISTORY_BACKEND=redis
            export SESSION_HISTORY_REDIS_REDIS_URL="redis://localhost:6379/5"
            service = await SessionHistoryServiceFactory.create(
                redis_url="redis://otherhost:6379/1"
            )

        3. Register a custom backend:
            from my_backend import PostgresSessionHistoryService
            SessionHistoryServiceFactory.register_backend(
                "postgres",
                PostgresSessionHistoryService,
            )
            export SESSION_HISTORY_BACKEND=postgres
            export SESSION_HISTORY_POSTGRES_DSN="postgresql://user:pass@localhost/db"  # noqa
            export SESSION_HISTORY_POSTGRES_POOL_SIZE="20"
            service = await SessionHistoryServiceFactory.create()
    """

    _registry: Dict[str, Callable[..., SessionHistoryService]] = {}
    _env_prefix = "SESSION_HISTORY_"
    _default_backend = "in_memory"


# === Default built-in backend registration ===

SessionHistoryServiceFactory.register_backend(
    "in_memory",
    InMemorySessionHistoryService,
)

SessionHistoryServiceFactory.register_backend(
    "redis",
    RedisSessionHistoryService,
)

if TABLESTORE_AVAILABLE:
    SessionHistoryServiceFactory.register_backend(
        "tablestore",
        TablestoreSessionHistoryService,
    )
