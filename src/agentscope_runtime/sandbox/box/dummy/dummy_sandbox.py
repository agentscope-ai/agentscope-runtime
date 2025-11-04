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
    ):
        self._sandbox_id = sandbox_id
        self.sandbox_type = sandbox_type
