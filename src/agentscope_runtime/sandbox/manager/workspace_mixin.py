# -*- coding: utf-8 -*-
"""
Workspace filesystem mixins for SandboxManager.

This module provides a single set of workspace APIs on SandboxManager that
works in BOTH SDK modes:

1) Embedded/local mode:
   - SandboxManager has no http_session/httpx_client.
   - It can connect to the runtime container directly via:
       _establish_connection(identity) / _establish_connection_async(identity)
   - Then it calls the runtime client's workspace_* APIs.

2) Remote mode:
   - SandboxManager has http_session/httpx_client and base_url.
   - It calls Manager(Server)'s streaming proxy endpoint:
       /proxy/{identity}/{path:path}
   - The proxy forwards request/response to runtime with streaming support.
"""
from __future__ import annotations

import os
import secrets
import asyncio

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

from ..constant import TIMEOUT


def _encode_multipart_formdata(fields: List[tuple], boundary: str) -> bytes:
    lines: List[bytes] = []
    b = boundary.encode()

    for name, value in fields:
        lines.append(b"--" + b)
        if isinstance(value, tuple):
            filename, content, content_type = value
            if isinstance(content, bytearray):
                content = bytes(content)
            if not isinstance(content, (bytes,)):
                raise TypeError(
                    f"file content must be bytes, got {type(content)}",
                )

            lines.append(
                f'Content-Disposition: form-data; name="{name}"; filename='
                f'"{filename}"'.encode(),
            )
            lines.append(f"Content-Type: {content_type}".encode())
            lines.append(b"")
            lines.append(content)
        else:
            if not isinstance(value, str):
                value = str(value)
            lines.append(
                f'Content-Disposition: form-data; name="{name}"'.encode(),
            )
            lines.append(b"")
            lines.append(value.encode("utf-8"))

    lines.append(b"--" + b + b"--")
    lines.append(b"")
    return b"\r\n".join(lines)


class ProxyBaseMixin:
    """
    Base helper to build Manager(Server) proxy URL in remote mode.

    Host class attributes:
      - base_url: str (remote mode only)

    Manager(Server) must expose:
      /proxy/{identity}/{path:path}
    """

    def proxy_url(self, identity: str, runtime_path: str) -> str:
        """
        Build the proxy URL for a runtime path.

        Args:
            identity: Sandbox/container identity
              (sandbox_id or container_name).
            runtime_path: Runtime path, e.g. "/workspace/file".

        Returns:
            A full URL like:
              {base_url}/proxy/{identity}/workspace/file
        """
        base_url = getattr(self, "base_url", None)
        if not base_url:
            raise RuntimeError(
                "proxy_url is only available in remote mode (base_url "
                "required).",
            )
        return (
            f"{base_url.rstrip('/')}/proxy/{identity}"
            f"/{runtime_path.lstrip('/')}"
        )


