# -*- coding: utf-8 -*-
"""
Workspace proxy mixins for SandboxManager (SDK side).

This file is designed for the "two-layer" architecture:
  SDK -> Manager(Server) -> Runtime(Container API)

In *remote mode*, SandboxManager talks to Manager(Server) via HTTP.
To support streaming upload/download for workspace APIs, the Manager(Server)
must expose a generic streaming proxy endpoint:

  /proxy/{identity}/{path:path}

The proxy endpoint should forward the request to the target runtime container,
injecting the runtime Authorization token, and streaming request/response
bodies without JSON-RPC wrapping.

These mixins provide a workspace-like API on SandboxManager by calling the
proxy endpoint, covering all WorkspaceClient methods:

  - fs_read / fs_write / fs_write_many
  - fs_list / fs_exists / fs_remove / fs_move / fs_mkdir
  - fs_write_from_path

Important:
  - Sync and async method names MUST NOT collide. Therefore, async variants use
    the `_async` suffix.
"""

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

from ..constant import TIMEOUT


class ProxyBaseMixin:
    """
    Base mixin for building proxy URLs to the Manager(Server).

    Host class requirements (remote mode):
      - self.base_url: str

    The Manager(Server) must expose:
      /proxy/{identity}/{path:path}

    which forwards to:
      {runtime_base_url}/{path}

    and injects runtime Authorization token automatically.
    """

    def proxy_url(self, identity: str, runtime_path: str) -> str:
        """
        Build a Manager(Server) proxy URL for a given runtime path.

        Args:
            identity: Sandbox/container identity (sandbox_id/container_name).
            runtime_path: Runtime path, e.g. "/workspace/file".

        Returns:
            Full URL to Manager(Server) proxy endpoint.
        """
        base_url = getattr(self, "base_url", None)
        if not base_url:
            raise RuntimeError(
                "Proxy is only available in remote mode (base_url required).",
            )
        runtime_path = runtime_path.lstrip("/")
        return f"{base_url.rstrip('/')}/proxy/{identity}/{runtime_path}"


