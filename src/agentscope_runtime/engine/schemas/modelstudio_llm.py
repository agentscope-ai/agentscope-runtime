# -*- coding: utf-8 -*-
import os
from typing import List, Literal, Optional, Union

from openai.types.chat import ChatCompletion, ChatCompletionChunk
from pydantic import (
    BaseModel,
    StrictInt,
    field_validator,
    Field,
)

from .oai_llm import (
    Parameters,
    OpenAIMessage,
)


class KnowledgeHolder(BaseModel):
    source: str
    """The source identifier or URL where the knowledge was retrieved from."""

    content: str
    """The actual content or knowledge text retrieved from the source."""


class IntentionOptions(BaseModel):
    white_list: List[str] = Field(default_factory=list)
    """A list of allowed intentions that can be processed."""

    black_list: List[str] = Field(default_factory=list)
    """A list of blocked intentions that should not be processed."""

    search_model: str = "search_v6"
    """The search model version to use for intentions recognition."""

    intensity: Optional[int] = None
    """The intensity level for intentions matching and processing."""

    scene_id: Optional[str] = None
    """The scene identifier for context-aware intentions processing."""


class SearchOptions(BaseModel):
    """
    Search Options on Modelstudio platform for knowledge retrieval and web
    search.
    """

    enable_source: bool = False
    """Whether to include source information in search results."""

    enable_citation: bool = False
    """Whether to include citation information for retrieved content."""

    enable_readpage: bool = False
    """Whether to enable full page reading for web content."""

    enable_online_read: bool = False
    """Whether to enable online reading capabilities for real-time content."""

    citation_format: str = "[<number>]"
    """The format string for citations in the response."""

    search_strategy: Literal[
        "standard",
        "pro_ultra",
        "pro",
        "lite",
        "pro_max",
        "image",
        "turbo",
        "max",
    ] = "turbo"
    """The search strategy to use ('standard', 'pro_ultra',
    'pro', 'lite','pro_max', 'image','turbo','max'). """

    forced_search: bool = False
    """Whether to force search even when cached results are available."""

    prepend_search_result: bool = False
    """Whether to prepend search results to the response."""

    enable_search_extension: bool = False
    """Whether to enable extended search capabilities."""

    item_cnt: int = 20000
    """The maximum number of items to retrieve in search results."""

    top_n: int = 0
    """The number of top results to return (0 means return all)."""

    intention_options: Union[IntentionOptions, None] = IntentionOptions()
    """Options for intentions recognition and processing during search."""


# maximum chunk size from knowledge base [1, 20]
PARAM_MAXIMUM_ALLOWED_CHUNK_NUM_MIN = int(
    os.getenv(
        "PARAM_MAXIMUM_ALLOWED_CHUNK_NUM_MIN",
        "1",
    ),
)
PARAM_MAXIMUM_ALLOWED_CHUNK_NUM_MAX = int(
    os.getenv(
        "PARAM_MAXIMUM_ALLOWED_CHUNK_NUM_MAX",
        "20",
    ),
)


