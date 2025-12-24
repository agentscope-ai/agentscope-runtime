# -*- coding: utf-8 -*-
import copy
import json
from typing import Any, Dict, List, Optional, Tuple

import tablestore
from langchain_core.embeddings import Embeddings
from tablestore import AsyncOTSClient as AsyncTablestoreClient
from tablestore.credentials import CredentialsProvider
from tablestore_for_agent_memory.base.base_knowledge_store import (
    Document as TablestoreDocument,
)
from tablestore_for_agent_memory.base.base_memory_store import (
    Message as TablestoreMessage,
)
from tablestore_for_agent_memory.base.base_memory_store import (
    Session as TablestoreSession,
)

from ...schemas.agent_schemas import ContentType, MessageType, Message
from ...schemas.session import Session


def create_tablestore_client(
    end_point: str,
    access_key_id: str,
    access_key_secret: str,
    instance_name: str,
    sts_token: Optional[str] = None,
    region: Optional[str] = None,
    credentials_provider: Optional[CredentialsProvider] = None,
    retry_policy: tablestore.RetryPolicy = tablestore.WriteRetryPolicy(),
    **kwargs: Any,
) -> AsyncTablestoreClient:
    return AsyncTablestoreClient(
        end_point=end_point,
        access_key_id=access_key_id,
        access_key_secret=access_key_secret,
        instance_name=instance_name,
        region=region,
        credentials_provider=credentials_provider,
        sts_token=None if sts_token == "" else sts_token,
        retry_policy=retry_policy,
        **kwargs,
    )


content_list_name = "content_list"


def exclude_None_fields_in_place(obj: Dict):
    """Remove fields with None values from dictionary in-place"""
    obj_copy = copy.deepcopy(obj)
    for key, value in obj_copy.items():
        if value is None:
            del obj[key]


def stringify_values(d: dict) -> dict:
    for k, v in d.items():
        if v is None:
            continue
        if isinstance(v, (dict, list)):
            d[k] = json.dumps(v, ensure_ascii=False)
        elif not isinstance(v, str):
            d[k] = str(v)
    return d


def _json_loads_if_str(v):
    if isinstance(v, str):
        try:
            return json.loads(v)
        except Exception:
            return v
    return v


def restore_json_strings(d: dict) -> dict:
    for k, v in d.items():
        d[k] = _json_loads_if_str(v)
    return d


def tablestore_log(msg: str):
    print(msg)


def convert_tablestore_session_to_session(
    tablestore_session: TablestoreSession,
    tablestore_messages: Optional[List[TablestoreMessage]] = None,
) -> Session:
    """Convert TablestoreSession to Session"""
    init_json = _generate_init_json_from_tablestore_session(
        tablestore_session,
        tablestore_messages,
    )
    return Session.model_validate(init_json)


# now, the func is not be used,
# because the interface of session history service don't need this func,
# just for future
def convert_session_to_tablestore_session(
    session: Session,
) -> Tuple[TablestoreSession, List[TablestoreMessage]]:
    """Convert Session to TablestoreSession and list of TablestoreMessage"""
    tablestore_session_metadata = session.model_dump(
        exclude={"id", "user_id", "messages"},
    )
    exclude_None_fields_in_place(tablestore_session_metadata)
    tablestore_session = TablestoreSession(
        user_id=session.user_id,
        session_id=session.id,
        metadata=tablestore_session_metadata,
    )
    tablestore_messages = [
        convert_message_to_tablestore_message(message, session)
        for message in session.messages
    ]

    return tablestore_session, tablestore_messages


def convert_tablestore_message_to_message(
    tablestore_message: TablestoreMessage,
) -> Message:
    """Convert TablestoreMessage to Message"""
    init_json = _generate_init_json_from_tablestore_message(tablestore_message)
    return Message.model_validate(init_json)


def convert_message_to_tablestore_message(
    message: Message,
    session: Session,
) -> TablestoreMessage:
    """Convert Message to TablestoreMessage"""
    content, content_list = _generate_tablestore_content_from_message(message)
    tablestore_message_metadata = message.model_dump(exclude={"content", "id"})
    tablestore_message_metadata = stringify_values(tablestore_message_metadata)
    tablestore_message_metadata[content_list_name] = json.dumps(
        content_list,
        ensure_ascii=False,
    )
    exclude_None_fields_in_place(tablestore_message_metadata)
    tablestore_message = TablestoreMessage(
        session_id=session.id,
        message_id=message.id,
        content=content,
        metadata=tablestore_message_metadata,
    )
    return tablestore_message


