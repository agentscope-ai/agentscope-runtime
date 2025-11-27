# -*- coding: utf-8 -*-
# pylint: disable=unused-argument, redefined-outer-name

import json
from typing import (
    Any,
    Dict,
    List,
    Optional,
    Sequence,
)

try:
    from autogen_core import CancellationToken
    from autogen_core.tools import BaseTool
except ImportError as e:
    # Create mock classes when autogen is not available
    raise ImportError(
        "Please install autogen-core to use this feature: "
        "pip install autogen-core",
    ) from e

from pydantic import BaseModel

from agentscope_runtime.tools.base import Tool


class AutogenToolAdapter(BaseTool[BaseModel, Any]):
    """Adapter class that wraps agentscope_runtime tools to make them
    compatible with AutoGen.

    This adapter allows any tool that inherits from
    agentscope_runtime.tools.base.Tool to be used as a tool in
    AutoGen agents

    Args:
        tool (Tool): The agentscope_runtime tool to wrap
        name (str, optional): Override the tool name. Defaults to
            tool.name
        description (str, optional): Override the tool description.
            Defaults to tool.description

    Examples:
        Basic usage with a search tool:

        .. code-block:: python

            from agentscope_runtime.tools.searches.modelstudio_search
            import ModelstudioSearch
            from agentscope_runtime.adapters.autogen.tool import
            AutogenToolAdapter
            from autogen_ext.models.openai import OpenAIChatCompletionClient
            from autogen_agentchat.agents import AssistantAgent
            from autogen_agentchat.messages import TextMessage
            from autogen_core import CancellationToken

            async def main():
                # Create the search tool
                search_tool = ModelstudioSearch()

                # Create the autogen tool adapter
                search_tool = AutogenToolAdapter(search_tool)

                # Create an agents with the search tool
                model = OpenAIChatCompletionClient(model="gpt-4")
                agents = AssistantAgent(
                    "assistant",
                    tools=[search_tool],
                    model_client=model,
                )

                # Use the agents
                response = await agents.on_messages(
                    [TextMessage(content="What's the weather in Beijing?",
                    source="user")],
                    CancellationToken(),
                )
                print(response.chat_message)

            asyncio.run(main())
    """

    def __init__(
        self,
        tool: Tool,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> None:
        """Initialize the tool tool adapter.

        Args:
            tool: The agentscope_runtime tool to wrap
            name: Optional override for the tool name
            description: Optional override for the tool description
        """

        self._tool = tool

        # Use provided name/description or fall back to tool defaults
        tool_name = name or tool.name
        tool_description = description or tool.description

        # Create input model from tool's input type
        arg_type = tool.input_type
        return_type = tool.return_type

        super().__init__(arg_type, return_type, tool_name, tool_description)

    async def run(
        self,
        args: BaseModel,
        cancellation_token: CancellationToken,
    ) -> Any:
        """Run the tool with the provided arguments.

        Args:
            args: The arguments to pass to the tool
            cancellation_token: Token to signal cancellation

        Returns:
            The result of the tool execution

        Raises:
            Exception: If the operation is cancelled or the tool
            execution fails
        """

        # Run the tool
        try:
            result = await self._tool.arun(args)
            # make sure return as string
            return json.dumps(result.model_dump(), ensure_ascii=False)
        except Exception as e:
            # Re-raise with more context
            raise RuntimeError(
                f"Tool {self._tool.name} failed: {str(e)}",
            ) from e


def create_autogen_tools(
    tools: Sequence[Tool],
    name_overrides: Optional[Dict[str, str]] = None,
    description_overrides: Optional[Dict[str, str]] = None,
) -> List[AutogenToolAdapter]:
    """Create a list of tool adapters for use with AutoGen agents.

    This is a convenience function that creates adapters for multiple
    tools at once, similar to how tool.py provides
    LanggraphNode.

    Args:
        tools: Sequence of agentscope_runtime tools to wrap
        name_overrides: Optional dict mapping tool names to override names
        description_overrides: Optional dict mapping tool names to
                override descriptions


    Returns:
        List of Tool instances ready to use with AutoGen agents

    Examples:
        Create tools from multiple tools:

        .. code-block:: python

            from agentscope_runtime.searches.modelstudio_search
            import ModelstudioSearch
            from agentscope_runtime.RAGs.modelstudio_rag import
            ModelstudioRag
            from agentscope_runtime.adapters.autogen.tool import
            AutogenToolAdapter
            from autogen_ext.models.openai import OpenAIChatCompletionClient
            from autogen_agentchat.agents import AssistantAgent

            async def main():
                # Create tools
                search_tool = ModelstudioSearch()
                rag_tool = ModelstudioRag()

                # Create autogen tools
                tools = create_autogen_tools([search_tool,
                    rag_tool])

                # Create agents with all tools
                model = OpenAIChatCompletionClient(model="gpt-4")
                agents = AssistantAgent(
                    "assistant",
                    tools=tools,
                    model_client=model,
                )

                # Use the agents...

            asyncio.run(main())
    """
    name_overrides = name_overrides or {}
    description_overrides = description_overrides or {}

    output_tools = []
    for tool in tools:
        name_override = name_overrides.get(tool.name)
        description_override = description_overrides.get(tool.name)

        adapted_tool = AutogenToolAdapter(
            tool,
            name=name_override,
            description=description_override,
        )
        output_tools.append(adapted_tool)

    return output_tools
