# -*- coding: utf-8 -*-
import json
import mimetypes
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urlparse

from ...engine.schemas.agent_schemas import (
    Message,
    ContentType,
)


def message_to_opencode_parts(
    messages: Union[Message, List[Message], List[Dict[str, Any]]],
) -> List[Dict[str, Any]]:
    """
    Convert runtime Message to OpenCode prompt parts.
    """
    prompt_message = _select_prompt_message(messages)
    if prompt_message is None:
        return []

    return _content_to_parts(prompt_message)


def _select_prompt_message(
    messages: Union[Message, List[Message], List[Dict[str, Any]]],
) -> Optional[Message]:
    if isinstance(messages, Message):
        return messages

    if not isinstance(messages, list) or not messages:
        return None

    converted: List[Message] = []
    for msg in messages:
        if isinstance(msg, Message):
            converted.append(msg)
        elif isinstance(msg, dict):
            try:
                converted.append(Message(**msg))
            except Exception:
                continue

    if not converted:
        return None

    for msg in reversed(converted):
        if msg.role == "user":
            return msg

    return converted[-1]


def _content_to_parts(message: Message) -> List[Dict[str, Any]]:
    parts: List[Dict[str, Any]] = []

    if not message.content:
        return parts

    handlers = {
        ContentType.TEXT: _handle_text_content,
        ContentType.IMAGE: _handle_image_content,
        ContentType.AUDIO: _handle_audio_content,
        ContentType.FILE: _handle_file_content,
        ContentType.DATA: _handle_data_content,
        ContentType.REFUSAL: _handle_refusal_content,
    }

    for content in message.content:
        content_type = _get_content_value(content, "type")
        handler = handlers.get(content_type, _handle_unknown_content)
        handler(parts, content)

    return parts


def _get_content_value(content: Any, key: str) -> Any:
    if isinstance(content, dict):
        return content.get(key)
    return getattr(content, key, None)


def _handle_text_content(parts: List[Dict[str, Any]], content: Any) -> None:
    text = _get_content_value(content, "text")
    if isinstance(text, str) and text:
        parts.append({"type": "text", "text": text})


def _handle_image_content(parts: List[Dict[str, Any]], content: Any) -> None:
    url = _get_content_value(content, "image_url")
    if url:
        parts.append(_file_part_from_url(url, None))


def _handle_audio_content(parts: List[Dict[str, Any]], content: Any) -> None:
    url = _get_content_value(content, "data")
    if url:
        parts.append(_file_part_from_url(url, None))


def _handle_file_content(parts: List[Dict[str, Any]], content: Any) -> None:
    file_url = _get_content_value(content, "file_url")
    url = file_url or _get_content_value(content, "file_data")
    filename = _get_content_value(content, "filename")
    if url:
        parts.append(_file_part_from_url(url, filename))


def _handle_data_content(parts: List[Dict[str, Any]], content: Any) -> None:
    payload = _get_content_value(content, "data")
    _append_json_text_part(parts, payload)


def _handle_refusal_content(parts: List[Dict[str, Any]], content: Any) -> None:
    payload = _get_content_value(content, "refusal")
    _append_json_text_part(parts, payload)


def _handle_unknown_content(parts: List[Dict[str, Any]], content: Any) -> None:
    raw_text = _get_content_value(content, "text")
    if raw_text:
        parts.append({"type": "text", "text": str(raw_text)})


def _append_json_text_part(
    parts: List[Dict[str, Any]],
    payload: Any,
) -> None:
    try:
        text = json.dumps(payload, ensure_ascii=False)
    except TypeError:
        text = str(payload)
    if text:
        parts.append({"type": "text", "text": text})


def _file_part_from_url(url: str, filename: Optional[str]) -> Dict[str, Any]:
    guessed_mime, _ = mimetypes.guess_type(url)
    mime = guessed_mime or "application/octet-stream"

    if not filename:
        parsed = urlparse(url)
        if parsed.path:
            filename = parsed.path.split("/")[-1] or None

    payload: Dict[str, Any] = {
        "type": "file",
        "url": url,
        "mime": mime,
    }
    if filename:
        payload["filename"] = filename
    return payload
