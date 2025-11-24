# -*- coding: utf-8 -*-
from typing import TYPE_CHECKING
from ....common.utils.lazy_loader import install_lazy_loader

if TYPE_CHECKING:
    from .memory_service import MemoryService, InMemoryMemoryService
    from .redis_memory_service import RedisMemoryService
    from .reme_task_memory_service import ReMeTaskMemoryService
    from .reme_personal_memory_service import ReMePersonalMemoryService
    from .mem0_memory_service import Mem0MemoryService
    from .tablestore_memory_service import TablestoreMemoryService

install_lazy_loader(
    globals(),
    {
        "MemoryService": ".memory_service",
        "InMemoryMemoryService": ".memory_service",
        "RedisMemoryService": ".redis_memory_service",
        "ReMeTaskMemoryService": {
            "module": ".reme_task_memory_service",
            "hint": "pip install agentscope-runtime[memory-ext]",
        },
        "ReMePersonalMemoryService": {
            "module": ".reme_personal_memory_service",
            "hint": "pip install agentscope-runtime[memory-ext]",
        },
        "Mem0MemoryService": {
            "module": ".mem0_memory_service",
            "hint": "pip install agentscope-runtime[memory-ext]",
        },
        "TablestoreMemoryService": {
            "module": ".tablestore_memory_service",
            "hint": "pip install agentscope-runtime[aliyun_tablestore_ext]",
        },
    },
)
