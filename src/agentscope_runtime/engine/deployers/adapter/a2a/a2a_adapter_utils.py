# -*- coding: utf-8 -*-
# pylint: disable=unused-argument
from a2a.types import (
    Message as A2AMessage,
    Part,
    TextPart,
    FilePart,
    DataPart,
    Artifact,
    TaskStatus,
    TaskState,
    Task,
    TaskStatusUpdateEvent,
    TaskArtifactUpdateEvent,
    TaskQueryParams,
)

from ....schemas.agent_schemas import (
    Message as AgentMessage,
    Content,
    TextContent,
    ImageContent,
    DataContent,
    AgentRequest,
    AgentResponse,
    MessageType,
    Role,
)


# Request conversion functions
# Functions to convert A2A protocol objects to internal Agent API objects


def a2a_message_to_agent_message(msg: A2AMessage) -> AgentMessage:
    """
    Convert A2A Message object to AgentAPI Message object

    Args:
        msg (A2AMessage): A2A protocol message object

    Returns:
        AgentMessage: Converted internal Agent API message object
    """
    contents = [a2a_part_to_agent_content(part) for part in msg.parts]

    return AgentMessage(
        role=msg.role,
        content=contents,
        id=msg.message_id,
        type=MessageType.MESSAGE,
    )


def a2a_part_to_agent_content(part: Part) -> Content:
    """
    Convert A2A protocol Part object to internal Content object

    Args:
        part (Part): A2A protocol part object

    Returns:
        Content: Converted internal content object

    Raises:
        ValueError: If the part type is unknown
    """
    # Unpack RootModel if exists
    real_part = part.root if hasattr(part, "root") else part

    if isinstance(real_part, TextPart):
        return TextContent(text=real_part.text)
    elif isinstance(real_part, FilePart):
        # Assume ImageContent is equivalent to file, adjust if needed
        return ImageContent(image_url=real_part.file.uri)
    elif isinstance(real_part, DataPart):
        return DataContent(data=real_part.data)
    else:
        raise ValueError(f"Unknown part type: {type(real_part)}")


def a2a_sendparams_to_agent_request(
    params: dict,
    stream: bool,
    context_id: str = None,
) -> AgentRequest:
    """
    Convert a2a MessageSendParams to agent-api AgentRequest

    Args:
        params (dict): MessageSendParams received from a2a protocol
        stream (bool): Whether this request is in stream mode
            (/message/send = False, /message/stream = True)
        context_id (str, optional): Context ID if message is appended to
            existing conversation

    Returns:
        AgentRequest: Converted agent request object
    """
    # 1. Convert a2a 'message' to agent-api 'Message' and wrap in list
    a2a_msg = params["message"]  # a2a Message
    agent_api_msg = a2a_message_to_agent_message(
        a2a_msg,
    )  # Conversion function already implemented

    # 2. Fill AgentRequest
    req = AgentRequest(
        input=[agent_api_msg],
        stream=stream,
        session_id=context_id or None,
        # Other fields (model, top_p, temperature, tools...) can be extended
        # later
    )
    return req


def a2a_taskqueryparams_to_agent_request(
    params: "TaskQueryParams",
    session_id: str = None,
) -> "AgentRequest":
    """
    Convert TaskQueryParams to AgentRequest, only set session_id
    Other fields are controlled by AgentRequest default values

    Args:
        params (TaskQueryParams): Task query parameters from a2a protocol
        session_id (str, optional): Session ID for the request

    Returns:
        AgentRequest: Converted agent request object with only session_id set
    """
    return AgentRequest(
        session_id=session_id or "",
        # input, stream etc. use default values
        response_id=TaskQueryParams.id,
    )


# Response conversion functions
# Functions to convert internal Agent API objects to A2A protocol objects


def agent_content_to_a2a_part(content: Content) -> Part:
    """
    Convert internal Content object to A2A protocol Part object

    Args:
        content (Content): Internal content object

    Returns:
        Part: Converted A2A protocol part object

    Raises:
        ValueError: If the content type is unknown
    """

    # Dispatch conversion based on type
    if isinstance(content, TextContent):
        return Part(root=TextPart(text=content.text))
    elif isinstance(content, ImageContent):
        # Assume it's FilePart, adjust if FilePart structure is different
        return Part(root=FilePart(url=content.image_url))
    elif isinstance(content, DataContent):
        return Part(root=DataPart(data=content.data))
    else:
        raise ValueError(f"Unknown content type: {type(content)}")


def agent_message_to_a2a_artifact(msg: AgentMessage) -> Artifact:
    """
    Convert AgentAPI Message to a2a Artifact

    Args:
        msg (AgentMessage): Agent API message object

    Returns:
        Artifact: Converted A2A protocol artifact object
    """
    # When content is empty, set parts to []
    parts = [agent_content_to_a2a_part(c) for c in (msg.content or [])]

    return Artifact(
        artifact_id=msg.id,
        name=msg.type,  # Changed to type
        description=None,
        parts=parts,
        metadata=None,
        extensions=None,
    )


