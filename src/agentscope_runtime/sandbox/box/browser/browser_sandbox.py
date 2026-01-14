# -*- coding: utf-8 -*-
# pylint: disable=too-many-public-methods
from typing import Optional
from urllib.parse import urlparse, urlunparse

from ...utils import build_image_uri
from ...registry import SandboxRegistry
from ...enums import SandboxType
from ...box.base import BaseSandbox, BaseSandboxAsync
from ...box.gui import GUIMixin, AsyncGUIMixin
from ...constant import TIMEOUT


def http_to_ws(url, use_localhost=True):
    parsed = urlparse(url)
    ws_scheme = "wss" if parsed.scheme == "https" else "ws"

    hostname = parsed.hostname
    if use_localhost and hostname == "127.0.0.1":
        hostname = "localhost"

    if parsed.port:
        new_netloc = f"{hostname}:{parsed.port}"
    else:
        new_netloc = hostname

    ws_url = urlunparse(parsed._replace(scheme=ws_scheme, netloc=new_netloc))
    return ws_url


@SandboxRegistry.register(
    build_image_uri("runtime-sandbox-browser"),
    sandbox_type=SandboxType.BROWSER,
    security_level="medium",
    timeout=TIMEOUT,
    description="Browser sandbox",
)
class BrowserSandbox(GUIMixin, BaseSandbox):
    def __init__(  # pylint: disable=useless-parent-delegation
        self,
        sandbox_id: Optional[str] = None,
        timeout: int = 3000,
        base_url: Optional[str] = None,
        bearer_token: Optional[str] = None,
        sandbox_type: SandboxType = SandboxType.BROWSER,
    ):
        super().__init__(
            sandbox_id,
            timeout,
            base_url,
            bearer_token,
            sandbox_type,
        )

    def browser_close(self):
        """Close the current browser page."""
        return self.call_tool("browser_close", {})

    def browser_resize(self, width: int, height: int):
        """Resize the browser window.

        Args:
            width (int): Width of the browser window.
            height (int): Height of the browser window.
        """
        return self.call_tool(
            "browser_resize",
            {"width": width, "height": height},
        )

    def browser_console_messages(self):
        """Return all console messages from the browser."""
        return self.call_tool("browser_console_messages", {})

    def browser_handle_dialog(self, accept: bool, prompt_text: str = ""):
        """Handle a dialog popup.

        Args:
            accept (bool): Whether to accept the dialog.
            prompt_text (str, optional): Text to input if the dialog is a
                prompt.
        """
        return self.call_tool(
            "browser_handle_dialog",
            {"accept": accept, "promptText": prompt_text},
        )

    def browser_file_upload(self, paths: list):
        """Upload one or multiple files in the browser.

        Args:
            paths (list[str]): Absolute paths to the files to upload.
        """
        return self.call_tool("browser_file_upload", {"paths": paths})

    def browser_press_key(self, key: str):
        """Press a key on the keyboard.

        Args:
            key (str): Name of the key to press or a character to enter.
        """
        return self.call_tool("browser_press_key", {"key": key})

    def browser_navigate(self, url: str):
        """Navigate to a specified URL.

        Args:
            url (str): The URL to load in the browser.
        """
        return self.call_tool("browser_navigate", {"url": url})

    def browser_navigate_back(self):
        """Go back to the previous page."""
        return self.call_tool("browser_navigate_back", {})

    def browser_navigate_forward(self):
        """Go forward to the next page."""
        return self.call_tool("browser_navigate_forward", {})

    def browser_network_requests(self):
        """Return all network requests since the page was loaded."""
        return self.call_tool("browser_network_requests", {})

    def browser_pdf_save(self, filename: str = ""):
        """Save the current page as a PDF.

        Args:
            filename (str, optional): File name to save the PDF as.
        """
        return self.call_tool("browser_pdf_save", {"filename": filename})

    def browser_take_screenshot(
        self,
        raw: bool = False,
        filename: str = "",
        element: str = "",
        ref: str = "",
    ):
        """Take a screenshot of the current page or of a specific element.

        Args:
            raw (bool, optional): If True, save in PNG without compression.
                Defaults to False (JPEG).
            filename (str, optional): File name for the screenshot.
            element (str, optional): Human-readable element description to
                screenshot.
            ref (str, optional): Exact element reference from the page
                snapshot.
        """
        return self.call_tool(
            "browser_take_screenshot",
            {"raw": raw, "filename": filename, "element": element, "ref": ref},
        )

    def browser_snapshot(self):
        """Capture an accessibility snapshot of the current page."""
        return self.call_tool("browser_snapshot", {})

    def browser_click(self, element: str, ref: str):
        """Click on an element in the current page.

        Args:
            element (str): Human-readable element description to click.
            ref (str): Exact element reference from the page snapshot.
        """
        return self.call_tool(
            "browser_click",
            {"element": element, "ref": ref},
        )

    def browser_drag(
        self,
        start_element: str,
        start_ref: str,
        end_element: str,
        end_ref: str,
    ):
        """Drag from one element and drop onto another.

        Args:
            start_element (str): Human-readable source element description.
            start_ref (str): Exact source element reference.
            end_element (str): Human-readable target element description.
            end_ref (str): Exact target element reference.
        """
        return self.call_tool(
            "browser_drag",
            {
                "startElement": start_element,
                "startRef": start_ref,
                "endElement": end_element,
                "endRef": end_ref,
            },
        )

    def browser_hover(self, element: str, ref: str):
        """Hover over an element in the current page.

        Args:
            element (str): Human-readable element description.
            ref (str): Exact element reference from the page snapshot.
        """
        return self.call_tool(
            "browser_hover",
            {"element": element, "ref": ref},
        )

    def browser_type(
        self,
        element: str,
        ref: str,
        text: str,
        submit: bool = False,
        slowly: bool = False,
    ):
        """Type text into an editable element.

        Args:
            element (str): Human-readable element description.
            ref (str): Exact element reference.
            text (str): Text to type into the element.
            submit (bool, optional): Press Enter after typing. Defaults to
                False.
            slowly (bool, optional): Type one character at a time. Defaults
                to False.
        """
        return self.call_tool(
            "browser_type",
            {
                "element": element,
                "ref": ref,
                "text": text,
                "submit": submit,
                "slowly": slowly,
            },
        )

    def browser_select_option(self, element: str, ref: str, values: list):
        """Select options in a dropdown.

        Args:
            element (str): Human-readable element description.
            ref (str): Exact element reference.
            values (list[str]): Values to select.
        """
        return self.call_tool(
            "browser_select_option",
            {"element": element, "ref": ref, "values": values},
        )

    def browser_tab_list(self):
        """List all browser tabs."""
        return self.call_tool("browser_tab_list", {})

    def browser_tab_new(self, url: str = ""):
        """Open a new browser tab.

        Args:
            url (str, optional): URL to open in the new tab. Blank if not
                provided.
        """
        return self.call_tool("browser_tab_new", {"url": url})

    def browser_tab_select(self, index: int):
        """Select a browser tab by index.

        Args:
            index (int): Index of the tab to select.
        """
        return self.call_tool("browser_tab_select", {"index": index})

    def browser_tab_close(self, index: int = None):
        """Close a browser tab.

        Args:
            index (int, optional): Index of the tab to close.
            Closes current tab if not provided.
        """
        return self.call_tool("browser_tab_close", {"index": index})

    def browser_wait_for(
        self,
        time: float = None,
        text: str = None,
        text_gone: str = None,
    ):
        """Wait for text to appear/disappear or for a specified time.

        Args:
            time (float, optional): Seconds to wait.
            text (str, optional): Text to wait for.
            text_gone (str, optional): Text to wait to disappear.
        """
        return self.call_tool(
            "browser_wait_for",
            {
                "time": time,
                "text": text,
                "textGone": text_gone,
            },
        )


