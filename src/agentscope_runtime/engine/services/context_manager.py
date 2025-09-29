# -*- coding: utf-8 -*-
from contextlib import asynccontextmanager
from typing import List

from .manager import ServiceManager
from .memory_service import MemoryService, InMemoryMemoryService
from .rag_service import RAGService
from .session_history_service import (
    SessionHistoryService,
    Session,
    InMemorySessionHistoryService,
)
from ..schemas.agent_schemas import (
    Message,
    MessageType,
    Role,
    TextContent,
    ContentType,
)


class ContextComposer:
    @staticmethod
    async def compose(
        request_input: List[Message],  # current input
        session: Session,  # session
        memory_service: MemoryService = None,
        session_history_service: SessionHistoryService = None,
        rag_service: RAGService = None,
    ):
        # session
        if session_history_service:
            await session_history_service.append_message(
                session=session,
                message=request_input,
            )
        else:
            session.messages += request_input
        # memory
        if memory_service:
            memories: List[Message] = await memory_service.search_memory(
                user_id=session.user_id,
                messages=request_input,
                filters={"top_k": 5},
            )
            await memory_service.add_memory(
                user_id=session.user_id,
                messages=request_input,
                session_id=session.id,
            )
            session.messages = memories + session.messages

        # rag
        if rag_service:
            query = await rag_service.get_query_text(request_input[-1])
            docs = await rag_service.retrieve(query=query, k=5)
            cooked_doc = "\n".join(docs)
            message = Message(
                type=MessageType.MESSAGE,
                role=Role.SYSTEM,
                content=[TextContent(type=ContentType.TEXT, text=cooked_doc)],
            )
            if len(session.messages) >= 1:
                last_message = session.messages[-1]
                session.messages.remove(last_message)
                session.messages.append(message)
                session.messages.append(last_message)
            else:
                session.messages.append(message)


class ContextManager(ServiceManager):
    """
    The contextManager class
    """

    def __init__(
        self,
        context_composer_cls=ContextComposer,
        session_history_service: SessionHistoryService = None,
        memory_service: MemoryService = None,
        rag_service: RAGService = None,
    ):
        self._context_composer_cls = context_composer_cls
        self._session_history_service = session_history_service
        self._memory_service = memory_service
        self._rag_service = rag_service
        super().__init__()

    def _register_default_services(self):
        """Register default services for context management."""
        self._session_history_service = (
            self._session_history_service or InMemorySessionHistoryService()
        )
        self._memory_service = self._memory_service or InMemoryMemoryService()

        self.register_service("session", self._session_history_service)
        self.register_service("memory", self._memory_service)
        if self._rag_service:
            self.register_service("rag", self._rag_service)

    async def compose_context(
        self,
        session: Session,
        request_input: List[Message],
    ):
        await self._context_composer_cls.compose(
            memory_service=self._memory_service,
            session_history_service=self._session_history_service,
            rag_service=self._rag_service,
            session=session,
            request_input=request_input,
        )

    async def compose_session(
        self,
        user_id: str,
        session_id: str,
    ):
        if self._session_history_service:
            session = await self._session_history_service.get_session(
                user_id=user_id,
                session_id=session_id,
            )
            if not session:
                raise RuntimeError(f"Session {session_id} not found")
        else:
            session = Session(
                user_id=user_id,
                id=session_id,
                messages=[],
            )
        return session

    async def append(self, session: Session, event_output: List[Message]):
        if self._session_history_service:
            await self._session_history_service.append_message(
                session=session,
                message=event_output,
            )
        if self._memory_service:
            await self._memory_service.add_memory(
                user_id=session.user_id,
                session_id=session.id,
                messages=event_output,
            )


@asynccontextmanager
async def create_context_manager(
    memory_service: MemoryService = None,
    session_history_service: SessionHistoryService = None,
    rag_service: RAGService = None,
    context_composer_cls=ContextComposer,
):
    manager = ContextManager(
        memory_service=memory_service,
        session_history_service=session_history_service,
        rag_service=rag_service,
        context_composer_cls=context_composer_cls,
    )

    async with manager:
        yield manager