def runstatus_to_a2a_taskstate(status: str) -> TaskState:
    """
    Map Internal RunStatus to a2a TaskState

    Args:
        status (str): Internal run status string

    Returns:
        TaskState: Mapped A2A task state
    """
    mapping = {
        "Created": TaskState.submitted,
        "Delta": TaskState.working,
        "InProgress": TaskState.working,
        "Completed": TaskState.completed,
        "Canceled": TaskState.canceled,
        "Failed": TaskState.failed,
        "Rejected": TaskState.rejected,
        "Unknown": TaskState.unknown,
        # Add other extensions if needed
    }
    # Support case insensitive
    status_key = status.strip().capitalize() if status else "Unknown"
    return mapping.get(status_key, TaskState.unknown)


def agent_response_to_a2a_task(resp: AgentResponse) -> Task:
    """
    Convert AgentResponse object to a2a Task object.

    Args:
        resp (AgentResponse): Internal agent response object

    Returns:
        Task: Converted A2A protocol task object
    """
    # 1. ID mapping
    task_id = resp.id

    # 2. context_id
    context_id = resp.session_id or ""

    # 3. status (TaskStatus)
    state = runstatus_to_a2a_taskstate(resp.status)
    # message: a2a TaskStatus not filled for now
    # timestamp: ISO8601
    if resp.created_at:
        from datetime import datetime

        timestamp = (
            datetime.utcfromtimestamp(resp.created_at).isoformat() + "Z"
        )
    else:
        timestamp = None
    status = TaskStatus(
        state=state,
        message=None,
        timestamp=timestamp,
    )

    # 4. history: Empty for now
    history = None

    # 5. artifacts
    artifacts = []
    if resp.output:
        artifacts = [agent_message_to_a2a_artifact(msg) for msg in resp.output]

    # 6. metadata: Empty for now
    metadata = None

    # 7. kind: Fixed as 'task'
    kind = "task"

    return Task(
        id=task_id,
        context_id=context_id,
        status=status,
        history=history,
        artifacts=artifacts,
        metadata=metadata,
        kind=kind,
    )


def response_to_task_status_update_event(
    response: AgentResponse,
) -> TaskStatusUpdateEvent:
    """
    Convert AgentResponse (internal response) to a2a TaskStatusUpdateEvent.

    Args:
        response (AgentResponse): Internal agent response object

    Returns:
        TaskStatusUpdateEvent: Converted A2A protocol task status update event
    """

    # ---- 1. context_id
    context_id = response.session_id or ""

    # ---- 2. task_id
    task_id = response.id

    # ---- 3. status (TaskStatus)
    state = runstatus_to_a2a_taskstate(response.status)
    # timestamp (use created_at or completed_at as time record, prefer
    # completed_at)
    from datetime import datetime

    ts = response.completed_at or response.created_at
    timestamp = datetime.utcfromtimestamp(ts).isoformat() + "Z" if ts else None
    status = TaskStatus(
        state=state,
        message=None,
        timestamp=timestamp,
    )

    # ---- 4. final: Whether the streaming event is the final package
    final_states = {"completed", "canceled", "failed", "rejected"}
    final = str(response.status).lower() in final_states

    # ---- 5. kind always 'status-update'
    kind = "status-update"

    # ---- 6. metadata (for extension, None for now)
    metadata = None

    return TaskStatusUpdateEvent(
        context_id=context_id,
        task_id=task_id,
        status=status,
        kind=kind,
        final=final,
        metadata=metadata,
    )


def content_to_task_artifact_update_event(
    content: "Content",
    context_id: str = "",
    task_id: str = None,
    append: bool = False,
    last_chunk: bool = False,
) -> "TaskArtifactUpdateEvent":
    """
    Convert single Content (TextContent/ImageContent/DataContent) to
    TaskArtifactUpdateEvent. If delta=false, should not return
    task_artifact_update_event

    Args:
        content: SSE returned content, including delta and non-delta types
        context_id: Corresponds to agent api sessionId, needs external input
        task_id: Currently equivalent to msg_id, or not passed
        append: Used to determine if current artifact is new or first
        last_chunk: Used to determine if current content is the last one

    Returns:
        TaskArtifactUpdateEvent: Converted A2A protocol task artifact update
        event
    """
    part = agent_content_to_a2a_part(content)
    artifact_id = (
        content.msg_id or ""
    )  # Content's msg_id may be None, need fallback

    artifact = Artifact(
        artifact_id=artifact_id,
        name=content.type,  # "text", "image", "data"
        description=None,
        parts=[part],
        metadata=None,
        extensions=None,
    )

    return TaskArtifactUpdateEvent(
        append=append,
        artifact=artifact,
        context_id=context_id,
        kind="artifact-update",
        last_chunk=last_chunk,
        task_id=task_id or artifact_id,
    )


def agent_role_to_a2a_role(role: str):
    if role == Role.ASSISTANT:
        return "agent"
    elif role == Role.USER:
        return "user"
    elif role == Role.SYSTEM:
        return "system"
    else:
        return "unknown"


def agent_message_to_a2a_message(msg: "AgentMessage") -> "A2AMessage":
    """
    Convert AgentAPI Message object to a2a protocol Message object

    Args:
        msg (AgentAPIMessage): Agent API message object

    Returns:
        A2AMessage: Converted A2A protocol message object
    """
    parts = [agent_content_to_a2a_part(content) for content in msg.content]
    return A2AMessage(
        message_id=msg.id,
        role=agent_role_to_a2a_role(msg.role),
        parts=parts,
        # Others can be added as needed, such as metadata
    )
