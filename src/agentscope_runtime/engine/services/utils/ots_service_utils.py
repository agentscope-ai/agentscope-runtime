import copy
import json
from typing import List, Dict, Any, Optional, Tuple
from tablestore_for_agent_memory.base.base_knowledge_store import (
    Document as OTSDocument,
)

from tablestore_for_agent_memory.base.base_memory_store import (
    Session as OTSSession,
    Message as OTSMessage,
)
from ..session_history_service import Session, Message
from ...schemas.agent_schemas import ContentType, MessageType

from langchain_core.embeddings import Embeddings


content_list_name = "content_list"


def exclude_None_fields_in_place(obj: Dict):
    obj_copy = copy.deepcopy(obj)
    for key, value in obj_copy.items():
        if value is None:
            del obj[key]


def convert_ots_session_to_session(
    ots_session: OTSSession, ots_messages: Optional[List[OTSMessage]] = None
) -> Session:
    init_json = _generate_init_json_from_ots_session(ots_session, ots_messages)
    return Session.model_validate(init_json)


# now, the func is not be used, because the interface of session history service don't need this func, just for future
def convert_session_to_ots_session(
    session: Session,
) -> Tuple[OTSSession, List[OTSMessage]]:
    ots_session = OTSSession(
        user_id=session.user_id,
        session_id=session.id,
        metadata=session.model_dump(exclude={"id", "user_id", "messages"}),
    )
    ots_messages = [
        convert_message_to_ots_message(message, session) for message in session.messages
    ]

    return ots_session, ots_messages


def convert_ots_message_to_message(ots_message: OTSMessage) -> Message:
    init_json = _generate_init_json_from_ots_message(ots_message)
    return Message.model_validate(init_json)


def convert_message_to_ots_message(message: Message, session: Session) -> OTSMessage:
    content, content_list = _generate_ots_content_from_message(message)
    ots_message_metadata = message.model_dump(exclude={"content", "id"})
    ots_message_metadata[content_list_name] = json.dumps(
        content_list, ensure_ascii=False
    )
    exclude_None_fields_in_place(ots_message_metadata)
    ots_message = OTSMessage(
        session_id=session.id,
        message_id=message.id,
        content=content,
        metadata=ots_message_metadata,
    )
    return ots_message


def convert_message_to_ots_document(
    message: Message,
    user_id: str,
    session_id: str,
    embedding_model: Optional[Embeddings] = None,
) -> OTSDocument:
    content, content_list = _generate_ots_content_from_message(message)
    ots_document_metadata = message.model_dump(exclude={"content", "id"})
    ots_document_metadata.update(
        {
            "user_id": user_id,
            "session_id": session_id,
            content_list_name: json.dumps(content_list, ensure_ascii=False),
        }
    )
    exclude_None_fields_in_place(ots_document_metadata)
    ots_document = OTSDocument(
        document_id=message.id,
        text=content,
        embedding=embedding_model.embed_query(content)
        if embedding_model and content
        else None,
        metadata=ots_document_metadata,
    )
    return ots_document


def convert_ots_document_to_message(ots_document: OTSDocument) -> Message:
    init_json = _generate_init_json_from_ots_document(ots_document)
    return Message.model_validate(init_json)


def _generate_init_json_from_ots_session(
    ots_session: OTSSession, ots_messages: Optional[List[OTSMessage]] = None
) -> Dict[str, Any]:
    init_json = {
        "id": ots_session.session_id,
        "user_id": ots_session.user_id,
        "messages": [
            convert_ots_message_to_message(ots_message) for ots_message in ots_messages
        ]
        if ots_messages is not None
        else [],
    }
    # for fit future, having more fields in Session
    init_json.update(ots_session.metadata)
    return init_json


def _generate_init_json_from_ots_message(ots_message: OTSMessage) -> Dict[str, Any]:
    ots_message_content_list = ots_message.metadata.pop(content_list_name, None)
    init_json = {
        "id": ots_message.message_id,
        "content": _generate_content_from_ots_content(
            text=ots_message.content,
            content_list=json.loads(ots_message_content_list)
            if ots_message_content_list
            else None,
        ),
    }
    init_json.update(ots_message.metadata)
    return init_json


def _generate_init_json_from_ots_document(ots_document: OTSDocument) -> Dict[str, Any]:
    ots_document_content_list = ots_document.metadata.pop(content_list_name, None)
    init_json = {
        "id": ots_document.document_id,
        "content": _generate_content_from_ots_content(
            text=ots_document.text,
            content_list=json.loads(ots_document_content_list)
            if ots_document_content_list
            else None,
        ),
    }
    init_json.update(ots_document.metadata)
    return init_json


def _generate_content_from_ots_content(
    text: str, content_list: List[Dict[str, Any]]
) -> Optional[List[Dict[str, Any]]]:
    if content_list is None:
        return None

    content_list_copy = copy.deepcopy(content_list)
    if text is not None:
        for content in content_list_copy:
            if content["type"] == ContentType.TEXT:
                content["text"] = text
                break
    return content_list_copy


def _generate_ots_content_from_message(
    message: Message,
) -> Tuple[Optional[str], Optional[List[Dict[str, Any]]]]:
    if message.content is None:
        return None, None

    content_json_list = [content.model_dump() for content in message.content]

    content = None
    if message.type == MessageType.MESSAGE:
        for content_json in content_json_list:
            if content_json["type"] == ContentType.TEXT:
                content = content_json.pop("text")
                break

    return content, content_json_list


# This global variable will be cached to reduce computation time overhead
message_metadata_names: Optional[List[str]] = None


def get_message_metadata_names():
    global message_metadata_names

    if message_metadata_names is not None:
        return message_metadata_names

    message_metadata_names = list(Message.model_fields.keys())

    message_metadata_exclude_names = ("id", "content")
    message_metadata_extra_names = (
        "document_id",
        "text",
        "user_id",
        "session_id",
        content_list_name,
    )

    for exclude_name in message_metadata_exclude_names:
        message_metadata_names.remove(exclude_name)
    for extra_name in message_metadata_extra_names:
        message_metadata_names.append(extra_name)

    return message_metadata_names
