# -*- coding: utf-8 -*-
from .reme_personal_memory_service import ReMePersonalMemoryService


class ReMeTaskMemoryService(ReMePersonalMemoryService):
    """
    Task memory service with optional mock mode.

    If mock_mode=True is provided, API keys and URLs are not required.
    """

    def __init__(self, mock_mode: bool = False, **kwargs):
        super().__init__(mock_mode=mock_mode, **kwargs)

        if not mock_mode:
            from reme_ai.service.task_memory_service import TaskMemoryService

            self.service = TaskMemoryService()
