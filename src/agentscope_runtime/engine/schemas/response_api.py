# -*- coding: utf-8 -*-
from typing import Dict, Literal, TypeAlias
from pydantic import ConfigDict
from pydantic.main import BaseModel
from openai.types.shared import Reasoning

from openai.types.responses import (
    ResponseFunctionToolCall,
    ResponseInputItemParam,
    ResponsePrompt,
    ResponseReasoningItem,
)
from openai.types.responses.response_input_param import Message
from openai.types.responses.response import ToolChoice

# Backward compatibility for OpenAI client versions
try:  # For older openai versions (< 1.100.0)
    from openai.types.responses import ResponseTextConfig
except ImportError:  # For newer openai versions (>= 1.100.0)
    from openai.types.responses import (
        ResponseFormatTextConfig as ResponseTextConfig,
    )


class OpenAIBaseModel(BaseModel):
    # OpenAI API does allow extra fields
    model_config = ConfigDict(extra="allow")


ResponseInputOutputItem: TypeAlias = (
    ResponseInputItemParam | ResponseReasoningItem | ResponseFunctionToolCall
)


class ResponseAPI(OpenAIBaseModel):
    # Ordered by official OpenAI API documentation
    # https://platform.openai.com/docs/api-reference/responses/create
    background: bool | None = False
    include: list[str] | None = None
    input: str | list[Message]
    instructions: str | None = None
    max_output_tokens: int | None = None
    max_tool_calls: int | None = None
    metadata: Dict[str, str] | None = None
    model: str | None = None
    parallel_tool_calls: bool | None = True
    previous_response_id: str | None = None
    prompt: ResponsePrompt | None = None
    reasoning: Reasoning | None = None
    service_tier: Literal[
        "auto",
        "default",
        "flex",
        "scale",
        "priority",
    ] = "auto"
    store: bool | None = True
    stream: bool | None = False
    temperature: float | None = None
    text: ResponseTextConfig | None = None
    tool_choice: ToolChoice = "auto"
    top_logprobs: int | None = 0
    top_p: float | None = None
    truncation: Literal["auto", "disabled"] | None = "disabled"
    user: str | None = None