class RagOptions(BaseModel):
    model_config = {"populate_by_name": True}

    class FallbackOptions(BaseModel):
        default_response_type: Optional[str] = "llm"
        """The type of default response when RAG fails ('llm', 'template',
        'none'). """

        default_response: Optional[str] = ""
        """The default response text to use when RAG fails."""

    class RewriteOptions(BaseModel):
        model_name: Optional[str] = None
        """The model name to use for rewriting."""

        class_name: Optional[str] = None
        """The class name to use for rewriting."""

    class RerankOptions(BaseModel):
        model_name: Optional[str] = None
        """The model name to use for reranking."""

    workspace_id: Optional[str] = ""
    """The modelstudio workspace id"""

    replaced_word: str = "${documents}"
    """The placeholder word in prompts that will be replaced with retrieved
    documents. """

    index_names: Optional[List[str]] = Field(default_factory=list)
    """List of index names to use for document processing and retrieval."""

    pipeline_ids: Optional[List[str]] = Field(default_factory=list)
    """List of pipeline IDs to use for document processing and retrieval."""

    file_ids: Optional[List[str]] = Field(
        default_factory=list,
        alias="file_id_list",
    )
    """List of specific file IDs to search within."""

    prompt_strategy: Optional[str] = Field(
        default="topK",
        alias="prompt_strategy_name",
    )
    """The strategy for selecting and organizing retrieved content in
    prompts. """

    maximum_allowed_chunk_num: Optional[int] = 5
    """The maximum number of document chunks to include in the context."""

    maximum_allowed_length: Optional[int] = 2000
    """The maximum total length of retrieved content in characters."""

    enable_citation: bool = Field(
        default=False,
        alias="prompt_enable_citation",
    )
    """Whether to include citation information for retrieved documents."""

    fallback_options: Optional[FallbackOptions] = None
    """Options for handling cases when RAG retrieval fails."""

    enable_web_search: bool = False
    """Whether to enable web search as part of the RAG pipeline."""

    session_file_ids: Optional[List[str]] = Field(default_factory=list)
    """List of file IDs that are specific to the current session."""

    dense_similarity_top_k: Optional[int] = 100
    """The number of most similar dense vectors to retrieve."""

    sparse_similarity_top_k: Optional[int] = 100
    """The number of most similar sparse vectors to retrieve."""

    enable_rewrite: Optional[bool] = None
    """Whether to enable content rewrite during RAG."""

    rewrite: Optional[List[RewriteOptions]] = None
    """Options for content rewrite."""

    enable_reranking: Optional[bool] = None
    """Whether to enable content reranking."""

    rerank_min_score: Optional[float] = None
    """The minimum score threshold for content reranking."""

    rerank_top_n: Optional[int] = None
    """The number of top results to return for content reranking."""

    rerank: Optional[List[RerankOptions]] = None

    enable_reject_filter: Optional[bool] = None
    """Whether to enable content rejection filtering."""

    reject_filter_type: Optional[str] = None
    """The type of content rejection filter to use."""

    reject_filter_model_name: Optional[str] = None
    """The name of the model to use for content rejection filtering."""

    reject_filter_prompt: Optional[str] = None
    """The prompt to use for content rejection filtering."""

    enable_agg_search: Optional[bool] = None
    """Whether to enable aggregation search."""

    enable_hybrid_gen: Optional[bool] = None
    """Whether to enable hybrid generations."""

    @field_validator("prompt_strategy")
    @classmethod
    def prompt_strategy_check(cls, value: str) -> str:
        if value:
            value = value.lower()
            if value in ["topk", "top_k"]:
                return "topK"
        return value

    @field_validator("maximum_allowed_chunk_num")
    @classmethod
    def maximum_allowed_chunk_num_check(cls, value: int) -> int:
        if value < int(PARAM_MAXIMUM_ALLOWED_CHUNK_NUM_MIN) or value > int(
            PARAM_MAXIMUM_ALLOWED_CHUNK_NUM_MAX,
        ):
            raise KeyError(
                f"Range of maximum_allowed_chunk_num should be "
                f"[{PARAM_MAXIMUM_ALLOWED_CHUNK_NUM_MIN}, "
                f"{PARAM_MAXIMUM_ALLOWED_CHUNK_NUM_MAX}]",
            )
        return value


class ModelstudioParameters(Parameters):
    """
    Parameters for Modelstudio platform, extending the base Parameters with
    Modelstudio-specific options.
    """

    repetition_penalty: Union[float, None] = None
    """Penalty for repeating tokens. Higher values reduce repetition."""

    length_penalty: Union[float, None] = None
    """Penalty applied to longer sequences. Affects the length of generated
    text. """

    top_k: Union[StrictInt, None] = None
    """The number of highest probability vocabulary tokens to keep for top-k
    filtering."""

    min_tokens: Optional[int] = None
    """The minimum number of tokens to generate before stopping."""

    result_format: Literal["text", "message"] = "message"
    """The format of the response ('text' for plain text, 'message' for
    structured message) """

    incremental_output: bool = False
    """Whether to return incremental output during generations."""

    # Search
    enable_search: bool = False
    """Whether to enable search capabilities for knowledge retrieval."""

    search_options: Optional[SearchOptions] = SearchOptions()
    """Configuration options for search functionality."""

    # RAG
    enable_rag: bool = False  # RAGs of modelstudio assistant service
    """Whether to enable Retrieval-Augmented Generation (RAG) for the
    Modelstudio assistant service. """

    rag_options: Union[RagOptions, None] = None
    """Configuration options for RAG functionality."""

    selected_model: Optional[str] = "qwen-max"
    """The selected model name to use for generations."""

    # Intention
    intention_options: Optional[IntentionOptions] = None
    """Options for intentions recognition and processing."""

    # MCP Servers
    mcp_config_file: Optional[str] = None
    """Path to the MCP (Model Context Protocol) configuration file."""


class ModelstudioChatRequest(ModelstudioParameters):
    messages: List[OpenAIMessage]
    """A list of messages comprising the conversation so far."""

    model: str
    """ID of the model to use for the chat completion."""


class ModelstudioChatResponse(ChatCompletion):
    pass


class ModelstudioChatCompletionChunk(ChatCompletionChunk):
    pass
