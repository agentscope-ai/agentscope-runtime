# -*- coding: utf-8 -*-
import os
from typing import Optional, Dict, Any, List

from mem0 import AsyncMemoryClient

from .memory_service import MemoryService
from ...schemas.agent_schemas import Message, MessageType, ContentType


class Mem0MemoryService(MemoryService):
    """
    Memory service that uses mem0 to store and retrieve memories.
    To get the api key, please refer to the following link:
    https://docs.mem0.ai/platform/quickstart
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.service = None
        self._health = False

    @staticmethod
    async def get_query_text(message: Message) -> str:
        """
        Get the query text from the message.
        """
        if message:
            if message.type == MessageType.MESSAGE:
                for content in message.content:
                    if content.type == ContentType.TEXT:
                        return content.text
        return ""

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

    async def transform_messages(self, messages: List[Message]) -> List[dict]:
        return [self.transform_message(message) for message in messages]

    async def start(self):
        mem0_api_key = os.getenv("MEM0_API_KEY")
        if mem0_api_key is None:
            raise ValueError("MEM0_API_KEY is not set")
        mem0_api_key = os.getenv("MEM0_API_KEY")

        # get the mem0 client instance
        self.service = AsyncMemoryClient(api_key=mem0_api_key)
        self._health = True

    async def stop(self):
        self.service = None
        self._health = False

    async def health(self):
        return self._health

    async def add_memory(
        self,
        user_id: str,
        messages: list,
        session_id: Optional[str] = None,
    ):
        messages = await self.transform_messages(messages)
        return await self.service.add(
            messages=messages,
            user_id=user_id,
            run_id=session_id,
            # async_mode=True,
        )

    async def search_memory(
        self,
        user_id: str,
        messages: list,
        filters: Optional[Dict[str, Any]] = None,
    ) -> list:
        query = await self.get_query_text(messages[-1])
        kwargs = {
            "query": query,
            "user_id": user_id,
        }
        if filters:
            kwargs["filters"] = filters
        return await self.service.search(**kwargs)

    async def list_memory(
        self,
        user_id: str,
        filters: Optional[Dict[str, Any]] = None,
    ) -> list:
        kwargs = {"user_id": user_id}
        if filters:
            kwargs["filters"] = filters
        return await self.service.get_all(**kwargs)

    async def delete_memory(
        self,
        user_id: str,
        session_id: Optional[str] = None,
    ) -> None:
        if session_id:
            return await self.service.delete_all(
                user_id=user_id,
                run_id=session_id,
            )
        else:
            return await self.service.delete_all(user_id=user_id)
