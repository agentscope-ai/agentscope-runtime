# -*- coding: utf-8 -*-
"""
Simple AgentBay Sandbox Demo with SandboxService Integration

This demo shows how to use AgentBay sandbox through SandboxService
and integrate it with AgentScope agents.
"""
import os
import asyncio
import logging
from pathlib import Path

from dotenv import load_dotenv
from agentscope import init, agent
from agentscope.model import DashScopeChatModel
from agentscope.formatter import DashScopeChatFormatter
from agentscope.tool import Toolkit, ToolResponse
from agentscope.message import Msg
from agentscope_runtime.sandbox.enums import SandboxType
from agentscope_runtime.engine.services.sandbox import SandboxService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_api_key(key_name: str) -> str | None:
    """
    Get API key from environment variable first, then from .env file.

    Priority:
    1. Environment variable (highest priority)
    2. .env file in current directory

    Args:
        key_name: The name of the API key environment variable

    Returns:
        API key value if found, None otherwise
    """
    # First try environment variable (highest priority)
    api_key = os.getenv(key_name)
    if api_key:
        return api_key

    # Try to load from .env file in current directory
    current_dir = Path(__file__).parent
    env_file = current_dir / ".env"

    if env_file.exists():
        load_dotenv(env_file, override=False)
        api_key = os.getenv(key_name)
        if api_key:
            return api_key

    return None


class SimpleAgentBayDemo:
    """
    Simple demo for AgentBay sandbox integration with AgentScope agents.
    """

    def __init__(self, dashscope_api_key: str, agentbay_api_key: str):
        self.dashscope_api_key = dashscope_api_key
        self.agentbay_api_key = agentbay_api_key
        self.sandbox_service = None
        self.sandbox = None
        self.agent = None

    async def setup_environment(self):
        """Setup sandbox service and environment manager."""
        try:
            logger.info(
                "Setting up sandbox service and environment manager...",
            )

            # Create sandbox service with AgentBay API key
            self.sandbox_service = SandboxService(
                bearer_token=self.agentbay_api_key,
            )
            await self.sandbox_service.start()

            # Connect to AgentBay sandbox
            sandboxes = self.sandbox_service.connect(
                session_id="demo_session",
                user_id="demo_user",
                sandbox_types=[SandboxType.AGENTBAY],
            )

            if not sandboxes:
                raise RuntimeError("No sandboxes created")

            self.sandbox = sandboxes[0]
            logger.info(
                f"Connected to AgentBay sandbox: {self.sandbox.sandbox_id}",
            )

            return True

        except Exception as e:
            logger.error(f"Failed to setup environment: {e}")
            return False

    async def setup_agent(self):
        """Setup AgentScope agent."""
        try:
            logger.info("Setting up AgentScope agent...")

            # Initialize AgentScope
            init()

            # Create DashScope model
            model = DashScopeChatModel(
                model_name="qwen-max",
                api_key=self.dashscope_api_key,
            )

            # Create DashScope formatter
            formatter = DashScopeChatFormatter()

            # Create agent
            self.agent = agent.ReActAgent(
                name="CloudAssistant",
                sys_prompt="""You are an AI assistant with access to a
                cloud-based sandbox environment. You can help users execute
                commands, manage files, and perform various tasks in the cloud.

                When users ask you to do something, you can use the available
                tools to:
                - Execute shell commands
                - Read and write files
                - List directory contents
                - Create directories
                - Run Python code
                - Take screenshots

                Always explain what you're doing and provide helpful
                responses.""",
                model=model,
                formatter=formatter,
                toolkit=self._get_toolkit(),
            )

            logger.info("AgentScope agent created successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to setup agent: {e}")
            return False

    def _get_toolkit(self) -> Toolkit:
        """Create and configure toolkit with AgentBay tools."""
        toolkit = Toolkit()

        # Register tool functions
        toolkit.register_tool_function(
            self.execute_command,
            func_description=(
                "Execute shell commands in the cloud environment"
            ),
        )
        toolkit.register_tool_function(
            self.write_file,
            func_description=(
                "Write content to a file in the cloud environment"
            ),
        )
        toolkit.register_tool_function(
            self.read_file,
            func_description=(
                "Read content from a file in the cloud environment"
            ),
        )
        toolkit.register_tool_function(
            self.list_directory,
            func_description=(
                "List files and directories in the cloud environment"
            ),
        )
        toolkit.register_tool_function(
            self.run_python,
            func_description="Execute Python code in the cloud environment",
        )

        return toolkit

    async def execute_command(self, command: str) -> ToolResponse:
        """Execute a shell command in the cloud environment."""
        try:
            result = self.sandbox.call_tool(
                "run_shell_command",
                {"command": command},
            )
            if result.get("success"):
                output = result.get("output", "")
                return ToolResponse(
                    content=f"✅ Command executed successfully:\n{output}",
                )
            else:
                error = result.get("error", "Unknown error")
                return ToolResponse(content=f"❌ Command failed: {error}")
        except Exception as e:
            return ToolResponse(content=f"❌ Error executing command: {str(e)}")

    async def write_file(self, path: str, content: str) -> ToolResponse:
        """Write content to a file in the cloud environment."""
        try:
            result = self.sandbox.call_tool(
                "write_file",
                {"path": path, "content": content},
            )
            if result.get("success"):
                return ToolResponse(
                    content=f"File written successfully to {path}",
                )
            else:
                return ToolResponse(
                    content=(
                        f"Failed to write file: "
                        f"{result.get('error', 'Unknown error')}"
                    ),
                )
        except Exception as e:
            return ToolResponse(content=f"Error writing file: {str(e)}")

    async def read_file(self, path: str) -> ToolResponse:
        """Read content from a file in the cloud environment."""
        try:
            result = self.sandbox.call_tool("read_file", {"path": path})
            if result.get("success"):
                content = result.get("content", "")
                return ToolResponse(
                    content=f"📄 File content from {path}:\n{content}",
                )
            else:
                return ToolResponse(
                    content=(
                        f"❌ Failed to read file: "
                        f"{result.get('error', 'Unknown error')}"
                    ),
                )
        except Exception as e:
            return ToolResponse(content=f"❌ Error reading file: {str(e)}")

    async def list_directory(self, path: str = ".") -> ToolResponse:
        """List files and directories in the cloud environment."""
        try:
            result = self.sandbox.call_tool("list_directory", {"path": path})
            if result.get("success"):
                files = result.get("files", [])
                file_list = "\n".join(files) if files else "No files found"
                return ToolResponse(
                    content=f"📁 Directory listing for {path}:\n{file_list}",
                )
            else:
                return ToolResponse(
                    content=(
                        f"❌ Failed to list directory: "
                        f"{result.get('error', 'Unknown error')}"
                    ),
                )
        except Exception as e:
            return ToolResponse(content=f"❌ Error listing directory: {str(e)}")

    async def run_python(self, code: str) -> ToolResponse:
        """Execute Python code in the cloud environment."""
        try:
            result = self.sandbox.call_tool("run_ipython_cell", {"code": code})
            if result.get("success"):
                output = result.get("output", "")
                return ToolResponse(
                    content=f"🐍 Python code executed successfully:\n{output}",
                )
            else:
                return ToolResponse(
                    content=(
                        f"❌ Python code execution failed: "
                        f"{result.get('error', 'Unknown error')}"
                    ),
                )
        except Exception as e:
            return ToolResponse(
                content=f"❌ Error executing Python code: {str(e)}",
            )

    async def run_demo(self):
        """Run the demo."""
        if not self.agent:
            logger.error("Agent not initialized")
            return

        logger.info("🚀 Starting AgentBay Sandbox Demo")
        logger.info("=" * 50)

        # Demo tasks
        tasks = [
            (
                "Hello! Please help me create a simple Python script that "
                "calculates the factorial of a number and save it to a file "
                "called factorial.py."
            ),
            (
                "Now please run the factorial.py script with the number 5 and "
                "show me the result."
            ),
            (
                "Please create a directory called 'demo_results' and move the "
                "factorial.py file there."
            ),
            (
                "Please list the contents of the demo_results directory to "
                "confirm the file was moved."
            ),
            (
                "Finally, please show me the current working directory and "
                "system information."
            ),
        ]

        for i, task in enumerate(tasks, 1):
            logger.info(f"\n📋 Task {i}: {task}")
            logger.info("-" * 30)

            try:
                response = await self.agent.reply(
                    Msg(name="user", role="user", content=task),
                )
                logger.info(f"🤖 Agent Response: {response}")
            except Exception as e:
                logger.error(f"❌ Error in task {i}: {e}")

            # Small delay between tasks
            await asyncio.sleep(1)

        logger.info("\n✅ Demo completed successfully!")

    async def cleanup(self):
        """Cleanup resources."""
        try:
            if self.sandbox_service:
                logger.info("Cleaning up environment...")
                self.sandbox_service.release(
                    "demo_session",
                    "demo_user",
                )
                await self.sandbox_service.stop()
                logger.info("Environment cleaned up successfully")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")


