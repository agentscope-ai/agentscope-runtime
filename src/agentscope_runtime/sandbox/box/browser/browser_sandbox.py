# -*- coding: utf-8 -*-
# pylint: disable=too-many-public-methods
from typing import Optional
from urllib.parse import urlparse, urlunparse

from ...constant import IMAGE_TAG
from ...registry import SandboxRegistry
from ...enums import SandboxType
from ...box.sandbox import Sandbox


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
    f"agentscope/runtime-sandbox-browser:{IMAGE_TAG}",
    sandbox_type=SandboxType.BROWSER,
    security_level="medium",
    timeout=60,
    description="Browser sandbox",
)
class BrowserSandbox(Sandbox):
    def __init__(
        self,
        sandbox_id: Optional[str] = None,
        timeout: int = 3000,
        base_url: Optional[str] = None,
        bearer_token: Optional[str] = None,
    ):
        super().__init__(
            sandbox_id,
            timeout,
            base_url,
            bearer_token,
            SandboxType.BROWSER,
        )

    @property
    def browser_ws(self):
        if self.base_url is None:
            # Local mode
            return self.get_info()["front_browser_ws"]
        return http_to_ws(f"{self.base_url}/browser/{self.sandbox_id}/cast")

    def browser_close(self):
        return self.call_tool("browser_close", {})

    def browser_resize(self, width: int, height: int):
        return self.call_tool(
            "browser_resize",
            {"width": width, "height": height},
        )

    def browser_console_messages(self):
        return self.call_tool("browser_console_messages", {})

    def browser_handle_dialog(self, accept: bool, prompt_text: str = ""):
        return self.call_tool(
            "browser_handle_dialog",
            {"accept": accept, "promptText": prompt_text},
        )

    def browser_file_upload(self, paths: list):
        return self.call_tool("browser_file_upload", {"paths": paths})

    def browser_press_key(self, key: str):
        return self.call_tool("browser_press_key", {"key": key})

    def browser_navigate(self, url: str):
        return self.call_tool("browser_navigate", {"url": url})

    def browser_navigate_back(self):
        return self.call_tool("browser_navigate_back", {})

    def browser_navigate_forward(self):
        return self.call_tool("browser_navigate_forward", {})

    def browser_network_requests(self):
        return self.call_tool("browser_network_requests", {})

    def browser_pdf_save(self, filename: str = ""):
        return self.call_tool("browser_pdf_save", {"filename": filename})

    def browser_take_screenshot(
        self,
        raw: bool = False,
        filename: str = "",
        element: str = "",
        ref: str = "",
    ):
        return self.call_tool(
            "browser_take_screenshot",
            {
                "raw": raw,
                "filename": filename,
                "element": element,
                "ref": ref,
            },
        )

    def browser_snapshot(self):
        return self.call_tool("browser_snapshot", {})

    def browser_click(self, element: str, ref: str):
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
        return self.call_tool(
            "browser_select_option",
            {
                "element": element,
                "ref": ref,
                "values": values,
            },
        )

    def browser_tab_list(self):
        return self.call_tool("browser_tab_list", {})

    def browser_tab_new(self, url: str = ""):
        return self.call_tool("browser_tab_new", {"url": url})

    def browser_tab_select(self, index: int):
        return self.call_tool("browser_tab_select", {"index": index})

    def browser_tab_close(self, index: int = None):
        return self.call_tool("browser_tab_close", {"index": index})

    def browser_wait_for(
        self,
        time: float = None,
        text: str = None,
        text_gone: str = None,
    ):
        return self.call_tool(
            "browser_wait_for",
            {
                "time": time,
                "text": text,
                "textGone": text_gone,
            },
        )
