# -*- coding: utf-8 -*-
"""OpenCode adapter."""

from .message import message_to_opencode_parts
from .stream import adapt_opencode_message_stream

__all__ = [
    "adapt_opencode_message_stream",
    "message_to_opencode_parts",
]