async def main():
    """Main demo function."""
    # Get API keys from environment variables or .env file
    dashscope_api_key = get_api_key("DASHSCOPE_API_KEY")
    agentbay_api_key = get_api_key("AGENTBAY_API_KEY")

    if not dashscope_api_key:
        logger.error(
            "❌ DASHSCOPE_API_KEY not found in environment variables or "
            ".env file",
        )
        logger.info(
            "Please set it with: export DASHSCOPE_API_KEY='your_key' or "
            "add it to .env file",
        )
        return

    if not agentbay_api_key:
        logger.error(
            "❌ AGENTBAY_API_KEY not found in environment variables or "
            ".env file",
        )
        logger.info(
            "Please set it with: export AGENTBAY_API_KEY='your_key' or "
            "add it to .env file",
        )
        return

    # Create demo instance
    demo = SimpleAgentBayDemo(dashscope_api_key, agentbay_api_key)

    try:
        # Setup environment
        if not await demo.setup_environment():
            logger.error("Failed to setup environment")
            return

        # Setup agent
        if not await demo.setup_agent():
            logger.error("Failed to setup agent")
            return

        # Run demo
        await demo.run_demo()

    except Exception as e:
        logger.error(f"Demo failed: {e}")
    finally:
        # Cleanup
        await demo.cleanup()


if __name__ == "__main__":
    print("🌟 AgentBay Sandbox Demo with AgentScope Agent Integration")
    print("=" * 60)
    print(
        "This demo shows how to use AgentBay cloud sandbox with "
        "AgentScope agents.",
    )
    print(
        "Make sure you have set both DASHSCOPE_API_KEY and AGENTBAY_API_KEY.",
    )
    print("=" * 60)

    asyncio.run(main())
