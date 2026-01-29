# -*- coding: utf-8 -*-
# pylint: disable=too-many-branches,too-many-statements
import json
from typing import AsyncIterator, Any, Dict, Optional, Union, Iterator

from ..utils import _update_obj_attrs
from ...engine.schemas.agent_schemas import (
    Message,
    Content,
    TextContent,
    DataContent,
    FileContent,
    FunctionCall,
    FunctionCallOutput,
    MessageType,
)
from ...engine.schemas.exception import AgentRuntimeErrorException


async def adapt_opencode_message_stream(
    source_stream: AsyncIterator[Any],
) -> AsyncIterator[Union[Message, Content]]:
    """
    Adapt OpenCode event stream into runtime Message/Content stream.
    """
    text_states: Dict[str, "_TextStreamState"] = {}
    reasoning_states: Dict[str, "_TextStreamState"] = {}
    tool_states: Dict[str, "_ToolStreamState"] = {}
    agent_by_message_id: Dict[str, str] = {}
    usage_by_message_id: Dict[str, Dict[str, Any]] = {}
    usage_state: Dict[str, Optional[Dict[str, Any]]] = {"last": None}

    async for raw_event in source_stream:
        event = _normalize_event(raw_event)
        if event is None:
            continue

        event_type = event.get("type")
        if not event_type:
            continue

        if event_type == "message.updated":
            info = _get_event_properties(event).get("info")
            if isinstance(info, dict):
                if info.get("role") == "assistant":
                    # Map message_id -> agent name and cache usage if provided.
                    message_id = info.get("id")
                    agent_name = info.get("agent")
                    if message_id and agent_name:
                        agent_by_message_id[message_id] = agent_name
                        _update_active_agent_states(
                            message_id,
                            agent_name,
                            text_states,
                            reasoning_states,
                            tool_states,
                        )

                    usage = _usage_from_info(info)
                    if message_id and usage:
                        usage_by_message_id[message_id] = usage
                        usage_state["last"] = usage
            continue

        if event_type == "message.part.updated":
            props = _get_event_properties(event)
            part = props.get("part")
            delta = props.get("delta")
            if not isinstance(part, dict):
                continue

            for item in _handle_part_event(
                part,
                delta,
                text_states,
                reasoning_states,
                tool_states,
                agent_by_message_id,
                usage_by_message_id,
                usage_state,
            ):
                yield item
            continue

        if event_type == "message.part.removed":
            props = _get_event_properties(event)
            for item in _emit_data_message(
                {
                    "type": "part-removed",
                    "sessionID": props.get("sessionID"),
                    "messageID": props.get("messageID"),
                    "partID": props.get("partID"),
                },
                agent_by_message_id,
                usage_by_message_id,
                usage_state,
            ):
                yield item
            continue

        if event_type == "message.removed":
            props = _get_event_properties(event)
            for item in _emit_data_message(
                {
                    "type": "message-removed",
                    "sessionID": props.get("sessionID"),
                    "messageID": props.get("messageID"),
                },
                agent_by_message_id,
                usage_by_message_id,
                usage_state,
            ):
                yield item
            continue

        if event_type == "session.error":
            props = _get_event_properties(event)
            detail = props.get("error") or {}
            message = _stringify_error(detail)
            raise AgentRuntimeErrorException(
                "OPENCODE_SESSION_ERROR",
                message,
                {"opencode_error": detail},
            )

        if event_type == "session.idle":
            continue

        if event_type == "session.status":
            props = _get_event_properties(event)
            status = props.get("status") if isinstance(props, dict) else None
            if isinstance(status, dict) and status.get("type") == "idle":
                continue
            continue

        for item in _emit_data_message(
            {
                "type": "event",
                "event": event_type,
                "properties": _get_event_properties(event),
            },
            agent_by_message_id,
            usage_by_message_id,
            usage_state,
        ):
            yield item


class _TextStreamState:
    def __init__(self, message: Message) -> None:
        self.message = message
        self.index: Optional[int] = None
        self.last_text = ""
        self.completed = False


