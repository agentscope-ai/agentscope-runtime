# -*- coding: utf-8 -*-
from .custom import *
from .box.base.base_sandbox import BaseSandbox
from .box.browser.browser_sandbox import BrowserSandbox
from .box.filesystem.filesystem_sandbox import FilesystemSandbox
from .box.gui.gui_sandbox import GuiSandbox
from .box.training_box.training_box import TrainingSandbox
from .box.cloud.cloud_sandbox import CloudSandbox
from .box.agentbay.agentbay_sandbox import AgentbaySandbox
from .box.cloud_api.cloud_computer_sandbox import CloudComputerSandbox
from .box.cloud_api.cloud_phone_sandbox import CloudPhoneSandbox
from .box.e2b.e2b_sandbox import E2bSandBox

__all__ = [
    "BaseSandbox",
    "BrowserSandbox",
    "FilesystemSandbox",
    "GuiSandbox",
    "TrainingSandbox",
    "CloudSandbox",
    "AgentbaySandbox",
    "CloudComputerSandbox",
    "CloudPhoneSandbox",
    "E2bSandBox",
]
