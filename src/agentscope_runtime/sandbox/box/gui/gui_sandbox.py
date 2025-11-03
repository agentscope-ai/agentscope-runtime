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
        payload = {"action": action}
        if coordinate is not None:
            payload["coordinate"] = coordinate
        if text is not None:
            payload["text"] = text

        return self.call_tool("computer", payload)
