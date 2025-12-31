# -*- coding: utf-8 -*-
import asyncio
import inspect
import json
import re
from typing import Any, Dict, List, Optional, Type, Union
import uuid

from crewai.memory.storage.interface import Storage
from crewai.memory.external.external_memory import ExternalMemory

from ....engine.schemas.session import Session
from ....engine.schemas.agent_schemas import AgentRole, Role

from ....engine.services.session_history import SessionHistoryService

from ....engine.schemas.agent_schemas import (
    FunctionCall,
    FunctionCallOutput,
    MessageType,
)


async def create_crewai_session_history_memory(
    service_or_class: Union[
        Type[SessionHistoryService],
        SessionHistoryService,
    ],
    user_id: str,
    session_id: str,
) -> ExternalMemory:
    """
    A factory to create a fully initialized CrewAI memory object
    backed by a SessionHistoryService.

    This function intelligently handles both service classes and instances:
    - If a class is provided, it creates an instance and starts it.
    - If an instance is provided, it checks if it's running and
        starts it if not.

    Args:
        service_or_class: The `SessionHistoryService` class to use (e.g.,
                          `InMemorySessionHistoryService`) OR a pre-existing
                          instance of a `SessionHistoryService` subclass.
        user_id: The user identifier.
        session_id: The session identifier.

    Returns:
        A fully initialized and wrapped `ExternalMemory` instance.
    """
    service_instance: SessionHistoryService

    if inspect.isclass(service_or_class) and issubclass(
        service_or_class,
        SessionHistoryService,
    ):
        service_instance = service_or_class()
    elif isinstance(service_or_class, SessionHistoryService):
        service_instance = service_or_class
    else:
        raise TypeError(
            "Expected a SessionHistoryService class or instance, "
            f"but got {type(service_or_class).__name__}",
        )

    if not await service_instance.health():
        await service_instance.start()

    storage_adapter = CrewAISessionHistoryStorage(
        service=service_instance,
        user_id=user_id,
        session_id=session_id,
    )

    return ExternalMemory(storage=storage_adapter)


