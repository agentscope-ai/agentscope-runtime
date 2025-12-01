# -*- coding: utf-8 -*-
"""LangGraph adapter for AgentScope runtime."""

from .message import langgraph_msg_to_message, message_to_langgraph_msg

__all__ = [
    "langgraph_msg_to_message",
    "message_to_langgraph_msg",
]
