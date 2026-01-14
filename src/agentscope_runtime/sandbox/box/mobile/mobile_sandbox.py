# -*- coding: utf-8 -*-
import logging
import subprocess
import platform
from typing import Optional, List, Union
from urllib.parse import urlencode, urljoin

from ..sandbox import Sandbox, SandboxAsync

from ...utils import build_image_uri
from ...registry import SandboxRegistry
from ...enums import SandboxType
from ...constant import TIMEOUT

logger = logging.getLogger(__name__)


class HostPrerequisiteError(Exception):
    """Exception raised when host prerequisites
    for MobileSandbox are not met."""


def _check_host_readiness() -> None:
    logger.info(
        "Performing one-time host environment check for MobileSandbox...",
    )

    architecture = platform.machine().lower()
    if architecture in ("aarch64", "arm64"):
        logger.warning(
            "\n======================== WARNING ========================\n"
            "ARM64/aarch64 architecture detected (e.g., Apple M-series).\n"
            "Running this mobile sandbox on a non-x86_64 host may lead \n"
            " to unexpected compatibility or performance issues.\n"
            "=========================================================",
        )

    os_type = platform.system()
    if os_type == "Linux":
        try:
            result = subprocess.run(
                ["lsmod"],
                capture_output=True,
                text=True,
                check=True,
            )
            loaded_modules = result.stdout
        except (FileNotFoundError, subprocess.CalledProcessError):
            loaded_modules = ""
            logger.warning(
                "Could not execute 'lsmod' to verify kernel modules.",
            )

        if "binder_linux" not in loaded_modules:
            error_message = (
                "\n========== HOST PREREQUISITE FAILED ==========\n"
                "MobileSandbox requires specific kernel modules"
                " that appear to be missing or not loaded.\n\n"
                "To fix this, please run the following commands"
                " on your Linux host:\n\n"
                "## Install required kernel modules\n"
                "sudo apt update"
                " && sudo apt install -y linux-modules-extra-`uname -r`\n"
                "sudo modprobe binder_linux"
                ' devices="binder,hwbinder,vndbinder"\n'
                "## (Optional) Load the ashmem driver for older kernels\n"
                "sudo modprobe ashmem_linux\n"
                "=================================================="
            )
            raise HostPrerequisiteError(error_message)

    if os_type == "Windows":
        try:
            result = subprocess.run(
                ["wsl", "lsmod"],
                capture_output=True,
                text=True,
                check=True,
                encoding="utf-8",
            )
            loaded_modules = result.stdout
        except (FileNotFoundError, subprocess.CalledProcessError):
            loaded_modules = ""
            logger.warning(
                "Could not execute 'wsl lsmod' to verify kernel modules.",
            )

        if "binder_linux" not in loaded_modules:
            error_message = (
                "\n========== HOST PREREQUISITE FAILED ==========\n"
                "MobileSandbox on Windows requires Docker Desktop "
                "with the WSL 2 backend.\n"
                "The required kernel modules seem to be missing "
                "in your WSL 2 environment.\n\n"
                "To fix this, please follow these steps:\n\n"
                "1. **Ensure Docker Desktop is using WSL 2**:\n"
                "   - Open Docker Desktop -> Settings -> General.\n"
                "   - Make sure 'Use the WSL 2 based engine' "
                "is checked.\n\n"
                "2. **Ensure WSL is installed and updated**:\n"
                "   - Open PowerShell or Command Prompt "
                "as Administrator.\n"
                "   - Run: wsl --install\n"
                "   - Run: wsl --update\n"
                "   (An update usually installs a recent Linux kernel "
                "with the required modules.)\n\n"
                "3. **Verify manually (Optional)**:\n"
                "   - After updating, run 'wsl lsmod | findstr binder' "
                "in your terminal.\n"
                "   - If it shows 'binder_linux', "
                "the issue should be resolved.\n"
                "=================================================="
            )
            raise HostPrerequisiteError(error_message)

    logger.info("Host environment check passed.")


class MobileMixin:
    @property
    def mobile_url(self):
        if not self.manager_api.check_health(identity=self.sandbox_id):
            raise RuntimeError(f"Sandbox {self.sandbox_id} is not healthy")

        info = self.get_info()
        # 'path' and 'remote_path' are conceptually different:
        # 'path' is used for local URLs,
        # 'remote_path' for remote URLs. In this implementation,
        # both point to "/websockify/".
        # If the endpoints diverge in the future,
        # update these values accordingly.
        path = "/websockify/"
        remote_path = "/websockify/"
        params = {"password": info["runtime_token"]}

        if self.base_url is None:
            return urljoin(info["url"], path) + "?" + urlencode(params)

        return (
            f"{self.base_url}/desktop/{self.sandbox_id}{remote_path}"
            f"?{urlencode(params)}"
        )


