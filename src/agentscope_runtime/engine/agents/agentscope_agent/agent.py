# -*- coding: utf-8 -*-
# pylint:disable=too-many-nested-blocks, too-many-branches, too-many-statements
# pylint:disable=line-too-long, protected-access

import json
import threading
import uuid
from functools import partial
from typing import Optional, Type

from agentscope import setup_logger
from agentscope.agent import ReActAgent
from agentscope.formatter import (
    FormatterBase,
    DashScopeChatFormatter,
    OpenAIChatFormatter,
    AnthropicChatFormatter,
    OllamaChatFormatter,
    GeminiChatFormatter,
)
from agentscope.memory import InMemoryMemory
from agentscope.message import Msg, ToolUseBlock, ToolResultBlock
from agentscope.model import (
    ChatModelBase,
    DashScopeChatModel,
    OpenAIChatModel,
    AnthropicChatModel,
    OllamaChatModel,
    GeminiChatModel,
)
from agentscope.tool import (
    Toolkit,
    ToolResponse,
)
from agentscope.tool._toolkit import RegisteredToolFunction

from .hooks import (
    pre_speak_msg_buffer_hook,
    get_msg_instances,
    clear_msg_instances,
    run_async_in_thread,
)
from ...agents import Agent
from ...schemas.agent_schemas import (
    Message,
    TextContent,
    DataContent,
    FunctionCall,
    FunctionCallOutput,
    MessageType,
)
from ...schemas.context import Context

# Disable logging from agentscope
setup_logger(level="CRITICAL")


class AgentScopeContextAdapter:
    def __init__(self, context: Context, attr: dict):
        self.context = context
        self.attr = attr

        # Adapted attribute
        self.toolkit = None
        self.model = None
        self.memory = None
        self.new_message = None

    async def initialize(self):
        self.model, self.formatter = await self.adapt_model()
        self.memory = await self.adapt_memory()
        self.new_message = await self.adapt_new_message()
        self.toolkit = await self.adapt_tools()

    async def adapt_memory(self):
        memory = self.attr["agent_config"].get("memory", InMemoryMemory())
        messages = []

        # Build context
        for msg in self.context.session.messages[:-1]:  # Exclude the last one
            messages.append(AgentScopeContextAdapter.converter(msg))

        memory.load_state_dict({"content": messages})

        return memory

    @staticmethod
    def converter(message: Message):
        # TODO: support more message type
        if message.role not in ["user", "system", "assistant"]:
            role_label = "user"
        else:
            role_label = message.role
        result = {
            "name": message.role,
            "role": role_label,
        }
        if message.type == MessageType.PLUGIN_CALL:
            result["content"] = [
                ToolUseBlock(
                    type="tool_use",
                    id=message.content[0].data["call_id"],
                    name=message.role,
                    input=json.loads(message.content[0].data["arguments"]),
                ),
            ]
        elif message.type == MessageType.PLUGIN_CALL_OUTPUT:
            result["content"] = [
                ToolResultBlock(
                    type="tool_result",
                    id=message.content[0].data["call_id"],
                    name=message.role,
                    output=message.content[0].data["output"],
                ),
            ]
        else:
            result["content"] = (
                message.content[0].text if message.content else ""
            )
        return result

    async def adapt_new_message(self):
        last_message = self.context.session.messages[-1]
        return Msg(**AgentScopeContextAdapter.converter(last_message))

    async def adapt_model(self):
        model = self.attr["model"]
        formatter = self.attr["agent_config"].get("formatter")
        if formatter and isinstance(formatter, FormatterBase):
            return model, formatter

        if isinstance(model, OpenAIChatModel):
            formatter = OpenAIChatFormatter()
        elif isinstance(model, DashScopeChatModel):
            formatter = DashScopeChatFormatter()
        elif isinstance(model, AnthropicChatModel):
            formatter = AnthropicChatFormatter()
        elif isinstance(model, OllamaChatModel):
            formatter = OllamaChatFormatter()
        elif isinstance(model, GeminiChatModel):
            formatter = GeminiChatFormatter()

        return model, formatter

    async def adapt_tools(self):
        def func_wrapper(func, **kwargs):
            func_res = func(**kwargs)
            return ToolResponse(
                content=func_res["content"],
            )

        toolkit = self.attr["agent_config"].get("toolkit", Toolkit())
        tools = self.attr["tools"]

        # in case, tools is None and tools == []
        if not tools:
            return toolkit

        if self.context.activate_tools:
            # Only add activated tool
            activated_tools = self.context.activate_tools
        else:
            # Lazy import
            from ....sandbox.tools.utils import setup_tools

            activated_tools = setup_tools(
                tools=self.attr["tools"],
                environment_manager=self.context.environment_manager,
                session_id=self.context.session.id,
                user_id=self.context.session.user_id,
                include_schemas=False,
            )

        for tool in activated_tools:
            function = RegisteredToolFunction(
                name=tool.name,
                source="mcp_server",
                mcp_name=tool.tool_type,
                original_func=partial(
                    func_wrapper,
                    tool,
                ),
                json_schema=tool.schema,
                group="basic",
            )
            toolkit.tools[tool.name] = function

        return toolkit


