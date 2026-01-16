# -*- coding: utf-8 -*-
from typing import TYPE_CHECKING
from ....common.utils.lazy_loader import install_lazy_loader
from ....common.utils.deprecation import deprecated_module

deprecated_module(
    module_name=__name__,
    removed_in="v1.1",
    alternative="agentscope.memory",
)

if TYPE_CHECKING:
    from .memory_service import MemoryService, InMemoryMemoryService
    from .redis_memory_service import RedisMemoryService
    from .reme_task_memory_service import ReMeTaskMemoryService
    from .reme_personal_memory_service import ReMePersonalMemoryService
    from .mem0_memory_service import Mem0MemoryService
    from .tablestore_memory_service import TablestoreMemoryService
    from .memory_service_factory import MemoryServiceFactory

install_lazy_loader(
    globals(),
    {
        "MemoryService": ".memory_service",
        "InMemoryMemoryService": ".memory_service",
        "RedisMemoryService": ".redis_memory_service",
        "ReMeTaskMemoryService": ".reme_task_memory_service",
        "ReMePersonalMemoryService": ".reme_personal_memory_service",
        "Mem0MemoryService": ".mem0_memory_service",
        "TablestoreMemoryService": ".tablestore_memory_service",
        "MemoryServiceFactory": ".memory_service_factory",
    },
)
