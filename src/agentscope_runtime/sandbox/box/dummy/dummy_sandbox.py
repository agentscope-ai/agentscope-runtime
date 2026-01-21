# -*- coding: utf-8 -*-
from typing import Optional

from ...registry import SandboxRegistry
from ...enums import SandboxType
from ...box.sandbox import Sandbox
from ...constant import TIMEOUT


@SandboxRegistry.register(
    "",
    sandbox_type=SandboxType.DUMMY,
    security_level="low",
    timeout=TIMEOUT,
    description="Dummy Sandbox",
)
class DummySandbox(Sandbox):
    def __init__(
        self,
        sandbox_id: Optional[str] = None,
        timeout: int = 3000,
        base_url: Optional[str] = None,
        bearer_token: Optional[str] = None,
        sandbox_type: SandboxType = SandboxType.DUMMY,
        workspace_dir: Optional[str] = None,
    ):
        super().__init__(
            sandbox_id,
            timeout,
            base_url,
            bearer_token,
            sandbox_type,
            workspace_dir,
        )
