# -*- coding: utf-8 -*-
import asyncio
import json
from typing import (
    Any,
    Dict,
    List,
    Optional,
    Sequence,
    Type,
)

from pydantic import BaseModel, create_model

from crewai.tools import BaseTool
from agentscope_runtime.tools.base import Tool


def crewai_tool_adapter(
    tool: Tool,
    name: Optional[str] = None,
    description: Optional[str] = None,
) -> BaseTool:
    """Convert an agentscope_runtime Tool to a crewai-compatible BaseTool."""

    tool_name = name or tool.name
    tool_description = description or tool.description

    sanitized_fields = {}
    if tool.input_type:
        for field_name, field_info in tool.input_type.model_fields.items():
            if field_name == "ctx":
                continue

            sanitized_fields[field_name] = (field_info.annotation, field_info)

    base_name = tool.input_type.__name__ if tool.input_type else "Tool"
    model_name = f"{base_name}SanitizedInput"
    SanitizedInputModel = (
        create_model(model_name, **sanitized_fields)
        if sanitized_fields
        else None
    )

    class CrewAIAdapterTool(BaseTool):
        """A dynamically generated adapter class for a specific tool."""

        name: str = tool_name
        description: str = tool_description
        args_schema: Type[BaseModel] = SanitizedInputModel

        def _run(self, **kwargs: Any) -> str:
            """Synchronous execution wrapper called by crewai."""
            try:
                original_input = (
                    tool.input_type.model_validate(kwargs)
                    if tool.input_type
                    else kwargs
                )
                if asyncio.iscoroutinefunction(tool.arun):
                    try:
                        loop = asyncio.get_running_loop()
                        future = asyncio.run_coroutine_threadsafe(
                            tool.arun(original_input),
                            loop,
                        )
                        result = future.result()
                    except RuntimeError:
                        result = asyncio.run(tool.arun(original_input))
                else:
                    result = tool.run(original_input)
            except Exception as e:
                return f"Tool execution error: {str(e)}"

            if hasattr(result, "model_dump"):
                return json.dumps(
                    result.model_dump(),
                    ensure_ascii=False,
                    indent=2,
                )
            return str(result)

        async def _arun(self, **kwargs: Any) -> str:
            """Asynchronous execution wrapper for crewai's async workflows."""
            try:
                original_input = (
                    tool.input_type.model_validate(kwargs)
                    if tool.input_type
                    else kwargs
                )
                if asyncio.iscoroutinefunction(tool.arun):
                    result = await tool.arun(original_input)
                else:
                    loop = asyncio.get_running_loop()
                    result = await loop.run_in_executor(
                        None,
                        tool.run,
                        original_input,
                    )
            except Exception as e:
                return f"Tool execution error: {str(e)}"

            if hasattr(result, "model_dump"):
                return json.dumps(
                    result.model_dump(),
                    ensure_ascii=False,
                    indent=2,
                )
            return str(result)

    return CrewAIAdapterTool()


def crewai_toolkit_adapter(
    tools: Sequence[Tool],
    name_overrides: Optional[Dict[str, str]] = None,
    description_overrides: Optional[Dict[str, str]] = None,
) -> List[BaseTool]:
    """Create a list of crewai tools from multiple agentscope_runtime tools."""
    name_overrides = name_overrides or {}
    description_overrides = description_overrides or {}
    crewai_tools = []
    for tool in tools:
        name_override = name_overrides.get(tool.name)
        description_override = description_overrides.get(tool.name)
        adapted_tool = crewai_tool_adapter(
            tool,
            name=name_override,
            description=description_override,
        )
        crewai_tools.append(adapted_tool)
    return crewai_tools
