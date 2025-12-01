# -*- coding: utf-8 -*-
# pylint: disable=protected-access
"""Sandbox Tool Adapter for LangGraph tools."""
import logging
import functools

from typing import Any, Dict, Union
from mcp.types import CallToolResult
from langchain_core.tools import BaseTool

logger = logging.getLogger(__name__)


def langgraph_tool_adapter(func):
    """
    LangGraph Tool Adapter.

    Wraps a LangGraph tool function so that its output is always converted
    into a format compatible with the runtime.

    This adapter preserves the original function signature and docstring
    so that JSON schemas can be correctly generated.

    Args:
        func: Original LangGraph tool function.

    Returns:
        A callable that produces standardized output.
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            res = func(*args, **kwargs)

            # If it's already in the expected format, return as is
            if isinstance(res, (str, dict, list)) or res is None:
                return res

            # If it's a BaseTool instance, call it properly
            if isinstance(res, BaseTool):
                # Handle tool calling with appropriate arguments
                if args and kwargs:
                    return res.invoke({"args": args, "kwargs": kwargs})
                elif args:
                    return res.invoke(args[0] if len(args) == 1 else args)
                elif kwargs:
                    return res.invoke(kwargs)
                else:
                    return res.invoke({})

            # For other types, convert to string representation
            return str(res)

        except Exception as e:
            logger.warning(
                (
                    f"Failed to execute LangGraph tool. "
                    f"Function: {func.__name__}, "
                    f"Args: {args}, "
                    f"Kwargs: {kwargs}, "
                    f"Error: {e}"
                ),
                exc_info=True,
            )
            # Return error as string
            return f"Tool execution failed: {str(e)}"

    return wrapper


def convert_tool_result_to_langgraph_format(
    result: Union[CallToolResult, Dict[str, Any], str],
) -> Dict[str, Any]:
    """
    Convert tool result to a format compatible with LangGraph.

    Args:
        result: Tool result in various formats.

    Returns:
        Dict representation compatible with LangGraph.
    """
    if isinstance(result, CallToolResult):
        try:
            # Try to parse content as JSON if it's a string
            if isinstance(result.content, str):
                import json

                try:
                    return json.loads(result.content)
                except json.JSONDecodeError:
                    return {"content": result.content}
            elif isinstance(result.content, list):
                # Handle list of content items
                content_list = []
                for item in result.content:
                    if hasattr(item, "text"):
                        content_list.append(item.text)
                    elif hasattr(item, "data"):
                        content_list.append(str(item.data))
                    else:
                        content_list.append(str(item))
                return {"content": "\n".join(content_list)}
            else:
                return {"content": str(result.content)}
        except Exception as e:
            logger.warning(f"Failed to convert CallToolResult: {e}")
            return {"content": str(result)}

    elif isinstance(result, dict):
        return result

    elif isinstance(result, str):
        # Try to parse as JSON, fallback to plain text
        try:
            import json

            return json.loads(result)
        except (json.JSONDecodeError, ValueError):
            return {"content": result}

    else:
        return {"content": str(result)}
