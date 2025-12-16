# -*- coding: utf-8 -*-
from typing import List, Union, Dict, Any

from pydantic import BaseModel

from .agent_schemas import Message


class Session(BaseModel):
    """Represents a single conversation session.

    A session contains the history of a conversation, including all
    messages, and is uniquely identified by its ID.

    Attributes:
        id: The unique identifier for the session.
        user_id: The identifier of the user who owns the session.
        messages: A list of messages formatted for Agent response

    """

    id: str
    user_id: str
    messages: List[Union[Message, Dict[str, Any]]] = []
