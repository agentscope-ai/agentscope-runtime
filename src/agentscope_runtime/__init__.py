# -*- coding: utf-8 -*-
from .version import __version__
from .common.utils.logging import setup_logger

setup_logger()

__all__ = ["__version__"]