class _ToolStreamState:
    def __init__(self, message: Message, call_id: str) -> None:
        self.message = message
        self.call_id = call_id
        self.last_arguments: Optional[str] = None
        self.completed = False


def _normalize_event(event: Any) -> Optional[Dict[str, Any]]:
    # OpenCode events may be raw dicts, wrapped under "data", or SDK objects.
    if event is None:
        return None

    if isinstance(event, dict):
        return _unwrap_event_payload(event)

    # The OpenCode SDK models expose to_dict() that emits API field names.
    to_dict = getattr(event, "to_dict", None)
    normalized: Optional[Dict[str, Any]] = None
    if callable(to_dict):
        as_dict = to_dict()
        if isinstance(as_dict, dict):
            normalized = as_dict

    if normalized is None:
        data = getattr(event, "data", None)
        if isinstance(data, dict):
            normalized = data

    if normalized is None:
        model_dump = getattr(event, "model_dump", None)
        if callable(model_dump):
            as_dict = model_dump(by_alias=True)
            if isinstance(as_dict, dict):
                normalized = as_dict

    if normalized is None:
        as_dict = getattr(event, "dict", None)
        if callable(as_dict):
            maybe_dict = as_dict()
            if isinstance(maybe_dict, dict):
                normalized = maybe_dict
    if normalized is None:
        return None
    return _unwrap_event_payload(normalized)


def _unwrap_event_payload(event: Dict[str, Any]) -> Dict[str, Any]:
    # Global event streams wrap payloads under "payload".
    current = event
    while isinstance(current, dict) and "type" not in current:
        if "payload" in current and isinstance(current.get("payload"), dict):
            current = current["payload"]
            continue
        if "data" in current and isinstance(current.get("data"), dict):
            current = current["data"]
            continue
        break
    return current


def _get_event_properties(event: Dict[str, Any]) -> Dict[str, Any]:
    # OpenCode keeps message payload under "properties" for event updates.
    props = event.get("properties")
    return props if isinstance(props, dict) else {}


def _handle_part_event(
    part: Dict[str, Any],
    delta: Optional[str],
    text_states: Dict[str, _TextStreamState],
    reasoning_states: Dict[str, _TextStreamState],
    tool_states: Dict[str, _ToolStreamState],
    agent_by_message_id: Dict[str, str],
    usage_by_message_id: Dict[str, Dict[str, Any]],
    usage_state: Dict[str, Optional[Dict[str, Any]]],
) -> Iterator[Union[Message, Content]]:
    part_type = part.get("type")

    if part_type == "agent":
        message_id = part.get("messageID")
        agent_name = part.get("name")
        if message_id and agent_name:
            agent_by_message_id[message_id] = agent_name
            _update_active_agent_states(
                message_id,
                agent_name,
                text_states,
                reasoning_states,
                tool_states,
            )
        yield from _emit_data_message(
            part,
            agent_by_message_id,
            usage_by_message_id,
            usage_state,
        )
    elif part_type == "step-start":
        # Step markers are control signals, not user-visible content.
        pass
    elif part_type == "text":
        yield from _handle_text_part(
            part,
            delta,
            text_states,
            MessageType.MESSAGE,
            agent_by_message_id,
            usage_by_message_id,
            usage_state,
        )
    elif part_type == "reasoning":
        yield from _handle_text_part(
            part,
            delta,
            reasoning_states,
            MessageType.REASONING,
            agent_by_message_id,
            usage_by_message_id,
            usage_state,
        )
    elif part_type == "tool":
        yield from _handle_tool_part(
            part,
            tool_states,
            agent_by_message_id,
            usage_by_message_id,
            usage_state,
        )
    elif part_type == "file":
        yield from _handle_file_part(
            part,
            agent_by_message_id,
            usage_by_message_id,
            usage_state,
        )
    elif part_type == "step-finish":
        # Step finish carries token/cost accounting for this message.
        usage = _usage_from_step_finish(part)
        message_id = part.get("messageID")
        if usage and message_id:
            usage_by_message_id[message_id] = usage
            usage_state["last"] = usage
    else:
        yield from _emit_data_message(
            part,
            agent_by_message_id,
            usage_by_message_id,
            usage_state,
        )


