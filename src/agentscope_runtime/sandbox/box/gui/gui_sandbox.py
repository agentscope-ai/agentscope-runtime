# -*- coding: utf-8 -*-
# flake8: noqa: E501
import logging
from typing import Optional, Union, Tuple, List

from urllib.parse import urljoin, urlencode

from ...utils import build_image_uri, get_platform
from ...registry import SandboxRegistry
from ...enums import SandboxType
from ...box.base import BaseSandbox, BaseSandboxAsync
from ...constant import TIMEOUT

logger = logging.getLogger(__name__)


class GUIMixin:
    @property
    def desktop_url(self):
        if not self.manager_api.check_health(identity=self.sandbox_id):
            raise RuntimeError(f"Sandbox {self.sandbox_id} is not healthy")

        info = self.get_info()
        path = "/vnc/vnc_lite.html"
        remote_path = "/vnc/vnc_relay.html"
        params = {"password": info["runtime_token"]}

        if self.base_url is None:
            return urljoin(info["url"], path) + "?" + urlencode(params)

        return (
            f"{self.base_url}/desktop/{self.sandbox_id}{remote_path}"
            f"?{urlencode(params)}"
        )


class AsyncGUIMixin:
    async def get_desktop_url_async(self):
        # Check sandbox health asynchronously
        is_healthy = await self.manager_api.check_health_async(
            identity=self.sandbox_id,
        )
        if not is_healthy:
            raise RuntimeError(f"Sandbox {self.sandbox_id} is not healthy")

        # Retrieve container information asynchronously
        info = await self.get_info_async()

        # Default local VNC path and remote VNC relay path
        path = "/vnc/vnc_lite.html"
        remote_path = "/vnc/vnc_relay.html"
        params = {"password": info["runtime_token"]}

        # If base_url is not set, construct the local URL
        if self.base_url is None:
            return urljoin(info["url"], path) + "?" + urlencode(params)

        # Construct the remote URL with sandbox ID and VNC relay path
        return (
            f"{self.base_url}/desktop/{self.sandbox_id}{remote_path}"
            f"?{urlencode(params)}"
        )


@SandboxRegistry.register(
    build_image_uri("runtime-sandbox-gui"),
    sandbox_type=SandboxType.GUI,
    security_level="high",
    timeout=TIMEOUT,
    description="GUI Sandbox",
)
class GuiSandbox(GUIMixin, BaseSandbox):
    def __init__(  # pylint: disable=useless-parent-delegation
        self,
        sandbox_id: Optional[str] = None,
        timeout: int = 3000,
        base_url: Optional[str] = None,
        bearer_token: Optional[str] = None,
        sandbox_type: SandboxType = SandboxType.GUI,
    ):
        super().__init__(
            sandbox_id,
            timeout,
            base_url,
            bearer_token,
            sandbox_type,
        )
        if get_platform() == "linux/arm64":
            logger.warning(
                "\nCompatibility Notice: This GUI Sandbox may have issues on "
                "arm64 CPU architectures, due to the computer-use-mcp does "
                "not provide linux/arm64 compatibility. It has been tested "
                "to work on Apple M4 chips with Rosetta enabled. However, "
                "on M1, M2, and M3 chips, chromium browser might crash due "
                "to the missing SSE3 instruction set.",
            )

    def computer_use(
        self,
        action: str,
        coordinate: Optional[Union[List[float], Tuple[float, float]]] = None,
        text: Optional[str] = None,
    ):
        """Use a mouse and keyboard to interact with a computer, and take screenshots.

        This is an interface to a desktop GUI. You do not have access to a terminal or
        applications menu. You must click on desktop icons to start applications.

        Guidelines:
            * Always prefer using keyboard shortcuts rather than clicking, where possible.
            * If you see boxes with two letters in them, typing these letters will click
              that element. Use this instead of other shortcuts or clicking, where possible.
            * Some applications may take time to start or process actions, so you may
              need to wait and take successive screenshots to see the results of your
              actions. For example, if you click on Firefox and a window doesn't open,
              try taking another screenshot.
            * Whenever you intend to move the cursor to click on an element (like an icon),
              consult a screenshot to determine the coordinates of the element before moving
              the cursor.
            * If clicking on a program or link fails to load, even after waiting, try adjusting
              your cursor position so that the tip falls visually on the element you want to click.
            * Make sure to click any buttons, links, icons, etc., with the cursor tip in the center
              of the element. Don't click boxes on their edges unless asked.

        Args:
            action (str): The action to perform. Options are:
                * `key`: Press a key or key-combination on the keyboard.
                * `type`: Type a string of text.
                * `get_cursor_position`: Get the current (x, y) pixel coordinate of the cursor.
                * `mouse_move`: Move the cursor to a specified (x, y) coordinate.
                * `left_click`: Click the left mouse button.
                * `left_click_drag`: Click and drag to a specified coordinate.
                * `right_click`: Click the right mouse button.
                * `middle_click`: Click the middle mouse button.
                * `double_click`: Double-click the left mouse button.
                * `get_screenshot`: Take a screenshot of the screen.
            coordinate (list[float] | tuple[float, float], optional):
                The (x, y) pixel coordinates.
                x = pixels from the left edge, y = pixels from the top edge.
            text (str, optional): Text to type or key command to execute.

        Returns:
            Any: Result of performing the specified computer action.
        """
        payload = {"action": action}
        if coordinate is not None:
            payload["coordinate"] = coordinate
        if text is not None:
            payload["text"] = text

        return self.call_tool("computer", payload)