@SandboxRegistry.register(
    build_image_uri("runtime-sandbox-browser"),
    sandbox_type=SandboxType.BROWSER_ASYNC,
    security_level="medium",
    timeout=TIMEOUT,
    description="Browser sandbox (Async)",
)
class BrowserSandboxAsync(GUIMixin, AsyncGUIMixin, BaseSandboxAsync):
    def __init__(  # pylint: disable=useless-parent-delegation
        self,
        sandbox_id: Optional[str] = None,
        timeout: int = 3000,
        base_url: Optional[str] = None,
        bearer_token: Optional[str] = None,
        sandbox_type: SandboxType = SandboxType.BROWSER_ASYNC,
    ):
        super().__init__(
            sandbox_id,
            timeout,
            base_url,
            bearer_token,
            sandbox_type,
        )

    async def browser_close(self):
        """Close the current browser page."""
        return await self.call_tool_async("browser_close", {})

    async def browser_resize(self, width: int, height: int):
        """Resize the browser window."""
        return await self.call_tool_async(
            "browser_resize",
            {"width": width, "height": height},
        )

    async def browser_console_messages(self):
        """Return all console messages from the browser."""
        return await self.call_tool_async("browser_console_messages", {})

    async def browser_handle_dialog(self, accept: bool, prompt_text: str = ""):
        """Handle a dialog popup."""
        return await self.call_tool_async(
            "browser_handle_dialog",
            {"accept": accept, "promptText": prompt_text},
        )

    async def browser_file_upload(self, paths: list):
        """Upload one or multiple files."""
        return await self.call_tool_async(
            "browser_file_upload",
            {"paths": paths},
        )

    async def browser_press_key(self, key: str):
        """Press a key in the browser."""
        return await self.call_tool_async("browser_press_key", {"key": key})

    async def browser_navigate(self, url: str):
        """Navigate to a URL."""
        return await self.call_tool_async("browser_navigate", {"url": url})

    async def browser_navigate_back(self):
        """Go back in browser history."""
        return await self.call_tool_async("browser_navigate_back", {})

    async def browser_navigate_forward(self):
        """Go forward in browser history."""
        return await self.call_tool_async("browser_navigate_forward", {})

    async def browser_network_requests(self):
        """Return network requests."""
        return await self.call_tool_async("browser_network_requests", {})

    async def browser_pdf_save(self, filename: str = ""):
        """Save page as a PDF."""
        return await self.call_tool_async(
            "browser_pdf_save",
            {"filename": filename},
        )

    async def browser_take_screenshot(
        self,
        raw=False,
        filename="",
        element="",
        ref="",
    ):
        """Take a screenshot."""
        return await self.call_tool_async(
            "browser_take_screenshot",
            {"raw": raw, "filename": filename, "element": element, "ref": ref},
        )

    async def browser_snapshot(self):
        """Accessibility snapshot."""
        return await self.call_tool_async("browser_snapshot", {})

    async def browser_click(self, element: str, ref: str):
        """Click an element."""
        return await self.call_tool_async(
            "browser_click",
            {"element": element, "ref": ref},
        )

    async def browser_drag(
        self,
        start_element: str,
        start_ref: str,
        end_element: str,
        end_ref: str,
    ):
        """Drag and drop."""
        return await self.call_tool_async(
            "browser_drag",
            {
                "startElement": start_element,
                "startRef": start_ref,
                "endElement": end_element,
                "endRef": end_ref,
            },
        )

    async def browser_hover(self, element: str, ref: str):
        """Hover over an element."""
        return await self.call_tool_async(
            "browser_hover",
            {"element": element, "ref": ref},
        )

    async def browser_type(
        self,
        element: str,
        ref: str,
        text: str,
        submit=False,
        slowly=False,
    ):
        """Type text into an element."""
        return await self.call_tool_async(
            "browser_type",
            {
                "element": element,
                "ref": ref,
                "text": text,
                "submit": submit,
                "slowly": slowly,
            },
        )

    async def browser_select_option(
        self,
        element: str,
        ref: str,
        values: list,
    ):
        """Select options in a dropdown."""
        return await self.call_tool_async(
            "browser_select_option",
            {"element": element, "ref": ref, "values": values},
        )

    async def browser_tab_list(self):
        """List all tabs."""
        return await self.call_tool_async("browser_tab_list", {})

    async def browser_tab_new(self, url: str = ""):
        """Open a new tab."""
        return await self.call_tool_async("browser_tab_new", {"url": url})

    async def browser_tab_select(self, index: int):
        """Select tab by index."""
        return await self.call_tool_async(
            "browser_tab_select",
            {"index": index},
        )

    async def browser_tab_close(self, index: int = None):
        """Close a tab."""
        return await self.call_tool_async(
            "browser_tab_close",
            {"index": index},
        )

    async def browser_wait_for(
        self,
        time: float = None,
        text: str = None,
        text_gone: str = None,
    ):
        """Wait for text or time."""
        return await self.call_tool_async(
            "browser_wait_for",
            {"time": time, "text": text, "textGone": text_gone},
        )
