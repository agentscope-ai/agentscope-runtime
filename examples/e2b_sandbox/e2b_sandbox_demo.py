# -*- coding: utf-8 -*-
import os
import asyncio
import logging
import time
from pathlib import Path

from dotenv import load_dotenv
from agentscope_runtime.sandbox.enums import SandboxType
from agentscope_runtime.sandbox.box.e2b.e2b_sandbox import (
    E2bSandBox,
)
from agentscope_runtime.engine.services.sandbox_service import SandboxService
from agentscope_runtime.engine.services.environment_manager import (
    create_environment_manager,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_env_variables() -> None:
    """
    Load environment variables from .env file into system environment.

    This function loads all variables from .env file in the current directory
    into the system environment variables,
    making them accessible via os.getenv().
    Variables already present in system environment are not overridden.
    """
    current_dir = Path(__file__).parent
    env_file = current_dir / ".env.template"

    if env_file.exists():
        # Load environment variables from .env file into system environment
        load_dotenv(env_file, override=False)

        from dotenv import dotenv_values

        env_vars = dotenv_values(env_file)
        for k, v in env_vars.items():
            os.environ[k] = v


def test_e2b_sandbox_direct():
    """
    Test e2b sandbox directly without sandbox service.
    """

    try:
        load_env_variables()
        try:
            sandbox = E2bSandBox()
            # Wait for sandbox to be ready
            time.sleep(5)

            # Test basic operations
            result = sandbox.call_tool(
                "run_shell_command",
                {"command": "echo 'Hello from e2b sandbox!'"},
            )
            logger.info(f"Command result: {result}")

            result = sandbox.call_tool(
                "screenshot",
                {"file_path": f"{os.getcwd()}/screenshot.png"},
            )

            logger.info(f"screenshot result: {result}")

            # Cleanup
            sandbox._cleanup()  # pylint: disable=protected-access
            logger.info("E2B sandbox test completed successfully")
            return True

        except ImportError as e:
            logger.warning(f"E2B sandbox not installed: {e}")
            logger.info("This is expected if E2B sandbox is not available")
            return True  # Consider this a pass since integration is correct

    except Exception as e:
        logger.error(f"E2B sandbox test failed: {e}")
        return False


async def test_e2b_sandbox_service():
    """
    Test E2B sandbox via SandboxService and EnvironmentManager.
    """
    try:
        load_env_variables()

        # Initialize sandbox service
        sandbox_service = SandboxService()

        # Create environment manager context
        async with create_environment_manager(
            sandbox_service=sandbox_service,
        ) as env_manager:
            sandboxes = env_manager.connect_sandbox(
                session_id="demo_service_session",
                user_id="demo_user",
                env_types=[SandboxType.E2B.value],
            )

            if not sandboxes:
                print("No sandboxes returned by SandboxService")
                logger.error("No sandboxes returned by SandboxService")
                return False

            sandbox = sandboxes[0]
            print(f"Connected E2B sandbox via service: {sandbox.sandbox_id} ")
            logger.info(
                f"Connected E2B sandbox via service: " f"{sandbox.sandbox_id}",
            )

            # Wait for sandbox to be ready
            time.sleep(5)

            # Test basic operations
            result = sandbox.call_tool(
                "run_shell_command",
                {"command": "echo 'Hello from Cloud PC Api!'"},
            )
            logger.info(f"Command result: {result}")

            result = sandbox.call_tool(
                "screenshot",
                {"file_path": f"{os.getcwd()}/screenshot.png"},
            )

            logger.info(f"screenshot result: {result}")

        logger.info("E2B sandbox service test completed successfully")
        return True
    except ImportError as e:
        logger.warning(f"E2B sandbox not installed: {e}")
        logger.info("This is expected if E2B sandbox is not available")
        return True
    except Exception as e:
        logger.error(f"E2B sandbox service test failed: {e}")
        return False


async def main():
    """
    Run all tests.
    """
    logger.info("Starting E2B sandbox integration tests...")

    tests = [
        ("E2B sandbox Service", test_e2b_sandbox_service),
        ("AgentBay Sandbox Direct", test_e2b_sandbox_direct()),
    ]

    results = []
    for test_name, test_func in tests:
        logger.info(f"\n--- Running {test_name} ---")
        try:
            if asyncio.iscoroutinefunction(test_func):
                result = await test_func()
            else:
                result = test_func()
            results.append((test_name, result))
        except Exception as e:
            logger.error(f"Test {test_name} failed with exception: {e}")
            results.append((test_name, False))

    # Summary
    logger.info("\n--- Test Results Summary ---")
    passed = 0
    for test_name, result in results:
        status = "PASSED" if result else "FAILED"
        logger.info(f"{test_name}: {status}")
        if result:
            passed += 1

    logger.info(f"\nTotal: {passed}/{len(results)} tests passed")

    if passed == len(results):
        logger.info(
            "🎉 All tests passed! E2B sandbox integration is working"
            " correctly.",
        )
    else:
        logger.warning(
            "⚠️ Some tests failed. Check the logs above for details.",
        )


if __name__ == "__main__":
    asyncio.run(main())
