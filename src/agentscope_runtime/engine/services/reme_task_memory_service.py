# -*- coding: utf-8 -*-
from .reme_personal_memory_service import ReMePersonalMemoryService


class ReMeTaskMemoryService(ReMePersonalMemoryService):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        from reme_ai.service.task_memory_service import TaskMemoryService

        self.service = TaskMemoryService()
