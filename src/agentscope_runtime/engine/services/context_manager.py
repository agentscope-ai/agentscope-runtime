# -*- coding: utf-8 -*-
import warnings

from contextlib import asynccontextmanager
from typing import List

from .manager import ServiceManager
from .memory_service import MemoryService
from .state_service import StateService
from .session_history_service import (
    SessionHistoryService,
    Session,
    InMemorySessionHistoryService,
)
from ..schemas.agent_schemas import Message


class ContextComposer:
    def __init__(self):
        warnings.warn(
            "ContextComposer is deprecated and will be removed in version "
            "v1.0.",
            DeprecationWarning,
            stacklevel=2,
        )
        super().__init__()

    @staticmethod
    async def compose(
        request_input: List[Message],  # current input
        session: Session,  # session
        memory_service: MemoryService = None,
        session_history_service: SessionHistoryService = None,
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


class ContextManager(ServiceManager):
    """
    The contextManager class
    """

    def __init__(
        self,
        context_composer_cls=ContextComposer,
        session_history_service: SessionHistoryService = None,
        memory_service: MemoryService = None,
        state_service: StateService = None,
    ):
        self._context_composer_cls = context_composer_cls
        self._session_history_service = session_history_service
        self._memory_service = memory_service
        self._state_service = state_service
        super().__init__()

    def _register_default_services(self):
        """Register default services for context management."""
        self._session_history_service = (
            self._session_history_service or InMemorySessionHistoryService()
        )

        # Default services
        self.register_service("session", self._session_history_service)

        # Optional services
        if self._memory_service:
            self.register_service("memory", self._memory_service)
        if self._state_service:
            self.register_service("state", self._state_service)

    async def compose_context(
        self,
        session: Session,
        request_input: List[Message],
    ):
        await self._context_composer_cls.compose(
            memory_service=self._memory_service,
            session_history_service=self._session_history_service,
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
    context_composer_cls=ContextComposer,
):
    manager = ContextManager(
        memory_service=memory_service,
        session_history_service=session_history_service,
        context_composer_cls=context_composer_cls,
    )

    async with manager:
        yield manager
