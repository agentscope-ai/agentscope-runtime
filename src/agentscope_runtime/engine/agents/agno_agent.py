# -*- coding: utf-8 -*-
# pylint:disable=too-many-nested-blocks, too-many-branches, too-many-statements
import json
from typing import Optional, Type

from agno.agent import Agent as AgAgent
from agno.models.base import Model
from agno.run.agent import (
    RunContentEvent,
    ToolCallStartedEvent,
    ToolCallCompletedEvent,
)
from agno.tools.function import Function

from .utils import build_agent
from ..agents import Agent
from ..schemas.context import Context
from ..schemas.agent_schemas import (
    Message,
    TextContent,
    DataContent,
    FunctionCall,
    FunctionCallOutput,
    MessageType,
    RunStatus,
)


class AgnoContextAdapter:
    def __init__(self, context: Context, attr: dict):
        self.context = context
        self.attr = attr

        # Adapted attribute
        self.toolkit = None
        self.model = None
        self.memory = None
        self.new_message = None

    async def initialize(self):
        self.model = await self.adapt_model()
        self.memory = await self.adapt_memory()
        self.new_message = await self.adapt_new_message()
        self.toolkit = await self.adapt_tools()

    async def adapt_memory(self):
        messages = []

        # Build context
        for msg in self.context.session.messages[:-1]:  # Exclude the last one
            messages.append(AgnoContextAdapter.converter(msg))

        return messages

    @staticmethod
    def converter(message: Message):
        # TODO: support more message type
        return dict(message)

    async def adapt_new_message(self):
        last_message = self.context.session.messages[-1]
        return AgnoContextAdapter.converter(last_message)

    async def adapt_model(self):
        return self.attr["model"]

    async def adapt_tools(self):
        toolkit = self.attr["agent_config"].get("tools", [])
        tools = self.attr["tools"]

        # in case, tools is None and tools == []
        if not tools:
            return toolkit

        if self.context.activate_tools:
            # Only add activated tool
            activated_tools = self.context.activate_tools
        else:
            from ...sandbox.tools.utils import setup_tools

            activated_tools = setup_tools(
                tools=self.attr["tools"],
                environment_manager=self.context.environment_manager,
                session_id=self.context.session.id,
                user_id=self.context.session.user_id,
                include_schemas=False,
            )

        for tool in activated_tools:
            func = Function(
                name=tool.name,
                description=tool.schema["function"]["description"],
                parameters=tool.schema["function"]["parameters"],
                entrypoint=tool.__call__,
            )
            toolkit.append(func)

        return toolkit


class AgnoAgent(Agent):
    def __init__(
        self,
        name: str,
        model: Model,
        tools=None,
        agent_config=None,
        agent_builder: Optional[Type[AgAgent]] = AgAgent,
    ):
        super().__init__(name=name, agent_config=agent_config)

        assert isinstance(
            model,
            Model,
        ), "model must be a subclass of Model in Agno"

        # Set default agent_builder
        if agent_builder is None:
            agent_builder = Agent

        assert issubclass(
            agent_builder,
            AgAgent,
        ), "agent_builder must be a subclass of Agent in Agno"

        # Replace name if not exists
        self.agent_config["name"] = self.agent_config.get("name") or name

        self._attr = {
            "model": model,
            "tools": tools,
            "agent_config": self.agent_config,
            "agent_builder": agent_builder,
        }
        self.tools = tools

    def copy(self) -> "AgnoAgent":
        return AgnoAgent(**self._attr)

    def build(self, as_context):
        params = {
            **self._attr["agent_config"],
            **{
                "model": as_context.model,
                "tools": as_context.toolkit,
            },  # Context will be added at `_agent.arun`
        }

        builder_cls = self._attr["agent_builder"]
        _agent = build_agent(builder_cls, params)

        return _agent

    async def run_async(
        self,
        context,
        **kwargs,
    ):
        ag_context = AgnoContextAdapter(context=context, attr=self._attr)
        await ag_context.initialize()

        # We should always build a new agent since the state is manage outside
        # the agent
        _agent = self.build(ag_context)

        text_message = Message(
            type=MessageType.MESSAGE,
            role="assistant",
            status=RunStatus.InProgress,
        )
        yield text_message

        text_delta_content = TextContent(delta=True)
        is_text_delta = False
        async for event in _agent.arun(
            ag_context.new_message,
            session_state=ag_context.memory,
            stream=True,
        ):
            if isinstance(event, RunContentEvent):
                is_text_delta = True
                text_delta_content.text = event.content
                text_delta_content = text_message.add_delta_content(
                    new_content=text_delta_content,
                )
                yield text_delta_content
            elif isinstance(event, ToolCallStartedEvent):
                json_str = json.dumps(event.tool.tool_args)
                data = DataContent(
                    data=FunctionCall(
                        call_id=event.tool.tool_call_id,
                        name=event.tool.tool_name,
                        arguments=json_str,
                    ).model_dump(),
                )
                message = Message(
                    type=MessageType.PLUGIN_CALL,
                    role="assistant",
                    status=RunStatus.Completed,
                    content=[data],
                )
                yield message
            elif isinstance(event, ToolCallCompletedEvent):
                data = DataContent(
                    data=FunctionCallOutput(
                        call_id=event.tool.tool_call_id,
                        output=str(event.tool.result),
                    ).model_dump(),
                )
                message = Message(
                    type=MessageType.PLUGIN_CALL_OUTPUT,
                    role="assistant",
                    status=RunStatus.Completed,
                    content=[data],
                )
                yield message

        if is_text_delta:
            yield text_message.content_completed(text_delta_content.index)
            yield text_message.completed()
