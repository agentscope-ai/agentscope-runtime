# -*- coding: utf-8 -*-
# Explicitly import all Sandbox classes so their modules execute immediately.
# This ensures SandboxRegistry.register() runs at import time.
# Without this, lazy loading delays module import and types may not be
# registered.
from .box.base.base_sandbox import BaseSandbox, BaseSandboxAsync
from .box.browser.browser_sandbox import BrowserSandbox, BrowserSandboxAsync
from .box.filesystem.filesystem_sandbox import (
    FilesystemSandbox,
    FilesystemSandboxAsync,
)
from .box.gui.gui_sandbox import GuiSandbox, GuiSandboxAsync
from .box.mobile.mobile_sandbox import MobileSandbox, MobileSandboxAsync
from .box.training_box.training_box import TrainingSandbox
from .box.cloud.cloud_sandbox import CloudSandbox
from .box.agentbay.agentbay_sandbox import AgentbaySandbox

__all__ = [
    "BaseSandbox",
    "BaseSandboxAsync",
    "BrowserSandbox",
    "BrowserSandboxAsync",
    "FilesystemSandbox",
    "FilesystemSandboxAsync",
    "GuiSandbox",
    "GuiSandboxAsync",
    "MobileSandbox",
    "MobileSandboxAsync",
    "TrainingSandbox",
    "CloudSandbox",
    "AgentbaySandbox",
]