class AsyncMobileMixin:
    async def get_mobile_url_async(self):
        """
        Asynchronously retrieve the mobile VNC/websockify connection URL.

        Returns:
            str: Fully qualified URL to access the mobile sandbox UI remotely.

        Raises:
            RuntimeError: If the sandbox is not healthy.
        """
        # Check health asynchronously
        is_healthy = await self.manager_api.check_health_async(
            identity=self.sandbox_id,
        )
        if not is_healthy:
            raise RuntimeError(f"Sandbox {self.sandbox_id} is not healthy")

        # Get container info asynchronously
        info = await self.get_info_async()

        # Local path and remote path (currently the same)
        path = "/websockify/"
        remote_path = "/websockify/"
        params = {"password": info["runtime_token"]}

        # Local URL if base_url is not set
        if self.base_url is None:
            return urljoin(info["url"], path) + "?" + urlencode(params)

        # Remote URL
        return (
            f"{self.base_url}/desktop/{self.sandbox_id}{remote_path}"
            f"?{urlencode(params)}"
        )


@SandboxRegistry.register(
    build_image_uri("runtime-sandbox-mobile"),
    sandbox_type=SandboxType.MOBILE,
    security_level="high",
    timeout=TIMEOUT,
    description="Mobile Sandbox",
    runtime_config={"privileged": True},
)
class MobileSandbox(MobileMixin, Sandbox):
    _host_check_done = False

    def __init__(  # pylint: disable=useless-parent-delegation
        self,
        sandbox_id: Optional[str] = None,
        timeout: int = 3000,
        base_url: Optional[str] = None,
        bearer_token: Optional[str] = None,
        sandbox_type: SandboxType = SandboxType.MOBILE,
    ):
        if base_url is None and not self.__class__._host_check_done:
            _check_host_readiness()
            self.__class__._host_check_done = True

        super().__init__(
            sandbox_id,
            timeout,
            base_url,
            bearer_token,
            sandbox_type,
        )

    def adb_use(
        self,
        action: str,
        coordinate: Optional[List[int]] = None,
        start: Optional[List[int]] = None,
        end: Optional[List[int]] = None,
        duration: Optional[int] = None,
        code: Optional[Union[int, str]] = None,
        text: Optional[str] = None,
    ):
        """A general-purpose method to execute various ADB actions.

        This function acts as a low-level dispatcher for
        different ADB commands. Only the parameters relevant
        to the specified `action` should be provided.
        For actions involving coordinates, the values are absolute
        pixels, with the origin (0, 0) at the top-left of the screen.

        Args:
            action (str): The specific ADB action to perform.
                Examples: 'tap', 'swipe', 'input_text', 'key_event',
                'get_screenshot', 'get_screen_resolution'.
            coordinate (Optional[List[int]]):
                The [x, y] coordinates for a 'tap' action.
            start (Optional[List[int]]):
                The starting [x, y] coordinates for a 'swipe' action.
            end (Optional[List[int]]):
                The ending [x, y] coordinates for a 'swipe' action.
            duration (int, optional):
                The duration of a 'swipe' gesture in milliseconds.
            code (int | str, optional):
                The key event code (e.g., 3) or name
                (e.g., 'HOME') for the 'key_event' action.
            text (Optional[str]):
                The text string to be entered for the 'input_text' action.
        """
        payload = {"action": action}
        if coordinate is not None:
            payload["coordinate"] = coordinate
        if start is not None:
            payload["start"] = start
        if end is not None:
            payload["end"] = end
        if duration is not None:
            payload["duration"] = duration
        if code is not None:
            payload["code"] = code
        if text is not None:
            payload["text"] = text

        return self.call_tool("adb", payload)

    def mobile_get_screen_resolution(self):
        """Get the screen resolution of the connected mobile device."""
        return self.call_tool("adb", {"action": "get_screen_resolution"})

    def mobile_tap(self, coordinate: List[int]):
        """Tap a specific coordinate on the screen.

        Args:
            coordinate (List[int]):
                The screen coordinates for the tap location.
        """
        return self.call_tool(
            "adb",
            {"action": "tap", "coordinate": coordinate},
        )

    def mobile_swipe(
        self,
        start: List[int],
        end: List[int],
        duration: Optional[int] = None,
    ):
        """
        Perform a swipe gesture on the screen
        from a start point to an end point.

        Args:
            start (List[int]):
                The starting coordinates [x, y] in pixels.
            end (List[int]):
                The ending coordinates [x, y] in pixels.
            duration (Optional[int]):
                The duration of the swipe in milliseconds.
        """
        return self.call_tool(
            "adb",
            {
                "action": "swipe",
                "start": start,
                "end": end,
                **({} if duration is None else {"duration": duration}),
            },
        )

    def mobile_input_text(self, text: str):
        """Input a text string into the currently focused UI element.

        Args:
            text (str): The string to be inputted.
        """
        return self.call_tool("adb", {"action": "input_text", "text": text})

    def mobile_key_event(self, code: Union[int, str]):
        """Send an Android key event to the device.

        Args:
            code (Union[int, str]): The key event code (e.g., 3 for HOME) or a
                              string representation (e.g., 'HOME', 'BACK').
        """
        return self.call_tool("adb", {"action": "key_event", "code": code})

    def mobile_get_screenshot(self):
        """Take a screenshot of the current device screen."""
        return self.call_tool("adb", {"action": "get_screenshot"})


