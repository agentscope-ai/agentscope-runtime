# -*- coding: utf-8 -*-
from typing import Optional

from ..utils import build_image_uri
from ..registry import SandboxRegistry
from ..enums import SandboxType
from ..box.base import BaseSandbox
from ..box.gui import GUIMixin


@SandboxRegistry.register(
    build_image_uri("runtime-sandbox-alias"),
    sandbox_type="alias",
    security_level="high",
    timeout=30,
    description="Alias Sandbox - 支持filesystem + playwright MCP servers",
)
class AliasSandbox(GUIMixin, BaseSandbox):
    """
    Alias项目专用沙箱
    - 继承GUIMixin提供GUI功能支持
    - 使用官方镜像: agentscope/runtime-sandbox-alias:latest
    - 支持filesystem和playwright MCP servers
    - 实现Agent级别沙箱隔离
    """

    def __init__(
        self,
        sandbox_id: Optional[str] = None,
        timeout: int = 3000,
        base_url: Optional[str] = None,
        bearer_token: Optional[str] = None,
        sandbox_type: SandboxType = "alias",
    ):
        # 确保sandbox_type是SandboxType枚举（兼容字符串输入）
        if isinstance(sandbox_type, str):
            sandbox_type = SandboxType(sandbox_type)

        super().__init__(
            sandbox_id,
            timeout,
            base_url,
            bearer_token,
            sandbox_type,
        )