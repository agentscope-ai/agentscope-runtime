# -*- coding: utf-8 -*-
"""
Agent Protocol Data Generator

Provides layered Builder pattern tools to generate streaming response data
that conforms to types/agent definitions
"""

import time
from typing import Any, Dict, Generator, List, Optional
from uuid import uuid4

from agentscope_runtime.engine.schemas.agent_schemas import (
    AgentResponse,
    AudioContent,
    Content,
    ContentType,
    DataContent,
    FileContent,
    ImageContent,
    Message,
    RefusalContent,
    Role,
    TextContent,
)


class ContentBuilder:
    """
    Content Builder

    Responsible for building and managing individual Content objects,
    supporting Text, Image, and Data content types
    """

    def __init__(
        self,
        message_builder: "MessageBuilder",
        content_type: str = ContentType.TEXT,
        index: int = 0,
    ):
        """
        Initialize Content Builder

        Args:
            message_builder: Associated MessageBuilder object
            content_type: Content type ('text', 'image', 'data')
            index: Content index, defaults to 0
        """
        self.message_builder = message_builder
        self.content_type = content_type
        self.index = index

        # Initialize corresponding data structures and content objects
        # based on Content type
        if content_type == ContentType.TEXT:
            self.text_tokens: List[str] = []
            self.content = TextContent(
                type=self.content_type,
                index=self.index,
                msg_id=self.message_builder.message.id,
            )
        elif content_type == ContentType.IMAGE:
            self.content = ImageContent(
                type=self.content_type,
                index=self.index,
                msg_id=self.message_builder.message.id,
            )
        elif content_type == ContentType.DATA:
            self.data_deltas: List[Dict[str, Any]] = []
            self.content = DataContent(
                type=self.content_type,
                index=self.index,
                msg_id=self.message_builder.message.id,
            )
        elif content_type == ContentType.REFUSAL:
            self.content = RefusalContent(
                type=self.content_type,
                index=self.index,
                msg_id=self.message_builder.message.id,
            )
        elif content_type == ContentType.FILE:
            self.content = FileContent(
                type=self.content_type,
                index=self.index,
                msg_id=self.message_builder.message.id,
            )
        elif content_type == ContentType.AUDIO:
            self.content = AudioContent(
                type=self.content_type,
                index=self.index,
                msg_id=self.message_builder.message.id,
            )
        else:
            raise ValueError(f"Unsupported content type: {content_type}")

    def add_text_delta(self, text: str) -> TextContent:
        """
        Add text delta (only applicable to text type)

        Args:
            text: Text fragment

        Returns:
            Delta content object
        """
        if self.content_type != ContentType.TEXT:
            raise ValueError("add_text_delta only supported for text content")

        self.text_tokens.append(text)

        # Create delta content
        delta_content = TextContent(
            type=self.content_type,
            index=self.index,
            delta=True,
            msg_id=self.message_builder.message.id,
            text=text,
        ).in_progress()

        return delta_content

    def set_text(self, text: str) -> TextContent:
        """
        Set complete text content (only applicable to text type)

        Args:
            text: Complete text content

        Returns:
            Content object
        """
        if self.content_type != ContentType.TEXT:
            raise ValueError("set_text only supported for text content")

        self.content.text = text
        self.content.in_progress()
        return self.content

    def set_refusal(self, text: str) -> RefusalContent:
        """
        Set complete refusal content (only applicable to refusal type)

        Args:
            text: Complete refusal content

        Returns:
            Content object
        """
        if self.content_type != ContentType.REFUSAL:
            raise ValueError("set_refusal only supported for refusal content")

        self.content.refusal = text
        self.content.in_progress()
        return self.content

    def set_image_url(self, image_url: str) -> ImageContent:
        """
        Set image URL (only applicable to image type)

        Args:
            image_url: Image URL

        Returns:
            Content object
        """
        if self.content_type != ContentType.IMAGE:
            raise ValueError("set_image_url only supported for image content")

        self.content.image_url = image_url
        self.content.in_progress()
        return self.content

    def set_data(self, data: Dict[str, Any]) -> DataContent:
        """
        Set data content (only applicable to data type)

        Args:
            data: Data dictionary

        Returns:
            Content object
        """
        if self.content_type != ContentType.DATA:
            raise ValueError("set_data only supported for data content")

        self.content.data = data
        self.content.in_progress()
        return self.content

    def update_data(self, key: str, value: Any) -> DataContent:
        """
        Update specific fields of data content (only applicable to data type)

        Args:
            key: Data key
            value: Data value

        Returns:
            Content object
        """
        if self.content_type != ContentType.DATA:
            raise ValueError("update_data only supported for data content")

        if self.content.data is None:
            self.content.data = {}
        self.content.data[key] = value
        self.content.in_progress()
        return self.content

    def add_data_delta(self, delta_data: Dict[str, Any]) -> DataContent:
        """
        Add data delta (only applicable to data type)

        Args:
            delta_data: Delta data dictionary

        Returns:
            Delta content object
        """
        if self.content_type != ContentType.DATA:
            raise ValueError("add_data_delta only supported for data content")

        self.data_deltas.append(delta_data)

        # Create delta content object
        delta_content = DataContent(
            type=self.content_type,
            index=self.index,
            delta=True,
            msg_id=self.message_builder.message.id,
            data=delta_data,
        ).in_progress()

        return delta_content

    def _merge_data_incrementally(
        self,
        base_data: Dict[str, Any],
        delta_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Intelligently merge data deltas

        Args:
            base_data: Base data
            delta_data: Delta data

        Returns:
            Merged data
        """
        result = base_data.copy() if base_data else {}

        for key, delta_value in delta_data.items():
            if key not in result:
                # New key, add directly
                result[key] = delta_value
            else:
                base_value = result[key]
                # Perform delta merge based on data type
                if isinstance(base_value, str) and isinstance(
                    delta_value,
                    str,
                ):
                    # String concatenation
                    result[key] = base_value + delta_value
                elif (
                    isinstance(base_value, (int, float))
                    and isinstance(delta_value, (int, float))
                    and not isinstance(base_value, bool)
                    and not isinstance(delta_value, bool)
                ):
                    # Numeric accumulation (excluding bool type,
                    # as bool is a subclass of int)
                    result[key] = base_value + delta_value
                elif isinstance(base_value, list) and isinstance(
                    delta_value,
                    list,
                ):
                    # List merging
                    result[key] = base_value + delta_value
                elif isinstance(base_value, dict) and isinstance(
                    delta_value,
                    dict,
                ):
                    # Dictionary recursive merging
                    result[key] = self._merge_data_incrementally(
                        base_value,
                        delta_value,
                    )
                else:
                    # Other cases directly replace (including bool,
                    # different types, etc.)
                    result[key] = delta_value

        return result

    def add_delta(self, text: str) -> TextContent:
        """
        Add text delta (backward compatibility method)

        Args:
            text: Text fragment

        Returns:
            Delta content object
        """
        return self.add_text_delta(text)

    def complete(self) -> Message:
        """
        Complete content building

        Returns:
            Dictionary representation of complete Content object
        """
        if self.content_type == ContentType.TEXT:
            # For text content, merge set text and tokens
            if hasattr(self, "text_tokens") and self.text_tokens:
                # Get existing text, if none then empty string
                existing_text = self.content.text or ""
                token_text = "".join(self.text_tokens)
                self.content.text = existing_text + token_text
            self.content.delta = False
        elif self.content_type == ContentType.DATA:
            # For data content, merge set data and delta data
            if hasattr(self, "data_deltas") and self.data_deltas:
                # Get existing data, if none then empty dictionary
                existing_data = self.content.data or {}

                # Gradually merge all delta data
                final_data = existing_data
                for delta_data in self.data_deltas:
                    final_data = self._merge_data_incrementally(
                        final_data,
                        delta_data,
                    )

                self.content.data = final_data
            self.content.delta = False

        # Set completion status
        self.content.completed()

        # Update message content list
        self.message_builder.add_content(self.content)

        return self.content

    def get_content_data(self) -> Content:
        """
        Get dictionary representation of current content

        Returns:
            Content object
        """
        return self.content


class MessageBuilder:
    """
    Message Builder

    Responsible for building and managing individual Message objects
    and updating associated Response
    """

    def __init__(
        self,
        response_builder: "ResponseBuilder",
        role: str = Role.ASSISTANT,
    ):
        """
        Initialize Message Builder

        Args:
            response_builder: Associated ResponseBuilder object
            role: Message role, defaults to assistant
        """
        self.response_builder = response_builder
        self.role = role
        self.message_id = f"msg_{uuid4()}"
        self.content_builders: List[ContentBuilder] = []

        # Create message object
        self.message = Message(
            id=self.message_id,
            role=self.role,
        ).in_progress()

        # Immediately add to response output
        self.response_builder.add_message(self.message)

    def create_content_builder(
        self,
        content_type: str = ContentType.TEXT,
    ) -> ContentBuilder:
        """
        Create Content Builder

        Args:
            content_type: Content type ('text', 'image', 'data')

        Returns:
            Newly created ContentBuilder instance
        """
        index = len(self.content_builders)
        content_builder = ContentBuilder(self, content_type, index)
        self.content_builders.append(content_builder)
        return content_builder

    def add_content(self, content: Content):
        """
        Add content to message

        Args:
            content: Content object
        """
        if self.message.content is None:
            self.message.content = []

        # Check if content with same index already exists, replace if exists
        existing_index = None
        for i, existing_content in enumerate(self.message.content):
            if (
                hasattr(existing_content, "index")
                and existing_content.index == content.index
            ):
                existing_index = i
                break

        if existing_index is not None:
            self.message.content[existing_index] = content
        else:
            self.message.content.append(content)

        # Notify response builder to update
        self.response_builder.update_message(self.message)

    def get_message_data(self) -> Message:
        """
        Get dictionary representation of current message

        Returns:
            Message object
        """
        return self.message

    def complete(self) -> Message:
        """
        Complete message building

        Returns:
            Dictionary representation of complete message object
        """
        self.message.completed()

        # Notify response builder to update
        self.response_builder.update_message(self.message)

        return self.message


class ResponseBuilder:
    """
    Response Builder

    Responsible for building and managing AgentResponse objects,
    coordinating MessageBuilder work
    """

    def __init__(
        self,
        session_id: Optional[str] = None,
        response_id: Optional[str] = None,
    ):
        """
        Initialize Response Builder

        Args:
            session_id: Session ID, optional
        """
        self.session_id = session_id
        self.response_id = response_id
        self.created_at = int(time.time())
        self.message_builders: List[MessageBuilder] = []

        # Create response object
        self.response = AgentResponse(
            id=self.response_id,
            session_id=self.session_id,
            created_at=self.created_at,
            output=[],
        )

    def reset(self):
        """
        Reset builder state, generate new ID and object instances
        """
        self.response_id = f"response_{uuid4()}"
        self.created_at = int(time.time())
        self.message_builders = []

        # Recreate response object
        self.response = AgentResponse(
            id=self.response_id,
            session_id=self.session_id,
            created_at=self.created_at,
            output=[],
        )

    def get_response_data(self) -> AgentResponse:
        """
        Get dictionary representation of current response

        Returns:
            Response object
        """
        return self.response

    def created(self) -> AgentResponse:
        """
        Set response status to created

        Returns:
            Response object
        """
        self.response.created()
        return self.response

    def in_progress(self) -> AgentResponse:
        """
        Set response status to in_progress

        Returns:
            Response object
        """
        self.response.in_progress()
        return self.response

    def completed(self) -> AgentResponse:
        """
        Set response status to completed

        Returns:
            Response object
        """
        self.response.completed()
        return self.response

    def create_message_builder(
        self,
        role: str = Role.ASSISTANT,
        message_type: str = "message",
    ) -> MessageBuilder:
        """
        Create Message Builder

        Args:
            role: Message role, defaults to assistant
            message_type: Message type, defaults to message

        Returns:
            Newly created MessageBuilder instance
        """
        message_builder = MessageBuilder(self, role)

        # Set the message type
        message_builder.message.type = message_type

        self.message_builders.append(message_builder)
        return message_builder

    def add_message(self, message: Message):
        """
        Add message to response output list

        Args:
            message: Message object
        """
        # Check if message with same ID already exists, replace if exists
        existing_index = None
        for i, existing_message in enumerate(self.response.output):
            if existing_message.id == message.id:
                existing_index = i
                break

        if existing_index is not None:
            self.response.output[existing_index] = message
        else:
            self.response.output.append(message)

    def update_message(self, message: Message):
        """
        Update message in response

        Args:
            message: Updated Message object
        """
        for i, existing_message in enumerate(self.response.output):
            if existing_message.id == message.id:
                self.response.output[i] = message
                break

    def generate_streaming_response(
        self,
        text_tokens: List[str],
        role: str = Role.ASSISTANT,
    ) -> Generator[Dict[str, Any], None, None]:
        """
        Generate complete streaming response sequence

        Args:
            text_tokens: Text fragment list
            role: Message role, defaults to assistant

        Yields:
            Dictionary of response objects generated in order
        """
        # Reset state
        self.reset()

        # 1. Create response (created)
        yield self.created()

        # 2. Start response (in_progress)
        yield self.in_progress()

        # 3. Create Message Builder
        message_builder = self.create_message_builder(role)
        yield message_builder.get_message_data()

        # 4. Create Content Builder
        content_builder = message_builder.create_content_builder()

        # 5. Stream output Text fragments
        for token in text_tokens:
            yield content_builder.add_delta(token)

        # 6. Complete content
        yield content_builder.complete()

        # 7. Complete message
        yield message_builder.complete()

        # 8. Complete response
        yield self.completed()


# For backward compatibility, provide aliases
StreamingResponseBuilder = ResponseBuilder
