# -*- coding: utf-8 -*-
import os
import uuid
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

    If mock_mode=True is provided, these env variables are not required.
    """

    def __init__(self, mock_mode: bool = False, **kwargs):
        super().__init__(**kwargs)
        self.mock_mode = mock_mode

        # For mock mode
        self.memory_store = {}  # user_id -> list of memories
        self.session_id_dict = {}  # session_id -> list of memory_ids

        if not mock_mode:
            for key in [
                "FLOW_EMBEDDING_API_KEY",
                "FLOW_EMBEDDING_BASE_URL",
                "FLOW_LLM_API_KEY",
                "FLOW_LLM_BASE_URL",
            ]:
                if os.getenv(key) is None:
                    raise ValueError(
                        f"ReMe requires the following env {key} to be set",
                    )

            from reme_ai.service.personal_memory_service import (
                PersonalMemoryService,
            )

            self.service = PersonalMemoryService()

    def add_session_memory_id(self, session_id: str, memory_id):
        """Add memory ID to session tracking"""
        if session_id not in self.session_id_dict:
            self.session_id_dict[session_id] = []

        self.session_id_dict[session_id].append(memory_id)

    @staticmethod
    def transform_message(message: Message) -> dict:
        if (
            hasattr(message, "content")
            and isinstance(message.content, list)
            and len(message.content) > 0
            and hasattr(message.content[0], "text")
        ):
            content_text = message.content[0].text
        else:
            # Optionally, raise an error or log a warning here
            content_text = None
        return {
            "role": message.role,
            "content": content_text,
        }

    def transform_messages(self, messages: List[Message]) -> List[dict]:
        return [self.transform_message(message) for message in messages]

    async def start(self) -> None:
        """Start the service"""
        if self.mock_mode:
            return None
        else:
            return await self.service.start()

    async def stop(self) -> None:
        """Stop the service"""
        if self.mock_mode:
            return None
        else:
            return await self.service.stop()

    async def health(self) -> bool:
        """Check service health"""
        if self.mock_mode:
            return True
        else:
            return await self.service.health()

    async def add_memory(
        self,
        user_id: str,
        messages: list,
        session_id: Optional[str] = None,
    ) -> None:
        """Add memory to the service"""
        transformed_messages = self.transform_messages(messages)
        if not session_id:
            session_id = str(uuid.uuid4())

        if self.mock_mode:
            if user_id not in self.memory_store:
                self.memory_store[user_id] = []

            for message in transformed_messages:
                memory_id = str(uuid.uuid4())
                content = (
                    message.get("content", "")
                    if isinstance(message, dict)
                    else "Mock content"
                )

                memory_item = {
                    "memory_id": memory_id,
                    "content": content,
                    "session_id": session_id,
                }

                self.memory_store[user_id].append(memory_item)
                self.add_session_memory_id(session_id, memory_id)
            return None

        else:
            return await self.service.add_memory(
                user_id,
                transformed_messages,
                session_id,
            )

    async def search_memory(
        self,
        user_id: str,
        messages: list,
        filters: Optional[Dict[str, Any]] = None,
    ) -> list:
        """Search memories from the service"""
        transformed_messages = self.transform_messages(messages)

        if self.mock_mode:
            if (
                user_id not in self.memory_store
                or not self.memory_store[user_id]
            ):
                return ["No memories found"]

            # Get the query from the last message
            query = ""
            if transformed_messages and isinstance(
                transformed_messages[-1],
                dict,
            ):
                query = transformed_messages[-1].get("content", "")

            top_k = filters.get("top_k", 1) if filters else 1

            results = []
            for memory in self.memory_store[user_id]:
                if query.lower() in memory["content"].lower():
                    results.append(f"Memory: {memory['content']}")

                if len(results) >= top_k:
                    break

            if not results:
                results = ["No relevant memories found"]
            return results
        else:
            return await self.service.search_memory(
                user_id,
                transformed_messages,
                filters,
            )

    async def list_memory(
        self,
        user_id: str,
        filters: Optional[Dict[str, Any]] = None,
    ) -> list:
        """List all memories for a user"""
        if self.mock_mode:
            if user_id not in self.memory_store:
                return []

            results = [
                f"Memory: {memory['content']}"
                for memory in self.memory_store[user_id]
            ]
            return results
        else:
            return await self.service.list_memory(user_id, filters)

    async def delete_memory(
        self,
        user_id: str,
        session_id: Optional[str] = None,
    ) -> None:
        """Delete memories for a user"""
        if self.mock_mode:
            if user_id not in self.memory_store:
                return None

            if session_id:
                # Delete memories for this session
                delete_ids = self.session_id_dict.get(session_id, [])
                if delete_ids:
                    self.memory_store[user_id] = [
                        memory
                        for memory in self.memory_store[user_id]
                        if memory["memory_id"] not in delete_ids
                    ]
                return None
            else:
                # Delete all memories for this user
                self.memory_store[user_id] = []
                return None
        else:
            return await self.service.delete_memory(user_id, session_id)
