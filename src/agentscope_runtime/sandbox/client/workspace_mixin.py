# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import asyncio
from typing import (
    IO,
    Any,
    Dict,
    Iterator,
    List,
    Literal,
    Optional,
    Union,
    AsyncIterator,
)


async def _afile_iter(
    f: IO[bytes],
    chunk_size: int = 1024 * 1024,
) -> AsyncIterator[bytes]:
    """
    Convert a sync file object into an async byte iterator for
    httpx.AsyncClient.
    """
    while True:
        chunk = await asyncio.to_thread(f.read, chunk_size)
        if not chunk:
            break
        yield chunk


class WorkspaceMixin:
    """
    Mixin for /workspace router.
    Requires the host class to provide:
      - self.base_url: str
      - self.session: requests.Session
      - self.timeout: int|float
      - self.safe_request(method, url, **kwargs)
      - self._request(method, url, **kwargs)  (optional, for streaming)
    """

    def workspace_read(
        self,
        path: str,
        fmt: Literal["text", "bytes", "stream"] = "text",
        *,
        chunk_size: int = 1024 * 1024,
    ) -> Union[str, bytes, Iterator[bytes]]:
        """
        Read a workspace file.

        - fmt="text": returns str
        - fmt="bytes": returns bytes
        - fmt="stream": returns Iterator[bytes]
        """
        url = f"{self.base_url}/workspace/file"

        if fmt == "stream":

            def gen() -> Iterator[bytes]:
                # Use raw request to keep the Response open during iteration.
                r = self._request(
                    "get",
                    url,
                    params={"path": path, "format": "bytes"},
                    stream=True,
                )
                r.raise_for_status()
                try:
                    for chunk in r.iter_content(chunk_size=chunk_size):
                        if chunk:
                            yield chunk
                finally:
                    r.close()

            return gen()

        r = self._request(
            "get",
            url,
            params={
                "path": path,
                "format": "text" if fmt == "text" else "bytes",
            },
        )
        r.raise_for_status()
        return r.text if fmt == "text" else r.content

    def workspace_write(
        self,
        path: str,
        data: Union[str, bytes, bytearray, IO[bytes]],
        *,
        content_type: str = "application/octet-stream",
    ) -> Dict[str, Any]:
        """
        Write a file to workspace. Supports streaming when data is file-like.
        """
        url = f"{self.base_url}/workspace/file"

        headers: Dict[str, str] = {}
        body: Union[bytes, IO[bytes]]

        if isinstance(data, str):
            body = data.encode("utf-8")
            headers["Content-Type"] = "text/plain; charset=utf-8"
        elif isinstance(data, (bytes, bytearray)):
            body = bytes(data)
            headers["Content-Type"] = content_type
        else:
            body = data
            headers["Content-Type"] = content_type

        r = self._request(
            "put",
            url,
            params={"path": path},
            data=body,
            headers=headers,
        )
        r.raise_for_status()
        return r.json()

    def workspace_write_many(
        self,
        files: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Batch upload multiple files via multipart/form-data.

        Server supports:
          - files: List[UploadFile] = File(...)
          - paths: List[str] = Form(...)

        We send `paths` explicitly to avoid relying on UploadFile.filename
        preserving directory components.
        """
        url = f"{self.base_url}/workspace/files:batch"

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

            # requests `files=` format: (fieldname, (filename,
            # fileobj/bytes, content_type))
            filename = os.path.basename(p)
            if isinstance(d, (bytes, bytearray)):
                multipart.append(("files", (filename, bytes(d), ct)))
            else:
                multipart.append(("files", (filename, d, ct)))

        r = self._request(
            "post",
            url,
            files=multipart,
            data=form_paths,
        )
        r.raise_for_status()
        return r.json()

    def workspace_list(
        self,
        path: str,
        depth: Optional[int] = 1,
    ) -> List[Dict[str, Any]]:
        return self.safe_request(
            "get",
            f"{self.base_url}/workspace/list",
            params={"path": path, "depth": depth},
        )

    def workspace_exists(self, path: str) -> bool:
        data = self.safe_request(
            "get",
            f"{self.base_url}/workspace/exists",
            params={"path": path},
        )
        return bool(isinstance(data, dict) and data.get("exists"))

    def workspace_remove(self, path: str) -> None:
        r = self._request(
            "delete",
            f"{self.base_url}/workspace/entry",
            params={"path": path},
        )
        r.raise_for_status()

    def workspace_move(self, source: str, destination: str) -> Dict[str, Any]:
        return self.safe_request(
            "post",
            f"{self.base_url}/workspace/move",
            json={"source": source, "destination": destination},
        )

    def workspace_mkdir(self, path: str) -> bool:
        data = self.safe_request(
            "post",
            f"{self.base_url}/workspace/mkdir",
            json={"path": path},
        )
        return bool(isinstance(data, dict) and data.get("created"))

    def workspace_write_from_path(
        self,
        workspace_path: str,
        local_path: str,
        *,
        content_type: str = "application/octet-stream",
    ) -> Dict[str, Any]:
        """
        Stream upload a local file to workspace_path.
        """
        with open(local_path, "rb") as f:
            return self.workspace_write(
                workspace_path,
                f,
                content_type=content_type,
            )


class WorkspaceAsyncMixin:
    """
    Async mixin for /workspace router.

    Requires the host class to provide:
      - self.base_url: str
      - self.client: httpx.AsyncClient
      - self.safe_request(method, url, **kwargs) -> awaitable
      - self._request(method, url, **kwargs) ->
        awaitable returning httpx.Response
    """

    async def workspace_read(
        self,
        path: str,
        fmt: Literal["text", "bytes", "stream"] = "text",
    ) -> Union[str, bytes, AsyncIterator[bytes]]:
        """
        Read a workspace file.

        - fmt="text": returns str
        - fmt="bytes": returns bytes
        - fmt="stream": returns AsyncIterator[bytes]
        """
        url = f"{self.base_url}/workspace/file"

        if fmt == "stream":

            async def gen() -> AsyncIterator[bytes]:
                async with self.client.stream(
                    "GET",
                    url,
                    params={"path": path, "format": "bytes"},
                ) as r:
                    r.raise_for_status()
                    async for chunk in r.aiter_bytes():
                        yield chunk

            return gen()

        r = await self._request(
            "get",
            url,
            params={
                "path": path,
                "format": "text" if fmt == "text" else "bytes",
            },
        )
        r.raise_for_status()
        return r.text if fmt == "text" else r.content

    async def workspace_write(
        self,
        path: str,
        data: Union[str, bytes, bytearray, IO[bytes]],
        *,
        content_type: str = "application/octet-stream",
    ) -> Dict[str, Any]:
        """
        Write a file to workspace. Streams when data is file-like.
        """
        url = f"{self.base_url}/workspace/file"

        headers: Dict[str, str] = {}
        body: Union[bytes, IO[bytes]]

        if isinstance(data, str):
            body = data.encode("utf-8")
            headers["Content-Type"] = "text/plain; charset=utf-8"
        elif isinstance(data, (bytes, bytearray)):
            body = bytes(data)
            headers["Content-Type"] = content_type
        else:
            # IMPORTANT: AsyncClient cannot stream from sync file-like
            # directly.
            headers["Content-Type"] = content_type
            body = _afile_iter(data)

        r = await self._request(
            "put",
            url,
            params={"path": path},
            content=body,  # NOTE: httpx uses `content=`
            headers=headers,
        )
        r.raise_for_status()
        return r.json()

    async def workspace_write_many(
        self,
        files: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Batch upload multiple files via multipart/form-data.

        Server supports:
          - files: List[UploadFile] = File(...)
          - paths: List[str] = Form(...)

        We send `paths` explicitly to avoid relying on UploadFile.filename
        preserving directory components.
        """
        url = f"{self.base_url}/workspace/files:batch"

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
                content_bytes = await asyncio.to_thread(d.read)
                multipart.append(("files", (filename, content_bytes, ct)))

        r = await self._request(
            "post",
            url,
            files=multipart,
            data=form_paths,
        )
        r.raise_for_status()
        return r.json()

    async def workspace_list(
        self,
        path: str,
        depth: Optional[int] = 1,
    ) -> List[Dict[str, Any]]:
        return await self.safe_request(
            "get",
            f"{self.base_url}/workspace/list",
            params={"path": path, "depth": depth},
        )

    async def workspace_exists(self, path: str) -> bool:
        data = await self.safe_request(
            "get",
            f"{self.base_url}/workspace/exists",
            params={"path": path},
        )
        return bool(isinstance(data, dict) and data.get("exists"))

    async def workspace_remove(self, path: str) -> None:
        r = await self._request(
            "delete",
            f"{self.base_url}/workspace/entry",
            params={"path": path},
        )
        r.raise_for_status()

    async def workspace_move(
        self,
        source: str,
        destination: str,
    ) -> Dict[str, Any]:
        return await self.safe_request(
            "post",
            f"{self.base_url}/workspace/move",
            json={"source": source, "destination": destination},
        )

    async def workspace_mkdir(self, path: str) -> bool:
        data = await self.safe_request(
            "post",
            f"{self.base_url}/workspace/mkdir",
            json={"path": path},
        )
        return bool(isinstance(data, dict) and data.get("created"))

    async def workspace_write_from_path(
        self,
        workspace_path: str,
        local_path: str,
        *,
        content_type: str = "application/octet-stream",
    ) -> Dict[str, Any]:
        """
        Stream upload a local file to workspace_path.
        (Note: reading local file is sync I/O; if you want fully async disk
        I/O, use aiofiles. This keeps the behavior consistent with your sync
        version.)
        """
        with open(local_path, "rb") as f:
            return await self.workspace_write(
                workspace_path,
                f,
                content_type=content_type,
            )
