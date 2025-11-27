# -*- coding: utf-8 -*-
# pylint: disable=redefined-outer-name, use-dict-literal

import asyncio
import inspect
import json
from typing import (
    Any,
    Callable,
    Literal,
    Optional,
    Sequence,
    Union,
    cast,
    get_args,
    get_origin,
    get_type_hints,
)

from pydantic import BaseModel

from agentscope_runtime.tools.base import Tool

try:
    from langchain_core.messages import ToolCall, ToolMessage
    from langchain_core.messages.tool import ToolOutputMixin
    from langchain_core.runnables import RunnableConfig
    from langchain_core.runnables.config import ensure_config
    from langgraph.errors import GraphBubbleUp
    from langgraph.prebuilt import ToolNode
    from langgraph.types import Command
except ImportError as e:
    raise ImportError(
        "Please install langgraph to use this feature. "
        "You can install it with `pip install langgraph`",
    ) from e


INVALID_TOOL_NAME_ERROR_TEMPLATE = (
    "Error: {requested_tool} is not a valid "
    "tool, try one of [{available_tools}]."
)
TOOL_CALL_ERROR_TEMPLATE = "Error: {error}\n Please fix your mistakes."


def msg_content_output(output: Any) -> Union[str, list[dict]]:
    recognized_content_block_types = ("image", "image_url", "text", "json")
    if isinstance(output, str):
        return output
    elif isinstance(output, list) and all(
        isinstance(x, dict) and x.get("type") in recognized_content_block_types
        for x in output
    ):
        return output
    # Technically a list of strings is also valid message content but it's
    # not currently
    # well tested that all chat models support this. And for backwards
    # compatibility
    # we want to make sure we don't break any existing ToolNode usage.
    else:
        try:
            return json.dumps(output, ensure_ascii=False)
        except Exception:
            return str(output)


def _handle_tool_error(
    e: Exception,
    *,
    flag: Union[
        bool,
        str,
        Callable[..., str],
        tuple[type[Exception], ...],
    ],
) -> str:
    if isinstance(flag, (bool, tuple)):
        content = TOOL_CALL_ERROR_TEMPLATE.format(error=repr(e))
    elif isinstance(flag, str):
        content = flag
    elif callable(flag):
        content = flag(e)
    else:
        raise ValueError(
            f"Got unexpected type of `handle_tool_error`. Expected bool, str "
            f"or callable. Received: {flag}",
        )
    return content


def _infer_handled_types(
    handler: Callable[..., str],
) -> tuple[type[Exception], ...]:
    sig = inspect.signature(handler)
    params = list(sig.parameters.values())
    if params:
        # If it's a method, the first argument is typically 'self' or 'cls'
        if params[0].name in ["self", "cls"] and len(params) == 2:
            first_param = params[1]
        else:
            first_param = params[0]

        type_hints = get_type_hints(handler)
        if first_param.name in type_hints:
            origin = get_origin(first_param.annotation)
            if origin is Union:
                args = get_args(first_param.annotation)
                if all(issubclass(arg, Exception) for arg in args):
                    return tuple(args)
                else:
                    raise ValueError(
                        "All types in the error handler error annotation "
                        "must be Exception types. "
                        "For example, `def custom_handler(e: Union["
                        "ValueError, TypeError])`. "
                        f"Got '{first_param.annotation}' instead.",
                    )

            exception_type = type_hints[first_param.name]
            if Exception in exception_type.__mro__:
                return (exception_type,)
            else:
                raise ValueError(
                    f"Arbitrary types are not supported in the error handler "
                    f"signature. Please annotate the error with either a "
                    f"specific Exception type or a union of Exception types. "
                    "For example, `def custom_handler(e: ValueError)` or "
                    "`def custom_handler(e: Union[ValueError, TypeError])`. "
                    f"Got '{exception_type}' instead.",
                )

    # If no type information is available, return (Exception,) for backwards
    # compatibility.
    return (Exception,)


