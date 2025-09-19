# -*- coding: utf-8 -*-
try:
    from langgraph import version as langgraph_version

    version = langgraph_version.__version__
except ImportError:
    version = "unknown"

try:
    from langchain import __version__ as langchain_version

    version2 = langchain_version
except ImportError:
    version2 = "unknown"
