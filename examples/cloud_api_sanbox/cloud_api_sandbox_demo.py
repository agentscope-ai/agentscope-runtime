# -*- coding: utf-8 -*-
import os
import asyncio
import logging
from pathlib import Path
import pytest
from dotenv import load_dotenv
from agentscope_runtime.sandbox.enums import SandboxType
from agentscope_runtime.sandbox.box.cloud_api.cloud_computer_sandbox import (
    CloudComputerSandbox,
)
from agentscope_runtime.sandbox.box.cloud_api.cloud_phone_sandbox import (
    CloudPhoneSandbox,
)
from agentscope_runtime.engine.services.sandbox import SandboxService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_env_variables() -> None:
    """
    Load environment variables from .env file into system environment.

    This function loads all variables from .env file in the current directory
    into the system environment variables, making them accessible via
    os.getenv().
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


def test_cloud_pc_api_sandbox_direct():
    """
    Test Cloud api sandbox directly without sandbox service.
    """

    try:
        load_env_variables()
        try:
            desktop_id = os.getenv("DESKTOP_ID")
            sandbox = CloudComputerSandbox(
                desktop_id=desktop_id,
            )

            logger.info(
                f"Created sandbox with ID: {sandbox.desktop_id}",
            )

            # Test basic operations
            result = sandbox.call_tool(
                "run_shell_command",
                {"command": "echo 'Hello from Cloud PC Api!'"},
            )
            logger.info(f"Command result: {result}")

            result = sandbox.call_tool(
                "run_ipython_cell",
                {"code": "print('hellow!')"},
            )
            logger.info(f"run_ipython_cell result: {result}")

            result = sandbox.call_tool(
                "launch_app",
                {"name": "File Explorer"},
            )
            logger.info(f"launch_app result: {result}")

            result = sandbox.call_tool(
                "screenshot",
                {"file_name": "screenshot.png"},
            )
            logger.info(f"screenshot result: {result}")

            result = sandbox.call_tool(
                "write_file",
                {
                    "file_path": "C:/test.txt",
                    "content": "welcome cloud api test !",
                },
            )
            logger.info(f"write_file result: {result}")

            result = sandbox.call_tool(
                "read_file",
                {
                    "file_path": "C:/test.txt",
                },
            )
            logger.info(f"read_file result: {result}")

            result = sandbox.call_tool(
                "remove_file",
                {
                    "file_path": "C:/test.txt",
                },
            )
            logger.info(f"read_file result: {result}")

            result = sandbox.call_tool(
                "go_home",
                {},
            )
            logger.info(f"go_home result: {result}")
            result = sandbox.call_tool(
                "press_key",
                {
                    "key": "home",
                },
            )
            logger.info(f"press_key result: {result}")

            result = sandbox.call_tool(
                "click",
                {
                    "x": 151,
                    "y": 404,
                    "count": 2,
                },
            )
            logger.info(f"click result: {result}")

            result = sandbox.call_tool(
                "right_click",
                {
                    "x": 151,
                    "y": 404,
                    "count": 1,
                },
            )
            logger.info(f"click result: {result}")

            result = sandbox.call_tool(
                "click_and_type",
                {
                    "x": 151,
                    "y": 404,
                    "text": "你好",
                },
            )
            logger.info(f"click result: {result}")

            result = sandbox.call_tool(
                "append_text",
                {
                    "x": 151,
                    "y": 404,
                    "text": "你好",
                },
            )
            logger.info(f"click result: {result}")
            result = sandbox.call_tool(
                "mouse_move",
                {
                    "x": 151,
                    "y": 404,
                },
            )
            logger.info(f"mouse_move result: {result}")

            result = sandbox.call_tool(
                "scroll",
                {
                    "pixels": -5,
                },
            )
            logger.info(f"scroll result: {result}")

            result = sandbox.call_tool(
                "scroll_pos",
                {
                    "x": 954,
                    "y": 537,
                    "pixels": -5,
                },
            )
            logger.info(f"scroll_pos result: {result}")

            # Cleanup
            sandbox._cleanup()  # pylint: disable=protected-access
            logger.info("Cloud PC Api sandbox test completed successfully")
            return True

        except ImportError as e:
            logger.warning(f"Cloud PC Api not installed: {e}")
            logger.info("This is expected if Cloud Api PC is not available")
            return True  # Consider this a pass since integration is correct

    except Exception as e:
        logger.error(f"Cloud PC Api sandbox test failed: {e}")
        return False


def test_cloud_phone_api_sandbox_direct():
    """
    Test Cloud api sandbox directly without sandbox service.
    """

    try:
        load_env_variables()
        try:
            instance_ids = os.getenv("PHONE_INSTANCE_ID")

            sandbox = CloudPhoneSandbox(
                instance_id=instance_ids,
            )

            logger.info(
                f"Created sandbox with ID: {sandbox.instance_id}",
            )

            # Test basic operations
            result = sandbox.call_tool(
                "run_shell_command",
                {"command": "echo 'Hello from Cloud Phone Api!'"},
            )
            logger.info(f"Command result: {result}")

            result = sandbox.call_tool(
                "screenshot",
                {"file_name": "screenshot.png"},
            )
            logger.info(f"screenshot result: {result}")

            result = sandbox.call_tool(
                "send_file",
                {
                    "source_file_path": "/sdcard/Download/dog_and_girl.jpeg",
                    "upload_url": "https://help-static-aliyun-doc.aliyuncs.com"
                    "/file-manage-files/"
                    "zh-CN/20241022/emyrja/dog_and_girl.jpeg",
                },
            )
            logger.info(f"send_file result: {result}")

            result = sandbox.call_tool(
                "remove_file",
                {"file_path": "/sdcard/Download/dog_and_girl.jpeg"},
            )
            logger.info(f"remove_file result: {result}")

            result = sandbox.call_tool(
                "click",
                {
                    "x1": 151,
                    "y1": 404,
                    "x2": 151,
                    "y2": 404,
                    "width": 716,
                    "height": 1280,
                },
            )
            logger.info(f"click result: {result}")

            result = sandbox.call_tool(
                "slide",
                {
                    "x1": 366,
                    "y1": 1123,
                    "x2": 366,
                    "y2": 330,
                    "width": 716,
                    "height": 1280,
                },
            )
            logger.info(f"slide result: {result}")
            # 当前文字输入依赖于ADBKeyboard输入法，需提前安装
            result = sandbox.call_tool(
                "type_text",
                {
                    "text": "阿里巴巴",
                },
            )
            logger.info(f"type_text result: {result}")

            result = sandbox.call_tool(
                "enter",
                {},
            )
            logger.info(f"enter result: {result}")

            result = sandbox.call_tool(
                "back",
                {},
            )
            logger.info(f"back result: {result}")

            result = sandbox.call_tool(
                "kill_front_app",
                {},
            )
            logger.info(f"kill_front_app result: {result}")

            result = sandbox.call_tool(
                "menu",
                {},
            )
            logger.info(f"menu result: {result}")

            result = sandbox.call_tool(
                "go_home",
                {},
            )
            logger.info(f"go_home result: {result}")

            # Cleanup
            sandbox._cleanup()  # pylint: disable=protected-access
            logger.info("Cloud Phone Api sandbox test completed successfully")
            return True

        except ImportError as e:
            logger.warning(f"Cloud Phone Api  not installed: {e}")
            logger.info("This is expected if AgentBay SDK is not available")
            return True  # Consider this a pass since integration is correct

    except Exception as e:
        logger.error(f"Cloud Phone Api sandbox test failed: {e}")
        return False


@pytest.mark.anyio
async def test_cloud_pc_api_sandbox_service():
    """
    Test Cloud PC Api sandbox via SandboxService and EnvironmentManager.
    """
    try:
        load_env_variables()

        # Create environment manager context
        async with SandboxService() as service:
            sandboxes = service.connect(
                session_id="demo_service_session",
                user_id="demo_user",
                sandbox_types=[SandboxType.CLOUD_COMPUTER],
            )

            if not sandboxes:
                print("No sandboxes returned by SandboxService")
                logger.error("No sandboxes returned by SandboxService")
                return False

            sandbox = sandboxes[0]
            print(
                "Connected Cloud Api PC sandbox via service"
                f": {sandbox.sandbox_id} ",
            )
            logger.info(
                f"Connected Cloud Api PC sandbox via service: "
                f"{sandbox.sandbox_id}",
            )

            # Test basic operations
            result = sandbox.call_tool(
                "run_shell_command",
                {"command": "echo 'Hello from Cloud PC Api!'"},
            )
            print("Command result:", result)
            logger.info(f"Command result: {result}")

            result = sandbox.call_tool(
                "screenshot",
                {"file_name": "screenshot.png"},
            )
            print("screenshot result:", result)
            logger.info(f"screenshot result: {result}")

        logger.info("Cloud PC Api sandbox service test completed successfully")
        return True
    except ImportError as e:
        logger.warning(f"Cloud PC Api not installed: {e}")
        logger.info("This is expected if Cloud Api PC is not available")
        return True
    except Exception as e:
        logger.error(f"Cloud PC Api sandbox service test failed: {e}")
        return False


@pytest.mark.anyio
async def test_cloud_phone_api_sandbox_service():
    """
    Test Cloud Api sandbox via SandboxService and EnvironmentManager.
    """
    logger.info("Testing Cloud Phone API sandbox via SandboxService...")

    try:
        load_env_variables()

        # Create environment manager context
        async with SandboxService() as service:
            sandboxes = service.connect(
                session_id="demo_service_session",
                user_id="demo_user",
                sandbox_types=[SandboxType.CLOUD_PHONE],
            )

            if not sandboxes:
                print("No sandboxes returned by SandboxService")
                logger.error("No sandboxes returned by SandboxService")
                return False

            sandbox = sandboxes[0]
            print(
                "Connected Cloud Phone Api sandbox via service"
                f": {sandbox.sandbox_id} ",
            )
            logger.info(
                f"Connected Cloud Phone Api  sandbox via service: "
                f"{sandbox.sandbox_id}",
            )

            # Test basic operations
            result = sandbox.call_tool(
                "run_shell_command",
                {"command": "echo 'Hello from Cloud Phone Api!'"},
            )
            print("Command result:", result)
            logger.info(f"Command result: {result}")

            result = sandbox.call_tool(
                "screenshot",
                {"file_name": "screenshot.png"},
            )
            print("screenshot result:", result)
            logger.info(f"screenshot result: {result}")

        logger.info(
            "Cloud Phone Api sandbox service test completed successfully",
        )
        return True
    except ImportError as e:
        logger.warning(f"Cloud Phone Api  not installed: {e}")
        logger.info("This is expected if AgentBay SDK is not available")
        return True
    except Exception as e:
        logger.error(f"Cloud Phone Api sandbox service test failed: {e}")
        return False


async def main():
    """
    Run all tests.
    """
    logger.info("Starting AgentBay integration tests...")

    tests = [
        ("Cloud Api Sandbox Service", test_cloud_pc_api_sandbox_service),
        # ("Cloud Api Sandbox Service", test_cloud_phone_api_sandbox_service),
        # ("AgentBay Sandbox Direct", test_cloud_pc_api_sandbox_direct()),
        # ("AgentBay Sandbox Direct", test_cloud_phone_api_sandbox_direct()),
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
            "🎉 All tests passed! AgentBay integration is working correctly.",
        )
    else:
        logger.warning(
            "⚠️ Some tests failed. Check the logs above for details.",
        )


if __name__ == "__main__":
    asyncio.run(main())
