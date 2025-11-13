# -*- coding: utf-8 -*-
# pylint:disable=too-many-nested-blocks, too-many-branches, too-many-statements
# pylint:disable=line-too-long, protected-access
import copy
import logging
import json
import traceback
from functools import partial
from typing import Optional, Type, List, Callable

from agentscope import setup_logger
from agentscope.agent import AgentBase, ReActAgent
from agentscope.formatter import (
    FormatterBase,
    DashScopeChatFormatter,
    OpenAIChatFormatter,
    AnthropicChatFormatter,
    OllamaChatFormatter,
    GeminiChatFormatter,
)
from agentscope.model import (
    ChatModelBase,
    DashScopeChatModel,
    OpenAIChatModel,
    AnthropicChatModel,
    OllamaChatModel,
    GeminiChatModel,
)
from agentscope.pipeline import stream_printing_messages
from agentscope.tool import (
    Toolkit,
    ToolResponse,
)
from agentscope.tool._toolkit import RegisteredToolFunction


from .utils import build_agent
from ..agents import Agent
from ..schemas.agent_schemas import (
    Message,
    TextContent,
    DataContent,
    FunctionCall,
    FunctionCallOutput,
    MessageType,
    RunStatus,
)
from ..schemas.context import Context
from ...adapters.agentscope.message import message_to_agentscope_msg
from ...adapters.agentscope.memory import AgentScopeSessionHistoryMemory
from ...adapters.agentscope.long_term_memory import AgentScopeLongTermMemory

