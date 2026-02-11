# -*- coding: utf-8 -*-
from .generic import generic_router
from .mcp import mcp_router
from .runtime_watcher import watcher_router
from .workspace import router as workspace_router

__all__ = [
    "mcp_router",
    "generic_router",
    "watcher_router",
    "workspace_router",
]
