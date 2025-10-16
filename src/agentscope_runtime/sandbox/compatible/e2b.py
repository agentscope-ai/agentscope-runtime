# -*- coding: utf-8 -*-
# pylint: disable=unused-argument,protected-access

import os
from urllib.parse import urlparse
from e2b.connection_config import ConnectionConfig
from e2b_code_interpreter import Sandbox


def e2b_patch(
    base_url: str = "http://localhost:8000",
    bearer_token: str = None,
):
    """
    Monkey-patch E2B Sandbox so it connects to a custom proxy.

    Args:
        bearer_token: Auth token for E2B API (mapped to E2B_API_KEY env var)
        base_url: Proxy base URL, e.g. http://127.0.0.1:8000
                  Will be parsed to extract host:port for internal use.

    Example:
        ```python
        from e2b_code_interpreter import Sandbox
        from agentscope_runtime.sandbox.compatible.e2b import e2b_patch

        # Apply patch once
        e2b_patch(base_url="http://127.0.0.1:8000")

        # Then use Sandbox normally
        with Sandbox.create() as sandbox:
            sandbox.run_code("x = 1")
            execution = sandbox.run_code("x += 1; x")
            print(execution, execution.text)  # should output 2
        ```
    """

    # Keep original environment variable names
    os.environ["E2B_API_KEY"] = bearer_token or "DUMMY"

    if base_url:
        # Parse to get just host:port
        parsed = urlparse(base_url)
        host_port = parsed.netloc if parsed.netloc else parsed.path
        if not host_port:
            raise ValueError(f"Invalid base_url: {base_url}")
        os.environ["E2B_DOMAIN"] = host_port
    else:
        raise RuntimeError(
            "E2B patching is not supported without remote sandbox server.",
        )

    # ---------------- Monkey Patch ---------------------
    _old_init = ConnectionConfig.__init__

    def _new_init(self, *args, **kwargs):
        _old_init(self, *args, **kwargs)
        self.api_url = f"http://{self.domain}"

    ConnectionConfig.__init__ = _new_init

    def patch_jupyter_url(self):
        return f"http://{host_port}"

    Sandbox._jupyter_url = property(patch_jupyter_url)