# Disable logging from agentscope
setup_logger(level="CRITICAL")
logger = logging.getLogger(__name__)


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
        self.long_term_memory = await self.adapt_long_term_memory()
        self.new_message = await self.adapt_new_message()
        self.toolkit = await self.adapt_tools()

    async def adapt_memory(self):
        memory = AgentScopeSessionHistoryMemory(
            service=self.context.context_manager._session_history_service,
            user_id=self.context.session.user_id,
            session_id=self.context.session.id,
        )

        return memory

    async def adapt_long_term_memory(self):
        if self.context.context_manager._memory_service:
            long_term_memory = AgentScopeLongTermMemory(
                service=self.context.context_manager._memory_service,
                user_id=self.context.session.user_id,
                session_id=self.context.session.id,
            )
            return long_term_memory
        return None

    async def adapt_new_message(self):
        return message_to_agentscope_msg(
            self.context.current_messages,
        )

    async def adapt_model(self):
        model = self.attr["model"]

        if hasattr(model, "stream"):
            model.stream = True

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

        # Deepcopy to avoid modify the original toolkit
        try:
            toolkit = copy.deepcopy(toolkit)
        except Exception as e:
            logger.warning(
                f"Failed to deepcopy toolkit for agent "
                f"'{self.attr.get('agent_config', {}).get('name')}' "
                f"Error: {e}\nTraceback:\n{traceback.format_exc()}",
            )

        tools = self.attr["tools"]

        # in case, tools is None and tools == []
        if not tools:
            return toolkit

        if self.context.activate_tools:
            # Only add activated tool
            activated_tools = self.context.activate_tools
        else:
            # Lazy import
            from ...sandbox.tools.utils import setup_tools

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
        agent_builder: Optional[Type[AgentBase]] = ReActAgent,
        custom_build_fn: Optional[Callable] = None,
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
            AgentBase,
        ), "agent_builder must be a subclass of AgentBase in AgentScope"

        # Replace name if not exists
        self.agent_config["name"] = self.agent_config.get("name") or name

        self._attr = {
            "model": model,
            "tools": tools,
            "agent_config": self.agent_config,
            "agent_builder": agent_builder,
            "custom_build_fn": custom_build_fn,
        }
        self.tools = tools

    def copy(self) -> "AgentScopeAgent":
        return AgentScopeAgent(**self._attr)

    def build(self, as_context) -> AgentBase:
        params = {
            **self._attr["agent_config"],
            **{
                "model": as_context.model,
                "formatter": self._attr["agent_config"].get(
                    "formatter",
                    as_context.formatter,
                ),
                "memory": as_context.memory,
                "long_term_memory": as_context.long_term_memory,
                "toolkit": as_context.toolkit,
            },
        }

        builder_cls = self._attr["agent_builder"]
        _agent = build_agent(builder_cls, params)

        return _agent

    async def run_async(
        self,
        context,
        **kwargs,
    ):
        as_context = AgentScopeContextAdapter(context=context, attr=self._attr)
        await as_context.initialize()
        local_truncate_memory = ""
        local_truncate_reasoning_memory = ""

        # We should always build a new agent since the state is manage outside
        # the agent
        if self._attr.get("custom_build_fn"):
            _agent = self._attr["custom_build_fn"](as_context, **kwargs)
        else:
            _agent = self.build(as_context)

        # Restore state from state service
        state_service = context.context_manager._state_service

        if hasattr(_agent, "load_state_dict") and state_service:
            state = await state_service.export_state(
                user_id=context.session.user_id,
                session_id=context.session.id,
            )
            if state:
                _agent.load_state_dict(state)

        if hasattr(_agent, "set_console_output_enabled"):
            _agent.set_console_output_enabled(False)

        # Yield new Msg instances as they are logged
        last_content = ""

        message = Message(type=MessageType.MESSAGE, role="assistant")
        reasoning_message = Message(
            type=MessageType.REASONING,
            role="assistant",
        )

        should_start_message = True
        should_start_reasoning_message = True

        index = None

        # Run agent
        async for msg, last in stream_printing_messages(
            agents=[_agent],
            coroutine_task=_agent(as_context.new_message),
        ):
            # deepcopy required to avoid modifying the original message object
            # which may be used elsewhere in the streaming pipeline
            msg = copy.deepcopy(msg)

            # Filter out unfinished tool_use messages
            if not last:
                new_blocks = []
                if isinstance(msg.content, List):
                    for block in msg.content:
                        if block.get("type", "") != "tool_use":
                            new_blocks.append(block)
                    msg.content = new_blocks

            if not msg.content:
                continue

            content = msg.content
            if isinstance(content, str):
                last_content = content
            else:
                for element in content:
                    if isinstance(element, str) and element:
                        if should_start_message:
                            index = None
                            yield message.in_progress()
                            should_start_message = False
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
                                if should_start_message:
                                    index = None
                                    yield message.in_progress()
                                    should_start_message = False

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
                                text_delta_content = message.add_delta_content(
                                    new_content=text_delta_content,
                                )
                                index = text_delta_content.index

                                # Only yield valid text
                                if text_delta_content.text:
                                    yield text_delta_content

                                if last:
                                    yield message.completed()
                                    message = Message(
                                        type=MessageType.MESSAGE,
                                        role="assistant",
                                    )
                                    index = None
                                    should_start_message = True

                        elif element.get("type") == "tool_use":
                            if (
                                reasoning_message.status
                                == RunStatus.InProgress
                            ):
                                yield reasoning_message.completed()
                                reasoning_message = Message(
                                    type=MessageType.REASONING,
                                    role="assistant",
                                )
                                index = None

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
                            index = None

                        elif element.get("type") == "tool_result":
                            json_str = json.dumps(element.get("output"))
                            data_delta_content = DataContent(
                                index=index,
                                data=FunctionCallOutput(
                                    call_id=element.get("id"),
                                    output=json_str,
                                ).model_dump(),
                            )
                            plugin_output_message = Message(
                                type=MessageType.PLUGIN_CALL_OUTPUT,
                                role="assistant",
                                content=[data_delta_content],
                            )
                            yield plugin_output_message.completed()
                            message = Message(
                                type=MessageType.MESSAGE,
                                role="assistant",
                            )
                            should_start_message = True
                            index = None

                        elif element.get("type") == "thinking":
                            reasoning = element.get(
                                "thinking",
                                "",
                            )
                            if reasoning:
                                if should_start_reasoning_message:
                                    index = None
                                    yield reasoning_message.in_progress()
                                    should_start_reasoning_message = False
                                text_delta_content = TextContent(
                                    delta=True,
                                    index=index,
                                    text=reasoning.removeprefix(
                                        local_truncate_reasoning_memory,
                                    ),
                                )
                                local_truncate_reasoning_memory = element.get(
                                    "thinking",
                                    "",
                                )
                                text_delta_content = (
                                    reasoning_message.add_delta_content(
                                        new_content=text_delta_content,
                                    )
                                )
                                index = text_delta_content.index

                                # Only yield valid text
                                if text_delta_content.text:
                                    yield text_delta_content

                                # The last won't happen in the thinking message
                                if last:
                                    yield reasoning_message.completed()
                                    reasoning_message = Message(
                                        type=MessageType.REASONING,
                                        role="assistant",
                                    )
                                    index = None
                        else:
                            if should_start_message:
                                index = None
                                yield message.in_progress()
                                should_start_message = False

                            text_delta_content = TextContent(
                                delta=True,
                                index=index,
                                text=f"{element}",
                            )
                            text_delta_content = message.add_delta_content(
                                new_content=text_delta_content,
                            )
                            index = text_delta_content.index
                            yield text_delta_content

        if last_content:
            if should_start_message:
                index = None
                yield message.in_progress()
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

        if state_service:
            state = _agent.state_dict()

            await state_service.save_state(
                user_id=context.session.user_id,
                session_id=context.session.id,
                state=state,
            )
