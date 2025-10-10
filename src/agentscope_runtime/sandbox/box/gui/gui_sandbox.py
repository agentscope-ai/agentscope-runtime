# -*- coding: utf-8 -*-
from typing import Optional, Union, Tuple, List

from urllib.parse import urljoin, urlencode

from ...utils import build_image_uri
from ...registry import SandboxRegistry
from ...enums import SandboxType
from ...box.sandbox import Sandbox


@SandboxRegistry.register(
    build_image_uri("runtime-sandbox-gui"),
    sandbox_type=SandboxType.GUI,
    security_level="high",
    timeout=30,
    description="GUI Sandbox",
)
class GuiSandbox(Sandbox):
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
            SandboxType.GUI,
        )

    @property
    def novnc_url(self):
        info = self.get_info()
        path = "/vnc/vnc_lite.html"
        params = {
            "password": info["runtime_token"],
        }

        if self.base_url is None:
            full_url = urljoin(info["url"], path) + "?" + urlencode(params)
            return full_url

        # TODO: Implement VNC in remote mode
        raise NotImplementedError("VNC is not supported in remote mode")

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