# This function is designed to
# facilitate batch embedding computation for better performance.
def convert_messages_to_tablestore_documents(
    messages: List[Message],
    user_id: str,
    session_id: str,
    embedding_model: Optional[Embeddings] = None,
) -> List[TablestoreDocument]:
    """Convert list of messages
    to TablestoreDocuments with optional batch embedding"""
    if not embedding_model:
        return [
            convert_message_to_tablestore_document(
                message,
                user_id,
                session_id,
            )
            for message in messages
        ]

    # Batch embed messages: extract content, filter non-empty,
    # compute embeddings, and align results with original messages
    contents = [
        _generate_tablestore_content_from_message(message)[0]
        for message in messages
    ]
    contents_not_none = [
        content for content in contents if content is not None
    ]

    embeddings_not_none = embedding_model.embed_documents(contents_not_none)
    embeddings = []
    index = 0
    for content in contents:
        if content is not None:
            embeddings.append(embeddings_not_none[index])
            index += 1
            continue
        embeddings.append(None)

    return [
        convert_message_to_tablestore_document(
            message,
            user_id,
            session_id,
            embedding,
        )
        for message, embedding in zip(messages, embeddings)
    ]


def convert_message_to_tablestore_document(
    message: Message,
    user_id: str,
    session_id: str,
    embedding: Optional[List[float]] = None,
) -> TablestoreDocument:
    """Convert Message to TablestoreDocument"""
    content, content_list = _generate_tablestore_content_from_message(message)
    tablestore_document_metadata = message.model_dump(
        exclude={"content", "id"},
    )
    tablestore_document_metadata.update(
        {
            "user_id": user_id,
            "session_id": session_id,
            content_list_name: json.dumps(content_list, ensure_ascii=False),
        },
    )
    exclude_None_fields_in_place(tablestore_document_metadata)
    tablestore_document = TablestoreDocument(
        document_id=message.id,
        text=content,
        embedding=embedding if embedding else None,
        metadata=tablestore_document_metadata,
    )
    return tablestore_document


def convert_tablestore_document_to_message(
    tablestore_document: TablestoreDocument,
) -> Message:
    """Convert TablestoreDocument to Message"""
    init_json = _generate_init_json_from_tablestore_document(
        tablestore_document,
    )
    return Message.model_validate(init_json)


def _generate_init_json_from_tablestore_session(
    tablestore_session: TablestoreSession,
    tablestore_messages: Optional[List[TablestoreMessage]] = None,
) -> Dict[str, Any]:
    """Generate initialization JSON from TablestoreSession"""
    init_json = {
        "id": tablestore_session.session_id,
        "user_id": tablestore_session.user_id,
        "messages": (
            [
                convert_tablestore_message_to_message(tablestore_message)
                for tablestore_message in tablestore_messages
            ]
            if tablestore_messages is not None
            else []
        ),
    }
    # for fit future, having more fields in Session
    init_json.update(tablestore_session.metadata)
    return init_json


def _generate_init_json_from_tablestore_message(
    tablestore_message: TablestoreMessage,
) -> Dict[str, Any]:
    """Generate initialization JSON from TablestoreMessage"""
    tablestore_message = copy.deepcopy(tablestore_message)
    tablestore_message.metadata = restore_json_strings(
        tablestore_message.metadata,
    )
    tablestore_message_content_list = tablestore_message.metadata.pop(
        content_list_name,
        None,
    )
    init_json = {
        "id": tablestore_message.message_id,
        "content": _generate_content_from_tablestore_content(
            text=tablestore_message.content,
            content_list=tablestore_message_content_list,
        ),
    }
    init_json.update(tablestore_message.metadata)
    return init_json


def _generate_init_json_from_tablestore_document(
    tablestore_document: TablestoreDocument,
) -> Dict[str, Any]:
    """Generate initialization JSON from TablestoreDocument"""
    tablestore_document = copy.deepcopy(tablestore_document)
    tablestore_document.metadata = restore_json_strings(
        tablestore_document.metadata,
    )
    tablestore_document_content_list = tablestore_document.metadata.pop(
        content_list_name,
        None,
    )
    init_json = {
        "id": tablestore_document.document_id,
        "content": _generate_content_from_tablestore_content(
            text=tablestore_document.text,
            content_list=tablestore_document_content_list,
        ),
    }
    init_json.update(tablestore_document.metadata)
    return init_json


def _generate_content_from_tablestore_content(
    text: str,
    content_list: List[Dict[str, Any]],
) -> Optional[List[Dict[str, Any]]]:
    """Generate final content from text and content list"""
    content_list = copy.deepcopy(content_list)

    if text is None:
        return content_list

    for content in content_list:
        if content["type"] == ContentType.TEXT:
            content["text"] = text
            break
    return content_list


def _generate_tablestore_content_from_message(
    message: Message,
) -> Tuple[Optional[str], Optional[List[Dict[str, Any]]]]:
    """Generate Tablestore content (text and content list) from Message"""
    if message.content is None:
        return None, None

    content_json_list = [content.model_dump() for content in message.content]
    content = None

    if message.type != MessageType.MESSAGE:
        return content, content_json_list

    for content_json in content_json_list:
        if content_json["type"] == ContentType.TEXT:
            content = content_json.pop("text")
            break

    return content, content_json_list


# This global variable will be cached to reduce computation time overhead
message_metadata_names: Optional[List[str]] = None


def get_message_metadata_names():
    """Get list of message metadata field names"""
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
