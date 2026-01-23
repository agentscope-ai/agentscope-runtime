# -*- coding: utf-8 -*-
from collections import defaultdict
from enum import Enum
import logging
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union, cast
from uuid import uuid4

from ag_ui.core import RunAgentInput
from ag_ui.core.events import (
    Event as AGUIEvent,
    EventType as AGUIEventType,
    RunErrorEvent,
    RunFinishedEvent,
    RunStartedEvent,
    TextMessageContentEvent,
    TextMessageEndEvent,
    TextMessageStartEvent,
    ToolCallArgsEvent,
    ToolCallEndEvent,
    ToolCallStartEvent,
    ToolCallResultEvent,
)
from ag_ui.core.types import (
    AssistantMessage,
    BinaryInputContent,
    DeveloperMessage,
    SystemMessage,
    TextInputContent,
    ToolMessage,
    UserMessage,
    ActivityMessage,
    Message as AGUIMessage,
    Tool as AGUITool,
)
from pydantic import BaseModel, TypeAdapter

from ....schemas.agent_schemas import (
    AgentRequest,
    AgentResponse,
    BaseResponse,
    Content,
    ContentType,
    DataContent,
    FunctionCall,
    FunctionCallOutput,
    FunctionTool,
    FunctionParameters,
    ImageContent,
    Message,
    MessageType,
    Role,
    RunStatus,
    TextContent,
    Tool,
)

if TYPE_CHECKING:
    from .agui_protocol_adapter import FlexibleRunAgentInput

logger = logging.getLogger(__name__)


# pylint: disable=too-many-branches,too-many-statements,too-many-nested-blocks
def convert_ag_ui_messages_to_agent_api_messages(
    ag_ui_messages: List[AGUIMessage],
) -> List[Message]:
    """
    Convert AG-UI messages to AgentRequest messages.

    Args:
        ag_ui_messages: List of AG-UI Message objects.

    Returns:
        List of Message objects compatible with AgentRequest.input
    """
    converted_messages = []

    for ag_ui_msg in ag_ui_messages:
        message_id = ag_ui_msg.id or f"msg_{uuid4()}"

        # Handle different AG-UI message types based on class
        if isinstance(ag_ui_msg, (DeveloperMessage, SystemMessage)):
            # Developer/System messages -> MESSAGE type with system role
            content_text = ag_ui_msg.content or ""
            user_msg = Message(
                id=message_id,
                type=MessageType.MESSAGE,
                role=Role.SYSTEM,
                content=[TextContent(text=content_text)],
            )
            converted_messages.append(user_msg)

        elif isinstance(ag_ui_msg, UserMessage):
            # User messages -> MESSAGE type with user role
            content = ag_ui_msg.content
            user_content = []

            if isinstance(content, str):
                # Simple text content
                user_content.append(TextContent(text=content))
            elif isinstance(content, list):
                # Multimodal content (text, binary/image, etc.)
                for item in content:
                    if isinstance(item, TextInputContent):
                        user_content.append(TextContent(text=item.text or ""))
                    elif isinstance(item, BinaryInputContent):
                        # Handle binary content (e.g., images)
                        mime_type = item.mime_type or ""
                        if mime_type.startswith("image/"):
                            # Convert binary to image content
                            image_url = item.url or item.data
                            if image_url:
                                user_content.append(
                                    ImageContent(image_url=image_url),
                                )
                        else:
                            # For other binary types, store as data content
                            user_content.append(
                                DataContent(
                                    data=item.model_dump(exclude_none=True),
                                ),
                            )
            else:
                raise ValueError(
                    f"Unsupported user message content: {type(content)}",
                )

            user_msg = Message(
                id=message_id,
                type=MessageType.MESSAGE,
                role=Role.USER,
                content=(
                    user_content if user_content else [TextContent(text="")]
                ),
            )
            converted_messages.append(user_msg)

        elif isinstance(ag_ui_msg, AssistantMessage):
            # Assistant messages can have text content and/or tool_calls
            content_text = ag_ui_msg.content
            tool_calls = ag_ui_msg.tool_calls

            if tool_calls:
                # Assistant message with tool calls -> FUNCTION_CALL type
                function_call_contents = []
                for tool_call in tool_calls:
                    function_data = tool_call.function
                    function_call_contents.append(
                        DataContent(
                            data=FunctionCall(
                                call_id=tool_call.id or f"call_{uuid4()}",
                                name=function_data.name or "",
                                arguments=function_data.arguments or "{}",
                            ).model_dump(),
                        ),
                    )

                user_msg = Message(
                    id=message_id,
                    type=MessageType.FUNCTION_CALL,
                    role=Role.ASSISTANT,
                    content=function_call_contents,
                )
                converted_messages.append(user_msg)
            elif isinstance(content_text, str) and content_text:
                # Assistant message with text only -> MESSAGE type
                user_msg = Message(
                    id=message_id,
                    type=MessageType.MESSAGE,
                    role=Role.ASSISTANT,
                    content=[TextContent(text=content_text)],
                )
                converted_messages.append(user_msg)

        elif isinstance(ag_ui_msg, ToolMessage):
            # Tool messages -> FUNCTION_CALL_OUTPUT type
            tool_call_id = ag_ui_msg.tool_call_id or ""
            if ag_ui_msg.content:
                content_text = ag_ui_msg.content
            elif ag_ui_msg.error:
                content_text = f"error: {ag_ui_msg.error}"
            else:
                content_text = ""

            user_msg = Message(
                id=message_id,
                type=MessageType.FUNCTION_CALL_OUTPUT,
                role=Role.TOOL,
                content=[
                    DataContent(
                        data=FunctionCallOutput(
                            call_id=tool_call_id,
                            output=content_text,
                        ).model_dump(),
                    ),
                ],
            )
            converted_messages.append(user_msg)

        elif isinstance(ag_ui_msg, ActivityMessage):
            logger.warning(
                "Activity messages are not supported yet: %s",
                ag_ui_msg,
            )
        else:
            raise ValueError(
                f"Unsupported AG-UI message type: {type(ag_ui_msg)}",
            )

    return converted_messages


