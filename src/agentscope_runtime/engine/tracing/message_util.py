# -*- coding: utf-8 -*-
from typing import List, Optional, Union

from openai.types.chat import ChatCompletionChunk
from openai.types.chat.chat_completion_chunk import ChoiceDeltaToolCall

from agentscope_runtime.engine.schemas.agent_schemas import (
    Role,
    FunctionCall,
    AgentResponse,
    RunStatus,
    Message,
    TextContent,
)

# Use OpenAI's ToolCall type instead of agentscope_bricks
ToolCall = ChoiceDeltaToolCall


# TODO: add this for streaming structured output support later
def merge_incremental_chunk(  # pylint: disable=too-many-branches,too-many-nested-blocks  # noqa: E501
    responses: List[ChatCompletionChunk],
) -> Optional[ChatCompletionChunk]:
    """
    Merge an incremental chunk list to a ChatCompletionChunk.

    Args:
        responses (List[ChatCompletionChunk]): List of incremental chat
            completion chunks to merge into a single response.

    Returns:
        Optional[ChatCompletionChunk]: The merged chat completion chunk,
        or None if the input list is empty.
    """

    if len(responses) == 0:
        return None

    if not isinstance(responses[0], ChatCompletionChunk):
        return None

    # get usage or finish reason
    merged = ChatCompletionChunk(**responses[-1].__dict__)

    # if the responses has usage info, then merge the finish reason chunk to
    # usage chunk
    if not merged.choices and len(responses) > 1:
        merged.choices = responses[-2].choices

    # might be multiple tool calls result
    tool_calls_dict = {}

    for resp in reversed(responses[:-1]):
        for i, j in zip(merged.choices, resp.choices):
            # jump the finish reason chunk
            if (i.delta.content is None and j.delta.content is not None) and (
                i.delta.tool_calls is None and j.delta.tool_calls is not None
            ):
                continue
            if j.delta.role == Role.TOOL:
                continue
            # merge content
            if not i.delta.content and isinstance(j.delta.content, str):
                i.delta.content = j.delta.content
            elif isinstance(i.delta.content, str) and isinstance(
                j.delta.content,
                str,
            ):
                i.delta.content = j.delta.content + i.delta.content

            # merge tool calls
            elif not i.delta.tool_calls and isinstance(
                j.delta.tool_calls,
                list,
            ):
                for tool_call in j.delta.tool_calls:
                    if tool_call.index not in tool_calls_dict:
                        tool_calls_dict[tool_call.index] = tool_call
                        # make sure function.arguments is a string
                        if not tool_call.function.arguments:
                            tool_calls_dict[
                                tool_call.index
                            ].function.arguments = ""
                    else:
                        if tool_call.id != "":
                            tool_calls_dict[tool_call.index].id = tool_call.id
                        if tool_call.function.name:
                            tool_calls_dict[
                                tool_call.index
                            ].function.name = tool_call.function.name
                        if (
                            tool_call.function.arguments
                            and not tool_calls_dict[
                                tool_call.index
                            ].function.arguments.startswith("{")
                        ):
                            tool_calls_dict[
                                tool_call.index
                            ].function.arguments = (
                                tool_call.function.arguments
                                + tool_calls_dict[
                                    tool_call.index
                                ].function.arguments
                            )

        if merged.usage and resp.usage:
            merged.usage.prompt_tokens += resp.usage.prompt_tokens
            merged.usage.completion_tokens += resp.usage.completion_tokens
            merged.usage.total_tokens += resp.usage.total_tokens

    if tool_calls_dict:
        merged.choices[0].delta.tool_calls = [
            ToolCall(
                id=tool_call.id,
                type=tool_call.type,
                function=FunctionCall(**tool_call.function.__dict__),
            )
            for tool_call in tool_calls_dict.values()
        ]
    return merged


def get_finish_reason(response: ChatCompletionChunk) -> Optional[str]:
    finish_reason = None

    if not isinstance(response, ChatCompletionChunk):
        return finish_reason

    if response.choices:
        if response.choices[0].finish_reason:
            finish_reason = response.choices[0].finish_reason

    return finish_reason


