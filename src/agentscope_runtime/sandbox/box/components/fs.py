# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import (
    IO,
    Any,
    AsyncIterator,
    Dict,
    Iterator,
    List,
    Literal,
    Optional,
    Union,
)


class SandboxFS:
    """
    Sync filesystem facade bound to a Sandbox instance.

    Expected Sandbox interface:
      - sandbox.sandbox_id: Optional[str]
      - sandbox.manager_api: SandboxManager (with fs_* methods)
    """

    def __init__(self, sandbox) -> None:
        self._sandbox = sandbox

    @property
    def sandbox_id(self) -> str:
        sid = self._sandbox.sandbox_id
        if not sid:
            raise RuntimeError(
                "Sandbox is not started yet (sandbox_id is None).",
            )
        return sid

    def read(
        self,
        path: str,
        fmt: Literal["text", "bytes", "stream"] = "text",
        *,
        chunk_size: int = 1024 * 1024,
    ) -> Union[str, bytes, Iterator[bytes]]:
        """
        Read a workspace file.
        """
        return self._sandbox.manager_api.fs_read(
            self.sandbox_id,
            path,
            fmt=fmt,
            chunk_size=chunk_size,
        )

    def write(
        self,
        path: str,
        data: Union[str, bytes, bytearray, IO[bytes]],
        *,
        content_type: str = "application/octet-stream",
    ) -> Dict[str, Any]:
        """
        Write a workspace file (supports file-like streaming upload).
        """
        return self._sandbox.manager_api.fs_write(
            self.sandbox_id,
            path,
            data,
            content_type=content_type,
        )

    def write_many(self, files: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Batch upload multiple files.
        """
        return self._sandbox.manager_api.fs_write_many(self.sandbox_id, files)

    def list(
        self,
        path: str,
        depth: Optional[int] = 1,
    ) -> List[Dict[str, Any]]:
        """
        List workspace entries.
        """
        return self._sandbox.manager_api.fs_list(
            self.sandbox_id,
            path,
            depth=depth,
        )

    def exists(self, path: str) -> bool:
        """
        Check if a workspace entry exists.
        """
        return self._sandbox.manager_api.fs_exists(self.sandbox_id, path)

    def remove(self, path: str) -> None:
        """
        Remove a workspace entry (file or directory).
        """
        return self._sandbox.manager_api.fs_remove(self.sandbox_id, path)

    def move(self, source: str, destination: str) -> Dict[str, Any]:
        """
        Move/rename a workspace entry.
        """
        return self._sandbox.manager_api.fs_move(
            self.sandbox_id,
            source,
            destination,
        )

    def mkdir(self, path: str) -> bool:
        """
        Create a workspace directory.
        """
        return self._sandbox.manager_api.fs_mkdir(self.sandbox_id, path)

    def write_from_path(
        self,
        workspace_path: str,
        local_path: str,
        *,
        content_type: str = "application/octet-stream",
    ) -> Dict[str, Any]:
        """
        Stream upload a local file to workspace.
        """
        return self._sandbox.manager_api.fs_write_from_path(
            self.sandbox_id,
            workspace_path,
            local_path,
            content_type=content_type,
        )


class SandboxFSAsync:
    """
    Async filesystem facade bound to a SandboxAsync instance.

    Expected SandboxAsync interface:
      - sandbox.sandbox_id: Optional[str]
      - sandbox.manager_api: SandboxManager (with fs_*_async methods)
    """

    def __init__(self, sandbox) -> None:
        self._sandbox = sandbox

    @property
    def sandbox_id(self) -> str:
        sid = self._sandbox.sandbox_id
        if not sid:
            raise RuntimeError(
                "Sandbox is not started yet (sandbox_id is None).",
            )
        return sid

    async def read_async(
        self,
        path: str,
        fmt: Literal["text", "bytes", "stream"] = "text",
    ) -> Union[str, bytes, AsyncIterator[bytes]]:
        """
        Async read a workspace file.

        If fmt="stream", returns an AsyncIterator[bytes].
        """
        return await self._sandbox.manager_api.fs_read_async(
            self.sandbox_id,
            path,
            fmt=fmt,
        )

    async def write_async(
        self,
        path: str,
        data: Union[str, bytes, bytearray, IO[bytes]],
        *,
        content_type: str = "application/octet-stream",
    ) -> Dict[str, Any]:
        """
        Async write a workspace file (supports file-like streaming upload).
        """
        return await self._sandbox.manager_api.fs_write_async(
            self.sandbox_id,
            path,
            data,
            content_type=content_type,
        )

    async def write_many_async(
        self,
        files: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Async batch upload multiple files.
        """
        return await self._sandbox.manager_api.fs_write_many_async(
            self.sandbox_id,
            files,
        )

    async def list_async(
        self,
        path: str,
        depth: Optional[int] = 1,
    ) -> List[Dict[str, Any]]:
        """
        Async list workspace entries.
        """
        return await self._sandbox.manager_api.fs_list_async(
            self.sandbox_id,
            path,
            depth=depth,
        )

    async def exists_async(self, path: str) -> bool:
        """
        Async exists check.
        """
        return await self._sandbox.manager_api.fs_exists_async(
            self.sandbox_id,
            path,
        )

    async def remove_async(self, path: str) -> None:
        """
        Async remove workspace entry.
        """
        return await self._sandbox.manager_api.fs_remove_async(
            self.sandbox_id,
            path,
        )

    async def move_async(
        self,
        source: str,
        destination: str,
    ) -> Dict[str, Any]:
        """
        Async move/rename workspace entry.
        """
        return await self._sandbox.manager_api.fs_move_async(
            self.sandbox_id,
            source,
            destination,
        )

    async def mkdir_async(self, path: str) -> bool:
        """
        Async mkdir.
        """
        return await self._sandbox.manager_api.fs_mkdir_async(
            self.sandbox_id,
            path,
        )

    async def write_from_path_async(
        self,
        workspace_path: str,
        local_path: str,
        *,
        content_type: str = "application/octet-stream",
    ) -> Dict[str, Any]:
        """
        Async stream upload a local file to workspace.

        Note:
            local file reading is synchronous in the manager mixin
            implementation.
        """
        return await self._sandbox.manager_api.fs_write_from_path_async(
            self.sandbox_id,
            workspace_path,
            local_path,
            content_type=content_type,
        )
