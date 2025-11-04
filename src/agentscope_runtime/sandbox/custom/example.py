# -*- coding: utf-8 -*-
from typing import Optional

from ..utils import build_image_uri
from ..registry import SandboxRegistry
from ..enums import SandboxType
from ..box.sandbox import Sandbox
from ..constant import TIMEOUT

SANDBOX_TYPE = "example"


@SandboxRegistry.register(
    build_image_uri(f"runtime-sandbox-{SANDBOX_TYPE}"),
    sandbox_type=SANDBOX_TYPE,
    security_level="medium",
    timeout=TIMEOUT,
    description="Example sandbox",
)
class ExampleSandbox(Sandbox):
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
            SandboxType(SANDBOX_TYPE),
        )
        raise NotImplementedError(
            "This sandbox is just a template and not implemented yet.",
        )
