# -*- coding: utf-8 -*-
import os
from typing import Optional, Dict, Any, List

from .memory_service import MemoryService
from ..schemas.agent_schemas import Message


class ReMePersonalMemoryService(MemoryService):
    """
    ReMe requires the following env variables to be set:
    FLOW_EMBEDDING_API_KEY=sk-xxxx
    FLOW_EMBEDDING_BASE_URL=https://xxxx/v1
    FLOW_LLM_API_KEY=sk-xxxx
    FLOW_LLM_BASE_URL=https://xxxx/v1
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        for key in [
            "FLOW_EMBEDDING_API_KEY",
            "FLOW_EMBEDDING_BASE_URL",
            "FLOW_LLM_API_KEY",
            "FLOW_LLM_BASE_URL",
        ]:
            if os.getenv(key) is None:
                raise ValueError(f"{key} is not set")

        from reme_ai.service.personal_memory_service import (
            PersonalMemoryService,
        )

        self.service = PersonalMemoryService()

    @staticmethod
    def transform_message(message: Message) -> dict:
        content_text = None

        try:
            if hasattr(message, "content") and isinstance(
                message.content,
                list,
            ):
                if len(message.content) > 0 and hasattr(
                    message.content[0],
                    "text",
                ):
                    content_text = message.content[0].text
        except (AttributeError, IndexError):
            # Log error or handle appropriately
            pass

        return {
            "role": getattr(message, "role", None),
            "content": content_text,
        }

    def transform_messages(self, messages: List[Message]) -> List[dict]:
        return [self.transform_message(message) for message in messages]

    async def start(self) -> None:
        return await self.service.start()

    async def stop(self) -> None:
        return await self.service.stop()

    async def health(self) -> bool:
        return await self.service.health()

    async def add_memory(
        self,
        user_id: str,
        messages: list,
        session_id: Optional[str] = None,
    ) -> None:
        return await self.service.add_memory(
            user_id,
            self.transform_messages(messages),
            session_id,
        )

    async def search_memory(
        self,
        user_id: str,
        messages: list,
        filters: Optional[Dict[str, Any]] = None,
    ) -> list:
        return await self.service.search_memory(
            user_id,
            self.transform_messages(messages),
            filters,
        )

    async def list_memory(
        self,
        user_id: str,
        filters: Optional[Dict[str, Any]] = None,
    ) -> list:
        return await self.service.list_memory(user_id, filters)

    async def delete_memory(
        self,
        user_id: str,
        session_id: Optional[str] = None,
    ) -> None:
        return await self.service.delete_memory(user_id, session_id)