def merge_agent_response(  # pylint: disable=too-many-return-statements,too-many-branches,too-many-statements,too-many-nested-blocks  # noqa: E501
    responses: List[Union[AgentResponse, Message, TextContent]],
) -> AgentResponse:
    """
    Merge a list of incremental response objects into a single AgentResponse.

    Args:
        responses (List[Union[AgentResponse, Message, TextContent]]):
            List of incremental responses to merge into a single response.

    Returns:
        AgentResponse: The merged agent response.
    """
    if len(responses) == 0:
        raise ValueError("Cannot merge empty response list")

    # Check if all responses are of the same object type
    object_types = set()
    for resp in responses:
        if hasattr(resp, "object"):
            object_types.add(resp.object)
        else:
            # If no object field, treat as AgentResponse
            object_types.add("response")

    if len(object_types) > 1:
        # Mixed object types, convert the last response to AgentResponse
        last_resp = responses[-1]
        if isinstance(last_resp, TextContent):
            # Convert TextContent to Message, then to AgentResponse
            message = Message(
                role=Role.ASSISTANT,
                content=[last_resp],
                status=last_resp.status or RunStatus.Completed,
            )
            return AgentResponse(
                output=[message],
                status=message.status,
                session_id=None,
            )
        elif isinstance(last_resp, Message):
            return AgentResponse(
                output=[last_resp],
                status=last_resp.status,
                session_id=None,
            )
        else:
            return AgentResponse(**last_resp.__dict__)

    object_type = list(object_types)[0]

    if object_type == "content":
        # For content objects, merge text content and convert to AgentResponse
        text_contents = [
            resp for resp in responses if hasattr(resp, "text") and resp.text
        ]
        if not text_contents:
            # Return empty AgentResponse if no text content
            return AgentResponse(
                status=RunStatus.Completed,
                session_id=None,
            )

        # Merge all text content
        merged_text = ""
        last_content = text_contents[-1]

        for content in text_contents:
            if content.delta:
                merged_text += content.text
            else:
                merged_text = content.text

        # Create a Message with merged content
        final_content = TextContent(
            text=merged_text,
            delta=False,
            index=0,
            msg_id=last_content.msg_id,
            status=RunStatus.Completed,
        )

        message = Message(
            role=Role.ASSISTANT,
            content=[final_content],
            status=RunStatus.Completed,
        )

        return AgentResponse(
            output=[message],
            status=RunStatus.Completed,
            session_id=None,
        )

    elif object_type == "message":
        # For message objects, convert to AgentResponse
        messages = [resp for resp in responses if isinstance(resp, Message)]
        if not messages:
            return AgentResponse(
                status=RunStatus.Completed,
                session_id=None,
            )

        # Return the last message as AgentResponse
        last_message = messages[-1]
        return AgentResponse(
            output=[last_message],
            status=last_message.status,
            session_id=None,
        )

    else:
        # For response objects, use existing logic
        # Filter only AgentResponse objects
        agent_responses = [
            resp for resp in responses if isinstance(resp, AgentResponse)
        ]

        if len(agent_responses) == 0:
            last_resp = responses[-1]
            if isinstance(last_resp, Message):
                return AgentResponse(
                    output=[last_resp],
                    status=last_resp.status,
                    session_id=None,
                )
            else:
                return AgentResponse(**last_resp.__dict__)

        # Get the last AgentResponse as base
        merged = AgentResponse(**agent_responses[-1].__dict__)

        # If no output, return the merged response
        if not merged.output:
            return merged

        # Merge content from all AgentResponse objects
        content_dict = {}

        for resp in agent_responses:
            if not resp.output:
                continue

            for message in resp.output:
                if not message.content:
                    continue

                for content in message.content:
                    if (
                        content.type == "text"
                        and hasattr(content, "text")
                        and content.text
                    ):
                        # For text content, accumulate the text
                        if content.msg_id not in content_dict:
                            content_dict[content.msg_id] = {
                                "content": content,
                                "text": content.text,
                                "delta": content.delta,
                            }
                        else:
                            # If delta is True, append text; if False, replace
                            if content.delta:
                                content_dict[content.msg_id][
                                    "text"
                                ] += content.text
                            else:
                                content_dict[content.msg_id][
                                    "text"
                                ] = content.text

                            # Update the content object with merged text
                            content_dict[content.msg_id][
                                "content"
                            ].text = content_dict[content.msg_id]["text"]
                            content_dict[content.msg_id][
                                "content"
                            ].delta = False

        # Update the merged response with accumulated content
        if content_dict:
            for message in merged.output:
                if message.content:
                    for content in message.content:
                        if (
                            content.type == "text"
                            and hasattr(content, "msg_id")
                            and content.msg_id in content_dict
                        ):
                            content.text = content_dict[content.msg_id]["text"]
                            content.delta = False

        return merged


def get_agent_response_finish_reason(
    response: Union[AgentResponse, Message, TextContent],
) -> Optional[str]:
    """
    Get the finish reason from a response object.

    Args:
        response (Union[AgentResponse, Message, TextContent]):
            The response object

    Returns:
        Optional[str]: The finish reason, or None if not finished
    """
    # Only consider AgentResponse objects as potential final responses
    if isinstance(response, AgentResponse):
        if (
            hasattr(response, "status")
            and response.status == RunStatus.Completed
        ):
            # Check if this is a final response with output
            if hasattr(response, "output") and response.output:
                return "stop"
    return None