class WorkspaceFSSyncMixin(ProxyBaseMixin):
    """
    Sync workspace filesystem APIs for SandboxManager.

    Embedded mode requirements:
      - _establish_connection(identity) ->
        runtime client implementing workspace_* methods

    Remote mode requirements:
      - http_session: requests.Session
      - base_url: str
      - Manager(Server) provides /proxy/{identity}/{path:path}
    """

    # -------- internal helpers --------

    def _is_remote_mode(self) -> bool:
        return bool(getattr(self, "http_session", None))

    def _runtime_client(self, identity: str):
        return self._establish_connection(identity)

    # -------- public APIs (cover WorkspaceClient) --------

    def fs_read(
        self,
        identity: str,
        path: str,
        fmt: Literal["text", "bytes", "stream"] = "text",
        *,
        chunk_size: int = 1024 * 1024,
    ) -> Union[str, bytes, Iterator[bytes]]:
        """
        Read a workspace file.

        Args:
            identity: Sandbox/container identity.
            path: Workspace path.
            fmt: "text" | "bytes" | "stream".
            chunk_size: Only used for remote streaming downloads.

        Returns:
            str / bytes / Iterator[bytes]
        """
        if not self._is_remote_mode():
            client = self._runtime_client(identity)
            return client.workspace_read(path, fmt=fmt)

        url = self.proxy_url(identity, "/workspace/file")

        if fmt == "stream":
            r = self.http_session.get(
                url,
                params={"path": path, "format": "bytes"},
                stream=True,
                timeout=TIMEOUT,
            )
            r.raise_for_status()

            def gen() -> Iterator[bytes]:
                with r:
                    for c in r.iter_content(chunk_size=chunk_size):
                        if c:
                            yield c

            return gen()

        r = self.http_session.get(
            url,
            params={
                "path": path,
                "format": "text" if fmt == "text" else "bytes",
            },
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        return r.text if fmt == "text" else r.content

    def fs_write(
        self,
        identity: str,
        path: str,
        data: Union[str, bytes, bytearray, IO[bytes]],
        *,
        content_type: str = "application/octet-stream",
    ) -> Dict[str, Any]:
        """
        Write a workspace file. Supports streaming upload via file-like object.
        """
        if not self._is_remote_mode():
            client = self._runtime_client(identity)
            return client.workspace_write(
                path,
                data,
                content_type=content_type,
            )

        url = self.proxy_url(identity, "/workspace/file")

        headers: Dict[str, str] = {}
        if isinstance(data, str):
            body = data.encode("utf-8")
            headers["Content-Type"] = "text/plain; charset=utf-8"
        elif isinstance(data, (bytes, bytearray)):
            body = bytes(data)
            headers["Content-Type"] = content_type
        else:
            body = data
            headers["Content-Type"] = content_type

        r = self.http_session.put(
            url,
            params={"path": path},
            data=body,
            headers=headers,
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        return r.json()

    def fs_write_many(
        self,
        identity: str,
        files: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Batch upload files.

        Each item:
          {"path": "...", "data": <str|bytes|file-like>, "content_type": "..."}
        """
        if not self._is_remote_mode():
            client = self._runtime_client(identity)
            return client.workspace_write_many(files)

        multipart = []
        form_paths = []

        for item in files:
            p = item["path"]
            d = item["data"]
            ct = item.get("content_type", "application/octet-stream")

            form_paths.append(("paths", p))

            if isinstance(d, str):
                d = d.encode("utf-8")
                ct = "text/plain; charset=utf-8"

            filename = os.path.basename(p)

            if isinstance(d, (bytes, bytearray)):
                multipart.append(("files", (filename, bytes(d), ct)))
            else:
                multipart.append(("files", (filename, d, ct)))

        url = self.proxy_url(identity, "/workspace/files:batch")
        r = self.http_session.post(
            url,
            files=multipart,
            data=form_paths,
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        return r.json()

    def fs_list(
        self,
        identity: str,
        path: str,
        depth: Optional[int] = 1,
    ) -> List[Dict[str, Any]]:
        """
        List directory entries in workspace.
        """
        if not self._is_remote_mode():
            client = self._runtime_client(identity)
            return client.workspace_list(path, depth=depth)

        url = self.proxy_url(identity, "/workspace/list")
        r = self.http_session.get(
            url,
            params={"path": path, "depth": depth},
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        return r.json()

    def fs_exists(self, identity: str, path: str) -> bool:
        """
        Check if workspace entry exists.
        """
        if not self._is_remote_mode():
            client = self._runtime_client(identity)
            return client.workspace_exists(path)

        url = self.proxy_url(identity, "/workspace/exists")
        r = self.http_session.get(
            url,
            params={"path": path},
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        return bool(r.json().get("exists"))

    def fs_remove(self, identity: str, path: str) -> None:
        """
        Remove a workspace entry (file or directory).
        """
        if not self._is_remote_mode():
            client = self._runtime_client(identity)
            client.workspace_remove(path)
            return

        url = self.proxy_url(identity, "/workspace/entry")
        r = self.http_session.delete(
            url,
            params={"path": path},
            timeout=TIMEOUT,
        )
        r.raise_for_status()

    def fs_move(
        self,
        identity: str,
        source: str,
        destination: str,
    ) -> Dict[str, Any]:
        """
        Move/rename a workspace entry.
        """
        if not self._is_remote_mode():
            client = self._runtime_client(identity)
            return client.workspace_move(source, destination)

        url = self.proxy_url(identity, "/workspace/move")
        r = self.http_session.post(
            url,
            json={"source": source, "destination": destination},
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        return r.json()

    def fs_mkdir(self, identity: str, path: str) -> bool:
        """
        Create a directory in workspace.
        """
        if not self._is_remote_mode():
            client = self._runtime_client(identity)
            return client.workspace_mkdir(path)

        url = self.proxy_url(identity, "/workspace/mkdir")
        r = self.http_session.post(
            url,
            json={"path": path},
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        return bool(r.json().get("created"))

    def fs_write_from_path(
        self,
        identity: str,
        workspace_path: str,
        local_path: str,
        *,
        content_type: str = "application/octet-stream",
    ) -> Dict[str, Any]:
        """
        Stream upload a local file to workspace.

        In embedded mode: delegated to runtime client implementation.
        In remote mode: uploads via proxy using a file handle.
        """
        if not self._is_remote_mode():
            client = self._runtime_client(identity)
            return client.workspace_write_from_path(
                workspace_path,
                local_path,
                content_type=content_type,
            )

        with open(local_path, "rb") as f:
            return self.fs_write(
                identity,
                workspace_path,
                f,
                content_type=content_type,
            )


class WorkspaceFSAsyncMixin(ProxyBaseMixin):
    """
    Async workspace filesystem APIs for SandboxManager.

    Embedded mode requirements:
      - _establish_connection_async(identity) ->
        runtime async client implementing workspace_* async methods

    Remote mode requirements:
      - httpx_client: httpx.AsyncClient
      - base_url: str
      - Manager(Server) provides /proxy/{identity}/{path:path}
    """

    def _is_remote_mode_async(self) -> bool:
        return bool(getattr(self, "httpx_client", None))

    async def _runtime_client_async(self, identity: str):
        return await self._establish_connection_async(identity)

    async def _async_iter_file(
        self,
        f: IO[bytes],
        chunk_size: int = 1024 * 1024,
    ) -> AsyncIterator[bytes]:
        """
        Convert a sync file-like object into an async byte iterator.

        httpx.AsyncClient cannot accept a sync file object as `content=...`.
        This helper reads the file in a worker thread to avoid blocking the
        event loop.
        """
        while True:
            chunk = await asyncio.to_thread(f.read, chunk_size)
            if not chunk:
                break
            yield chunk

    async def fs_read_async(
        self,
        identity: str,
        path: str,
        fmt: Literal["text", "bytes", "stream"] = "text",
    ) -> Union[str, bytes, AsyncIterator[bytes]]:
        """
        Async read workspace file.

        Returns:
            str / bytes / AsyncIterator[bytes]
        """
        if not self._is_remote_mode_async():
            client = await self._runtime_client_async(identity)
            return await client.workspace_read(path, fmt=fmt)

        url = self.proxy_url(identity, "/workspace/file")

        if fmt == "stream":

            async def gen() -> AsyncIterator[bytes]:
                async with self.httpx_client.stream(
                    "GET",
                    url,
                    params={"path": path, "format": "bytes"},
                ) as r:
                    r.raise_for_status()
                    async for c in r.aiter_bytes():
                        if c:
                            yield c

            return gen()

        r = await self.httpx_client.get(
            url,
            params={
                "path": path,
                "format": "text" if fmt == "text" else "bytes",
            },
        )
        r.raise_for_status()
        return r.text if fmt == "text" else r.content

    async def fs_write_async(
        self,
        identity: str,
        path: str,
        data: Union[str, bytes, bytearray, IO[bytes]],
        *,
        content_type: str = "application/octet-stream",
    ) -> Dict[str, Any]:
        """
        Async write workspace file (stream upload supported).
        """
        if not self._is_remote_mode_async():
            client = await self._runtime_client_async(identity)
            return await client.workspace_write(
                path,
                data,
                content_type=content_type,
            )

        url = self.proxy_url(identity, "/workspace/file")

        headers: Dict[str, str] = {}
        if isinstance(data, str):
            body = data.encode("utf-8")
            headers["Content-Type"] = "text/plain; charset=utf-8"
        elif isinstance(data, (bytes, bytearray)):
            body = bytes(data)
            headers["Content-Type"] = content_type
        else:
            headers["Content-Type"] = content_type
            body = self._async_iter_file(data)

        r = await self.httpx_client.put(
            url,
            params={"path": path},
            content=body,
            headers=headers,
        )
        r.raise_for_status()
        return r.json()

    async def fs_write_many_async(
        self,
        identity: str,
        files: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Async batch upload files.
        """
        if not self._is_remote_mode_async():
            client = await self._runtime_client_async(identity)
            return await client.workspace_write_many(files)

        url = self.proxy_url(identity, "/workspace/files:batch")

        fields: List[tuple] = []
        for item in files:
            p = item["path"]
            d = item["data"]
            ct = item.get("content_type", "application/octet-stream")

            fields.append(("paths", p))

            if isinstance(d, str):
                content = d.encode("utf-8")
                ct = "text/plain; charset=utf-8"
            elif isinstance(d, (bytes, bytearray)):
                content = bytes(d)
            else:
                content = await asyncio.to_thread(d.read)
                if isinstance(content, str):
                    content = content.encode("utf-8")
                content = bytes(content)

            filename = os.path.basename(p) or "file"
            fields.append(("files", (filename, content, ct)))

        boundary = "----agentscope-" + secrets.token_hex(16)
        body = _encode_multipart_formdata(fields, boundary)
        headers = {"Content-Type": f"multipart/form-data; boundary={boundary}"}

        async def _body_chunks() -> AsyncIterator[bytes]:
            yield body

        r = await self.httpx_client.post(
            url,
            content=_body_chunks(),
            headers=headers,
        )
        r.raise_for_status()
        return r.json()

    async def fs_list_async(
        self,
        identity: str,
        path: str,
        depth: Optional[int] = 1,
    ) -> List[Dict[str, Any]]:
        """
        Async list workspace entries.
        """
        if not self._is_remote_mode_async():
            client = await self._runtime_client_async(identity)
            return await client.workspace_list(path, depth=depth)

        url = self.proxy_url(identity, "/workspace/list")
        r = await self.httpx_client.get(
            url,
            params={"path": path, "depth": depth},
        )
        r.raise_for_status()
        return r.json()

    async def fs_exists_async(self, identity: str, path: str) -> bool:
        """
        Async exists check.
        """
        if not self._is_remote_mode_async():
            client = await self._runtime_client_async(identity)
            return await client.workspace_exists(path)

        url = self.proxy_url(identity, "/workspace/exists")
        r = await self.httpx_client.get(
            url,
            params={"path": path},
        )
        r.raise_for_status()
        return bool(r.json().get("exists"))

    async def fs_remove_async(self, identity: str, path: str) -> None:
        """
        Async remove workspace entry.
        """
        if not self._is_remote_mode_async():
            client = await self._runtime_client_async(identity)
            await client.workspace_remove(path)
            return

        url = self.proxy_url(identity, "/workspace/entry")
        r = await self.httpx_client.delete(
            url,
            params={"path": path},
        )
        r.raise_for_status()

    async def fs_move_async(
        self,
        identity: str,
        source: str,
        destination: str,
    ) -> Dict[str, Any]:
        """
        Async move/rename workspace entry.
        """
        if not self._is_remote_mode_async():
            client = await self._runtime_client_async(identity)
            return await client.workspace_move(source, destination)

        url = self.proxy_url(identity, "/workspace/move")
        r = await self.httpx_client.post(
            url,
            json={"source": source, "destination": destination},
        )
        r.raise_for_status()
        return r.json()

    async def fs_mkdir_async(self, identity: str, path: str) -> bool:
        """
        Async mkdir.
        """
        if not self._is_remote_mode_async():
            client = await self._runtime_client_async(identity)
            return await client.workspace_mkdir(path)

        url = self.proxy_url(identity, "/workspace/mkdir")
        r = await self.httpx_client.post(
            url,
            json={"path": path},
        )
        r.raise_for_status()
        return bool(r.json().get("created"))

    async def fs_write_from_path_async(
        self,
        identity: str,
        workspace_path: str,
        local_path: str,
        *,
        content_type: str = "application/octet-stream",
    ) -> Dict[str, Any]:
        """
        Async upload local file to workspace_path.

        Note:
            Local disk reading here is synchronous (built-in `open`).
            If you need fully async disk I/O, use aiofiles.
        """
        if not self._is_remote_mode_async():
            client = await self._runtime_client_async(identity)
            return await client.workspace_write_from_path(
                workspace_path,
                local_path,
                content_type=content_type,
            )

        with open(local_path, "rb") as f:
            return await self.fs_write_async(
                identity,
                workspace_path,
                f,
                content_type=content_type,
            )


class WorkspaceFSMixin(WorkspaceFSSyncMixin, WorkspaceFSAsyncMixin):
    pass
