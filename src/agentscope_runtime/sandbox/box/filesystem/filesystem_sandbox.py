# -*- coding: utf-8 -*-
# pylint: disable=dangerous-default-value
from typing import Optional

from ...utils import build_image_uri
from ...registry import SandboxRegistry
from ...enums import SandboxType
from ...box.base import BaseSandbox, BaseSandboxAsync
from ...box.gui import GUIMixin, AsyncGUIMixin
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
        """Read the complete contents of a file.

        Args:
            path (str): Path to the file to read.
        """
        return self.call_tool("read_file", {"path": path})

    def read_multiple_files(self, paths: list):
        """Read the contents of multiple files simultaneously.

        Args:
            paths (list[str]): List of file paths to read.
        """
        return self.call_tool("read_multiple_files", {"paths": paths})

    def write_file(self, path: str, content: str):
        """Create a new file or overwrite an existing file with new content.

        Args:
            path (str): Path to the file to write.
            content (str): Content to write to the file.
        """
        return self.call_tool("write_file", {"path": path, "content": content})

    def edit_file(self, path: str, edits: list, dry_run: bool = False):
        """Make line-based edits to a text file.

        Args:
            path (str): Path to the file to edit.
            edits (list[dict]): List of edits to make. Each edit must contain:
                oldText (str): Text to search for (exact match).
                newText (str): Text to replace with.
            dry_run (bool): If True, preview the changes using git-style
                diff format.
        """
        return self.call_tool(
            "edit_file",
            {
                "path": path,
                "edits": edits,
                "dryRun": dry_run,
            },
        )

    def create_directory(self, path: str):
        """Create a new directory or ensure it exists.

        Args:
            path (str): Path to the directory to create.
        """
        return self.call_tool("create_directory", {"path": path})

    def list_directory(self, path: str):
        """
        Get a detailed listing of all files and directories in a specified
        path.

        Args:
            path (str): Path to list contents from.
        """
        return self.call_tool("list_directory", {"path": path})

    def directory_tree(self, path: str):
        """
        Get a recursive tree view of files and directories as a JSON structure.

        Args:
            path (str): Path to get tree structure from.
        """
        return self.call_tool("directory_tree", {"path": path})

    def move_file(self, source: str, destination: str):
        """Move or rename files and directories.

        Args:
            source (str): Source path to move from.
            destination (str): Destination path to move to.
        """
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
        """Recursively search for files and directories matching a pattern.

        Args:
            path (str): Starting path for the search.
            pattern (str): Pattern to match files/directories.
            exclude_patterns (list[str]): Patterns to exclude from the search.
        """
        return self.call_tool(
            "search_files",
            {
                "path": path,
                "pattern": pattern,
                "excludePatterns": exclude_patterns,
            },
        )

    def get_file_info(self, path: str):
        """
        Retrieve detailed metadata about a file or directory.

        Args:
            path (str): Path to the file or directory.
        """
        return self.call_tool("get_file_info", {"path": path})

    def list_allowed_directories(self):
        """
        Returns the list of directories that this serveris allowed to access.
        """
        return self.call_tool("list_allowed_directories", {})


@SandboxRegistry.register(
    build_image_uri("runtime-sandbox-filesystem"),
    sandbox_type=SandboxType.FILESYSTEM_ASYNC,
    security_level="medium",
    timeout=TIMEOUT,
    description="Filesystem sandbox (Async)",
)
class FilesystemSandboxAsync(GUIMixin, AsyncGUIMixin, BaseSandboxAsync):
    def __init__(  # pylint: disable=useless-parent-delegation
        self,
        sandbox_id: Optional[str] = None,
        timeout: int = 3000,
        base_url: Optional[str] = None,
        bearer_token: Optional[str] = None,
        sandbox_type: SandboxType = SandboxType.FILESYSTEM_ASYNC,
    ):
        super().__init__(
            sandbox_id,
            timeout,
            base_url,
            bearer_token,
            sandbox_type,
        )

    async def read_file(self, path: str):
        """Read the complete contents of a file."""
        return await self.call_tool_async("read_file", {"path": path})

    async def read_multiple_files(self, paths: list):
        """Read the contents of multiple files simultaneously."""
        return await self.call_tool_async(
            "read_multiple_files",
            {"paths": paths},
        )

    async def write_file(self, path: str, content: str):
        """Create or overwrite a file with new content."""
        return await self.call_tool_async(
            "write_file",
            {"path": path, "content": content},
        )

    async def edit_file(self, path: str, edits: list, dry_run: bool = False):
        """Make line-based edits to a text file."""
        return await self.call_tool_async(
            "edit_file",
            {
                "path": path,
                "edits": edits,
                "dryRun": dry_run,
            },
        )

    async def create_directory(self, path: str):
        """Create a new directory or ensure it exists."""
        return await self.call_tool_async("create_directory", {"path": path})

    async def list_directory(self, path: str):
        """Get a detailed listing of all files and directories."""
        return await self.call_tool_async("list_directory", {"path": path})

    async def directory_tree(self, path: str):
        """Get a recursive tree view of files and directories as JSON."""
        return await self.call_tool_async("directory_tree", {"path": path})

    async def move_file(self, source: str, destination: str):
        """Move or rename files and directories."""
        return await self.call_tool_async(
            "move_file",
            {"source": source, "destination": destination},
        )

    async def search_files(
        self,
        path: str,
        pattern: str,
        exclude_patterns: list = [],
    ):
        """Recursively search for files and directories matching a pattern."""
        return await self.call_tool_async(
            "search_files",
            {
                "path": path,
                "pattern": pattern,
                "excludePatterns": exclude_patterns,
            },
        )

    async def get_file_info(self, path: str):
        """Retrieve metadata about a file or directory."""
        return await self.call_tool_async("get_file_info", {"path": path})

    async def list_allowed_directories(self):
        """Returns directories this server can access."""
        return await self.call_tool_async("list_allowed_directories", {})