def _handle_text_part(
    part: Dict[str, Any],
    delta: Optional[str],
    states: Dict[str, _TextStreamState],
    message_type: str,
    agent_by_message_id: Dict[str, str],
    usage_by_message_id: Dict[str, Dict[str, Any]],
    usage_state: Dict[str, Optional[Dict[str, Any]]],
) -> Iterator[Union[Message, Content]]:
    if part.get("ignored") is True:
        return

    part_id = part.get("id")
    message_id = part.get("messageID")
    if not part_id:
        return

    state = states.get(part_id)
    if state is None:
        message = _build_message_for_part(
            part,
            message_type,
            "assistant",
            agent_by_message_id,
            usage_by_message_id,
            usage_state,
        )
        yield message.in_progress()
        state = _TextStreamState(message)
        states[part_id] = state

    delta_text = _get_part_delta_text(part, delta, state.last_text)
    if delta_text:
        text_delta = TextContent(
            delta=True,
            index=state.index,
            text=delta_text,
        )
        text_delta = state.message.add_delta_content(text_delta)
        state.index = text_delta.index
        if text_delta.text:
            yield text_delta

    if "text" in part and isinstance(part.get("text"), str):
        state.last_text = part.get("text") or state.last_text

    if _part_is_completed(part) and not state.completed:
        if state.index is not None and state.message.content:
            completed_content = state.message.content[state.index]
            if getattr(completed_content, "text", None):
                yield completed_content.completed()

        _apply_usage_to_message(
            state.message,
            message_id,
            usage_by_message_id,
            usage_state,
        )
        yield state.message.completed()
        state.completed = True
        states.pop(part_id, None)


def _handle_tool_part(
    part: Dict[str, Any],
    tool_states: Dict[str, _ToolStreamState],
    agent_by_message_id: Dict[str, str],
    usage_by_message_id: Dict[str, Dict[str, Any]],
    usage_state: Dict[str, Optional[Dict[str, Any]]],
) -> Iterator[Union[Message, Content]]:
    call_id = part.get("callID")
    if not call_id:
        return

    raw_state = part.get("state")
    state: Dict[str, Any] = raw_state if isinstance(raw_state, dict) else {}
    status = state.get("status")
    message_id = part.get("messageID")
    agent_name = _resolve_agent_name(part, agent_by_message_id)
    tool_state = tool_states.get(call_id)
    if tool_state is None:
        message = _build_message_for_part(
            part,
            MessageType.PLUGIN_CALL,
            "assistant",
            agent_by_message_id,
            usage_by_message_id,
            usage_state,
        )
        yield message.in_progress()
        tool_state = _ToolStreamState(message, call_id)
        tool_states[call_id] = tool_state

    arguments = _tool_arguments_from_state(state)
    arguments_json = json.dumps(arguments, ensure_ascii=False)
    if arguments_json != tool_state.last_arguments:
        data_content = DataContent(
            index=0,
            data=FunctionCall(
                call_id=call_id,
                name=part.get("tool"),
                arguments=arguments_json,
            ).model_dump(),
            delta=False,
        )
        data_content.msg_id = tool_state.message.id
        yield data_content.in_progress()
        tool_state.last_arguments = arguments_json

    if status in ("completed", "error") and not tool_state.completed:
        final_data = DataContent(
            index=0,
            data=FunctionCall(
                call_id=call_id,
                name=part.get("tool"),
                arguments=arguments_json,
            ).model_dump(),
            delta=False,
        )
        final_data.msg_id = tool_state.message.id
        tool_state.message.content = [final_data]
        _apply_usage_to_message(
            tool_state.message,
            message_id,
            usage_by_message_id,
            usage_state,
        )
        yield final_data.completed()
        yield tool_state.message.completed()
        tool_state.completed = True
        tool_states.pop(call_id, None)

        output_payload = _tool_output_from_state(state)
        try:
            output_json = json.dumps(output_payload, ensure_ascii=False)
        except TypeError:
            output_json = str(output_payload)
        output_message = Message(
            type=MessageType.PLUGIN_CALL_OUTPUT,
            role="tool",
        )
        output_message.metadata = _build_metadata(part, agent_name)
        _apply_usage_to_message(
            output_message,
            message_id,
            usage_by_message_id,
            usage_state,
        )
        output_content = DataContent(
            index=0,
            data=FunctionCallOutput(
                call_id=call_id,
                name=part.get("tool"),
                output=output_json,
            ).model_dump(),
            delta=False,
        )
        output_content.msg_id = output_message.id
        output_message.content = [output_content]
        yield output_content.completed()
        yield output_message.completed()


