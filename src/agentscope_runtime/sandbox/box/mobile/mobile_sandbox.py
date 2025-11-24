# -*- coding: utf-8 -*-
import logging
from typing import Optional, Union, Tuple, List

from urllib.parse import urljoin, urlencode

from ...utils import build_image_uri, get_platform
from ...registry import SandboxRegistry
from ...enums import SandboxType
from ...box.base import BaseSandbox
from ...constant import TIMEOUT

logger = logging.getLogger(__name__)


@SandboxRegistry.register(
    build_image_uri("runtime-sandbox-mobile"),
    sandbox_type=SandboxType.MOBILE,
    security_level="high",
    timeout=TIMEOUT,
    description="Mobile Sandbox",
    runtime_config={'privileged': True,}
)
class MobileSandbox(BaseSandbox):
    def __init__(  # pylint: disable=useless-parent-delegation
        self,
        sandbox_id: Optional[str] = None,
        timeout: int = 3000,
        base_url: Optional[str] = None,
        bearer_token: Optional[str] = None,
        sandbox_type: SandboxType = SandboxType.MOBILE,
    ):
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
        duration: int = None,
        code: int|str = None,
        text: Optional[str] = None,
    ):
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
        return self.call_tool("adb", {"action": "get_screen_resolution"})
    
    def mobile_tap(self, x: int, y: int):
        return self.call_tool("adb", {"action": "tap", "coordinate": [x, y]})
    
    def mobile_swipe(
            self,
            start: Optional[List[int]], 
            end: Optional[List[int]], 
            duration: int = None):
        return self.call_tool("adb", 
                              {"action": "swipe", "start": start, "end": end, 
                               **({} if duration is None else {"duration": duration})})
    
    def mobile_input_text(self, text: str):
        return self.call_tool("adb", {"action": "input_text", "text": text})
    
    def mobile_key_event(self, code: int|str):
        return self.call_tool("adb", {"action": "key_event", "code": code})
    
    def mobile_get_screenshot(self):
        return self.call_tool("adb", {"action": "get_screenshot"})