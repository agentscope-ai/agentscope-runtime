# -*- coding: utf-8 -*-
# pylint: disable=unused-argument
import inspect

from abc import ABC, abstractmethod
from typing import Optional, Any, Dict
from ..enums import SandboxType


class Tool(ABC):
    """Abstract base class for all tools.

    This abstract class defines the common interface that all tool
    implementations must follow, including both SandboxTool and FunctionTool.

    Key responsibilities:
    - Define the standard tool interface
    - Ensure consistent behavior across different tool types
    - Provide common functionality where applicable
    """

    def __init__(
        self,
        *,
        name: Optional[str] = None,
        tool_type: Optional[str] = None,
        **kwargs,
    ):
        """
        Initialize the tool with basic parameters.

        Args:
            name: Tool name
            tool_type: Tool type identifier
            **kwargs: Additional tool-specific parameters
        """
        self._name = name
        self._tool_type = tool_type

    @property
    def __name__(self) -> str:
        return self.name

    @property
    @abstractmethod
    def name(self) -> str:
        """Get the tool name."""

    @property
    @abstractmethod
    def tool_type(self) -> str:
        """Get the tool type."""

    @property
    @abstractmethod
    def schema(self) -> Dict:
        """Get the tool schema in OpenAI function calling format."""

    @property
    @abstractmethod
    def sandbox_type(self) -> SandboxType:
        """Get the required sandbox type for this tool."""

    @property
    @abstractmethod
    def sandbox(self) -> Optional[Any]:
        """Get the current sandbox instance (if any)."""

    def __call__(self, *, sandbox: Optional[Any] = None, **kwargs):
        """Call the tool with optional sandbox override.

        This is a convenience method that delegates to the call() method.

        Args:
            sandbox: Optional sandbox to use for this call
            **kwargs: Tool parameters

        Returns:
            Tool execution result
        """
        return self.call(sandbox=sandbox, **kwargs)

    @abstractmethod
    def call(self, *, sandbox: Optional[Any] = None, **kwargs) -> Dict:
        """Execute the tool call.

        This is the core method that each tool implementation must provide.

        Args:
            sandbox: Optional sandbox to use for this call
            **kwargs: Tool parameters

        Returns:
            Tool execution result in standardized format:
            {
                "meta": Optional[Dict],
                "content": List[Dict],
                "isError": bool
            }
        """

    @abstractmethod
    def bind(self, *args, **kwargs) -> "Tool":
        """Bind parameters or context to create a new tool instance.

        The specific binding behavior depends on the tool type:
        - SandboxTool: binds to a sandbox
        - FunctionTool: binds function parameters

        Returns:
            New tool instance with bound parameters/context
        """

    def __str__(self) -> str:
        """String representation of the tool."""
        return (
            f"{self.__class__.__name__}(name='{self.name}', type="
            f"'{self.tool_type}')"
        )

    def __repr__(self) -> str:
        """Detailed string representation of the tool."""
        return (
            f"{self.__class__.__name__}("
            f"name='{self.name}', "
            f"tool_type='{self.tool_type}', "
            f"sandbox_type='{self.sandbox_type}'"
            f")"
        )

    def make_function(self):
        """Create a function with proper type signatures from schema."""
        tool_call = self.__call__
        parameters = self.schema["function"]["parameters"]

        # Extract properties and required parameters from the schema
        properties = parameters.get("properties", {})
        required = parameters.get("required", [])

        # Type mapping from JSON schema types to Python types
        type_mapping = {
            "string": str,
            "integer": int,
            "number": float,
            "boolean": bool,
            "array": list,
            "object": dict,
        }

        # Build parameter signature
        sig_params = []
        for param_name, param_info in properties.items():
            param_type = type_mapping.get(
                param_info.get("type", "string"),
                str,
            )

            if param_name in required:
                # Required parameter
                param = inspect.Parameter(
                    param_name,
                    inspect.Parameter.POSITIONAL_OR_KEYWORD,
                    annotation=param_type,
                )
            else:
                # Optional parameter with default None
                param = inspect.Parameter(
                    param_name,
                    inspect.Parameter.POSITIONAL_OR_KEYWORD,
                    default=None,
                    annotation=Optional[param_type],
                )

            sig_params.append(param)

        # Create the function signature
        new_signature = inspect.Signature(sig_params, return_annotation=Any)

        def generated_function(*args, **kwargs):
            """
            Dynamically generated function wrapper for the tool schema.

            This function is created at runtime to match the tool's parameter
            signature as defined in the schema. It validates arguments and
            forwards them to the tool's call interface.
            """
            # Bind arguments to signature
            bound = new_signature.bind(*args, **kwargs)
            bound.apply_defaults()

            # Validate required parameters
            missing_required = [
                param_name
                for param_name in required
                if param_name not in bound.arguments
                or bound.arguments[param_name] is None
            ]

            if missing_required:
                raise TypeError(
                    f"Missing required arguments: {set(missing_required)}",
                )

            # Filter kwargs based on defined properties and remove None
            # values for optional params
            filtered_kwargs = {
                k: v
                for k, v in bound.arguments.items()
                if k in properties and (k in required or v is not None)
            }

            return tool_call(**filtered_kwargs)

        # Set the correct signature and metadata
        generated_function.__signature__ = new_signature
        generated_function.__name__ = self.name

        # Build docstring with parameter information
        doc_parts = []
        for name, info in properties.items():
            required_str = " (required)" if name in required else " (optional)"
            doc_parts.append(
                f"    {name}: {info.get('type', 'string')}{required_str} -"
                f" {info.get('description', '')}",
            )

        generated_function.__doc__ = (
            self.schema["function"]["description"]
            + "\n\nParameters:\n"
            + "\n".join(doc_parts)
        )

        # Set type annotations for compatibility with typing inspection
        annotations = {param.name: param.annotation for param in sig_params}
        annotations["return"] = Any
        generated_function.__annotations__ = annotations

        return generated_function
