# -*- coding: utf-8 -*-
from typing import Optional, Union, Tuple, List

from urllib.parse import urljoin, urlencode

from ...utils import build_image_uri
from ...registry import SandboxRegistry
from ...enums import SandboxType
from ...box.base import BaseSandbox


@SandboxRegistry.register(
    build_image_uri("runtime-sandbox-gui"),
    sandbox_type=SandboxType.GUI,
    security_level="high",
    timeout=30,
    description="GUI Sandbox",
)
class GuiSandbox(BaseSandbox):
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

    @property
    def desktop_url(self):
        info = self.get_info()
        path = "/vnc/vnc_lite.html"
        remote_path = "/vnc/vnc_relay.html"
        params = {
            "password": info["runtime_token"],
        }

        if self.base_url is None:
            full_url = urljoin(info["url"], path) + "?" + urlencode(params)
            return full_url

        # Should align with app.py
        return (
            f"{self.base_url}/desktop/{self.sandbox_id}{remote_path}"
            f"?{urlencode(params)}"
        )

    def computer_use(
        self,
        action: str,
        coordinate: Optional[Union[List[float], Tuple[float, float]]] = None,
        text: Optional[str] = None,
    ):
        payload = {"action": action}
        if coordinate is not None:
            payload["coordinate"] = coordinate
        if text is not None:
            payload["text"] = text

        return self.call_tool("computer", payload)