def _handle_file_part(
    part: Dict[str, Any],
    agent_by_message_id: Dict[str, str],
    usage_by_message_id: Dict[str, Dict[str, Any]],
    usage_state: Dict[str, Optional[Dict[str, Any]]],
) -> Iterator[Union[Message, Content]]:
    message_id = part.get("messageID")
    agent_name = _resolve_agent_name(part, agent_by_message_id)
    message = Message(type=MessageType.MESSAGE, role="assistant")
    message.metadata = _build_metadata(part, agent_name)
    _apply_usage_to_message(
        message,
        message_id,
        usage_by_message_id,
        usage_state,
    )
    yield message.in_progress()

    file_content = FileContent(
        index=0,
        file_url=part.get("url"),
        filename=part.get("filename"),
    )
    file_content.msg_id = message.id
    message.content = [file_content]

    yield file_content.completed()
    yield message.completed()


def _emit_data_message(
    part: Dict[str, Any],
    agent_by_message_id: Dict[str, str],
    usage_by_message_id: Dict[str, Dict[str, Any]],
    usage_state: Dict[str, Optional[Dict[str, Any]]],
) -> Iterator[Union[Message, Content]]:
    message_id = part.get("messageID")
    agent_name = _resolve_agent_name(part, agent_by_message_id)
    message = Message(type=MessageType.MESSAGE, role="assistant")
    message.metadata = _build_metadata(part, agent_name)
    _apply_usage_to_message(
        message,
        message_id,
        usage_by_message_id,
        usage_state,
    )
    yield message.in_progress()

    data_content = DataContent(
        index=0,
        data={"opencode_part": part},
        delta=False,
    )
    data_content.msg_id = message.id
    message.content = [data_content]

    yield data_content.completed()
    yield message.completed()


def _build_message_for_part(
    part: Dict[str, Any],
    message_type: str,
    role: str,
    agent_by_message_id: Dict[str, str],
    usage_by_message_id: Dict[str, Dict[str, Any]],
    usage_state: Dict[str, Optional[Dict[str, Any]]],
) -> Message:
    message_id = part.get("messageID")
    agent_name = _resolve_agent_name(part, agent_by_message_id)
    message = Message(type=message_type, role=role)
    message.metadata = _build_metadata(part, agent_name)
    _apply_usage_to_message(
        message,
        message_id,
        usage_by_message_id,
        usage_state,
    )
    return message


def _resolve_agent_name(
    part: Dict[str, Any],
    agent_by_message_id: Dict[str, str],
) -> Optional[str]:
    message_id = part.get("messageID")
    if message_id and message_id in agent_by_message_id:
        return agent_by_message_id[message_id]
    if part.get("agent"):
        return part.get("agent")
    if part.get("type") == "agent":
        return part.get("name")
    return None


def _build_metadata(
    part: Dict[str, Any],
    agent_name: Optional[str],
) -> Dict[str, Any]:
    metadata: Dict[str, Any] = {
        "opencode": {
            "session_id": part.get("sessionID"),
            "message_id": part.get("messageID"),
            "part_id": part.get("id"),
            "part_type": part.get("type"),
        },
    }

    if agent_name:
        metadata["original_name"] = agent_name
        metadata["agent_name"] = agent_name

    if isinstance(part.get("metadata"), dict):
        metadata["opencode_part_metadata"] = part.get("metadata")

    return metadata