class AGUI_MESSAGE_STATUS(Enum):
    CREATED = "CREATED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"


class AGUIAdapterUtils:
    """
    Utility adapter that converts between Agent API events and AG-UI events.
    """

    def __init__(
        self,
        thread_id: Optional[str] = None,
        run_id: Optional[str] = None,
        threadId: Optional[str] = None,
        runId: Optional[str] = None,
    ) -> None:
        thread_id = thread_id or threadId
        run_id = run_id or runId
        self.thread_id = thread_id or f"thread_{uuid4()}"
        self.run_id = run_id or f"run_{uuid4()}"
        self._run_started_emitted = False
        self._run_finished_emitted = False
        self._agui_message_status: dict[
            str,
            AGUI_MESSAGE_STATUS,
        ] = defaultdict(lambda: AGUI_MESSAGE_STATUS.CREATED)
        self._message_id_to_agui_message_id_mapping = defaultdict(set[str])

    @property
    def run_finished_emitted(self) -> bool:
        return self._run_finished_emitted

    def convert_agui_request_to_agent_request(
        self,
        agui_request: Union[RunAgentInput, "FlexibleRunAgentInput"],
    ) -> AgentRequest:
        """
        Convert an AG-UI request payload to an AgentRequest.

        Accepts both RunAgentInput and FlexibleRunAgentInput.
        """
        converted_messages = convert_ag_ui_messages_to_agent_api_messages(
            agui_request.messages,
        )

        user_id_fields = ["user_id", "userId"]

        user_id = "default_user_id"
        forward_props = agui_request.forwarded_props or {}
        for user_id_field in user_id_fields:
            if user_id_field in forward_props:
                user_id = forward_props[user_id_field]
                break

        if agui_request.tools:
            tools = [
                self.convert_ag_ui_tool(tool).model_dump()
                for tool in agui_request.tools
            ]
        else:
            tools = []

        agent_request = AgentRequest.model_validate(
            {
                "input": [
                    msg.model_dump(exclude_none=True)
                    for msg in converted_messages
                ],
                "stream": True,  # AG-UI request is always in stream mode
                "id": self.run_id,
                "session_id": self.thread_id,
                "user_id": user_id,
                "tools": tools,
                # extra fields from agui_request
                "state": agui_request.state,
                "forwarded_props": agui_request.forwarded_props,
                "parent_run_id": agui_request.parent_run_id,
                "context": agui_request.context,
            },
        )
        return agent_request

    def convert_ag_ui_tool(self, ag_tool: AGUITool) -> Tool:
        """
        Convert an AG-UI Tool(name/description/parameters) into the Agent API
         Tool.
        """
        params = ag_tool.parameters

        if isinstance(params, BaseModel):
            params = params.model_dump(
                mode="json",
                exclude_none=True,
            )

        if params is None:
            params = {
                "type": "object",
                "properties": {},
                "required": [],
            }

        # If it's not a dict, we can't interpret it as JSON Schema; just wrap
        # as-is
        if not isinstance(params, dict):
            return Tool(
                type="function",
                function=FunctionTool(
                    name=ag_tool.name,
                    description=ag_tool.description,
                    parameters=params,  # preserve without crashing
                ),
            )

        # Heuristic: try to construct FunctionParameters if it matches the
        # expected shape
        schema_type = params.get("type")
        properties = params.get("properties")
        required = params.get("required", None)

        if schema_type == "object" and isinstance(properties, dict):
            if required is not None and not (
                isinstance(required, list)
                and all(isinstance(x, str) for x in required)
            ):
                required = None

            fp = FunctionParameters(
                type="object",
                properties=properties,
                required=required,
            )
            converted_params: Union[FunctionParameters, Dict[str, Any]] = fp
        else:
            converted_params = params

        return Tool(
            type="function",
            function=FunctionTool(
                name=ag_tool.name,
                description=ag_tool.description,
                parameters=converted_params,
            ),
        )

    def convert_agent_event_to_agui_events(
        self,
        agent_event: Content | Message | AgentResponse,
    ) -> List[AGUIEvent]:
        """
        Convert an Agent API event to one or more AG-UI events.
        """
        if isinstance(agent_event, AgentResponse):
            return self._convert_response_event(agent_event)
        elif isinstance(agent_event, Message):
            return self._convert_message_event(agent_event)
        elif isinstance(agent_event, Content):
            return self._convert_content_event(agent_event)
        else:
            logger.warning(
                f"Ignore not support agent api events: {agent_event}",
            )
            return []

    def _convert_message_event(
        self,
        message_event: Message,
    ) -> List[AGUIEvent]:
        events: List[AGUIEvent] = []
        events.extend(self._ensure_run_started_event())
        # Process message completion status
        if message_event.status in {RunStatus.Completed}:
            agui_message_ids = self._message_id_to_agui_message_id_mapping[
                message_event.id
            ]
            for agui_message_id in agui_message_ids:
                agui_message_status = self._agui_message_status.get(
                    agui_message_id,
                    None,
                )
                if not agui_message_status:
                    logger.warning(
                        "AG UI message not started before Agent API message"
                        " completed: %s",
                        agui_message_id,
                    )
                    continue

                if agui_message_status != AGUI_MESSAGE_STATUS.COMPLETED:
                    events.append(
                        TextMessageEndEvent(
                            message_id=agui_message_id,
                        ),
                    )
                    self._agui_message_status[
                        agui_message_id
                    ] = AGUI_MESSAGE_STATUS.COMPLETED

        return events

    def _convert_response_event(
        self,
        response_event: BaseResponse,
    ) -> List[AGUIEvent]:
        events: List[AGUIEvent] = []

        if response_event.status == RunStatus.Created:
            events.extend(self._ensure_run_started_event())
        elif response_event.status in {RunStatus.Failed, RunStatus.Rejected}:
            if getattr(response_event, "error", None):
                error_dict = response_event.error.model_dump()
                message = error_dict.get("message", "agent run failed")
                code = error_dict.get("code", "unknown_error")
            else:
                message = "agent run failed"
                code = "unknown_error"

            events.append(
                self.build_run_event(
                    AGUIEventType.RUN_ERROR,
                    message=message,
                    code=code,
                ),
            )
            self._run_finished_emitted = True
        elif response_event.status in {RunStatus.Completed}:
            self._run_finished_emitted = True
            events.append(
                self.build_run_event(event_type=AGUIEventType.RUN_FINISHED),
            )
        elif response_event.status in {RunStatus.Canceled}:
            self._run_finished_emitted = True
            events.append(
                self.build_run_event(
                    event_type=AGUIEventType.RUN_FINISHED,
                    result="agent run canceled",
                ),
            )
        else:
            logger.info(f"Not support AgentResponse event: {response_event}")
        return events

    def _get_msg_content_index(self, content: Content) -> int:
        values = sorted(
            [
                str(v)
                for k, v in vars(ContentType).items()
                if not k.startswith("_") and isinstance(v, str)
            ],
        )
        return values.index(content.type)

    def _convert_content_event(self, content: Content) -> List[AGUIEvent]:
        events: List[AGUIEvent] = []
        events.extend(self._ensure_run_started_event())

        def _ensure_agui_text_message_started(
            agui_msg_id: str,
        ) -> List[AGUIEvent]:
            if agui_msg_id in self._agui_message_status:
                return []
            self._agui_message_status[
                agui_msg_id
            ] = AGUI_MESSAGE_STATUS.CREATED
            return [
                TextMessageStartEvent(
                    message_id=agui_msg_id,
                ),
            ]

        def _ensure_agui_tool_call_message_started(
            agui_msg_id: str,
            tool_call: FunctionCall,
        ) -> List[AGUIEvent]:
            if agui_msg_id in self._agui_message_status:
                return []
            self._agui_message_status[
                agui_msg_id
            ] = AGUI_MESSAGE_STATUS.CREATED
            return [
                ToolCallStartEvent(
                    tool_call_id=tool_call.call_id,
                    tool_call_name=tool_call.name,
                ),
            ]

        if content.index is None:
            logger.warning("Content Index is Null")
            logger.warning(
                "Content: %s",
                content.model_dump(exclude_none=True),
            )

        agui_msg_id = content.msg_id
        self._message_id_to_agui_message_id_mapping[content.msg_id].add(
            agui_msg_id,
        )

        if isinstance(content, TextContent):
            events.extend(_ensure_agui_text_message_started(agui_msg_id))
            if content.delta:
                if (
                    self._agui_message_status[agui_msg_id]
                    == AGUI_MESSAGE_STATUS.COMPLETED
                ):
                    logger.warning(
                        "Message already completed: %s",
                        agui_msg_id,
                    )
                elif content.text:
                    self._agui_message_status[
                        agui_msg_id
                    ] = AGUI_MESSAGE_STATUS.IN_PROGRESS
                    events.append(
                        TextMessageContentEvent(
                            message_id=agui_msg_id,
                            delta=content.text,
                        ),
                    )
            else:
                if (
                    self._agui_message_status[agui_msg_id]
                    == AGUI_MESSAGE_STATUS.IN_PROGRESS
                ):
                    events.append(
                        TextMessageEndEvent(
                            message_id=agui_msg_id,
                        ),
                    )

                    self._agui_message_status[
                        agui_msg_id
                    ] = AGUI_MESSAGE_STATUS.COMPLETED
                elif (
                    self._agui_message_status[agui_msg_id]
                    == AGUI_MESSAGE_STATUS.CREATED
                ):
                    events.append(
                        TextMessageContentEvent(
                            message_id=agui_msg_id,
                            delta=content.text,
                        ),
                    )
                    self._agui_message_status[
                        agui_msg_id
                    ] = AGUI_MESSAGE_STATUS.COMPLETED
                else:
                    logger.warning(
                        "AG UI message stream is completed for the "
                        "text content: %s",
                        content.text,
                    )
        elif isinstance(content, DataContent):
            # currently, Agent API Protocol does not support streaming tool
            # calls events
            if agui_msg_id in self._agui_message_status:
                logger.warning(
                    "AG UI message stream is completed for the "
                    "tool call content: %s",
                    content.data,
                )
            elif content.status == RunStatus.Completed:
                X = Union[FunctionCall, FunctionCallOutput]
                ta = TypeAdapter(X)
                val = ta.validate_python(content.data)

                if isinstance(val, FunctionCall):
                    events.extend(
                        _ensure_agui_tool_call_message_started(
                            agui_msg_id=agui_msg_id,
                            tool_call=val,
                        ),
                    )
                    events.append(
                        ToolCallArgsEvent(
                            tool_call_id=val.call_id,
                            delta=val.arguments,
                        ),
                    )

                    events.append(
                        ToolCallEndEvent(
                            tool_call_id=val.call_id,
                        ),
                    )

                    self._agui_message_status[
                        agui_msg_id
                    ] = AGUI_MESSAGE_STATUS.COMPLETED
                else:
                    val = cast(FunctionCallOutput, val)
                    events.append(
                        ToolCallResultEvent(
                            message_id=agui_msg_id,
                            tool_call_id=val.call_id,
                            content=val.output,
                            role=Role.TOOL,
                        ),
                    )

        else:
            logger.warning(
                "Not support Agent API Content type: %s, content: %s",
                type(content),
                content.model_dump(exclude_none=True),
            )

        return events

    def _ensure_run_started_event(self) -> List[AGUIEvent]:
        if self._run_started_emitted:
            return []
        self._run_started_emitted = True
        return [
            RunStartedEvent(
                thread_id=self.thread_id,
                run_id=self.run_id,
            ),
        ]

    def build_run_event(
        self,
        event_type: AGUIEventType,
        **kwargs: Any,
    ) -> AGUIEvent:
        if event_type == AGUIEventType.RUN_STARTED:
            return RunStartedEvent(
                thread_id=self.thread_id,
                run_id=self.run_id,
                **kwargs,
            )
        if event_type == AGUIEventType.RUN_FINISHED:
            return RunFinishedEvent(
                thread_id=self.thread_id,
                run_id=self.run_id,
                **kwargs,
            )
        if event_type == AGUIEventType.RUN_ERROR:
            return RunErrorEvent(
                run_id=self.run_id,
                **kwargs,
            )
        raise ValueError(f"Unsupported run event type: {event_type}")
