# -*- coding: utf-8 -*-
# pylint: disable=too-many-branches,too-many-return-statements,line-too-long

"""
Responses Adapter

Bidirectional protocol converter: Responses API ↔ Agent API

Conversion functions:
1. Responses API request → Agent API request
2. Agent API event → Responses API event
3. Support for streaming and non-streaming conversion
"""

import time
import uuid
from typing import Any, Dict, List, Optional, Union

# OpenAI Responses API Types
from openai.types.responses import (
    Response,
    ResponseCompletedEvent,
    ResponseContentPartAddedEvent,
    ResponseContentPartDoneEvent,
    ResponseCreatedEvent,
    ResponseErrorEvent,
    ResponseFailedEvent,
    ResponseFunctionCallArgumentsDeltaEvent,
    ResponseFunctionCallArgumentsDoneEvent,
    ResponseInProgressEvent,
    ResponseOutputItemAddedEvent,
    ResponseOutputItemDoneEvent,
    ResponseReasoningTextDeltaEvent,
    ResponseReasoningTextDoneEvent,
    ResponseRefusalDeltaEvent,
    ResponseRefusalDoneEvent,
    ResponseStatus,
    ResponseStreamEvent,
    ResponseTextDeltaEvent,
    ResponseTextDoneEvent,
)
from openai.types.responses.response_function_tool_call import (
    ResponseFunctionToolCall,
)
from openai.types.responses.response_mcp_call_completed_event import (
    ResponseMcpCallCompletedEvent,
)
from openai.types.responses.response_mcp_call_in_progress_event import (
    ResponseMcpCallInProgressEvent,
)
from openai.types.responses.response_mcp_list_tools_completed_event import (
    ResponseMcpListToolsCompletedEvent,
)
from openai.types.responses.response_mcp_list_tools_in_progress_event import (
    ResponseMcpListToolsInProgressEvent,
)
from openai.types.responses.response_output_item import (
    McpCall,
    McpListTools,
    McpListToolsTool,
    ResponseOutputItem,
)
from openai.types.responses.response_output_message import (
    ResponseOutputMessage,
)
from openai.types.responses.response_output_refusal import (
    ResponseOutputRefusal,
)
from openai.types.responses.response_output_text import ResponseOutputText
from openai.types.responses.response_reasoning_item import (
    ResponseReasoningItem,
)

from openai.types.responses.response_reasoning_item import (
    Content as ReasoningContent,
)

from agentscope_runtime.engine.schemas.agent_schemas import (
    AgentRequest,
    BaseResponse,
    Content,
    ContentType,
    DataContent,
    Event,
    Message,
    MessageType,
    RefusalContent,
    Role,
    RunStatus,
    TextContent,
    ToolCall,
    ToolCallOutput,
    FunctionTool,
    Tool,
    ImageContent,
    AudioContent,
    FileContent,
)


# Agent API Types


