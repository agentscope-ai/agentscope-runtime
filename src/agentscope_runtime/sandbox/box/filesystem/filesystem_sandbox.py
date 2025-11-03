# -*- coding: utf-8 -*-
# pylint: disable=dangerous-default-value
from typing import Optional

from ...utils import build_image_uri
from ...registry import SandboxRegistry
from ...enums import SandboxType
from ...box.base import BaseSandbox
from ...box.gui import GUIMixin
from ...constant import TIMEOUT


@SandboxRegistry.register(
    build_image_uri("runtime-sandbox-filesystem"),
    sandbox_type=SandboxType.FILESYSTEM,
    security_level="medium",
    timeout=TIMEOUT,
    description="Filesystem sandbox",
)
class FilesystemSandbox(GUIMixin, BaseSandbox):
    def __init__(  # pylint: disable=useless-parent-delegation
        self,
        sandbox_id: Optional[str] = None,
        timeout: int = 3000,
        base_url: Optional[str] = None,
        bearer_token: Optional[str] = None,
        sandbox_type: SandboxType = SandboxType.FILESYSTEM,
    ):
        super().__init__(
            sandbox_id,
            timeout,
            base_url,
            bearer_token,
            sandbox_type,
        )

    def read_file(self, path: str):
        return self.call_tool("read_file", {"path": path})

    def read_multiple_files(self, paths: list):
        return self.call_tool("read_multiple_files", {"paths": paths})

    def write_file(self, path: str, content: str):
        return self.call_tool("write_file", {"path": path, "content": content})

    def edit_file(self, path: str, edits: list, dry_run: bool = False):
        return self.call_tool(
            "edit_file",
            {
                "path": path,
                "edits": edits,
                "dryRun": dry_run,
            },
        )

    def create_directory(self, path: str):
        return self.call_tool("create_directory", {"path": path})

    def list_directory(self, path: str):
        return self.call_tool("list_directory", {"path": path})

    def directory_tree(self, path: str):
        return self.call_tool("directory_tree", {"path": path})

    def move_file(self, source: str, destination: str):
        return self.call_tool(
            "move_file",
            {"source": source, "destination": destination},
        )

    def search_files(
        self,
        path: str,
        pattern: str,
        exclude_patterns: list = [],
    ):
        return self.call_tool(
            "search_files",
            {
                "path": path,
                "pattern": pattern,
                "excludePatterns": exclude_patterns,
            },
        )

    def get_file_info(self, path: str):
        return self.call_tool("get_file_info", {"path": path})

    def list_allowed_directories(self):
        return self.call_tool("list_allowed_directories", {})
