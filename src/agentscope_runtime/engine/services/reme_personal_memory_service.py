from typing import Optional, Dict, Any

from .memory_service import MemoryService


class ReMePersonalMemoryService(MemoryService):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        from reme_ai.service.personal_memory_service import PersonalMemoryService
        self.service = PersonalMemoryService()

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
        return await self.service.add_memory(user_id, messages, session_id)

    async def search_memory(
            self,
            user_id: str,
            messages: list,
            filters: Optional[Dict[str, Any]] = None,
    ) -> list:
        return await self.service.search_memory(user_id, messages, filters)

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