class ResponsesAdapter:
    """
    Bidirectional protocol converter: Responses API ↔ Agent API

    Main functions:
    1. Convert Responses API request → Agent API request
    2. Convert Agent API event → Responses API event
    3. Convert Responses API event stream → Agent API event stream
    4. Handle various message types (text, tool calls, reasoning, etc.)
    """

    def __init__(self):
        self.sequence_counter = 0
        # Temporary storage structure: key is message id, value is dict
        # containing message_type and content_index_list
        self._message_content_index_map: Dict = {}
        # Additional adaptation work for adapting Agent API RAG plugin calls
        # to Responses API FileSearch calls
        self._file_search_call_map: Optional[Dict] = None
        self._output_index: int = 0
        self._output: List[ResponseOutputItem] = []

    def convert_agent_response_to_responses(
        self,
        agent_response: BaseResponse,
    ):
        # First convert Response
        response = self._convert_agent_response_responses_api(
            agent_response=agent_response,
        )

        # Convert Message
        messages = self._convert_agent_message_to_responses(
            agent_message_list=agent_response.output,
        )
        response.output = messages

        # Convert Content
        return response

    def convert_status_to_responses(self, agent_status: str) -> ResponseStatus:
        if agent_status in (RunStatus.Created, RunStatus.Queued):
            return "queued"
        elif agent_status == RunStatus.InProgress:
            return "in_progress"
        elif agent_status == RunStatus.Completed:
            return "completed"
        elif agent_status == RunStatus.Failed:
            return "failed"
        elif agent_status == RunStatus.Cancelled:
            return "cancelled"
        elif agent_status == RunStatus.Incomplete:
            return "incomplete"
        else:
            return "in_progress"

    def _convert_agent_message_to_responses(
        self,
        agent_message_list: List[Message],
    ):
        messages = []
        if agent_message_list:
            for message in agent_message_list:
                if message.type == MessageType.MESSAGE:
                    output_message = (
                        self._convert_message_type_to_output_message(
                            message,
                        )
                    )
                    messages.append(output_message)
                if message.type == MessageType.FUNCTION_CALL:
                    function_call_message = (
                        self._convert_function_call_to_output_message(
                            message,
                        )
                    )
                    messages.append(function_call_message)
                if message.type == MessageType.MCP_LIST_TOOLS:
                    mcp_list_tools_message = (
                        self._convert_mcp_list_tools_to_output_message(
                            message,
                        )
                    )
                    messages.append(mcp_list_tools_message)
                if message.type == MessageType.MCP_TOOL_CALL:
                    tool_call_message = (
                        self._convert_mcp_tool_call_to_output_message(
                            message,
                        )
                    )
                    messages.append(tool_call_message)
                if message.type == MessageType.REASONING:
                    reasoning_message = (
                        self._convert_reasoning_to_output_message(
                            message,
                        )
                    )
                    messages.append(reasoning_message)
        return messages

    def _convert_agent_response_responses_api(
        self,
        agent_response: BaseResponse,
    ):
        status = agent_response.status
        response_status = self.convert_status_to_responses(status)

        # Extract real data from agent_event
        response_id = (
            getattr(
                agent_response,
                "id",
                f"resp_{uuid.uuid4().hex[:8]}",
            )
            or f"resp_{uuid.uuid4().hex[:8]}"
        )
        created_at = (
            getattr(
                agent_response,
                "created_at",
                time.time(),
            )
            or time.time()
        )
        # Modified: ensure model value returns default empty string when None
        model = getattr(agent_response, "model", "") or ""
        parallel_tool_calls = (
            getattr(
                agent_response,
                "parallel_tool_calls",
                False,
            )
            or False
        )
        tool_choice = getattr(agent_response, "tool_choice", "auto") or "auto"
        tools = getattr(agent_response, "tools", []) or []
        error = getattr(agent_response, "error", None)

        # Convert Agent API error to Responses API error
        responses_error = None
        if error:
            responses_error = self._convert_agent_error_to_responses_error(
                error,
            )

        # Create real Response object using data from agent_event
        response = Response(
            id=response_id,
            status=response_status,
            created_at=created_at,
            model=model,
            object="response",
            output=[],
            parallel_tool_calls=parallel_tool_calls,
            tool_choice=tool_choice,
            tools=tools,
            error=responses_error,  # Set converted error
        )

        return response

    # ===== Request conversion: Responses API → Agent API =====

    def convert_responses_request_to_agent_request(
        self,
        responses_request: Dict[str, Any],
    ) -> AgentRequest:
        """
        Convert Responses API request to Agent API request

        Implement automatic assignment of fields with the same name,
        then explicitly handle different field names

        Args:
            responses_request: OpenAI ResponseCreateParams

        Returns:
            AgentRequest: Agent API request format
        """
        # 1. Extract input messages
        input_messages = self._extract_input_messages(responses_request)

        # 2. Automatic assignment of fields with the same name
        common_fields = self._extract_common_fields(
            responses_request=responses_request,
            request_type="agent",
        )

        # 3. Explicit mapping of different field names
        special_mappings = self._extract_special_mappings(responses_request)

        # 4. Merge all fields to create AgentRequest
        agent_request_data = {
            "input": input_messages,
            **common_fields,
            **special_mappings,
        }

        return AgentRequest(**agent_request_data)

    def _extract_input_messages(
        self,
        responses_request: Dict[str, Any],
    ) -> List[Message]:
        """Extract and convert input messages"""
        input_messages = []

        # Extract input from responses_request
        if "input" in responses_request and responses_request["input"]:
            input_data = responses_request["input"]

            # Handle Text input (string) type
            if isinstance(input_data, str):
                message = self._convert_text_input_to_agent_message(input_data)
                input_messages.append(message)

            # Handle Input item list (array) type
            elif isinstance(input_data, list):
                for input_item in input_data:
                    # Filter out developer role (not supported yet)
                    if "developer" == input_item.get("role", "user"):
                        continue

                    # Handle dictionary format input
                    if isinstance(input_item, dict):
                        item_type = input_item.get("type")

                        # If there's no type field but has role and content,
                        # consider it as message type
                        if (
                            not item_type
                            and "role" in input_item
                            and "content" in input_item
                        ):
                            item_type = "message"
                    else:
                        item_type = getattr(input_item, "type", None)

                    if item_type == "message":
                        # Convert to Agent API Message
                        message = self._convert_responses_input_message_to_agent_message(  # noqa: E501
                            input_item,
                        )
                        input_messages.append(message)
                    elif item_type == "reasoning":
                        # Convert to Agent API Message (type=REASONING)
                        message = self._convert_reasoning_to_message(
                            input_item,
                        )
                        input_messages.append(message)
                    elif item_type == "custom_tool_call":
                        # Convert to Agent API Message (type=PLUGIN_CALL)
                        message = self._convert_custom_tool_call_to_message(
                            input_item,
                        )
                        input_messages.append(message)
                    elif item_type == "custom_tool_call_output":
                        # Convert to Agent API Message
                        # (type=PLUGIN_CALL_OUTPUT)
                        message = (
                            self._convert_custom_tool_call_output_to_message(
                                input_item,
                            )
                        )
                        input_messages.append(message)
                    elif item_type == "function_call":
                        # Convert to Agent API Message (type=FUNCTION_CALL)
                        message = self._convert_function_call_to_message(
                            input_item,
                        )
                        input_messages.append(message)
                    elif item_type == "function_call_output":
                        # Convert to Agent API Message
                        # (type=FUNCTION_CALL_OUTPUT)
                        message = (
                            self._convert_function_call_output_to_message(
                                input_item,
                            )
                        )
                        input_messages.append(message)

        return input_messages

    def _convert_text_input_to_agent_message(self, text_input: str) -> Message:
        """Convert Text input (string) to Agent API Message"""

        # Create text content
        text_content = TextContent(type="text", text=text_input, delta=False)

        # Create message
        message = Message(
            role=Role.USER,
            type="message",
            content=[text_content],
        )

        return message

    def _extract_common_fields(
        self,
        responses_request: Dict[str, Any],
        request_type: Optional[str] = "agent",
    ) -> Dict[str, Any]:
        """
        Intelligently extract fields with the same name, automatically detect
        and map fields with the same name and type

        Automatically discover fields with the same name and type in
        ResponseCreateParams and AgentRequest through reflection mechanism
        """
        common_fields = {}

        # Get AgentRequest field information
        request_fields = None
        if request_type == "workflow":
            request_fields = self._get_workflow_request_field_info()
        else:
            request_fields = self._get_agent_request_field_info()

        # Iterate through all keys in ResponseCreateParams
        for attr_name in responses_request.keys():
            # Skip private attributes and methods
            if attr_name.startswith("_"):
                continue

            # Get value
            try:
                value = responses_request[attr_name]
            except KeyError:
                continue

            # Skip None values
            if value is None:
                continue

            # Check if AgentRequest has field with same name
            if attr_name not in request_fields:
                continue

            # Skip fields that need special handling
            if attr_name == "input":
                # input field needs special conversion, not handled here
                continue
            if attr_name == "tools":
                # tools field needs special conversion, convert Responses API
                # format to Agent API format
                converted_tools = self._convert_responses_tools_to_agent_tools(
                    value,
                )
                if converted_tools is not None:
                    common_fields[attr_name] = converted_tools
                continue

            # Check if types are compatible
            agent_field_type = request_fields[attr_name]
            if self._is_type_compatible(value, agent_field_type):
                common_fields[attr_name] = value

        return common_fields

    def _convert_responses_tools_to_agent_tools(
        self,
        responses_tools: List[
            Dict[
                str,
                Any,
            ]
        ],
    ) -> Optional[List[Any]]:
        """
        Convert Responses API tools format to Agent API tools format

        Responses API format:
        [{
            "name": "get_weather",
            "description": "Get the current weather in a given location",
            "strict": true,
            "type": "function",
            "parameters": {
                "type": "object",
                "properties": {...},
                "required": [...]
            }
        }]

        Agent API format:
        [{
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get the current weather in a given location",
                "parameters": {
                    "type": "object",
                    "properties": {...},
                    "required": [...]
                }
            }
        }]
        """
        if not responses_tools or not isinstance(responses_tools, list):
            return None

        converted_tools = []
        for tool_data in responses_tools:
            if not isinstance(tool_data, dict):
                continue

            # Extract basic information
            name = tool_data.get("name", "")
            description = tool_data.get("description", "")
            tool_type = tool_data.get("type", "function")
            parameters = tool_data.get("parameters", {})

            # Skip invalid tools
            if not name:
                continue

            # Create FunctionTool
            function_tool = FunctionTool(
                name=name,
                description=description,
                parameters=parameters,
            )

            # Create Agent API Tool
            agent_tool = Tool(type=tool_type, function=function_tool)

            converted_tools.append(agent_tool)

        return converted_tools if converted_tools else None

    def _get_agent_request_field_info(self) -> Dict[str, type]:
        """Get AgentRequest field type information"""
        # Cache field information to avoid repeated calculations
        if not hasattr(self, "_agent_request_fields_cache"):
            from typing import get_type_hints

            # Get AgentRequest type annotations
            type_hints = get_type_hints(AgentRequest)
            self._agent_request_fields_cache = type_hints

        return self._agent_request_fields_cache

    def _is_type_compatible(self, value: Any, target_type: type) -> bool:
        """Check if value type is compatible with target type"""
        if target_type is None:
            return True

        # Handle Union types (e.g. Optional[str] = Union[str, None])
        if (
            hasattr(
                target_type,
                "__origin__",
            )
            and target_type.__origin__ is Union
        ):
            # Check if compatible with any type in Union
            for union_type in target_type.__args__:
                if union_type is type(None):  # Skip None type
                    continue
                if self._is_type_compatible(value, union_type):
                    return True
            return False

        # Handle List types
        if (
            hasattr(
                target_type,
                "__origin__",
            )
            and target_type.__origin__ is list
        ):
            if isinstance(value, list):
                return True
            return False

        # Handle basic types
        try:
            # Direct type check
            if isinstance(value, target_type):
                return True

            # Special type conversion check - more strict check
            if target_type == str and isinstance(value, (str, int, float)):
                return True
            if target_type == int and isinstance(value, int):
                return True  # Only allow integers
            if target_type == float and isinstance(value, (float, int)):
                return True  # Allow integer to float conversion
            if target_type == bool and isinstance(value, bool):
                return True  # Only allow boolean values

        except Exception:
            pass

        return False

    def _extract_special_mappings(
        self,
        responses_request: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Extract different field names, explicit mapping

        Different field name mappings:
        - max_output_tokens -> max_tokens
        - conversation -> session_id
        - previous_response_id -> previous_response_id
        """
        special_mappings = {}

        # conversation -> session_id
        if "conversation" in responses_request:
            conversation = responses_request["conversation"]
            if conversation is not None:
                # If conversation is an object, extract ID
                if hasattr(conversation, "id"):
                    special_mappings["session_id"] = conversation.id
                elif isinstance(conversation, dict) and "id" in conversation:
                    special_mappings["session_id"] = conversation["id"]
                else:
                    # If conversation is itself an ID string
                    special_mappings["session_id"] = str(conversation)

        return special_mappings

    def _convert_responses_input_message_to_agent_message(
        self,
        input_message,
    ) -> Message:
        """Convert Responses API Input message to Agent API Message"""

        # Extract message attributes
        if isinstance(input_message, dict):
            content = input_message.get("content", [])
            role = input_message.get("role", "user")
            msg_type = input_message.get("type", "message")
        else:
            content = getattr(input_message, "content", [])
            role = getattr(input_message, "role", "user")
            msg_type = getattr(input_message, "type", "message")

        # Convert content items
        content_list = []

        # If content is string, directly convert to TextContent
        if isinstance(content, str):
            text_content = TextContent(
                type=ContentType.TEXT,
                text=content,
                delta=False,
            )
            content_list.append(text_content)
        # If content is list, iterate and convert each item
        elif isinstance(content, list):
            for content_item in content:
                agent_content = self._convert_content_item_to_agent_content(
                    content_item,
                )
                if agent_content:
                    content_list.append(agent_content)

        # Create Agent API Message
        message = Message(role=role, type=msg_type, content=content_list)

        return message

    def _convert_reasoning_to_message(self, input_reasoning) -> Message:
        """Convert Responses API Input reasoning to Agent API Message"""
        # Extract reasoning attributes
        if isinstance(input_reasoning, dict):
            content = input_reasoning.get("content", [])
        else:
            content = getattr(input_reasoning, "content", [])

        # Convert content items to text content
        content_list = []

        # Process content
        for content_item in content:
            if isinstance(content_item, dict):
                content_text = content_item.get("text", "")
            else:
                content_text = getattr(content_item, "text", "")

            if content_text:
                text_content = TextContent(
                    type=ContentType.TEXT,
                    text=content_text,
                )
                content_list.append(text_content)

        # Create Agent API Message (type=REASONING)
        message = Message(
            role="assistant",
            # reasoning is usually assistant's reasoning process
            type=MessageType.REASONING,
            content=content_list,
        )

        return message

    def _convert_content_item_to_agent_content(self, content_item):
        """Convert content item to Agent API Content"""

        # Handle dictionary or object format content items
        if isinstance(content_item, dict):
            content_type = content_item.get("type")
            content_text = content_item.get("text")
            content_refusal = content_item.get("refusal")
            image_url = content_item.get("image_url")
            # Audio data is in input_audio object
            input_audio = content_item.get("input_audio", {})
            audio_data = (
                input_audio.get("data")
                if isinstance(
                    input_audio,
                    dict,
                )
                else None
            )
            audio_format = (
                input_audio.get("format")
                if isinstance(
                    input_audio,
                    dict,
                )
                else None
            )
            # File data is directly at root level
            file_data = content_item.get("file_data")
            file_id = content_item.get("file_id")
            file_url = content_item.get("file_url")
            filename = content_item.get("filename")
        else:
            content_type = getattr(content_item, "type", None)
            content_text = getattr(content_item, "text", None)
            content_refusal = getattr(content_item, "refusal", None)
            image_url = getattr(content_item, "image_url", None)
            # Audio data is in input_audio object
            input_audio = getattr(content_item, "input_audio", None)
            audio_data = (
                getattr(
                    input_audio,
                    "data",
                    None,
                )
                if input_audio
                else None
            )
            audio_format = (
                getattr(
                    input_audio,
                    "format",
                    None,
                )
                if input_audio
                else None
            )
            # File data is directly at root level
            file_data = getattr(content_item, "file_data", None)
            file_id = getattr(content_item, "file_id", None)
            file_url = getattr(content_item, "file_url", None)
            filename = getattr(content_item, "filename", None)

        # Convert different types of input content
        if content_type == "input_text" and content_text:
            return TextContent(type=ContentType.TEXT, text=content_text)
        elif content_type == "output_text" and content_text:
            return TextContent(type=ContentType.TEXT, text=content_text)
        elif content_type == "refusal" and content_refusal:
            return RefusalContent(
                type=ContentType.REFUSAL,
                refusal=content_refusal,
            )
        elif content_type == "input_image" and image_url:
            return ImageContent(type=ContentType.IMAGE, image_url=image_url)
        elif content_type == "input_audio" and audio_data:
            return AudioContent(
                type=ContentType.AUDIO,
                data=audio_data,
                format=audio_format,
            )
        elif content_type == "input_file" and (
            file_url or file_id or file_data
        ):
            return FileContent(
                type=ContentType.FILE,
                file_url=file_url,
                file_id=file_id,
                filename=filename,
            )

        return None

    # ===== Response conversion: Agent API → Responses API =====

    def convert_agent_event_to_responses_event(
        self,
        agent_event: Event,
    ) -> Optional[List[ResponseStreamEvent]]:
        """
        Convert Agent API event to Responses API stream event

        Args:
            agent_event: Agent API Event

        Returns:
            ResponseStreamEvent or None
        """
        # 1. If it's a response message type, convert to response stream
        # message in responses api
        if isinstance(agent_event, BaseResponse):
            return self._convert_response_to_responses_event(agent_event)

        # 2. If it's a message message type, convert to corresponding
        # message type
        elif isinstance(agent_event, Message):
            return self._convert_message_to_responses_event(agent_event)

        # 3. If it's a content message, perform corresponding
        # content conversion
        elif isinstance(agent_event, Content):
            return self._convert_content_to_responses_event(agent_event)

        # Other types return None for now
        return None

    def _convert_response_to_responses_event(
        self,
        response_event: BaseResponse,
    ) -> Optional[List[ResponseStreamEvent]]:
        """
        Convert response message type to Responses API stream event

        Args:
            response_event: Agent API BaseResponse

        Returns:
            ResponseStreamEvent or None
        """
        status = response_event.status
        responses = []

        response = self._convert_agent_response_responses_api(response_event)
        response.output = self._output

        # Create corresponding events based on status
        if status == "created":
            created = ResponseCreatedEvent(
                type="response.created",
                response=response,
                sequence_number=0,
            )  # Will be set uniformly in responses_service
            responses.append(created)
        elif status == "in_progress":
            in_progress = ResponseInProgressEvent(
                type="response.in_progress",
                response=response,
                sequence_number=0,
            )  # Will be set uniformly in responses_service
            responses.append(in_progress)
        elif status == "completed":
            completed = ResponseCompletedEvent(
                type="response.completed",
                response=response,
                sequence_number=0,
            )  # Will be set uniformly in responses_service
            responses.append(completed)
        elif status == "failed":
            failed = ResponseFailedEvent(
                type="response.failed",
                response=response,
                sequence_number=0,
            )  # Will be set uniformly in responses_service
            responses.append(failed)

        return responses

    def _convert_message_to_responses_event(
        self,
        message_event: Message,
    ) -> Optional[List[ResponseStreamEvent]]:
        """
        Convert message message type to Responses API stream event

        Args:
            message_event: Agent API Message

        Returns:
            ResponseStreamEvent or None
        """
        message_id = message_event.id

        # Check if message id already exists in temporary storage structure
        if message_id not in self._message_content_index_map:
            # If not, record it in the structure
            self._message_content_index_map[message_id] = {
                "message_type": message_event.type,
                "content_index_list": [],
            }

            # If message_id doesn't exist, handle new message
            return self._handle_new_message(message_event)
        else:
            # If message_id already exists, handle differently based on
            # message status
            return self._handle_existing_message(message_event)

    def _get_add_output_index(self, message_id: str):
        output_index = self._output_index
        if (
            self._message_content_index_map
            and self._message_content_index_map[message_id]
        ):
            self._message_content_index_map[message_id][
                "output_index"
            ] = output_index
            self._output_index += 1
        return output_index

    def _get_output_index(self, message_id: str):
        if (
            self._message_content_index_map
            and self._message_content_index_map[message_id]
        ):
            return self._message_content_index_map[message_id]["output_index"]
        return self._output_index

    def _handle_new_message(
        self,
        message_event: Message,
    ) -> Optional[List[ResponseStreamEvent]]:
        messages = []

        # Handle different message types
        if message_event.type == MessageType.FUNCTION_CALL:
            self._get_add_output_index(message_event.id)

        elif message_event.type == MessageType.REASONING:
            # reasoning directly returns ResponseReasoningItem
            reasoning_item = self._convert_reasoning_to_output_message(
                message_event,
            )
            item_added_event = ResponseOutputItemAddedEvent(
                type="response.output_item.added",
                item=reasoning_item,
                output_index=self._output_index,
                sequence_number=0,
            )  # Will be set uniformly in responses_service

            # sequence_number will be set uniformly in responses_service
            self._get_add_output_index(message_event.id)
            messages.append(item_added_event)

        elif message_event.type == MessageType.MCP_LIST_TOOLS:
            # Convert MCP tool list to ResponseOutputMessage
            output_message = self._convert_mcp_list_tools_to_output_message(
                message_event,
            )
            output_item_added_event = ResponseOutputItemAddedEvent(
                type="response.output_item.added",
                item=output_message,
                output_index=self._output_index,
                sequence_number=0,
            )  # Will be set uniformly in responses_service

            # sequence_number will be set uniformly in responses_service
            self._get_add_output_index(message_event.id)
            messages.append(output_item_added_event)

        elif message_event.type == MessageType.MCP_TOOL_CALL:
            # Convert MCP tool call to ResponseFunctionToolCall
            function_tool_call = self._convert_mcp_tool_call_to_output_message(
                message_event,
            )
            output_item_added_event = ResponseOutputItemAddedEvent(
                type="response.output_item.added",
                item=function_tool_call,
                output_index=self._output_index,
                sequence_number=0,
            )  # Will be set uniformly in responses_service

            # sequence_number will be set uniformly in responses_service
            self._get_add_output_index(message_event.id)
            messages.append(output_item_added_event)

        elif message_event.type == MessageType.MESSAGE:
            # Convert other types to ResponseOutputMessage
            add_output_message = self._convert_message_type_to_output_message(
                message_event,
            )
            add_output_message.content = []
            add_output_message.status = RunStatus.InProgress
            output_item_added_event = ResponseOutputItemAddedEvent(
                type="response.output_item.added",
                item=add_output_message,
                output_index=self._output_index,
                sequence_number=0,
            )  # Will be set uniformly in responses_service

            # sequence_number will be set uniformly in responses_service
            self._get_add_output_index(message_event.id)
            messages.append(output_item_added_event)

            if message_event.status == "completed":
                output_message = self._convert_message_type_to_output_message(
                    message_event,
                )

                if not output_message:
                    return messages

                # Generate response.output_item.done
                # corresponding responses api object
                # sequence_number will be set uniformly in responses_service
                event = ResponseOutputItemDoneEvent(
                    type="response.output_item.done",
                    item=output_message,
                    output_index=self._output_index,
                    sequence_number=0,
                )  # Will be set uniformly in responses_service
                self._output.append(output_message)
                messages.append(event)

        return messages

    def _handle_existing_message(
        self,
        message_event: Message,
    ) -> Optional[List[ResponseStreamEvent]]:
        """
        # Handle existing message, generate corresponding events
        # based on message type and status

        Args:
            message_event: Agent API Message

        Returns:
            ResponseStreamEvent or None
        """
        # Dispatch to corresponding handler functions based on message type
        if message_event.type == MessageType.MESSAGE:
            return self._handle_message_status_change(message_event)
        elif message_event.type == MessageType.FUNCTION_CALL:
            return self._handle_function_call_status_change(message_event)
        elif message_event.type == MessageType.MCP_LIST_TOOLS:
            return self._handle_mcp_list_tools_status_change(message_event)
        elif message_event.type == MessageType.MCP_TOOL_CALL:
            return self._handle_mcp_tool_call_status_change(message_event)
        elif message_event.type == MessageType.REASONING:
            return self._handle_reasoning_status_change(message_event)
        elif message_event.type == MessageType.ERROR:
            return self._handle_error_status_change(message_event)

        return None

    def _handle_message_status_change(
        self,
        message_event: Message,
    ) -> Optional[List[ResponseStreamEvent]]:
        """
        Handle MESSAGE type message status changes

        Args:
            message_event: Agent API Message

        Returns:
            ResponseStreamEvent list or None
        """
        status = getattr(message_event, "status", "completed")

        messages = []

        if status == "completed":
            output_message = self._convert_message_type_to_output_message(
                message_event,
            )

            if not output_message:
                return messages

            output_index = self._get_output_index(message_id=message_event.id)

            # Generate response.output_item.done
            # corresponding responses api object
            # sequence_number will be set uniformly in responses_service
            event = ResponseOutputItemDoneEvent(
                type="response.output_item.done",
                item=output_message,
                output_index=output_index,
                sequence_number=0,
            )  # Will be set uniformly in responses_service
            self._output.append(output_message)
            messages.append(event)

        return messages

    def _handle_function_call_status_change(
        self,
        message_event: Message,
    ) -> Optional[List[ResponseStreamEvent]]:
        """
        Handle FUNCTION_CALL type message status changes

        Args:
            message_event: Agent API Message

        Returns:
            ResponseStreamEvent list or None
        """
        status = getattr(message_event, "status", "completed")

        if status == "completed":
            messages = []
            output_message = None

            output_message = self._convert_function_call_to_output_message(
                message_event,
            )

            if not output_message:
                return messages

            output_index = self._get_output_index(message_id=message_event.id)

            # Generate response.output_item.done
            # corresponding responses api object
            # sequence_number will be set uniformly in responses_service
            event = ResponseOutputItemDoneEvent(
                type="response.output_item.done",
                item=output_message,
                output_index=output_index,
                sequence_number=0,
            )  # Will be set uniformly in responses_service
            messages.append(event)
            self._output.append(output_message)
            return messages

        return None

    def _handle_mcp_list_tools_status_change(
        self,
        message_event: Message,
    ) -> Optional[List[ResponseStreamEvent]]:
        """
        Handle MCP_LIST_TOOLS type message status changes

        Args:
            message_event: Agent API Message

        Returns:
            ResponseStreamEvent list or None
        """
        status = getattr(message_event, "status", "completed")
        events = []

        # Get output_index
        output_index = self._get_output_index(message_event.id)

        if status == "in_progress":
            event = self._create_mcp_list_tools_in_progress_event(
                message_event,
                output_index,
            )
            if event:
                events.append(event)
        elif status == "completed":
            completed_events = self._create_mcp_list_tools_completed_event(
                message_event,
                output_index,
            )
            if completed_events:
                events.extend(completed_events)
        elif status == "failed":
            error_message = "MCP list tools operation failed"
            error_event = self._create_error_event(
                error_message=error_message,
            )
            if error_event:
                events.append(error_event)

        return events if events else None

    def _handle_mcp_tool_call_status_change(
        self,
        message_event: Message,
    ) -> Optional[List[ResponseStreamEvent]]:
        """
        Handle MCP_TOOL_CALL type message status changes

        Args:
            message_event: Agent API Message

        Returns:
            ResponseStreamEvent list or None
        """
        status = getattr(message_event, "status", "completed")
        events = []

        # Get output_index
        output_index = self._get_output_index(message_event.id)

        if status == "in_progress":
            event = self._create_mcp_tool_call_in_progress_event(
                message_event,
                output_index,
            )
            if event:
                events.append(event)
        elif status == "completed":
            completed_events = self._create_mcp_tool_call_completed_event(
                message_event,
                output_index,
            )
            if completed_events:
                events.extend(completed_events)
        elif status == "failed":
            error_message = "MCP tool call operation failed"
            error_event = self._create_error_event(
                error_message=error_message,
            )
            if error_event:
                events.append(error_event)

        return events if events else None

    def _handle_reasoning_status_change(
        self,
        message_event: Message,
    ) -> Optional[List[ResponseStreamEvent]]:
        """
        Handle REASONING type message status changes

        Args:
            message_event: Agent API Message

        Returns:
            ResponseStreamEvent list or None
        """
        status = getattr(message_event, "status", "completed")

        if status == "completed":
            messages = []

            output_message = self._convert_reasoning_to_output_message(
                message_event,
            )

            if not output_message:
                return messages

                # Generate response.output_item.done
                # corresponding responses api object
            # sequence_number will be set uniformly in responses_service
            event = ResponseOutputItemDoneEvent(
                type="response.output_item.done",
                item=output_message,
                output_index=self._output_index,
                sequence_number=0,
            )  # Will be set uniformly in responses_service
            messages.append(event)
            self._output.append(output_message)
            return messages

        return None

    def _handle_error_status_change(
        self,
        message_event: Message,
    ) -> Optional[List[ResponseStreamEvent]]:
        """
        Handle ERROR type message status changes

        Args:
            message_event: Agent API Message

        Returns:
            ResponseStreamEvent list or None
        """
        status = getattr(message_event, "status", "completed")

        if status == "completed":
            messages = []

            output_message = self._convert_error_to_output_message(
                message_event,
            )

            if not output_message:
                return messages

                # Generate response.output_item.done
                # corresponding responses api object
            # sequence_number will be set uniformly in responses_service
            event = ResponseOutputItemDoneEvent(
                type="response.output_item.done",
                item=output_message,
                output_index=self._output_index,
                sequence_number=0,
            )  # Will be set uniformly in responses_service
            messages.append(event)
            return messages

        return None

    def _convert_message_type_to_output_message(
        self,
        message: Message,
    ) -> ResponseOutputMessage:
        """
        Convert normal message type to ResponseOutputMessage

        Args:
            message: Agent API Message (type='message')

        Returns:
            ResponseOutputMessage: Responses API output message
        """
        # Convert content
        output_content = []
        if message.content:
            for content_item in message.content:
                if content_item.type == ContentType.TEXT:
                    output_text = ResponseOutputText(
                        type="output_text",
                        text=content_item.text,
                        annotations=[],
                    )
                    output_content.append(output_text)
                elif content_item.type == ContentType.REFUSAL:
                    # Handle REFUSAL type
                    refusal_text = getattr(content_item, "refusal", "")
                    output_refusal = ResponseOutputRefusal(
                        type="refusal",
                        refusal=refusal_text,
                    )
                    output_content.append(output_refusal)

        return self._create_base_output_message(message, output_content)

    def _convert_function_call_to_output_message(
        self,
        message: Message,
    ) -> ResponseFunctionToolCall:
        """
        Convert function_call type to ResponseFunctionToolCall

        Args:
            message: Agent API Message (type='function_call')

        Returns:
            ResponseFunctionToolCall: Responses API function tool call
        """
        # Convert function call data
        function_call_data = {}
        if message.content:
            for content_item in message.content:
                if content_item.type == ContentType.DATA:
                    function_call_data = content_item.data
                    break

        if not isinstance(function_call_data, dict):
            function_call_data = {}

        # Create ResponseFunctionToolCall
        return ResponseFunctionToolCall(
            id=message.id,
            type="function_call",
            name=function_call_data.get("name", ""),
            arguments=function_call_data.get("arguments", ""),
            call_id=function_call_data.get("call_id", ""),
            status=message.status,
        )

    def _convert_reasoning_to_output_message(
        self,
        message: Message,
    ) -> ResponseReasoningItem:
        """
        Convert reasoning type to ResponseReasoningItem

        Args:
            message: Agent API Message (type='reasoning')

        Returns:
            ResponseReasoningItem: Responses API reasoning item
        """
        # Extract reasoning text content from message content
        reasoning_text = ""
        if message.content:
            for content_item in message.content:
                if content_item.type == ContentType.TEXT:
                    reasoning_text = content_item.text
                    break

        # Create ResponseReasoningItem
        return ResponseReasoningItem(
            type="reasoning",
            id=message.id,
            summary=[],  # Empty summary
            content=(
                [ReasoningContent(type="reasoning_text", text=reasoning_text)]
                if reasoning_text
                else None
            ),
            encrypted_content=None,
            status=None,
        )

    def _convert_error_to_output_message(
        self,
        message: Message,
    ) -> ResponseOutputMessage:
        """
        Convert error type to ResponseOutputMessage

        Args:
            message: Agent API Message (type='error')

        Returns:
            ResponseOutputMessage: Responses API output message
        """
        # Convert error data to text content
        output_content = []
        if message.content:
            for content_item in message.content:
                if content_item.type == ContentType.TEXT:
                    # Convert error text content to ResponseOutputText
                    error_text = content_item.text
                    if error_text:
                        output_text_obj = ResponseOutputText(
                            type="output_text",
                            text=error_text,
                            annotations=[],
                        )
                        output_content.append(output_text_obj)
                elif content_item.type == ContentType.DATA:
                    # Handle error data content
                    error_data = content_item.data
                    if isinstance(error_data, dict):
                        error_message = error_data.get(
                            "message",
                            str(error_data),
                        )
                        if error_message:
                            output_text_obj = ResponseOutputText(
                                type="output_text",
                                text=error_message,
                                annotations=[],
                            )
                            output_content.append(output_text_obj)

        return self._create_base_output_message(message, output_content)

    def _create_base_output_message(
        self,
        message: Message,
        content: List,
    ) -> ResponseOutputMessage:
        """
        Create base ResponseOutputMessage object

        Args:
            message: Agent API Message
            content: Converted content list

        Returns:
            ResponseOutputMessage: Responses API output message
        """
        # Determine status
        status = "completed"  # Default status
        if hasattr(message, "status") and message.status:
            # Map Agent API status to Responses API status
            if message.status in ["in_progress", "completed", "incomplete"]:
                status = message.status
            else:
                status = "completed"  # Other statuses default to completed

        return ResponseOutputMessage(
            id=message.id,
            type="message",
            role="assistant",
            content=content,
            status=status,
        )

    def _convert_content_to_responses_event(
        self,
        content_event,
    ) -> Optional[ResponseStreamEvent]:
        """
        Convert content message type to Responses API stream event

        Args:
            content_event: Agent API Content

        Returns:
            ResponseStreamEvent or None
        """
        message_id = getattr(content_event, "msg_id", None)
        if not message_id:
            return None

        # Query corresponding message id from temporary storage structure
        # If message id doesn't exist, indicates abnormal situation,
        # should not process this content
        if message_id not in self._message_content_index_map:
            # Abnormal situation: message corresponding to
            # content event doesn't exist
            # This usually indicates message processing order issue,
            # directly return None
            return None

        # Get message information
        message_info = self._message_content_index_map[message_id]
        message_type = message_info["message_type"]

        # plugin calls need special adaptation, streaming not supported
        if message_type in [
            MessageType.PLUGIN_CALL,
            MessageType.PLUGIN_CALL_OUTPUT,
        ]:
            return None

        content_indexes = message_info["content_index_list"]
        output_index = message_info["output_index"]

        # Check if corresponding index already exists
        # (need to determine index based on content)
        content_index = content_event.index

        new_content = content_index not in content_indexes

        # If not, insert
        if new_content:
            content_indexes.append(content_index)

        # Perform different content adaptation based on message type
        message_type = message_info["message_type"]
        if message_type == MessageType.MESSAGE:
            events = self._convert_message_content_to_responses_event(
                content_event,
                new_content,
                output_index,
            )
            return events if events else None
        elif message_type == MessageType.FUNCTION_CALL:
            events = self._convert_function_call_content_to_responses_event(
                content_event,
                new_content,
                output_index,
            )
            return events if events else None
        elif message_type == MessageType.REASONING:
            events = self._convert_reasoning_content_to_responses_event(
                content_event=content_event,
                output_index=output_index,
            )
            return events if events else None
        elif message_type == MessageType.ERROR:
            events = self._convert_error_content_to_responses_event(
                content_event=content_event,
                new_content=new_content,
            )
            return events if events else None

        return None

    def convert_response_to_agent_events(
        self,
        response: Response,
    ) -> List[Event]:
        """
        Convert OpenAI Response object to Agent API Event list

        Args:
            response: OpenAI Response object

        Returns:
            Agent API Event list
        """
        events = []

        # Reset sequence counter
        self.sequence_counter = 0

        # Create response created event
        response_created = BaseResponse(
            sequence_number=0,  # Will be set uniformly in responses_service
            object="response",
            status="created",
            error=None,
        )
        events.append(response_created)

        # Process output items
        for output_item in response.output:
            if output_item.type == "message":
                # Convert to Agent API Message and Content events
                message_events = self._convert_output_message_to_events(
                    output_item,
                )
                events.extend(message_events)

        # Create response completed event
        response_completed = BaseResponse(
            sequence_number=0,  # Will be set uniformly in responses_service
            object="response",
            status="completed",
            error=None,
        )
        events.append(response_completed)

        return events

    def _convert_output_message_to_events(self, output_message) -> List[Event]:
        """Convert OutputMessage to Agent API events"""
        events = []

        # Create message in progress event
        message_id = f"msg_{uuid.uuid4().hex[:8]}"
        message_event = Message(
            sequence_number=0,  # Will be set uniformly in responses_service
            object="message",
            status="in_progress",
            error=None,
            id=message_id,
            type=MessageType.MESSAGE,
            role=Role.ASSISTANT,
        )
        events.append(message_event)

        # Process content items
        for content_item in output_message.content:
            if content_item.type == "output_text":
                # Create text content events
                text_content = TextContent(
                    sequence_number=0,
                    # Will be set uniformly in responses_service
                    object="content",
                    status="completed",
                    error=None,
                    type=ContentType.TEXT,
                    msg_id=message_id,
                    delta=False,
                    text=content_item.text,
                )
                events.append(text_content)

        # Create message completed event
        message_completed = Message(
            sequence_number=0,  # Will be set uniformly in responses_service
            object="message",
            status="completed",
            error=None,
            id=message_id,
            type=MessageType.MESSAGE,
            role=Role.ASSISTANT,
        )
        events.append(message_completed)

        return events

    def _convert_custom_tool_call_to_message(self, tool_call_item) -> Message:
        """Convert Custom tool call to Agent API Message"""

        # Extract tool call attributes
        if isinstance(tool_call_item, dict):
            call_id = tool_call_item.get("call_id", "")
            name = tool_call_item.get("name", "")
            input_data = tool_call_item.get("input", "")
            tool_id = tool_call_item.get("id", "")
        else:
            call_id = getattr(tool_call_item, "call_id", "")
            name = getattr(tool_call_item, "name", "")
            input_data = getattr(tool_call_item, "input", "")
            tool_id = getattr(tool_call_item, "id", "")

        # Create DataContent containing tool call data
        tool_call_data = {
            "call_id": call_id,
            "name": name,
            "input": input_data,
            "id": tool_id,
        }

        data_content = DataContent(
            type=ContentType.DATA,
            data=tool_call_data,
            delta=False,
        )

        # Create Message
        message = Message(type=MessageType.PLUGIN_CALL, content=[data_content])

        return message

    def _convert_custom_tool_call_output_to_message(
        self,
        tool_output_item,
    ) -> Message:
        """Convert Custom tool call output to Agent API Message"""

        # Extract tool call output attributes
        if isinstance(tool_output_item, dict):
            call_id = tool_output_item.get("call_id", "")
            output = tool_output_item.get("output", "")
            output_id = tool_output_item.get("id", "")
        else:
            call_id = getattr(tool_output_item, "call_id", "")
            output = getattr(tool_output_item, "output", "")
            output_id = getattr(tool_output_item, "id", "")

        # Create DataContent containing tool call output data
        tool_output_data = {
            "call_id": call_id,
            "output": output,
            "id": output_id,
        }

        data_content = DataContent(
            type=ContentType.DATA,
            data=tool_output_data,
            delta=False,
        )

        # Create Message
        message = Message(
            type=MessageType.PLUGIN_CALL_OUTPUT,
            content=[data_content],
        )

        return message

    def _convert_function_call_to_message(self, function_call_item) -> Message:
        """Convert Function tool call to Agent API Message"""

        # Extract function call attributes
        if isinstance(function_call_item, dict):
            name = function_call_item.get("name", "")
            arguments = function_call_item.get("arguments", "")
            call_id = function_call_item.get("call_id", "")
        else:
            name = getattr(function_call_item, "name", "")
            arguments = getattr(function_call_item, "arguments", "")
            call_id = getattr(function_call_item, "call_id", "")

        # Create DataContent containing function call data
        function_call_data = ToolCall.model_validate(
            {
                "name": name,
                "arguments": arguments,
                "call_id": call_id,
            },
        ).model_dump()

        data_content = DataContent(
            type=ContentType.DATA,
            data=function_call_data,
        )

        # Create Message
        message = Message(
            type=MessageType.FUNCTION_CALL,
            content=[data_content],
        )

        return message

    def _convert_function_call_output_to_message(
        self,
        function_output_item,
    ) -> Message:
        """Convert Function tool call output to Agent API Message"""

        # Extract function call output attributes
        if isinstance(function_output_item, dict):
            call_id = function_output_item.get("call_id", "")
            output = function_output_item.get("output", "")
        else:
            call_id = getattr(function_output_item, "call_id", "")
            output = getattr(function_output_item, "output", "")

        # Create DataContent containing function call output data
        function_output_data = ToolCallOutput.model_validate(
            {
                "call_id": call_id,
                "output": output,
            },
        ).model_dump()

        data_content = DataContent(
            type=ContentType.DATA,
            data=function_output_data,
        )

        # Create Message
        message = Message(
            type=MessageType.FUNCTION_CALL_OUTPUT,
            content=[data_content],
        )

        return message

    # ===== Content adaptation methods =====

    def _convert_message_content_to_responses_event(
        self,
        content_event,
        new_content: bool,
        output_index: int = 0,
    ) -> Optional[ResponseStreamEvent]:
        """
        Convert MESSAGE type content to Responses API events

        Args:
            content_event: Agent API Content event
            new_content: whether it is new content

        Returns:
            ResponseStreamEvent or None
        """
        events = []

        # Determine event type based on content type
        content_type = getattr(content_event, "type", None)
        content_status = getattr(content_event, "status", None)

        if content_type == ContentType.TEXT:
            # If content is new, generate a response.content_part.added event
            if new_content:
                content_add_event = self._create_content_part_added_event(
                    content_event,
                    output_index,
                )
                events.append(content_add_event)

            # If content is completed, generate a
            # response.content_part.done event
            if content_status == "completed":
                output_text_done_event = self._create_output_text_done_event(
                    content_event,
                    output_index,
                )
                events.append(output_text_done_event)
                content_done_event = self._create_content_part_done_event(
                    content_event,
                    output_index,
                )
                events.append(content_done_event)

            if content_status == "in_progress":
                content_in_progress_event = self._create_text_delta_event(
                    content_event,
                    output_index,
                )
                events.append(content_in_progress_event)

        if content_type == ContentType.REFUSAL:
            if new_content:
                content_add_event = self._create_content_part_added_event(
                    content_event,
                    output_index,
                )
                events.append(content_add_event)

            if content_status == "completed":
                output_text_done_event = self._create_refusal_text_done_event(
                    content_event,
                    output_index,
                )
                events.append(output_text_done_event)
                content_done_event = self._create_content_part_done_event(
                    content_event,
                    output_index,
                )
                events.append(content_done_event)

            if content_status == "in_progress":
                content_in_progress_event = (
                    self._create_refusal_text_delta_event(
                        content_event,
                        output_index,
                    )
                )
                events.append(content_in_progress_event)

        return events

    def _convert_function_call_content_to_responses_event(
        self,
        content_event,
        new_content: bool,
        output_index: int = 0,
    ) -> Optional[ResponseStreamEvent]:
        """
        Convert FUNCTION_CALL type content to Responses API events

        Args:
            content_event: Agent API Content event
            new_content: whether it is new content

        Returns:
            ResponseStreamEvent or None
        """
        events = []

        # Get content type and status
        content_type = getattr(content_event, "type", None)
        content_status = getattr(content_event, "status", None)

        if content_type == ContentType.DATA:
            if new_content:
                add_event = (
                    self._create_function_call_arguments_add_output_item_event(
                        content_event=content_event,
                        output_index=output_index,
                    )
                )
                events.append(add_event)

            # Extract function call information from data
            function = getattr(content_event, "data", {})
            if isinstance(function, dict):
                arguments = function.get("arguments", "")

                # Generate function_call_arguments.delta event
                if content_status == "in_progress":
                    delta_event = (
                        self._create_function_call_arguments_delta_event(
                            content_event,
                            arguments,
                            output_index,
                        )
                    )
                    events.append(delta_event)

                if content_status == "completed":
                    done_event = (
                        self._create_function_call_arguments_done_event(
                            content_event,
                            arguments,
                            output_index,
                        )
                    )
                    events.append(done_event)

        return events if events else None

    def _convert_reasoning_content_to_responses_event(
        self,
        content_event,
        output_index: int = 0,
    ) -> Optional[ResponseStreamEvent]:
        """
        Convert REASONING type content to Responses API events

        Args:
            content_event: Agent API Content event
            new_content: whether it is new content
            output_index: output index

        Returns:
            ResponseStreamEvent or None
        """
        events = []

        # Get content type and status
        content_type = getattr(content_event, "type", None)
        content_status = getattr(content_event, "status", None)

        if content_type == ContentType.TEXT:
            # Extract reasoning content from text
            reasoning_text = getattr(content_event, "text", "")

            # Generate reasoning_text.delta event
            if content_status == "in_progress":
                delta_event = self._create_reasoning_text_delta_event(
                    content_event,
                    reasoning_text,
                    output_index,
                )
                events.append(delta_event)

            if content_status == "completed":
                # First generate delta event, then generate done event
                delta_event = self._create_reasoning_text_delta_event(
                    content_event,
                    reasoning_text,
                    output_index,
                )
                events.append(delta_event)
                done_event = self._create_reasoning_text_done_event(
                    content_event,
                    reasoning_text,
                    output_index,
                )
                events.append(done_event)

        return events if events else None

    def _convert_error_content_to_responses_event(
        self,
        content_event,
        new_content: bool,
    ) -> Optional[ResponseStreamEvent]:
        """
        Convert ERROR type content to Responses API events

        Args:
            content_event: Agent API Content event
            new_content: whether it is new content

        Returns:
            ResponseStreamEvent or None
        """
        events = []

        # Get content type and status
        content_type = getattr(content_event, "type", None)
        content_status = getattr(content_event, "status", None)

        if content_type == ContentType.TEXT:
            # Extract error message from text
            error_text = getattr(content_event, "text", "")

            if new_content and content_status == "completed":
                # Generate error event
                error_event = self._create_error_event(
                    error_message=error_text,
                )
                events.append(error_event)
        elif content_type == ContentType.DATA:
            # Extract error information from data
            data = getattr(content_event, "data", {})
            if isinstance(data, dict):
                error_message = data.get("message", str(data))

                if new_content and content_status == "completed":
                    # Generate error event
                    error_event = self._create_error_event(
                        error_message=error_message,
                    )
                    events.append(error_event)

        return events if events else None

    def _create_content_part_added_event(
        self,
        content_event: Content,
        output_index: int = 0,
    ) -> ResponseStreamEvent:
        """
        Create response.content_part.added event

        Args:
            content_event: Agent API Content event

        Returns:
            ResponseStreamEvent: Responses API event
        """
        # Create corresponding part based on content type
        content_type = getattr(content_event, "type", None)

        if content_type == ContentType.TEXT:
            part = ResponseOutputText(
                type="output_text",
                text="",
                annotations=[],
            )
        elif content_type == ContentType.REFUSAL:
            part = ResponseOutputRefusal(type="refusal", refusal="")
        else:
            # Default to text type
            part = ResponseOutputText(
                type="output_text",
                text=getattr(content_event, "text", ""),
                annotations=[],
            )

        # Generate response.content_part.added structure
        # sequence_number will be set uniformly in responses_service
        return ResponseContentPartAddedEvent(
            type="response.content_part.added",
            content_index=content_event.index,
            item_id=content_event.msg_id,
            output_index=output_index,
            part=part,
            sequence_number=0,
        )  # Will be set uniformly in responses_service

    def _create_content_part_done_event(
        self,
        content_event: Content,
        output_index: int = 0,
    ) -> ResponseStreamEvent:
        """
        Create response.content_part.done event

        Args:
            content_event: Agent API Content event

        Returns:
            ResponseStreamEvent: Responses API event
        """
        # Create corresponding part based on content type
        content_type = getattr(content_event, "type", None)

        if content_type == ContentType.TEXT:
            part = ResponseOutputText(
                type="output_text",
                text=getattr(content_event, "text", ""),
                annotations=[],
            )
        elif content_type == ContentType.REFUSAL:
            part = ResponseOutputRefusal(
                type="refusal",
                refusal=getattr(
                    content_event,
                    "refusal",
                    "",
                ),
            )
        else:
            # Default to text type
            part = ResponseOutputText(
                type="output_text",
                text=getattr(content_event, "text", ""),
                annotations=[],
            )

        # Generate response.content_part.done structure
        # sequence_number will be set uniformly in responses_service
        return ResponseContentPartDoneEvent(
            type="response.content_part.done",
            content_index=content_event.index,
            item_id=content_event.msg_id,
            output_index=output_index,
            part=part,
            sequence_number=0,
        )  # Will be set uniformly in responses_service

    def _create_output_text_done_event(
        self,
        content_event: Content,
        output_index: int = 0,
    ) -> ResponseStreamEvent:
        """
        Create response.output_text.done event

        Args:
            content_event: Agent API Content event

        Returns:
            ResponseStreamEvent: Responses API event
        """
        # Generate response.output_text.done structure
        # sequence_number will be set uniformly in responses_service
        return ResponseTextDoneEvent(
            type="response.output_text.done",
            content_index=content_event.index,
            item_id=content_event.msg_id,
            output_index=output_index,
            text=getattr(content_event, "text", ""),
            logprobs=[],
            # Temporarily use empty list, can add logprobs support later
            sequence_number=0,
        )  # Will be set uniformly in responses_service

    def _create_text_delta_event(
        self,
        content_event: Content,
        output_index: int = 0,
    ) -> ResponseStreamEvent:
        """
        Create response.output_text.delta event

        Args:
            content_event: Agent API Content event

        Returns:
            ResponseStreamEvent: Responses API event
        """
        # Generate response.output_text.delta structure
        # sequence_number will be set uniformly in responses_service
        return ResponseTextDeltaEvent(
            type="response.output_text.delta",
            content_index=content_event.index,
            item_id=content_event.msg_id,
            output_index=output_index,
            delta=getattr(content_event, "text", ""),
            logprobs=[],
            # Temporarily use empty list, can add logprobs support later
            sequence_number=0,
        )  # Will be set uniformly in responses_service

    def _create_refusal_text_done_event(
        self,
        content_event: Content,
        output_index: int = 0,
    ) -> ResponseStreamEvent:
        """
        Create response.refusal.done event

        Args:
            content_event: Agent API Content event

        Returns:
            ResponseStreamEvent: Responses API event
        """
        # Generate response.refusal.done structure
        # sequence_number will be set uniformly in responses_service
        return ResponseRefusalDoneEvent(
            type="response.refusal.done",
            content_index=content_event.index,
            item_id=content_event.msg_id,
            output_index=output_index,
            refusal=getattr(content_event, "refusal", ""),
            sequence_number=0,
        )  # Will be set uniformly in responses_service

    def _create_refusal_text_delta_event(
        self,
        content_event: Content,
        output_index: int = 0,
    ) -> ResponseStreamEvent:
        """
        Create response.refusal.delta event

        Args:
            content_event: Agent API Content event

        Returns:
            ResponseStreamEvent: Responses API event
        """
        # Generate response.refusal.delta structure
        # sequence_number will be set uniformly in responses_service
        return ResponseRefusalDeltaEvent(
            type="response.refusal.delta",
            content_index=content_event.index,
            item_id=content_event.msg_id,
            output_index=output_index,
            delta=getattr(content_event, "refusal", ""),
            sequence_number=0,
        )  # Will be set uniformly in responses_service

    def _next_sequence(self) -> int:
        """Get next sequence number"""
        current = self.sequence_counter
        # sequence_number will be set uniformly in responses_service
        return current

    # ===== New event creation methods =====

    def _create_function_call_arguments_add_output_item_event(
        self,
        content_event,
        output_index: int = 0,
    ) -> ResponseStreamEvent:
        """
        Create function call corresponding response.output_item.added event

        Args:
            content_event: Agent API Content event
            arguments: function call parameters
            output_index: output index

        Returns:
            ResponseStreamEvent: Responses API event
        """

        # Convert function call data
        function_call_data = {}
        if content_event:
            if content_event.type == ContentType.DATA:
                function_call_data = content_event.data

        if not isinstance(function_call_data, dict):
            function_call_data = {}

        # Create ResponseFunctionToolCall
        function_tool_call = ResponseFunctionToolCall(
            type="function_call",
            name=function_call_data.get("name", ""),
            arguments="",
            call_id=function_call_data.get("call_id", ""),
            status=content_event.status,
        )

        return ResponseOutputItemAddedEvent(
            type="response.output_item.added",
            item=function_tool_call,
            output_index=output_index,
            sequence_number=0,
        )  # Will be set uniformly in responses_service

    def _create_function_call_arguments_delta_event(
        self,
        content_event,
        arguments: str,
        output_index: int = 0,
    ) -> ResponseStreamEvent:
        """
        Create response.function_call_arguments.delta event

        Args:
            content_event: Agent API Content event
            arguments: function call parameters
            output_index: output index

        Returns:
            ResponseStreamEvent: Responses API event
        """
        # sequence_number will be set uniformly in responses_service
        return ResponseFunctionCallArgumentsDeltaEvent(
            type="response.function_call_arguments.delta",
            delta=arguments,
            item_id=content_event.msg_id,
            output_index=output_index,
            sequence_number=0,
        )  # Will be set uniformly in responses_service

    def _create_function_call_arguments_done_event(
        self,
        content_event,
        arguments: str,
        output_index: int = 0,
    ) -> ResponseStreamEvent:
        """
        Create response.function_call_arguments.done event

        Args:
            content_event: Agent API Content event
            arguments: function call parameters
            output_index: output index

        Returns:
            ResponseStreamEvent: Responses API event
        """
        # sequence_number will be set uniformly in responses_service
        return ResponseFunctionCallArgumentsDoneEvent(
            type="response.function_call_arguments.done",
            arguments=arguments,
            item_id=content_event.msg_id,
            output_index=output_index,
            sequence_number=0,
        )  # Will be set uniformly in responses_service

    def _create_reasoning_text_delta_event(
        self,
        content_event,
        text: str,
        output_index: int = 0,
    ) -> ResponseStreamEvent:
        """
        Create response.reasoning_text.delta event

        Args:
            content_event: Agent API Content event
            text: reasoning text content
            output_index: output index

        Returns:
            ResponseStreamEvent: Responses API event
        """
        # sequence_number will be set uniformly in responses_service
        return ResponseReasoningTextDeltaEvent(
            type="response.reasoning_text.delta",
            content_index=content_event.index,
            delta=text,
            item_id=content_event.msg_id,
            output_index=output_index,
            sequence_number=0,
        )  # Will be set uniformly in responses_service

    def _create_reasoning_text_done_event(
        self,
        content_event,
        text: str,
        output_index: int = 0,
    ) -> ResponseStreamEvent:
        """
        Create response.reasoning_text.done event

        Args:
            content_event: Agent API Content event
            text: reasoning text content
            output_index: output index

        Returns:
            ResponseStreamEvent: Responses API event
        """
        # sequence_number will be set uniformly in responses_service
        return ResponseReasoningTextDoneEvent(
            type="response.reasoning_text.done",
            content_index=content_event.index,
            text=text,
            item_id=content_event.msg_id,
            output_index=output_index,
            sequence_number=0,
        )  # Will be set uniformly in responses_service

    def _convert_agent_error_to_responses_error(
        self,
        agent_error,
    ) -> Optional[Any]:
        """
        Convert Agent API Error to Responses API ResponseError

        Args:
            agent_error: Agent API Error object

        Returns:
            ResponseError: Responses API ResponseError or None
        """
        if not agent_error:
            return None

        try:
            # Extract error information from Agent API Error object
            error_code = getattr(agent_error, "code", "server_error")
            error_message = getattr(
                agent_error,
                "message",
                "Unknown error occurred",
            )

            # Map Agent API error code to Responses API error code
            # If Agent API code is not in Responses API allowed range,
            # use server_error as default
            valid_codes = [
                "server_error",
                "rate_limit_exceeded",
                "invalid_prompt",
                "vector_store_timeout",
                "invalid_image",
                "invalid_image_format",
                "invalid_base64_image",
                "invalid_image_url",
                "image_too_large",
                "image_too_small",
                "image_parse_error",
                "image_content_policy_violation",
                "invalid_image_mode",
                "image_file_too_large",
                "unsupported_image_media_type",
                "empty_image_file",
                "failed_to_download_image",
                "image_file_not_found",
            ]

            # If Agent API code is in valid range, use directly;
            # otherwise use server_error
            mapped_code = (
                error_code if error_code in valid_codes else "server_error"
            )

            # Create Responses API ResponseError
            from openai.types.responses import ResponseError

            return ResponseError(code=mapped_code, message=error_message)
        except Exception as e:
            # If conversion fails, log error and return None
            print(f"Error converting agent error to responses error: {e}")
            return None

    def _create_error_event(
        self,
        error_message: str,
    ) -> ResponseStreamEvent:
        """
        Create error event

        Args:
            content_event: Agent API Content event
            error_message: error message
            output_index: output index

        Returns:
            ResponseStreamEvent: Responses API event
        """
        # sequence_number will be set uniformly in responses_service
        return ResponseErrorEvent(
            type="error",
            message=error_message,
            sequence_number=0,
        )  # Will be set uniformly in responses_service

    def _create_function_call_item_added_event(
        self,
        content_event,
        output_index: int = 0,
    ) -> ResponseStreamEvent:
        """
        Create function_call type response.output_item.added event

        Args:
            content_event: Agent API Content event
            output_index: output index

        Returns:
            ResponseStreamEvent: Responses API event
        """
        # Extract function call information from data
        data = getattr(content_event, "data", {})
        name = data.get("name", "")
        arguments = data.get("arguments", "")
        call_id = data.get("call_id", "")

        # Create ResponseFunctionToolCall as item
        item = ResponseFunctionToolCall(
            type="function_call",
            name=name,
            arguments=arguments,
            call_id=call_id,
            id=data.get("id"),
            status=data.get("status"),
        )

        # Generate response.output_item.added structure
        # sequence_number will be set uniformly in responses_service
        return ResponseOutputItemAddedEvent(
            type="response.output_item.added",
            item=item,
            output_index=output_index,
            sequence_number=0,
        )  # Will be set uniformly in responses_service

    def _create_reasoning_item_added_event(
        self,
        content_event,
        output_index: int = 0,
    ) -> ResponseStreamEvent:
        """
        Create reasoning type response.output_item.added event

        Args:
            content_event: Agent API Content event
            output_index: output index

        Returns:
            ResponseStreamEvent: Responses API event
        """
        # Extract reasoning content from text
        reasoning_text = getattr(content_event, "text", "")

        # Create ResponseReasoningItem as item
        item = ResponseReasoningItem(
            type="reasoning",
            id=content_event.msg_id,
            summary=[],  # Empty summary
            content=(
                [Content(type="reasoning_text", text=reasoning_text)]
                if reasoning_text
                else None
            ),
            encrypted_content=None,
            status=None,
        )

        # Generate response.output_item.added structure
        # sequence_number will be set uniformly in responses_service
        return ResponseOutputItemAddedEvent(
            type="response.output_item.added",
            item=item,
            output_index=output_index,
            sequence_number=0,
        )  # Will be set uniformly in responses_service

    def _convert_mcp_list_tools_to_output_message(
        self,
        message: Message,
    ) -> McpListTools:
        """
        Convert MCP tool list message to McpListTools

        Args:
            message: Agent API Message (type='mcp_list_tools')

        Returns:
            McpListTools: Responses API MCP tool list
        """
        # Convert MCP tool list data
        mcp_data = {}
        if message.content:
            for content_item in message.content:
                if content_item.type == ContentType.DATA:
                    mcp_data = content_item.data
                    break

        if not isinstance(mcp_data, dict):
            mcp_data = {}

        # Extract tool list information
        tools_info = mcp_data.get("tools", [])
        tools = []
        for tool_info in tools_info:
            if isinstance(tool_info, dict):
                tool = McpListToolsTool(
                    name=tool_info.get("name", "unknown"),
                    input_schema=tool_info.get("input_schema", {}),
                    description=tool_info.get("description", ""),
                    annotations=tool_info.get("annotations"),
                )
                tools.append(tool)

        # Create McpListTools
        return McpListTools(
            id=message.id,
            server_label=mcp_data.get("server_label", "MCP Server"),
            tools=tools,
            type="mcp_list_tools",
        )

    def _convert_mcp_tool_call_to_output_message(
        self,
        message: Message,
    ) -> McpCall:
        """
        Convert MCP tool call message to McpCall

        Args:
            message: Agent API Message (type='mcp_call')

        Returns:
            McpCall: Responses API MCP tool call
        """
        # Convert MCP tool call data
        mcp_call_data = {}
        if message.content:
            for content_item in message.content:
                if content_item.type == ContentType.DATA:
                    mcp_call_data = content_item.data
                    break

        if not isinstance(mcp_call_data, dict):
            mcp_call_data = {}

        # Extract MCP tool call information
        tool_name = mcp_call_data.get("name", "mcp_tool")
        tool_arguments = mcp_call_data.get("arguments", "{}")
        server_label = mcp_call_data.get("server_label", "MCP Server")

        # Create McpCall
        return McpCall(
            id=message.id,
            name=tool_name,
            arguments=tool_arguments,
            server_label=server_label,
            type="mcp_call",
            error=mcp_call_data.get("error"),
            output=mcp_call_data.get("output"),
        )

    def _create_mcp_list_tools_item_added_event(
        self,
        content_event,
        output_index: int = 0,
    ) -> ResponseStreamEvent:
        """
        Create MCP tool list item added event

        Args:
            content_event: Agent API Content event
            output_index: output index

        Returns:
            ResponseStreamEvent: Responses API event
        """
        # Extract MCP tool list information from data
        data = getattr(content_event, "data", {})
        if not isinstance(data, dict):
            data = {}

        # Extract tool list information
        tools_info = data.get("tools", [])
        tools = []
        for tool_info in tools_info:
            if isinstance(tool_info, dict):
                tool = McpListToolsTool(
                    name=tool_info.get("name", "unknown"),
                    input_schema=tool_info.get("input_schema", {}),
                    description=tool_info.get("description", ""),
                    annotations=tool_info.get("annotations"),
                )
                tools.append(tool)

        # Create McpListTools as item
        item = McpListTools(
            id=content_event.msg_id,
            server_label=data.get("server_label", "MCP Server"),
            tools=tools,
            type="mcp_list_tools",
        )

        # Generate response.output_item.added structure
        # sequence_number will be set uniformly in responses_service
        return ResponseOutputItemAddedEvent(
            type="response.output_item.added",
            item=item,
            output_index=output_index,
            sequence_number=0,
        )  # Will be set uniformly in responses_service

    def _create_mcp_tool_call_item_added_event(
        self,
        content_event,
        output_index: int = 0,
    ) -> ResponseStreamEvent:
        """
        Create MCP tool call item added event

        Args:
            content_event: Agent API Content event
            output_index: output index

        Returns:
            ResponseStreamEvent: Responses API event
        """
        # Extract MCP tool call information from data
        data = getattr(content_event, "data", {})
        if not isinstance(data, dict):
            data = {}

        # Extract MCP tool call information
        tool_name = data.get("name", "mcp_tool")
        tool_arguments = data.get("arguments", "{}")
        server_label = data.get("server_label", "MCP Server")

        # Create McpCall as item
        item = McpCall(
            id=content_event.msg_id,
            name=tool_name,
            arguments=tool_arguments,
            server_label=server_label,
            type="mcp_call",
            error=data.get("error"),
            output=data.get("output"),
        )

        # Generate response.output_item.added structure
        # sequence_number will be set uniformly in responses_service
        return ResponseOutputItemAddedEvent(
            type="response.output_item.added",
            item=item,
            output_index=output_index,
            sequence_number=0,
        )  # Will be set uniformly in responses_service

    def _create_mcp_list_tools_in_progress_event(
        self,
        message_event: Message,
        output_index: int = 0,
    ) -> ResponseStreamEvent:
        """
        Create MCP tool list in_progress event

        Args:
            message_event: Agent API Message event
            output_index: output index

        Returns:
            ResponseStreamEvent: Responses API event
        """
        # Generate response.mcp_list_tools.in_progress event
        # sequence_number will be set uniformly in responses_service
        return ResponseMcpListToolsInProgressEvent(
            type="response.mcp_list_tools.in_progress",
            item_id=message_event.id,
            output_index=output_index,
            sequence_number=0,
        )  # Will be set uniformly in responses_service

    def _create_mcp_list_tools_completed_event(
        self,
        message_event: Message,
        output_index: int = 0,
    ) -> List[ResponseStreamEvent]:
        """
        Create MCP tool list completed event

        Args:
            message_event: Agent API Message event
            output_index: output index

        Returns:
            List[ResponseStreamEvent]: Responses API event list
        """
        events = []

        # 1. Generate response.mcp_list_tools.completed event
        mcp_completed_event = ResponseMcpListToolsCompletedEvent(
            type="response.mcp_list_tools.completed",
            item_id=message_event.id,
            output_index=output_index,
            sequence_number=0,
        )  # Will be set uniformly in responses_service
        events.append(mcp_completed_event)

        # 2. Generate response.output_item.done event
        output_message = self._convert_mcp_list_tools_to_output_message(
            message_event,
        )
        if output_message:
            output_item_done_event = ResponseOutputItemDoneEvent(
                type="response.output_item.done",
                item=output_message,
                output_index=output_index,
                sequence_number=0,
            )  # Will be set uniformly in responses_service
            events.append(output_item_done_event)
            # Add to _output list
            self._output.append(output_message)

        return events

    def _create_mcp_tool_call_in_progress_event(
        self,
        message_event: Message,
        output_index: int = 0,
    ) -> ResponseStreamEvent:
        """
        Create MCP tool call in_progress event

        Args:
            message_event: Agent API Message event
            output_index: output index

        Returns:
            ResponseStreamEvent: Responses API event
        """
        # Generate response.mcp_call.in_progress event
        # sequence_number will be set uniformly in responses_service
        return ResponseMcpCallInProgressEvent(
            type="response.mcp_call.in_progress",
            item_id=message_event.id,
            output_index=output_index,
            sequence_number=0,
        )  # Will be set uniformly in responses_service

    def _create_mcp_tool_call_completed_event(
        self,
        message_event: Message,
        output_index: int = 0,
    ) -> List[ResponseStreamEvent]:
        """
        Create MCP tool call completed event

        Args:
            message_event: Agent API Message event
            output_index: output index

        Returns:
            List[ResponseStreamEvent]: Responses API event list
        """
        events = []

        # 1. Generate response.mcp_call.completed event
        mcp_completed_event = ResponseMcpCallCompletedEvent(
            type="response.mcp_call.completed",
            item_id=message_event.id,
            output_index=output_index,
            sequence_number=0,
        )  # Will be set uniformly in responses_service
        events.append(mcp_completed_event)

        # 2. Generate response.output_item.done event
        output_message = self._convert_mcp_tool_call_to_output_message(
            message_event,
        )
        if output_message:
            output_item_done_event = ResponseOutputItemDoneEvent(
                type="response.output_item.done",
                item=output_message,
                output_index=output_index,
                sequence_number=0,
            )  # Will be set uniformly in responses_service
            events.append(output_item_done_event)
            # Add to _output list
            self._output.append(output_message)

        return events


# Export main adapter class
__all__ = ["ResponsesAdapter"]