def _update_active_agent_states(
    message_id: str,
    agent_name: str,
    text_states: Dict[str, _TextStreamState],
    reasoning_states: Dict[str, _TextStreamState],
    tool_states: Dict[str, _ToolStreamState],
) -> None:
    for state in text_states.values():
        _apply_agent_name_to_message(state.message, message_id, agent_name)
    for state in reasoning_states.values():
        _apply_agent_name_to_message(state.message, message_id, agent_name)
    for state in tool_states.values():
        _apply_agent_name_to_message(state.message, message_id, agent_name)


def _apply_agent_name_to_message(
    message: Message,
    message_id: str,
    agent_name: str,
) -> None:
    metadata = message.metadata or {}
    opencode = metadata.get("opencode")
    if isinstance(opencode, dict) and opencode.get("message_id") == message_id:
        metadata["original_name"] = agent_name
        metadata["agent_name"] = agent_name
        message.metadata = metadata


def _apply_usage_to_message(
    message: Message,
    message_id: Optional[str],
    usage_by_message_id: Dict[str, Dict[str, Any]],
    usage_state: Dict[str, Optional[Dict[str, Any]]],
) -> None:
    # Usage can arrive before or after text parts;
    # prefer message_id, fallback last.
    if message.usage is not None:
        return

    usage = None
    if message_id:
        usage = usage_by_message_id.get(message_id)
    if usage is None:
        usage = usage_state.get("last")

    if usage:
        _update_obj_attrs(message, usage=usage)


def _get_part_delta_text(
    part: Dict[str, Any],
    delta: Optional[str],
    previous_text: str,
) -> str:
    # Prefer explicit delta; otherwise derive delta by prefix diff.
    if isinstance(delta, str) and delta:
        return delta

    text = part.get("text")
    if not isinstance(text, str) or not text:
        return ""

    if previous_text and text.startswith(previous_text):
        return text[len(previous_text) :]

    return text


def _part_is_completed(part: Dict[str, Any]) -> bool:
    # OpenCode marks part completion by setting time.end.
    raw_time = part.get("time")
    if not isinstance(raw_time, dict):
        return False
    return "end" in raw_time


def _tool_arguments_from_state(state: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(state, dict):
        return {}

    input_data = state.get("input")
    raw_data = state.get("raw")

    if isinstance(input_data, dict) and input_data:
        return input_data

    if raw_data:
        return {"raw": raw_data}

    return {}


def _tool_output_from_state(state: Dict[str, Any]) -> Dict[str, Any]:
    output = state.get("output") if isinstance(state, dict) else None
    error = state.get("error") if isinstance(state, dict) else None
    metadata = state.get("metadata") if isinstance(state, dict) else None
    attachments = state.get("attachments") if isinstance(state, dict) else None

    payload: Dict[str, Any] = {}
    if output is not None:
        payload["output"] = output
    if error is not None:
        payload["error"] = error
    if metadata is not None:
        payload["metadata"] = metadata
    if attachments is not None:
        payload["attachments"] = attachments
    return payload


def _usage_from_info(info: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    raw_tokens = info.get("tokens")
    tokens = raw_tokens if isinstance(raw_tokens, dict) else None
    cost = info.get("cost")
    return _usage_from_tokens(tokens, cost)


def _usage_from_step_finish(part: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    raw_tokens = part.get("tokens")
    tokens = raw_tokens if isinstance(raw_tokens, dict) else None
    cost = part.get("cost")
    return _usage_from_tokens(tokens, cost)


def _usage_from_tokens(
    tokens: Optional[Dict[str, Any]],
    cost: Optional[float],
) -> Optional[Dict[str, Any]]:
    if not tokens:
        return None

    raw_cache = tokens.get("cache")
    cache = raw_cache if isinstance(raw_cache, dict) else {}
    usage: Dict[str, Any] = {
        "input_tokens": tokens.get("input"),
        "output_tokens": tokens.get("output"),
        "reasoning_tokens": tokens.get("reasoning"),
        "cache_read_tokens": cache.get("read"),
        "cache_write_tokens": cache.get("write"),
    }

    if cost is not None:
        usage["cost"] = cost

    return usage


def _stringify_error(error: Any) -> str:
    if isinstance(error, dict):
        name = error.get("name") or "opencode_error"
        message = (
            error.get("message") or error.get("description") or str(error)
        )
        return f"{name}: {message}"
    return str(error)
