# -*- coding: utf-8 -*-
class TraceType(str):
    """Callback manager event types.

    Attributes:
        LLM: Logs for the template and response of LLM calls.
        TOOL：Logs for the tool name and its arguments and
            the output of tool calls
        AGENT_STEP: Logs for the agent loop start and end?
    """

    # Officially supported event types
    LLM = "LLM"
    TOOL = "TOOL"
    AGENT_STEP = "AGENT_STEP"
    MEMORY = "MEMORY"
    SEARCH = "SEARCH"
    AIGC = "AIGC"
    RAG = "RAG"
    INTENTION = "INTENTION"
    PLUGIN = "PLUGIN"
    FUNCTION_CALL = "FUNCTION_CALL"
    AGENT = "AGENT"
    PLANNING = "PLANNING"
    CHAIN = "CHAIN"
    RETRIEVER = "RETRIEVER"
    RERANKER = "RERANKER"
    EMBEDDING = "EMBEDDING"
    TASK = "TASK"
    GUARDRAIL = "GUARDRAIL"
    REWRITER = "REWRITER"
    OTHER = "OTHER"

    def __init__(self, value: str):
        """Initialize a TraceType with a string value.

        Args:
            value (str): The string value for the trace type.

        Raises:
            ValueError: If value is not a string.
        """
        if not isinstance(value, str):
            raise ValueError(
                f"TraceType value must be a string, got {type(value)}",
            )
        self._value_ = value

    def __str__(self) -> str:
        """Return the string representation of the trace type.

        Returns:
            str: The trace type value.
        """
        return self._value_

    def __repr__(self) -> str:
        """Return the detailed string representation of the trace type.

        Returns:
            str: The trace type representation in the format TraceType(value).
        """
        return f"TraceType({self._value_})"

    @classmethod
    def add_type(cls, name: str, value: str) -> None:
        """Add a new trace type to the class.

        Args:
            name (str): The name of the new trace type attribute.
            value (str): The string value for the new trace type.

        Raises:
            ValueError: If name or value are not strings, or if the name
            already exists.
        """
        if not isinstance(name, str) or not isinstance(value, str):
            raise ValueError("Name and value must be strings")
        if hasattr(cls, name):
            raise ValueError(f"TraceType {name} already exists")
        setattr(cls, name, cls(value))