def merge_agent_message(  # pylint: disable=too-many-return-statements,too-many-branches,too-many-statements,too-many-nested-blocks  # noqa: E501
    messages: List[Union[Message, TextContent]],
) -> Message:
    """
    Merge a list of incremental message objects into a single Message.

    Args:
        messages (List[Union[Message, TextContent]]):
            List of incremental messages to merge into a single message.

    Returns:
        Message: The merged message.
    """
    if len(messages) == 0:
        raise ValueError("Cannot merge empty message list")

    # Check if all messages are of the same object type
    object_types = set()
    for msg in messages:
        if hasattr(msg, "object"):
            object_types.add(msg.object)
        else:
            # If no object field, treat as Message
            object_types.add("message")

    if len(object_types) > 1:
        # Mixed object types, convert the last message to Message
        last_msg = messages[-1]
        if isinstance(last_msg, TextContent):
            # Convert TextContent to Message with delta=False
            final_content = TextContent(
                text=last_msg.text,
                delta=False,
                index=last_msg.index,
                msg_id=last_msg.msg_id,
                status=RunStatus.Completed,
            )
            return Message(
                role=Role.ASSISTANT,
                content=[final_content],
                status=RunStatus.Completed,
            )
        else:
            return Message(**last_msg.__dict__)

    object_type = list(object_types)[0]

    if object_type == "content":
        # For content objects, merge text content and convert to Message
        text_contents = [
            msg for msg in messages if hasattr(msg, "text") and msg.text
        ]
        if not text_contents:
            # Return empty Message if no text content
            return Message(
                role=Role.ASSISTANT,
                status=RunStatus.Completed,
            )

        # Merge all text content
        merged_text = ""
        last_content = text_contents[-1]

        for content in text_contents:
            if content.delta:
                merged_text += content.text
            else:
                merged_text = content.text

        # Create a Message with merged content
        final_content = TextContent(
            text=merged_text,
            delta=False,
            index=0,
            msg_id=last_content.msg_id,
            status=RunStatus.Completed,
        )

        return Message(
            role=Role.ASSISTANT,
            content=[final_content],
            status=RunStatus.Completed,
        )

    else:
        # For message objects, use existing logic
        # Filter only Message objects
        message_objects = [msg for msg in messages if isinstance(msg, Message)]

        if len(message_objects) == 0:
            last_msg = messages[-1]
            if isinstance(last_msg, TextContent):
                return Message(
                    role=Role.ASSISTANT,
                    content=[last_msg],
                    status=last_msg.status or RunStatus.Completed,
                )
            else:
                return Message(**last_msg.__dict__)

        # Get the last Message as base
        merged = Message(**message_objects[-1].__dict__)

        # If no content, return the merged message
        if not merged.content:
            return merged

        # Merge content from all Message objects
        # Use msg_id + index as key to avoid overwriting different contents
        # with the same msg_id but different indexes
        content_dict = {}

        for msg in message_objects:
            if not msg.content:
                continue

            for content in msg.content:
                if (
                    content.type == "text"
                    and hasattr(content, "text")
                    and content.text
                ):
                    # Create unique key using msg_id and index
                    content_key = f"{content.msg_id}_{content.index}"

                    # For text content, accumulate the text
                    if content_key not in content_dict:
                        content_dict[content_key] = {
                            "content": content,
                            "text": content.text,
                            "delta": content.delta,
                            "msg_id": content.msg_id,
                            "index": content.index,
                        }
                    else:
                        # If delta is True, append text; if False, replace
                        if content.delta:
                            content_dict[content_key]["text"] += content.text
                        else:
                            content_dict[content_key]["text"] = content.text

                        # Update the content object with merged text
                        content_dict[content_key][
                            "content"
                        ].text = content_dict[content_key]["text"]
                        content_dict[content_key]["content"].delta = False

        # Update the merged message with accumulated content
        if content_dict:
            for content in merged.content:
                if (
                    content.type == "text"
                    and hasattr(content, "msg_id")
                    and hasattr(content, "index")
                ):
                    content_key = f"{content.msg_id}_{content.index}"
                    if content_key in content_dict:
                        content.text = content_dict[content_key]["text"]
                        content.delta = False

        return merged


def get_agent_message_finish_reason(
    message: Optional[Union[Message, TextContent]],
) -> Optional[str]:
    if message is None:
        return None

    if isinstance(message, Message):
        return "stop" if message.status == RunStatus.Completed else None

    return None
