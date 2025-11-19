# -*- coding: utf-8 -*-
import asyncio
import json
import traceback
from typing import Optional, Any, Dict

from .tool import Tool
from ..enums import SandboxType
from ...common.skills.base import Skill


class BuiltinTool(Tool):
    """Adapter class that wraps agentscope-runtime builtin tool to make them
    compatible with AgentScope Runtime sandbox.

    This adapter allows any skill that inherits from
    agentscope_runtime.common.skills._base to be used as a tool in
     AgentScope Runtime environments.

    Args:
        skill (Skill): The agentscope-runtime skill to wrap
        name (str, optional): Override the skill name. Defaults to
            skill.name
        description (str, optional): Override the skill description.
            Defaults to skill.description
        tool_type (str): The tool type. Defaults to "function"

    Examples:
        Basic usage with a search skill:

        .. code-block:: python

            from agentscope_bricks.zh.searches.modelstudio_search
            import ModelstudioSearch
            from agentscope_bricks.agentscope_runtime_utils import (
                AgentScopeRuntimeToolAdapter,
            )

            # Create the search skill
            search_skill = ModelstudioSearch()

            # Create the runtime adapter
            search_tool = AgentScopeRuntimeAdapter(search_skill)

            # Use the tool
            result = search_tool(query="What's the weather in Beijing?")
    """

    def __init__(
        self,
        skill: Skill,
        name: Optional[str] = None,
        description: Optional[str] = None,
        tool_type: str = "function",
    ) -> None:
        """Initialize the skill adapter.

        Args:
            skill: The agentscope_bricks skill to wrap
            name: Optional override for the skill name
            description: Optional override for the skill description
            tool_type: The tool type
        """
        self._skill = skill
        self._name = name or skill.name
        self._description = description or skill.description
        self._tool_type = tool_type

        # Generate schema from skill's function schema
        self._schema = self._generate_schema_from_skill()

    @property
    def name(self) -> str:
        """Get the tool name."""
        return self._name

    @property
    def tool_type(self) -> str:
        """Get the tool type."""
        return self._tool_type

    @property
    def schema(self) -> Dict:
        """Get the tool schema in AgentScope Runtime format."""
        return {
            "type": "function",
            "function": self._schema,
        }

    @property
    def sandbox_type(self) -> SandboxType:
        """Skill tools don't need a sandbox type."""
        return SandboxType.DUMMY

    @property
    def sandbox(self) -> None:
        """Skill tools don't have sandbox."""
        return None

    def __call__(self, **kwargs: Any) -> dict:
        """Call the skill directly."""
        return self.call(**kwargs)

    def call(self, *, sandbox: Optional[Any] = None, **kwargs: Any) -> dict:
        """Execute the skill call.

        Args:
            sandbox: Ignored for skill tools (for interface compatibility)
            **kwargs: Skill parameters

        Returns:
            Dict: Result in AgentScope Runtime format
        """
        try:
            # Validate input with skill's input type
            if self._skill.input_type:
                validated_input = self._skill.input_type.model_validate(
                    kwargs,
                )
            else:
                validated_input = kwargs

            # Execute the skill asynchronously
            try:
                # We're in an async context, but need to run sync
                import concurrent.futures

                def run_async() -> Any:
                    return asyncio.run(self._skill.arun(validated_input))

                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(run_async)
                    result = future.result()
            except RuntimeError:
                # No event loop running, safe to use asyncio.run
                result = asyncio.run(self._skill.arun(validated_input))

            # Format result
            if hasattr(result, "model_dump"):
                # Pydantic model result
                result_dict = result.model_dump()
                content_text = json.dumps(
                    result_dict,
                    ensure_ascii=False,
                    indent=2,
                )
            else:
                # Other result types
                content_text = str(result)

            return {
                "meta": None,
                "content": [
                    {
                        "type": "text",
                        "text": content_text,
                        "annotations": None,
                        "description": "None",
                    },
                ],
                "isError": False,
            }

        except Exception as e:
            return {
                "meta": None,
                "content": [
                    {
                        "type": "text",
                        "text": f"{e}:\n{traceback.format_exc()}",
                        "annotations": None,
                        "description": "None",
                    },
                ],
                "isError": True,
            }

    def bind(self, *args: Any, **kwargs: Any) -> Any:
        """Return a new instance (for interface compatibility).

        Note: agentscope_bricks zh don't support binding like partial
        functions,
        so this returns the same instance.
        """
        return self

    def _generate_schema_from_skill(self) -> Dict:
        """Generate schema from skill's function schema."""
        # Get the skill's function schema
        function_schema = self._skill.function_schema.model_dump()

        # Convert to AgentScope Runtime format
        schema = {
            "name": self._name,
            "description": self._description,
            "parameters": function_schema.get("parameters", {}),
        }

        return schema
