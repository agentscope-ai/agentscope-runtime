# -*- coding: utf-8 -*-
from typing import TYPE_CHECKING
from ..common.utils.lazy_loader import install_lazy_loader
from .custom import *

if TYPE_CHECKING:
    from .box.base.base_sandbox import BaseSandbox
    from .box.browser.browser_sandbox import BrowserSandbox
    from .box.filesystem.filesystem_sandbox import FilesystemSandbox
    from .box.gui.gui_sandbox import GuiSandbox
    from .box.training_box.training_box import TrainingSandbox
    from .box.cloud.cloud_sandbox import CloudSandbox
    from .box.agentbay.agentbay_sandbox import AgentbaySandbox
    from .box.mobile.mobile_sandbox import MobileSandbox

install_lazy_loader(
    globals(),
    {
        "BaseSandbox": ".box.base.base_sandbox",
        "BrowserSandbox": ".box.browser.browser_sandbox",
        "FilesystemSandbox": ".box.filesystem.filesystem_sandbox",
        "GuiSandbox": ".box.gui.gui_sandbox",
        "TrainingSandbox": ".box.training_box.training_box",
        "CloudSandbox": ".box.cloud.cloud_sandbox",
        "AgentbaySandbox": ".box.agentbay.agentbay_sandbox",
        "MobileSandbox": ".box.mobile.mobile_sandbox",
    },
)
