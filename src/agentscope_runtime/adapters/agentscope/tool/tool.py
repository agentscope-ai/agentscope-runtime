# -*- coding: utf-8 -*-
import logging
import functools

from agentscope.message import TextBlock
from agentscope.tool import ToolResponse


logger = logging.getLogger(__name__)


def tool_adapter(func=None, *, description=None):
    """
    Tool Adapter factory that allows custom description.

    Args:
        func: Tool function.
        description (str): Optional docstring/description for the wrapped
        function.
    """

    if func is None:
        return lambda real_func: tool_adapter(
            real_func,
            description=description,
        )

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        res = func(*args, **kwargs)
        if isinstance(res, ToolResponse):
            return res

        return ToolResponse(
            content=[
                TextBlock(text=str(res)),
            ],
        )

    if description is not None:
        wrapper.__doc__ = description

    return wrapper