class WorkspaceProxySyncMixin(ProxyBaseMixin):
    """
    Synchronous workspace proxy mixin for SandboxManager.

    Host class requirements:
      - self.http_session: requests.Session

    This mixin implements workspace APIs by calling the Manager(Server) proxy
    endpoint. It supports streaming downloads (fmt='stream') and streaming
    uploads (data is a file-like object).
    """

    def fs_read(
        self,
        identity: str,
        path: str,
        fmt: Literal["text", "bytes", "stream"] = "text",
        *,
        chunk_size: int = 1024 * 1024,
    ) -> Union[str, bytes, Iterator[bytes]]:
        """
        Read a file from runtime workspace via Manager(Server) proxy.

        Args:
            identity: Sandbox/container identity.
            path: Workspace file path.
            fmt: "text" | "bytes" | "stream".
            chunk_size: Chunk size for streaming response iteration.

        Returns:
            - str when fmt="text"
            - bytes when fmt="bytes"
            - Iterator[bytes] when fmt="stream"
        """
        url = self.proxy_url(identity, "/workspace/file")

        if fmt == "stream":
            r = self.http_session.get(  # type: ignore[attr-defined]
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

        r = self.http_session.get(  # type: ignore[attr-defined]
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
        Write a file to runtime workspace via Manager(Server) proxy.

        Args:
            identity: Sandbox/container identity.
            path: Workspace file path.
            data: str/bytes/file-like. If file-like, request body is streamed.
            content_type: Content-Type used when data is bytes or file-like.

        Returns:
            JSON dict from runtime (as returned by /workspace/file PUT).
        """
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

        r = self.http_session.put(  # type: ignore[attr-defined]
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
        Batch upload multiple files via Manager(Server) proxy.

        Args:
            identity: Sandbox/container identity.
            files: A list of items:
                {
                  "path": "dir/a.txt",
                  "data": <str|bytes|file-like>,
                  "content_type": "..."   # optional
                }

        Returns:
            List of JSON dicts from runtime.
        """
        multipart = []
        for item in files:
            p = item["path"]
            d = item["data"]
            ct = item.get("content_type", "application/octet-stream")

            if isinstance(d, str):
                d = d.encode("utf-8")
                ct = "text/plain; charset=utf-8"

            # requests format:
            #  (field, (filename, fileobj_or_bytes, content_type))
            if isinstance(d, (bytes, bytearray)):
                multipart.append(("files", (p, bytes(d), ct)))
            else:
                multipart.append(("files", (p, d, ct)))

        url = self.proxy_url(identity, "/workspace/files:batch")
        r = self.http_session.post(  # type: ignore[attr-defined]
            url,
            files=multipart,
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
        List workspace directory entries via proxy.

        Args:
            identity: Sandbox/container identity.
            path: Workspace directory path.
            depth: Depth of traversal.

        Returns:
            List of dict entries.
        """
        url = self.proxy_url(identity, "/workspace/list")
        r = self.http_session.get(  # type: ignore[attr-defined]
            url,
            params={"path": path, "depth": depth},
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        return r.json()

    def fs_exists(self, identity: str, path: str) -> bool:
        """
        Check if a workspace entry exists via proxy.

        Returns:
            True if exists.
        """
        url = self.proxy_url(identity, "/workspace/exists")
        r = self.http_session.get(  # type: ignore[attr-defined]
            url,
            params={"path": path},
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        return bool(r.json().get("exists"))

    def fs_remove(self, identity: str, path: str) -> None:
        """
        Remove a workspace entry (file or directory) via proxy.
        """
        url = self.proxy_url(identity, "/workspace/entry")
        r = self.http_session.delete(  # type: ignore[attr-defined]
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
        Move/rename a workspace entry via proxy.
        """
        url = self.proxy_url(identity, "/workspace/move")
        r = self.http_session.post(  # type: ignore[attr-defined]
            url,
            json={"source": source, "destination": destination},
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        return r.json()

    def fs_mkdir(self, identity: str, path: str) -> bool:
        """
        Create a workspace directory via proxy.

        Returns:
            True if created.
        """
        url = self.proxy_url(identity, "/workspace/mkdir")
        r = self.http_session.post(  # type: ignore[attr-defined]
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
        Stream upload a local file to runtime workspace via proxy.

        This avoids loading the whole file into memory on the SDK side.

        Args:
            identity: Sandbox/container identity.
            workspace_path: Target workspace path in runtime.
            local_path: Local filesystem path to upload.
            content_type: Content-Type for the uploaded file.

        Returns:
            JSON dict from runtime.
        """
        with open(local_path, "rb") as f:
            return self.fs_write(
                identity,
                workspace_path,
                f,
                content_type=content_type,
            )


class WorkspaceProxyAsyncMixin(ProxyBaseMixin):
    """
    Asynchronous workspace proxy mixin for SandboxManager.

    Host class requirements:
      - self.httpx_client: httpx.AsyncClient

    Async method names use the `_async` suffix to avoid name collisions with
    the sync mixin (Python MRO would otherwise overwrite methods).
    """

    async def fs_read_async(
        self,
        identity: str,
        path: str,
        fmt: Literal["text", "bytes", "stream"] = "text",
    ) -> Union[str, bytes, AsyncIterator[bytes]]:
        """
        Async read a file from workspace via proxy.

        Returns:
            - str when fmt="text"
            - bytes when fmt="bytes"
            - AsyncIterator[bytes] when fmt="stream"
        """
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

        r = await self.httpx_client.get(  # type: ignore[attr-defined]
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
        Async write a file to workspace via proxy (streaming supported).

        Returns:
            JSON dict from runtime.
        """
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

        r = await self.httpx_client.put(  # type: ignore[attr-defined]
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
        Async batch upload files via proxy.
        """
        multipart = []
        for item in files:
            p = item["path"]
            d = item["data"]
            ct = item.get("content_type", "application/octet-stream")

            if isinstance(d, str):
                d = d.encode("utf-8")
                ct = "text/plain; charset=utf-8"

            if isinstance(d, (bytes, bytearray)):
                multipart.append(("files", (p, bytes(d), ct)))
            else:
                multipart.append(("files", (p, d, ct)))

        url = self.proxy_url(identity, "/workspace/files:batch")
        r = await self.httpx_client.post(  # type: ignore[attr-defined]
            url,
            files=multipart,
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
        Async list workspace entries via proxy.
        """
        url = self.proxy_url(identity, "/workspace/list")
        r = await self.httpx_client.get(  # type: ignore[attr-defined]
            url,
            params={"path": path, "depth": depth},
        )
        r.raise_for_status()
        return r.json()

    async def fs_exists_async(self, identity: str, path: str) -> bool:
        """
        Async exists check via proxy.
        """
        url = self.proxy_url(identity, "/workspace/exists")
        r = await self.httpx_client.get(  # type: ignore[attr-defined]
            url,
            params={"path": path},
        )
        r.raise_for_status()
        return bool(r.json().get("exists"))

    async def fs_remove_async(self, identity: str, path: str) -> None:
        """
        Async remove a workspace entry via proxy.
        """
        url = self.proxy_url(identity, "/workspace/entry")
        r = await self.httpx_client.delete(  # type: ignore[attr-defined]
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
        Async move/rename a workspace entry via proxy.
        """
        url = self.proxy_url(identity, "/workspace/move")
        r = await self.httpx_client.post(  # type: ignore[attr-defined]
            url,
            json={"source": source, "destination": destination},
        )
        r.raise_for_status()
        return r.json()

    async def fs_mkdir_async(self, identity: str, path: str) -> bool:
        """
        Async mkdir via proxy.
        """
        url = self.proxy_url(identity, "/workspace/mkdir")
        r = await self.httpx_client.post(  # type: ignore[attr-defined]
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
        Async stream upload a local file to workspace via proxy.

        Note:
            Local disk reading here is synchronous (built-in `open`).
            If you need fully async disk I/O, use aiofiles and pass the stream.
        """
        with open(local_path, "rb") as f:
            return await self.fs_write_async(
                identity,
                workspace_path,
                f,
                content_type=content_type,
            )