class LanggraphNodeAdapter(ToolNode):
    """A node that runs the tools called in the last AIMessage from langgraph

    It can be used either in StateGraph with a "messages" state key
    (or a custom key passed via ToolNode's 'messages_key').
    If multiple tool calls are requested, they will be run in parallel. The
    output will be
    a list of ToolMessages, one for each tool call.

    Args:
        tools: A sequence of tools that generate from tool can be
        invoked by the LanggraphNode.
        name: The name of the LanggraphNode in the graph. Defaults to "tools".
        tags: Optional tags to associate with the node. Defaults to None.
        handle_tool_errors: How to handle tool errors raised by
            tools inside the node. Defaults to True.
            Must be one of the following:

            - True: all errors will be caught and
                a ToolMessage with a default error message (
                TOOL_CALL_ERROR_TEMPLATE) will be returned.
            - str: all errors will be caught and
                a ToolMessage with the string value of 'handle_tool_errors'
                will be returned.
            - tuple[type[Exception], ...]: exceptions in the tuple will be
            caught and
                a ToolMessage with a default error message (
                TOOL_CALL_ERROR_TEMPLATE) will be returned.
            - Callable[..., str]: exceptions from the signature of the
            callable will be caught and
                a ToolMessage with the string value of the result of the
                'handle_tool_errors' callable will be returned.
            - False: none of the errors raised by the tools will be caught
        messages_key: The state key in the input that contains the list of
        messages.
            The same key will be used for the output from the ToolNode.
            Defaults to "messages".

    The `ToolNode` is roughly analogous to:

    ```python
    tools_by_name = {tool.name: tool for tool in tools}
    def tool_node(state: dict):
        result = []
        for tool_call in state["messages"][-1].tool_calls:
            tool = tools_by_name[tool_call["name"]]
            observation = tool.invoke(tool_call["args"])
            result.append(ToolMessage(content=observation,
            tool_call_id=tool_call["id"]))
        return {"messages": result}
    ```

    Important:
        - The state MUST contain a list of messages.
        - The last message MUST be an `AIMessage`.
        - The `AIMessage` MUST have `tool_calls` populated.
    """

    name: str = "ToolNode"

    def __init__(
        self,
        tools: Sequence[Tool],
        *,
        name: str = "tools",
        tags: Optional[list[str]] = None,
        handle_tool_errors: Union[
            bool,
            str,
            Callable[..., str],
            tuple[type[Exception], ...],
        ] = True,
        messages_key: str = "messages",
    ) -> None:
        super().__init__(
            [],
            name=name,
            tags=tags,
            handle_tool_errors=handle_tool_errors,
            messages_key=messages_key,
        )
        self.tools_by_name: dict[str, Any] = {}
        self.tools_input: dict[str, BaseModel] = {}
        self.tools_output: dict[str, BaseModel] = {}
        self.handle_tool_errors = handle_tool_errors
        self.messages_key = messages_key
        self.tool_schemas = []
        for tool_ in tools:
            self.tools_by_name[tool_.name] = tool_.arun
            self.tools_input[tool_.name] = tool_.input_type
            self.tools_output[tool_.name] = tool_.return_type
            self.tool_schemas.append(tool_.function_schema.model_dump())
            self.tool_to_state_args[tool_.name] = {}
            self.tool_to_store_arg[tool_.name] = {}

    def _prep_run_args(
        self,
        inputs: Union[str, dict, ToolCall],
        config: Optional[RunnableConfig],
        **kwargs: Any,
    ) -> tuple[BaseModel, dict]:
        def _is_tool_call(x: Any) -> bool:
            return isinstance(x, dict) and x.get("type") == "tool_call"

        input_type = self.tools_input.get(kwargs.get("tool_name", ""), None)

        config = ensure_config(config)
        if _is_tool_call(inputs):
            tool_call_id: Optional[str] = cast(ToolCall, inputs)["id"]
            tool_input: Union[str, dict] = cast(ToolCall, inputs)[
                "args"
            ].copy()
        else:
            tool_call_id = None
            tool_input = cast(Union[str, dict], inputs)

        if input_type:
            tool_input = input_type.model_validate(tool_input)
        return (
            tool_input,
            dict(
                callbacks=config.get("callbacks"),
                tags=config.get("tags"),
                metadata=config.get("metadata"),
                run_name=config.get("run_name"),
                run_id=config.pop("run_id", None),
                config=config,
                tool_call_id=tool_call_id,
                **kwargs,
            ),
        )

    def _format_output(
        self,
        content: BaseModel,
        tool_call_id: Optional[str],
        name: str,
        status: str,
    ) -> Union[ToolOutputMixin, Any]:
        output_type = self.tools_output.get(name, None)
        if output_type:
            if not isinstance(content, output_type):
                raise TypeError(
                    f"Tool {name} returned unexpected type: {type(content)}. "
                    f"Expected: {output_type}",
                )
        content_string = content.model_dump_json()
        return ToolMessage(
            content_string,
            artifact=content.model_dump(),
            tool_call_id=tool_call_id,
            name=name,
            status=status,
        )

    def _run_one(
        self,
        call: ToolCall,
        input_type: Literal["list", "dict"],
        config: RunnableConfig,
    ) -> ToolMessage:
        if invalid_tool_message := self._validate_tool_call(call):
            return invalid_tool_message

        async def async_tool_call(
            tools_by_name: dict,
            name: str,
            t_input: BaseModel,
            **kwargs: Any,
        ) -> Any:
            return await tools_by_name[name](t_input, **kwargs)

        try:
            inputs = {**call, **{"type": "tool_call"}}
            tool_input, kwargs = self._prep_run_args(
                inputs,
                config,
                tool_name=call["name"],
            )
            response = asyncio.run(
                async_tool_call(
                    self.tools_by_name,
                    call["name"],
                    tool_input,
                    **kwargs,
                ),
            )
            response = self._format_output(
                response,
                call["id"],
                call["name"],
                "success",
            )

        except GraphBubbleUp as e:
            raise e
        except Exception as e:
            if isinstance(self.handle_tool_errors, tuple):
                handled_types: tuple = self.handle_tool_errors
            elif callable(self.handle_tool_errors):
                handled_types = _infer_handled_types(self.handle_tool_errors)
            else:
                # default behavior is catching all exceptions
                handled_types = (Exception,)

            # Unhandled
            if not self.handle_tool_errors or not isinstance(e, handled_types):
                raise e
            # Handled
            content = _handle_tool_error(e, flag=self.handle_tool_errors)
            return ToolMessage(
                content=content,
                name=call["name"],
                tool_call_id=call["id"],
                status="error",
            )

        if isinstance(response, Command):
            return self._validate_tool_command(response, call, input_type)
        elif isinstance(response, ToolMessage):
            response.content = cast(
                Union[str, list],
                msg_content_output(response.content),
            )
            return response
        else:
            raise TypeError(
                f"Tool {call['name']} returned unexpected type: "
                f"{type(response)}",
            )

    async def _arun_one(
        self,
        call: ToolCall,
        input_type: Literal["list", "dict"],
        config: RunnableConfig,
    ) -> ToolMessage:
        if invalid_tool_message := self._validate_tool_call(call):
            return invalid_tool_message

        async def async_tool_call(
            tools_by_name: dict,
            name: str,
            t_input: BaseModel,
            **kwargs: Any,
        ) -> Any:
            return await tools_by_name[name](t_input, **kwargs)

        try:
            inputs = {**call, **{"type": "tool_call"}}
            tool_input, kwargs = self._prep_run_args(
                inputs,
                config,
                tool_name=call["name"],
            )
            response = await async_tool_call(
                self.tools_by_name,
                call["name"],
                tool_input,
                **kwargs,
            )

            response = self._format_output(
                response,
                call["id"],
                call["name"],
                "success",
            )

        except GraphBubbleUp as e:
            raise e
        except Exception as e:
            if isinstance(self.handle_tool_errors, tuple):
                handled_types: tuple = self.handle_tool_errors
            elif callable(self.handle_tool_errors):
                handled_types = _infer_handled_types(self.handle_tool_errors)
            else:
                # default behavior is catching all exceptions
                handled_types = (Exception,)

            # Unhandled
            if not self.handle_tool_errors or not isinstance(e, handled_types):
                raise e
            # Handled
            content = _handle_tool_error(e, flag=self.handle_tool_errors)
            return ToolMessage(
                content=content,
                name=call["name"],
                tool_call_id=call["id"],
                status="error",
            )

        if isinstance(response, Command):
            return self._validate_tool_command(response, call, input_type)
        elif isinstance(response, ToolMessage):
            response.content = cast(
                Union[str, list],
                msg_content_output(response.content),
            )
            return response
        else:
            raise TypeError(
                f"Tool {call['name']} returned unexpected type: "
                f"{type(response)}",
            )