class AgentScopeAgent(Agent):
    def __init__(
        self,
        name: str,
        model: ChatModelBase,
        tools=None,
        agent_config=None,
        agent_builder: Optional[Type[ReActAgent]] = ReActAgent,
    ):
        super().__init__(name=name, agent_config=agent_config)
        assert isinstance(
            model,
            ChatModelBase,
        ), "model must be a subclass of ChatModelBase in AgentScope"

        # Set default agent_builder
        if agent_builder is None:
            agent_builder = ReActAgent

        assert issubclass(
            agent_builder,
            ReActAgent,
        ), "agent_builder must be a subclass of AgentBase in AgentScope"

        # Replace name if not exists
        self.agent_config["name"] = self.agent_config.get("name") or name

        self._attr = {
            "model": model,
            "tools": tools,
            "agent_config": self.agent_config,
            "agent_builder": agent_builder,
        }
        self._agent = None
        self.tools = tools

    def copy(self) -> "AgentScopeAgent":
        return AgentScopeAgent(**self._attr)

    def build(self, as_context):
        self._agent = self._attr["agent_builder"](
            **self._attr["agent_config"],
            model=as_context.model,
            formatter=as_context.formatter,
            memory=as_context.memory,
            toolkit=as_context.toolkit,
        )
        self._agent._disable_console_output = True

        self._agent.register_instance_hook(
            "pre_print",
            "pre_speak_msg_buffer_hook",
            pre_speak_msg_buffer_hook,
        )

        return self._agent

    async def run(self, context):
        as_context = AgentScopeContextAdapter(context=context, attr=self._attr)
        await as_context.initialize()
        local_truncate_memory = ""

        # We should always build a new agent since the state is manage outside
        # the agent
        self._agent = self.build(as_context)

        # Make the output a generator
        thread_id = "pipeline" + str(uuid.uuid4())
        try:
            # Run the main function in a separate thread
            thread = threading.Thread(
                target=run_async_in_thread,
                args=(self._agent.reply(msg=as_context.new_message),),
                name=thread_id,
            )
            clear_msg_instances(thread_id=thread_id)
            thread.start()

            # Yield new Msg instances as they are logged
            last_content = ""

            message = Message(type=MessageType.MESSAGE, role="assistant")
            yield message.in_progress()
            index = None

            for msg, msg_len in get_msg_instances(thread_id=thread_id):
                if msg:
                    content = msg.content
                    if isinstance(content, str):
                        last_content = content
                    else:
                        for element in content:
                            if isinstance(element, str) and element:
                                text_delta_content = TextContent(
                                    delta=True,
                                    index=index,
                                    text=element,
                                )
                                text_delta_content = message.add_delta_content(
                                    new_content=text_delta_content,
                                )
                                index = text_delta_content.index
                                yield text_delta_content
                            elif isinstance(element, dict):
                                if element.get("type") == "text":
                                    text = element.get(
                                        "text",
                                        "",
                                    )
                                    if text:
                                        text_delta_content = TextContent(
                                            delta=True,
                                            index=index,
                                            text=text.removeprefix(
                                                local_truncate_memory,
                                            ),
                                        )
                                        local_truncate_memory = element.get(
                                            "text",
                                            "",
                                        )
                                        text_delta_content = (
                                            message.add_delta_content(
                                                new_content=text_delta_content,
                                            )
                                        )
                                        index = text_delta_content.index
                                        yield text_delta_content
                                        if hasattr(msg, "is_last"):
                                            yield message.completed()
                                            message = Message(
                                                type=MessageType.MESSAGE,
                                                role="assistant",
                                            )
                                            index = None

                                elif element.get("type") == "tool_use":
                                    json_str = json.dumps(element.get("input"))
                                    data_delta_content = DataContent(
                                        index=index,
                                        data=FunctionCall(
                                            call_id=element.get("id"),
                                            name=element.get("name"),
                                            arguments=json_str,
                                        ).model_dump(),
                                    )
                                    plugin_call_message = Message(
                                        type=MessageType.PLUGIN_CALL,
                                        role="assistant",
                                        content=[data_delta_content],
                                    )
                                    yield plugin_call_message.completed()
                                elif element.get("type") == "tool_result":
                                    data_delta_content = DataContent(
                                        index=index,
                                        data=FunctionCallOutput(
                                            call_id=element.get("id"),
                                            output=str(element.get("output")),
                                        ).model_dump(),
                                    )
                                    plugin_output_message = Message(
                                        type=MessageType.PLUGIN_CALL_OUTPUT,
                                        role="assistant",
                                        content=[data_delta_content],
                                    )
                                    yield plugin_output_message.completed()
                                else:
                                    text_delta_content = TextContent(
                                        delta=True,
                                        index=index,
                                        text=f"{element}",
                                    )
                                    text_delta_content = (
                                        message.add_delta_content(
                                            new_content=text_delta_content,
                                        )
                                    )
                                    index = text_delta_content.index
                                    yield text_delta_content

                # Break if the thread is dead and no more messages are expected
                if not thread.is_alive() and msg_len == 0:
                    break

            if last_content:
                text_delta_content = TextContent(
                    delta=True,
                    index=index,
                    text=last_content,
                )
                text_delta_content = message.add_delta_content(
                    new_content=text_delta_content,
                )
                yield text_delta_content
                yield message.completed()

            # Wait for the function to finish
            thread.join()
        finally:
            pass

    async def run_async(
        self,
        context,
        **kwargs,
    ):
        async for event in self.run(context):
            yield event
