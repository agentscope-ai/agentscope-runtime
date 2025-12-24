# -*- coding: utf-8 -*-
import concurrent.futures
import json
from typing import (
    Any,
    Dict,
    Optional,
    Sequence,
)

from agentscope.tool import Toolkit, ToolResponse
from agentscope.tool._types import RegisteredToolFunction

from agentscope_runtime.tools.base import Tool


def agentscope_tool_adapter(
    tool: Tool,
    name: Optional[str] = None,
    description: Optional[str] = None,
) -> RegisteredToolFunction:
    """Convert an agentscope_runtime tool to an AgentScope tool.

    This function wraps agentscope_runtime tools to make them compatible
    with AgentScope's toolkit system.

    Args:
        tool (Tool): The agentscope_runtime tool to wrap
        name (str, optional): Override the tool name. Defaults to
            tool.name
        description (str, optional): Override the tool description.
            Defaults to tool.description

    Returns:
        RegisteredToolFunction: The AgentScope tool function

    Examples:
        Basic usage with a search tool:

        .. code-block:: python

            from agentscope_runtime.searches.modelstudio_search
            import ModelstudioSearch
            from agentscope_runtime.adapters.agentscope.tool import
            agentscope_tool_adapter
            from agentscope.tool import Toolkit

            # Create the search tool
            search_tool = ModelstudioSearch()

            # Convert to AgentScope tool
            search_tool = agentscope_tool_adapter(search_tool)

            # Add to toolkit
            toolkit = Toolkit()
            toolkit.tools[search_tool.name] = search_tool
    """

    def func_wrapper(**kwargs: Any) -> ToolResponse:
        """Wrapper function that adapts tool execution to AgentScope
        format."""
        import asyncio

        # Validate input with tool's input type
        if tool.input_type:
            try:
                validated_input = tool.input_type.model_validate(kwargs)
            except Exception as e:
                return ToolResponse(
                    content=[
                        {
                            "type": "text",
                            "text": f"Input validation error: {str(e)}",
                        },
                    ],
                    metadata={"error": True},
                )
        else:
            validated_input = kwargs

        # Execute the tool
        try:
            if asyncio.iscoroutinefunction(tool.arun):
                # Check if we're already in an event loop
                try:

                    def run_async() -> Any:
                        return asyncio.run(tool.arun(validated_input))

                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(run_async)
                        result = future.result()
                except RuntimeError:
                    # No event loop running, safe to use asyncio.run
                    result = asyncio.run(tool.arun(validated_input))
            else:
                # Run sync tool
                result = tool.run(validated_input)
        except Exception as e:
            return ToolResponse(
                content=[
                    {
                        "type": "text",
                        "text": f"Tool execution error: {str(e)}",
                    },
                ],
                metadata={"error": True},
            )

        # Convert result to ToolResponse format
        try:
            if hasattr(result, "model_dump"):
                # Pydantic model result
                result_dict = result.model_dump()
                content_text = json.dumps(
                    result_dict,
                    ensure_ascii=False,
                    indent=2,
                )
            else:
                # Other result types
                content_text = str(result)
                result_dict = result

            return ToolResponse(
                content=[
                    {
                        "type": "text",
                        "text": content_text,
                    },
                ],
                metadata={"tool_result": result_dict},
            )
        except Exception as e:
            return ToolResponse(
                content=[
                    {
                        "type": "text",
                        "text": f"Result formatting error: {str(e)}",
                    },
                ],
                metadata={"error": True},
            )

    # Use provided name/description or fall back to tool defaults
    tool_name = name or tool.name
    tool_description = description or tool.description

    # Get the tool's function schema and convert to AgentScope format
    function_schema = tool.function_schema.model_dump()

    # Convert from OpenAI function calling format to AgentScope format
    agentscope_schema = {
        "type": "function",
        "function": {
            "name": tool_name,
            "description": tool_description,
            "parameters": function_schema.get("parameters", {}),
        },
    }

    return RegisteredToolFunction(
        name=tool_name,
        source="function",
        mcp_name=None,
        original_func=func_wrapper,
        json_schema=agentscope_schema,
        group="basic",
    )


def agentscope_toolkit_adapter(
    tools: Sequence[Tool],
    name_overrides: Optional[Dict[str, str]] = None,
    description_overrides: Optional[Dict[str, str]] = None,
) -> Toolkit:
    """Create an AgentScope toolkit from multiple agentscope_runtime tools.

    This is a convenience function that creates a toolkit with multiple
    tools converted to AgentScope tools.

    Args:
        tools: Sequence of agentscope_runtime tools to convert
        name_overrides: Optional dict mapping tool names to override names
        description_overrides: Optional dict mapping tool names to
            override descriptions

    Returns:
        Toolkit: AgentScope toolkit with all tools as tools

    Examples:
        Create toolkit from multiple tools:

        .. code-block:: python

            from agentscope_runtime.searches.modelstudio_search
            import ModelstudioSearch
            from agentscope_runtime.RAGs.modelstudio_rag import
            ModelstudioRag
            from agentscope_runtime.adapters.agentscope.tool import
            agentscope_tool_adapter
            from agentscope.tool import Toolkit

            # Create the search tool
            search_tool = ModelstudioSearch()
            rag_tool = ModelstudioRag()

            # Create toolkit
            toolkit = agentscope_toolkit_adapter([search_tool,
            rag_tool])

            # Use in agents...
    """
    name_overrides = name_overrides or {}
    description_overrides = description_overrides or {}

    toolkit = Toolkit()

    for tool in tools:
        name_override = name_overrides.get(tool.name)
        description_override = description_overrides.get(tool.name)

        adapted_tool = agentscope_tool_adapter(
            tool,
            name=name_override,
            description=description_override,
        )

        toolkit.tools[tool.name] = adapted_tool

    return toolkit
