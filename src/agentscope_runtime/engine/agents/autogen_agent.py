# -*- coding: utf-8 -*-
from typing import Optional, Type

from autogen_core.models import ChatCompletionClient
from autogen_core.tools import FunctionTool
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.messages import (
    TextMessage,
    ToolCallExecutionEvent,
    ToolCallRequestEvent,
    ModelClientStreamingChunkEvent,
)

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


class AutogenContextAdapter:
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
            messages.append(AutogenContextAdapter.converter(msg))

        return messages

    @staticmethod
    def converter(message: Message):
        # TODO: support more message type
        return TextMessage.load(
            {
                "id": message.id,
                "source": message.role,
                "content": message.content[0].text if message.content else "",
            },
        )

    async def adapt_new_message(self):
        last_message = self.context.session.messages[-1]

        return AutogenContextAdapter.converter(last_message)

    async def adapt_model(self):
        return self.attr["model"]

    async def adapt_tools(self):
        toolkit = self.attr["agent_config"].get("toolkit", [])
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
            func = FunctionTool(
                func=tool.make_function(),
                description=tool.schema["function"]["description"],
                name=tool.name,
            )
            toolkit.append(func)

        return toolkit


class AutogenAgent(Agent):
    def __init__(
        self,
        name: str,
        model: ChatCompletionClient,
        tools=None,
        agent_config=None,
        agent_builder: Optional[Type[AssistantAgent]] = AssistantAgent,
    ):
        super().__init__(name=name, agent_config=agent_config)

        assert isinstance(
            model,
            ChatCompletionClient,
        ), "model must be a subclass of ChatCompletionClient in autogen"

        # Set default agent_builder
        if agent_builder is None:
            agent_builder = AssistantAgent

        assert issubclass(
            agent_builder,
            AssistantAgent,
        ), "agent_builder must be a subclass of AssistantAgent in autogen"

        # Replace name if not exists
        self.agent_config["name"] = self.agent_config.get("name") or name

        self._attr = {
            "model": model,
            "tools": tools,
            "agent_config": self.agent_config,
            "agent_builder": agent_builder,
        }
        self.tools = tools

    def copy(self) -> "AutogenAgent":
        return AutogenAgent(**self._attr)

    def build(self, as_context):
        params = {
            **self._attr["agent_config"],
            **{
                "model_client": as_context.model,
                "tools": as_context.toolkit,
            },  # Context will be added at `_agent.run_stream`
        }

        builder_cls = self._attr["agent_builder"]
        _agent = build_agent(builder_cls, params)

        return _agent

    async def run(self, context):
        ag_context = AutogenContextAdapter(context=context, attr=self._attr)
        await ag_context.initialize()

        # We should always build a new agent since the state is manage outside
        # the agent
        _agent = self.build(ag_context)

        resp = _agent.run_stream(
            task=ag_context.memory + [ag_context.new_message],
        )

        text_message = Message(
            type=MessageType.MESSAGE,
            role="assistant",
            status=RunStatus.InProgress,
        )
        yield text_message

        text_delta_content = TextContent(delta=True)
        is_text_delta = False
        stream_mode = False
        async for event in resp:
            if getattr(event, "source", "user") == "user":
                continue

            if isinstance(event, TextMessage):
                if stream_mode:
                    continue
                is_text_delta = True
                text_delta_content.text = event.content
                text_delta_content = text_message.add_delta_content(
                    new_content=text_delta_content,
                )
                yield text_delta_content
            elif isinstance(event, ModelClientStreamingChunkEvent):
                stream_mode = True
                is_text_delta = True
                text_delta_content.text = event.content
                text_delta_content = text_message.add_delta_content(
                    new_content=text_delta_content,
                )
                yield text_delta_content
            elif isinstance(event, ToolCallRequestEvent):
                data = DataContent(
                    data=FunctionCall(
                        call_id=event.id,
                        name=event.content[0].name,
                        arguments=event.content[0].arguments,
                    ).model_dump(),
                )
                message = Message(
                    type=MessageType.PLUGIN_CALL,
                    role="assistant",
                    status=RunStatus.Completed,
                    content=[data],
                )
                yield message
            elif isinstance(event, ToolCallExecutionEvent):
                data = DataContent(
                    data=FunctionCallOutput(
                        call_id=event.id,
                        output=event.content[0].content,
                    ).model_dump(),
                )
                message = Message(
                    type=MessageType.PLUGIN_CALL_OUTPUT,
                    role="assistant",
                    status=RunStatus.Completed,
                    content=[data],
                )
                yield message

                # Add to message
                is_text_delta = True
                text_delta_content.text = event.content[0].content
                text_delta_content = text_message.add_delta_content(
                    new_content=text_delta_content,
                )
                yield text_delta_content

        if is_text_delta:
            yield text_message.content_completed(text_delta_content.index)
            yield text_message.completed()

    async def run_async(
        self,
        context,
        **kwargs,
    ):
        async for event in self.run(context):
            yield event
