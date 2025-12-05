# -*- coding: utf-8 -*-

from typing import Callable, Dict

from ..service_factory import ServiceFactory
from .memory_service import MemoryService, InMemoryMemoryService
from .redis_memory_service import RedisMemoryService
from .mem0_memory_service import Mem0MemoryService
from .reme_personal_memory_service import ReMePersonalMemoryService
from .reme_task_memory_service import ReMeTaskMemoryService

try:
    from .tablestore_memory_service import (
        TablestoreMemoryService,
        SearchStrategy,
    )

    TABLESTORE_AVAILABLE = True
except ImportError:
    TABLESTORE_AVAILABLE = False
    SearchStrategy = None  # type: ignore


class MemoryServiceFactory(ServiceFactory[MemoryService]):
    """
    Factory for MemoryService, supporting both environment variables and
    kwargs.

    Usage examples:
        1. Startup using only environment variables:
            export MEMORY_BACKEND=redis
            export MEMORY_REDIS_REDIS_URL="redis://localhost:6379/5"
            service = await MemoryServiceFactory.create()

        2. Override environment variables using arguments:
            export MEMORY_BACKEND=redis
            export MEMORY_REDIS_REDIS_URL="redis://localhost:6379/5"
            service = await MemoryServiceFactory.create(
                redis_url="redis://otherhost:6379/1"
            )

        3. Register a custom backend:
            from my_backend import PostgresMemoryService
            MemoryServiceFactory.register_backend(
                "postgres",
                PostgresMemoryService,
            )
            export MEMORY_BACKEND=postgres
            export MEMORY_POSTGRES_DSN="postgresql://user:pass@localhost/db"
            service = await MemoryServiceFactory.create()
    """

    _registry: Dict[str, Callable[..., MemoryService]] = {}
    _env_prefix = "MEMORY_"
    _default_backend = "in_memory"


# === Default built-in backend registration ===

MemoryServiceFactory.register_backend(
    "in_memory",
    lambda **kwargs: InMemoryMemoryService(),
)

MemoryServiceFactory.register_backend(
    "redis",
    RedisMemoryService,
)

MemoryServiceFactory.register_backend(
    "mem0",
    Mem0MemoryService,
)

MemoryServiceFactory.register_backend(
    "reme_personal",
    ReMePersonalMemoryService,
)

MemoryServiceFactory.register_backend(
    "reme_task",
    ReMeTaskMemoryService,
)

if TABLESTORE_AVAILABLE:

    def _create_tablestore_memory_service(**kwargs):
        """Helper function to create a TablestoreMemoryService instance."""
        search_strategy = kwargs.get("search_strategy")
        if isinstance(search_strategy, str):
            search_strategy = SearchStrategy(search_strategy.lower())
        elif search_strategy is None:
            search_strategy = SearchStrategy.FULL_TEXT

        return TablestoreMemoryService(
            tablestore_client=kwargs["tablestore_client"],
            search_strategy=search_strategy,
            embedding_model=kwargs.get("embedding_model"),
            vector_dimension=int(kwargs.get("vector_dimension", 1536)),
            table_name=kwargs.get("table_name", "agentscope_runtime_memory"),
            search_index_schema=kwargs.get("search_index_schema"),
            text_field=kwargs.get("text_field", "text"),
            embedding_field=kwargs.get("embedding_field", "embedding"),
            vector_metric_type=kwargs.get("vector_metric_type"),
            **{
                k: v
                for k, v in kwargs.items()
                if k
                not in [
                    "tablestore_client",
                    "search_strategy",
                    "embedding_model",
                    "vector_dimension",
                    "table_name",
                    "search_index_schema",
                    "text_field",
                    "embedding_field",
                    "vector_metric_type",
                ]
            },
        )

    MemoryServiceFactory.register_backend(
        "tablestore",
        _create_tablestore_memory_service,
    )
