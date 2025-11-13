# -*- coding: utf-8 -*-
import os

from typing import Optional

from ..utils import build_image_uri
from ..registry import SandboxRegistry
from ..enums import SandboxType
from ..box.sandbox import Sandbox
from ..constant import TIMEOUT

SANDBOX_TYPE = "custom_sandbox"


@SandboxRegistry.register(
    build_image_uri(f"runtime-sandbox-{SANDBOX_TYPE}"),
    sandbox_type=SANDBOX_TYPE,
    security_level="medium",
    timeout=TIMEOUT,
    description="my sandbox",
    environment={
        "TAVILY_API_KEY": os.getenv("TAVILY_API_KEY", ""),
        "AMAP_MAPS_API_KEY": os.getenv("AMAP_MAPS_API_KEY", ""),
    },
)
class CustomSandbox(Sandbox):
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
