# -*- coding: utf-8 -*-
# pylint:disable=unused-argument

import uuid
from typing import Any

from mcp.server.fastmcp import Context


def get_mcp_dash_request_id(
    ctx: Context,
    **kwargs: Any,
) -> str:
    """
    Return the MCP dash request ID.
    Args:
        ctx: MCP CONTEXT
        **kwargs (Any): Additional keyword arguments.

    Returns:
        dash request ID.
    """
    dashscope_request_id = None
    if ctx and ctx.request_context:
        http_request = ctx.request_context.request
        if http_request:
            headers = dict(http_request.headers.items())
            if headers:
                dashscope_request_id = headers.get("dashscope_request_id")

    if dashscope_request_id and dashscope_request_id.strip():
        dashscope_request_id = dashscope_request_id.strip()
    else:
        dashscope_request_id = str(uuid.uuid4())
    return dashscope_request_id
