# -*- coding: utf-8 -*-
import argparse
import inspect
import logging

from mcp.server.fastmcp import FastMCP
from .box.base.base_sandbox import BaseSandbox
from .box.browser.browser_sandbox import BrowserSandbox
from .box.filesystem.filesystem_sandbox import FilesystemSandbox
from .enums import SandboxType

logger = logging.getLogger(__name__)

mcp = FastMCP("AgentRuntime Sandbox MCP Server")


def json_type_to_python_type(json_type: str):
    """Convert JSON schema type to Python type annotation."""
    type_mapping = {
        "string": str,
        "integer": int,
        "number": float,
        "boolean": bool,
        "array": list,
        "object": dict,
    }
    return type_mapping.get(json_type, str)


def extract_content_from_mcp_response(response):
    """Extract actual content from MCP protocol response."""
    if isinstance(response, dict):
        if "content" in response:
            content = response["content"]
            if isinstance(content, list) and len(content) > 0:
                first_item = content[0]
                if isinstance(first_item, dict) and "text" in first_item:
                    return first_item["text"]
                elif isinstance(first_item, dict) and "data" in first_item:
                    return first_item["data"]
            return content
        elif "result" in response:
            return response["result"]
        elif "data" in response:
            return response["data"]
    return response


def create_dynamic_function(schema, method_name, box):
    """Safely create a function with dynamic signature using inspect API."""
    func_name = schema["function"]["name"]
    func_description = schema["function"]["description"]
    parameters = schema["function"]["parameters"]
    properties = parameters.get("properties", {})
    required = parameters.get("required", [])

    # Create parameter list using inspect.Parameter
    params = []
    for param_name, param_info in properties.items():
        param_type = json_type_to_python_type(param_info.get("type", "string"))
        if param_name in required:
            param = inspect.Parameter(
                param_name,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                annotation=param_type,
            )
        else:
            param = inspect.Parameter(
                param_name,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                default=None,
                annotation=param_type,
            )
        params.append(param)

    # Create new signature
    new_signature = inspect.Signature(params)

    # Create wrapper function
    def wrapper(*args, **kwargs):
        """Dynamically generated wrapper function."""
        # Bind arguments to signature
        try:
            bound = new_signature.bind(*args, **kwargs)
            bound.apply_defaults()
        except TypeError as e:
            raise TypeError(f"Invalid arguments for {func_name}: {e}") from e

        # Filter out None values for optional parameters
        filtered_kwargs = {
            k: v for k, v in bound.arguments.items() if v is not None
        }

        # Call the actual method and extract content from MCP response
        mcp_response = getattr(box, method_name)(**filtered_kwargs)
        # Extract the actual content, not the MCP protocol wrapper
        actual_result = extract_content_from_mcp_response(mcp_response)

        return actual_result

    # Set function metadata
    wrapper.__signature__ = new_signature
    wrapper.__name__ = func_name
    wrapper.__doc__ = func_description
    wrapper.__qualname__ = func_name
    return wrapper


def register_tools(box):
    """Register all tools with the MCP server using FastMCP decorators."""
    try:
        tools_json = box.list_tools()

        for server_name, tool_dict in tools_json.items():
            logger.info(f"Registering tools from server: {server_name}")

            for tool_name, tool_info in tool_dict.items():
                json_schema = tool_info["json_schema"]

                # Create dynamic function with proper signature
                dynamic_func = create_dynamic_function(
                    json_schema,
                    tool_name,
                    box,
                )

                # Apply MCP decorator
                _ = mcp.tool(
                    name=json_schema["function"]["name"],
                    description=json_schema["function"]["description"],
                )(dynamic_func)

                logger.info(
                    f"Registered tool: {json_schema['function']['name']}",
                )

    except Exception as e:
        logger.error(f"Error registering tools: {e}")
        raise


def main():
    parser = argparse.ArgumentParser(
        description="Run the AgentRuntime MCP Server.",
    )
    parser.add_argument(
        "--type",
        required=False,
        default="base",
        choices=["base", "browser", "filesystem"],
        help="Type of sandbox to run",
    )
    parser.add_argument(
        "--base_url",
        required=False,
        default=None,
        help="Base URL for the server",
    )
    parser.add_argument(
        "--bearer_token",
        required=False,
        default=None,
        help="Bearer token for authentication",
    )

    args = parser.parse_args()

    logger.info(
        f"Running {args.type} sandbox with base URL `{args.base_url}` and "
        f"bearer token `{args.bearer_token}`",
    )

    sandbox_type = SandboxType(args.type)

    if sandbox_type == SandboxType.BASE:
        sandbox_cls = BaseSandbox
    elif sandbox_type == SandboxType.BROWSER:
        sandbox_cls = BrowserSandbox
    elif sandbox_type == SandboxType.FILESYSTEM:
        sandbox_cls = FilesystemSandbox

    with sandbox_cls(
        base_url=args.base_url,
        bearer_token=args.bearer_token,
    ) as box:
        register_tools(box)
        mcp.run()


if __name__ == "__main__":
    main()
