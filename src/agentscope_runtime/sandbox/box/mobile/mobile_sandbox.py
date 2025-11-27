# -*- coding: utf-8 -*-
import logging
import os
import platform
from typing import Optional, List, Union

from agentscope_runtime.sandbox.box.sandbox import Sandbox

from ...utils import build_image_uri
from ...registry import SandboxRegistry
from ...enums import SandboxType
from ...constant import TIMEOUT

logger = logging.getLogger(__name__)


class HostPrerequisiteError(Exception):
    """Custom exception raised when host prerequisites
    for MobileSandbox are not met."""


@SandboxRegistry.register(
    build_image_uri("runtime-sandbox-mobile"),
    sandbox_type=SandboxType.MOBILE,
    security_level="high",
    timeout=TIMEOUT,
    description="Mobile Sandbox",
    runtime_config={"privileged": True},
)
class MobileSandbox(Sandbox):
    _host_check_done = False

    def __init__(  # pylint: disable=useless-parent-delegation
        self,
        sandbox_id: Optional[str] = None,
        timeout: int = 3000,
        base_url: Optional[str] = None,
        bearer_token: Optional[str] = None,
        sandbox_type: SandboxType = SandboxType.MOBILE,
    ):
        if not self.__class__._host_check_done:
            self._check_host_readiness()
            self.__class__._host_check_done = True

        super().__init__(
            sandbox_id,
            timeout,
            base_url,
            bearer_token,
            sandbox_type,
        )

    def _check_host_readiness(self) -> None:
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

        if platform.system() == "Linux":
            required_devices = [
                "/dev/binder",
                "/dev/hwbinder",
                "/dev/vndbinder",
                "/dev/ashmem",
            ]

            missing_devices = [
                dev for dev in required_devices if not os.path.exists(dev)
            ]

            if missing_devices:
                error_message = (
                    f"\n========== HOST PREREQUISITE FAILED ==========\n"
                    f"MobileSandbox requires specific kernel \
                        modules on the host machine.\n"
                    f"The following required device files are missing:\n"
                    f"  - {', '.join(missing_devices)}\n\n"
                    "To fix this, please run the following \
                        commands on your Linux host:\n\n"
                    "1. Install extra kernel modules:\n"
                    "   sudo apt update && \
                        sudo apt install -y linux-modules-extra-`uname -r`\n\n"
                    "2. Load modules and create device nodes:\n"
                    '   sudo modprobe binder_linux devices=\
                        "binder,hwbinder,vndbinder"\n'
                    "   sudo modprobe ashmem_linux\n\n"
                    "After running these commands, verify with:\n"
                    "   ls -l /dev/binder* /dev/ashmem\n"
                    "=================================================="
                )
                raise HostPrerequisiteError(error_message)

        logger.info("Host environment check passed.")

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

    def mobile_tap(self, x: int, y: int):
        """Tap a specific coordinate on the screen.

        Args:
            x (int): The x-coordinate in pixels from the left edge.
            y (int): The y-coordinate in pixels from the top edge.
        """
        return self.call_tool("adb", {"action": "tap", "coordinate": [x, y]})

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
            start (Optional[List[int]]):
                The starting coordinates [x, y] in pixels.
            end (Optional[List[int]]):
                The ending coordinates [x, y] in pixels.
            duration (int, optional):
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
            code (int | str): The key event code (e.g., 3 for HOME) or a
                              string representation (e.g., 'HOME', 'BACK').
        """
        return self.call_tool("adb", {"action": "key_event", "code": code})

    def mobile_get_screenshot(self):
        """Take a screenshot of the current device screen."""
        return self.call_tool("adb", {"action": "get_screenshot"})