class CrewAISessionHistoryStorage(Storage):
    def __init__(
        self,
        service: SessionHistoryService,
        user_id: str,
        session_id: str,
    ):
        self._service = service
        self.user_id = user_id
        self.session_id = session_id
        self._session: Optional[Session] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def _get_running_loop(self) -> asyncio.AbstractEventLoop:
        if self._loop and self._loop.is_running():
            return self._loop

        try:
            self._loop = asyncio.get_running_loop()
        except RuntimeError:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
        return self._loop

    async def _ensure_session(self) -> None:
        self._session = await self._service.get_session(
            self.user_id,
            self.session_id,
        )
        if self._session is None:
            self._session = await self._service.create_session(
                self.user_id,
                self.session_id,
            )

    def save(
        self,
        value: Any,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        loop = self._get_running_loop()
        if loop.is_running():
            loop.create_task(self.asave(value, metadata))
        else:
            loop.run_until_complete(self.asave(value, metadata))

    def search(
        self,
        query: str,
        limit: int = 5,
        score_threshold: float = 0.7,
    ) -> List[Dict[str, Any]]:
        loop = self._get_running_loop()
        if loop.is_running():
            future = asyncio.run_coroutine_threadsafe(
                self.asearch(query, limit, score_threshold),
                loop,
            )
            return future.result()
        else:
            return loop.run_until_complete(
                self.asearch(query, limit, score_threshold),
            )

    def reset(self) -> None:
        loop = self._get_running_loop()
        if loop.is_running():
            loop.create_task(self.areset())
        else:
            loop.run_until_complete(self.areset())

    async def asave(
        self,
        value: Any,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        await self._ensure_session()
        if self._session is None:
            raise RuntimeError(
                f"Failed to create or retrieve session '{self.session_id}'.",
            )
        messages_to_save = self._parse_and_format_turn_structured(
            value,
            metadata,
        )
        if messages_to_save:
            await self._service.append_message(self._session, messages_to_save)

    # pylint: disable=unused-argument
    async def asearch(
        self,
        query: str,
        limit: int = 5,
        score_threshold: float = 0.7,
    ) -> List[Dict[str, Any]]:
        await self._ensure_session()
        if not self._session or not self._session.messages:
            return []
        recent_messages = self._session.messages[-20:]
        return self._format_structured_history_for_crewai(recent_messages)

    async def areset(self) -> None:
        await self._service.delete_session(
            user_id=self.user_id,
            session_id=self.session_id,
        )
        self._session = None

    def _parse_and_format_turn_structured(
        self,
        value: Any,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        if not metadata or not isinstance(metadata.get("messages"), list):
            return self._parse_and_format_turn_simple(value, metadata)
        all_messages_to_save = []
        for turn_message in metadata["messages"]:
            role, content = turn_message.get("role"), str(
                turn_message.get("content", ""),
            )
            if not content:
                continue
            if role == "user":
                user_task = metadata.get("description", content).strip()
                if not any(
                    m.get("role") == Role.USER for m in all_messages_to_save
                ):
                    all_messages_to_save.append(
                        self._create_structured_message(
                            Role.USER,
                            MessageType.MESSAGE,
                            text_content=user_task,
                        ),
                    )
            elif role == "assistant":
                all_messages_to_save.extend(
                    self._parse_assistant_content(content),
                )
        return all_messages_to_save

    # pylint: disable=too-many-branches
    def _parse_assistant_content(self, content: str) -> List[Dict[str, Any]]:
        messages = []
        remaining_content = content

        final_answer_pattern = r"\n*Final Answer:\s*(.*)"
        observation_pattern = r"\n*Observation:\s*(.*)"
        action_input_pattern = r"\n*Action Input:\s*({.*})"
        action_pattern = r"\n*Action:\s*([\w_]+)"

        final_answer_text = None
        final_answer_match = re.search(
            final_answer_pattern,
            remaining_content,
            re.DOTALL,
        )
        if final_answer_match:
            final_answer_text = final_answer_match.group(1).strip()
            remaining_content = re.sub(
                final_answer_pattern,
                "",
                remaining_content,
                count=1,
                flags=re.DOTALL,
            )

        obs_text = None
        observation_match = re.search(
            observation_pattern,
            remaining_content,
            re.DOTALL,
        )
        if observation_match:
            obs_text = observation_match.group(1).strip()
            remaining_content = re.sub(
                observation_pattern,
                "",
                remaining_content,
                count=1,
                flags=re.DOTALL,
            )

        input_str = None
        input_match = re.search(
            action_input_pattern,
            remaining_content,
            re.DOTALL,
        )
        if input_match:
            input_str = input_match.group(1).strip()
            remaining_content = re.sub(
                action_input_pattern,
                "",
                remaining_content,
                count=1,
                flags=re.DOTALL,
            )

        action_name = None
        action_match = re.search(action_pattern, remaining_content)
        if action_match:
            action_name = action_match.group(1).strip()
            remaining_content = re.sub(
                action_pattern,
                "",
                remaining_content,
                count=1,
            )

        call_id = None
        if obs_text:
            try:
                obs_json = json.loads(obs_text)
                if isinstance(obs_json, dict) and "request_id" in obs_json:
                    call_id = obs_json["request_id"]
            except (json.JSONDecodeError, TypeError):
                pass

        if call_id is None and action_name:
            call_id = uuid.uuid4().hex

        # 1. The remainder is guaranteed to be pure Thought
        thought_text = (
            remaining_content.strip().removeprefix("Thought:").strip()
        )
        if thought_text:
            messages.append(
                self._create_structured_message(
                    Role.ASSISTANT,
                    MessageType.REASONING,
                    text_content=thought_text,
                ),
            )

        # 2. Action/Input
        if action_name and input_str and call_id:
            call_data = FunctionCall(
                call_id=call_id,
                name=action_name,
                arguments=input_str,
            ).model_dump()
            messages.append(
                self._create_structured_message(
                    Role.ASSISTANT,
                    MessageType.PLUGIN_CALL,
                    data_content=call_data,
                ),
            )

        # 3. Observation
        if obs_text and call_id and action_name:
            output_data = FunctionCallOutput(
                call_id=call_id,
                name=action_name,
                output=obs_text,
            ).model_dump(exclude_none=True)
            messages.append(
                self._create_structured_message(
                    Role.SYSTEM,
                    MessageType.PLUGIN_CALL_OUTPUT,
                    data_content=output_data,
                ),
            )

        # 4. Final Answer
        if final_answer_text:
            messages.append(
                self._create_structured_message(
                    Role.ASSISTANT,
                    MessageType.MESSAGE,
                    text_content=final_answer_text,
                ),
            )

        # Fallback
        if not messages and content:
            messages.append(
                self._create_structured_message(
                    Role.ASSISTANT,
                    MessageType.MESSAGE,
                    text_content=content,
                ),
            )

        return messages

    @staticmethod
    def _format_structured_history_for_crewai(
        runtime_messages: List[Dict[str, Any]],
    ) -> List[Dict[str, str]]:
        formatted_context = []
        if not runtime_messages:
            return formatted_context

        formatted_context.append(
            {"content": "Context from Session History Service:"},
        )

        for msg in runtime_messages:
            role = msg.get("role")
            msg_type = msg.get("type")
            content_list = msg.get("content", [])

            text_parts = []

            if msg_type == MessageType.MESSAGE:
                text = content_list[0].get("text", "")
                prefix = (
                    "User asked" if role == Role.USER else "Assistant answered"
                )
                text_parts.append(f"{prefix}: {text}")

            elif msg_type == MessageType.REASONING:
                text = content_list[0].get("text", "")
                text_parts.append(f"Assistant thought: {text}")

            elif msg_type == MessageType.PLUGIN_CALL:
                data = content_list[0].get("data", {})
                tool_name = data.get("name", "unknown_tool")
                args = data.get("arguments", "{}")
                text_parts.append(
                    f"Assistant decided to use tool '{tool_name}' "
                    f"with input: {args}",
                )

            elif msg_type == MessageType.PLUGIN_CALL_OUTPUT:
                data = content_list[0].get("data", {})
                tool_name = data.get("name", "unknown_tool")
                output = data.get("output", "[No output]")
                if len(output) > 500:  # Truncate long outputs
                    output = output[:500] + "..."
                text_parts.append(
                    f"Tool '{tool_name}' returned: {output}",
                )

            full_text = " ".join(text_parts)
            if full_text:
                formatted_context.append({"content": full_text})

        return formatted_context

    @staticmethod
    def _create_structured_message(
        role: Union[AgentRole, str],
        msg_type: Union[MessageType, str],
        text_content: Optional[str] = None,
        data_content: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        content_list: List[Dict[str, Any]] = []
        if text_content is not None:
            content_list.append({"type": "text", "text": text_content})
        if data_content is not None:
            content_list.append({"type": "data", "data": data_content})
        return {
            "role": str(role),
            "type": str(msg_type),
            "content": content_list,
        }

    def _parse_and_format_turn_simple(
        self,
        value: Any,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        if not metadata or not value:
            return []
        user_content_str = metadata.get("description", "").strip()
        try:
            assistant_content_str = (
                str(value).rsplit("Final Answer:", maxsplit=1)[-1].strip()
            )
        except (AttributeError, IndexError):
            assistant_content_str = str(value).strip()
        messages = []
        if user_content_str:
            messages.append(
                self._create_structured_message(
                    Role.USER,
                    MessageType.MESSAGE,
                    text_content=user_content_str,
                ),
            )
        if assistant_content_str:
            messages.append(
                self._create_structured_message(
                    Role.ASSISTANT,
                    MessageType.MESSAGE,
                    text_content=assistant_content_str,
                ),
            )
        return messages
