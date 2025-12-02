# -*- coding: utf-8 -*-
# Explicitly import all Sandbox classes so their modules execute immediately.
# This ensures SandboxRegistry.register() runs at import time.
# Without this, lazy loading delays module import and types may not be
# registered.
from .box.base.base_sandbox import BaseSandbox
from .box.browser.browser_sandbox import BrowserSandbox
from .box.filesystem.filesystem_sandbox import FilesystemSandbox
from .box.gui.gui_sandbox import GuiSandbox
from .box.training_box.training_box import TrainingSandbox
from .box.cloud.cloud_sandbox import CloudSandbox
from .box.mobile.mobile_sandbox import MobileSandbox
from .box.agentbay.agentbay_sandbox import AgentbaySandbox

__all__ = [
    "BaseSandbox",
    "BrowserSandbox",
    "FilesystemSandbox",
    "GuiSandbox",
    "TrainingSandbox",
    "CloudSandbox",
    "MobileSandbox",
    "AgentbaySandbox",
]