@SandboxRegistry.register(
    build_image_uri("runtime-sandbox-gui"),
    sandbox_type=SandboxType.GUI_ASYNC,
    security_level="high",
    timeout=TIMEOUT,
    description="GUI Sandbox (Async)",
)
class GuiSandboxAsync(GUIMixin, AsyncGUIMixin, BaseSandboxAsync):
    def __init__(  # pylint: disable=useless-parent-delegation
        self,
        sandbox_id: Optional[str] = None,
        timeout: int = 3000,
        base_url: Optional[str] = None,
        bearer_token: Optional[str] = None,
        sandbox_type: SandboxType = SandboxType.GUI_ASYNC,
    ):
        super().__init__(
            sandbox_id,
            timeout,
            base_url,
            bearer_token,
            sandbox_type,
        )
        # Architecture compatibility warning
        if get_platform() == "linux/arm64":
            logger.warning(
                "\nCompatibility Notice: This GUI Sandbox may have issues on "
                "arm64 CPU architectures, due to the computer-use-mcp not "
                "providing linux/arm64 compatibility. It has been tested "
                "on Apple M4 chips with Rosetta enabled. However, on M1, M2, "
                "and M3 chips, Chromium browser might crash due to the missing "
                "SSE3 instruction set.",
            )

    async def computer_use(
        self,
        action: str,
        coordinate: Optional[Union[List[float], Tuple[float, float]]] = None,
        text: Optional[str] = None,
    ):
        """
        Asynchronously use mouse and keyboard to interact with a desktop GUI.

        This method interfaces with the sandbox's GUI environment.
        You do not have access to a terminal or applications menu;
        interaction is performed by clicking on desktop icons or using
        keyboard shortcuts.

        Guidelines:
            * Prefer keyboard shortcuts where possible over cursor actions.
            * If visual keyboard hints (two-letter boxes) are shown, typing
              those letters will click the element — use this where possible.
            * Applications or actions may require waiting; e.g., repeat
              screenshots if windows don’t open immediately.
            * Always determine cursor coordinates using screenshots before moving
              the cursor to click on elements.
            * If clicks fail to load content, try adjusting cursor coordinates to
              center on the target element.
            * Click with the cursor tip centered on elements, not on edges.

        Args:
            action (str): The action to perform. Options include:
                * `key` — Press a key or key combination.
                * `type` — Type a string of text.
                * `get_cursor_position` — Get current cursor coordinates (x, y).
                * `mouse_move` — Move cursor to given (x, y).
                * `left_click` — Left mouse click.
                * `left_click_drag` — Click and drag to given (x, y).
                * `right_click` — Right mouse click.
                * `middle_click` — Middle mouse click.
                * `double_click` — Double left mouse click.
                * `get_screenshot` — Capture screen screenshot.
            coordinate (list[float] | tuple[float, float], optional):
                Pixel coordinates (x from left edge, y from top edge).
            text (str, optional): String to type, or key-combination for `key` action.

        Returns:
            Any: Tool execution result from the sandbox.
        """
        payload = {"action": action}
        if coordinate is not None:
            payload["coordinate"] = coordinate
        if text is not None:
            payload["text"] = text

        return await self.call_tool_async("computer", payload)