@SandboxRegistry.register(
    build_image_uri("runtime-sandbox-mobile"),
    sandbox_type=SandboxType.MOBILE_ASYNC,
    security_level="high",
    timeout=TIMEOUT,
    description="Mobile Sandbox (Async)",
    runtime_config={"privileged": True},
)
class MobileSandboxAsync(MobileMixin, AsyncMobileMixin, SandboxAsync):
    _host_check_done = False

    def __init__(
        self,
        sandbox_id: Optional[str] = None,
        timeout: int = 3000,
        base_url: Optional[str] = None,
        bearer_token: Optional[str] = None,
        sandbox_type: SandboxType = SandboxType.MOBILE_ASYNC,
    ):
        if base_url is None and not self.__class__._host_check_done:
            _check_host_readiness()
            self.__class__._host_check_done = True

        super().__init__(
            sandbox_id,
            timeout,
            base_url,
            bearer_token,
            sandbox_type,
        )

    async def adb_use(
        self,
        action: str,
        coordinate: Optional[List[int]] = None,
        start: Optional[List[int]] = None,
        end: Optional[List[int]] = None,
        duration: Optional[int] = None,
        code: Optional[Union[int, str]] = None,
        text: Optional[str] = None,
    ):
        """
        Asynchronously execute a general-purpose ADB action.
        """
        payload = {"action": action}
        if coordinate is not None:
            payload["coordinate"] = coordinate
        if start is not None:
            payload["start"] = start
        if end is not None:
            payload["end"] = end
        if duration is not None:
            payload["duration"] = duration
        if code is not None:
            payload["code"] = code
        if text is not None:
            payload["text"] = text

        return await self.call_tool_async("adb", payload)

    async def mobile_get_screen_resolution(self):
        """Asynchronously get the screen resolution."""
        return await self.call_tool_async(
            "adb",
            {"action": "get_screen_resolution"},
        )

    async def mobile_tap(self, coordinate: List[int]):
        """Asynchronously tap specific screen coordinates."""
        return await self.call_tool_async(
            "adb",
            {"action": "tap", "coordinate": coordinate},
        )

    async def mobile_swipe(
        self,
        start: List[int],
        end: List[int],
        duration: Optional[int] = None,
    ):
        """Asynchronously perform a swipe gesture."""
        payload = {
            "action": "swipe",
            "start": start,
            "end": end,
        }
        if duration is not None:
            payload["duration"] = duration
        return await self.call_tool_async("adb", payload)

    async def mobile_input_text(self, text: str):
        """Asynchronously input text into the focused UI element."""
        return await self.call_tool_async(
            "adb",
            {"action": "input_text", "text": text},
        )

    async def mobile_key_event(self, code: Union[int, str]):
        """Asynchronously send a key event to the device."""
        return await self.call_tool_async(
            "adb",
            {"action": "key_event", "code": code},
        )

    async def mobile_get_screenshot(self):
        """Asynchronously take a screenshot."""
        return await self.call_tool_async("adb", {"action": "get_screenshot"})
