# -*- coding: utf-8 -*-
import os
import shutil
from typing import Optional, Literal, List, Dict, Any, Tuple

import anyio
from fastapi import (
    APIRouter,
    HTTPException,
    Query,
    Request,
    UploadFile,
    File,
    Form,
)
from fastapi.responses import (
    PlainTextResponse,
    StreamingResponse,
    JSONResponse,
    Response,
)

router = APIRouter()

BASE_DIR = os.getenv("WORKSPACE_DIR", "/workspace")
CHUNK_SIZE = 1024 * 1024  # 1MB


def ensure_within_workspace(path: str, base_directory: str = BASE_DIR) -> str:
    """
    Ensure the provided path is within the BASE_DIR directory.
    """
    base_directory = os.path.abspath(base_directory)

    if os.path.isabs(path):
        full_path = os.path.abspath(path)
    else:
        full_path = os.path.abspath(os.path.join(base_directory, path))

    if not full_path.startswith(base_directory):
        raise HTTPException(
            status_code=403,
            detail=f"Permission error. Access restricted to {BASE_DIR} "
            "directory.",
        )

    return full_path


# ---------- threaded helpers (to avoid blocking event loop) ----------


async def _exists(p: str) -> bool:
    return await anyio.to_thread.run_sync(os.path.exists, p)


async def _isdir(p: str) -> bool:
    return await anyio.to_thread.run_sync(os.path.isdir, p)


async def _isfile(p: str) -> bool:
    return await anyio.to_thread.run_sync(os.path.isfile, p)


async def _islink(p: str) -> bool:
    return await anyio.to_thread.run_sync(os.path.islink, p)


async def _makedirs(p: str) -> None:
    if not p:
        return
    await anyio.to_thread.run_sync(lambda: os.makedirs(p, exist_ok=True))


async def _remove_file(p: str) -> None:
    await anyio.to_thread.run_sync(os.remove, p)


async def _rmtree(p: str) -> None:
    await anyio.to_thread.run_sync(shutil.rmtree, p)


async def _replace(src: str, dst: str) -> None:
    await anyio.to_thread.run_sync(os.replace, src, dst)


async def _lstat(p: str):
    return await anyio.to_thread.run_sync(os.lstat, p)


async def _read_text(p: str) -> str:
    def _read():
        with open(p, "r", encoding="utf-8") as f:
            return f.read()

    return await anyio.to_thread.run_sync(_read)


async def _write_bytes_stream_to_file(
    full_path: str,
    request: Request,
) -> None:
    """
    Stream request body -> file, chunked, with file writes in a thread.
    """

    def _open():
        return open(full_path, "wb")

    f = await anyio.to_thread.run_sync(_open)
    try:
        async for chunk in request.stream():
            if not chunk:
                continue
            await anyio.to_thread.run_sync(f.write, chunk)
        await anyio.to_thread.run_sync(f.flush)
    finally:
        await anyio.to_thread.run_sync(f.close)


async def _write_uploadfile_to_path(uf: UploadFile, target: str) -> None:
    """
    Stream UploadFile -> disk in chunks. UploadFile.read is async; disk
    write is threaded.
    """

    def _open():
        return open(target, "wb")

    f = await anyio.to_thread.run_sync(_open)
    try:
        while True:
            chunk = await uf.read(CHUNK_SIZE)
            if not chunk:
                break
            await anyio.to_thread.run_sync(f.write, chunk)
        await anyio.to_thread.run_sync(f.flush)
    finally:
        await anyio.to_thread.run_sync(f.close)


async def entry_info(full_path: str) -> Dict[str, Any]:
    st = await _lstat(full_path)

    if await _isdir(full_path):
        t = "dir"
    elif await _isfile(full_path):
        t = "file"
    elif await _islink(full_path):
        t = "symlink"
    else:
        t = "other"

    return {
        "path": full_path,
        "name": os.path.basename(full_path.rstrip("/")),
        "type": t,
        "size": st.st_size if t == "file" else None,
        "mtime_ms": int(st.st_mtime * 1000),
    }


async def _list_dir_recursive(root: str, depth: Optional[int]) -> List[str]:
    """
    Return list of absolute paths under root, up to depth.
    Uses blocking os.scandir in thread, but recursion logic stays async.
    """
    results: List[str] = []

    def _scandir(p: str) -> List[Tuple[str, bool]]:
        out = []
        with os.scandir(p) as it:
            for ent in it:
                # follow_symlinks=False to avoid escaping via symlink dirs
                is_dir = ent.is_dir(follow_symlinks=False)
                out.append((ent.path, is_dir))
        return out

    async def walk(cur: str, d: int):
        try:
            items = await anyio.to_thread.run_sync(_scandir, cur)
        except FileNotFoundError:
            return

        for p, is_dir in items:
            results.append(p)
            if is_dir and (depth is None or d < depth):
                await walk(p, d + 1)

    await walk(root, 1)
    return results


# -------------------- routes --------------------


@router.get("/file")
async def read_file(
    path: str = Query(...),
    fmt: Literal["text", "bytes"] = Query("text", alias="format"),
):
    full_path = ensure_within_workspace(path)

    if not await _exists(full_path) or await _isdir(full_path):
        raise HTTPException(status_code=404, detail="not found")

    if fmt == "text":
        text = await _read_text(full_path)
        return PlainTextResponse(text)

    async def aiter_file_bytes():
        """
        Async generator producing file chunks, but file reads happen in a
        thread.
        """

        def _open():
            return open(full_path, "rb")

        f = await anyio.to_thread.run_sync(_open)
        try:
            while True:
                chunk = await anyio.to_thread.run_sync(f.read, CHUNK_SIZE)
                if not chunk:
                    break
                yield chunk
        finally:
            await anyio.to_thread.run_sync(f.close)

    return StreamingResponse(
        aiter_file_bytes(),
        media_type="application/octet-stream",
    )


@router.put("/file")
async def write_file(
    request: Request,
    path: str = Query(...),
):
    full_path = ensure_within_workspace(path)
    parent = os.path.dirname(full_path)

    await _makedirs(parent)

    if await _exists(full_path) and await _isdir(full_path):
        raise HTTPException(
            status_code=409,
            detail="path exists and is a directory",
        )

    try:
        await _write_bytes_stream_to_file(full_path, request)
    except Exception:
        try:
            if await _exists(full_path):
                await _remove_file(full_path)
        except Exception:
            pass
        raise

    return JSONResponse(await entry_info(full_path))


@router.post("/files:batch")
async def batch_write(
    files: List[UploadFile] = File(default=[]),
    paths: List[str] = Form(default=[]),
):
    """
    Batch write workspace files.

    Compatibility:
      - If `paths` is provided, it must have the same length as `files` and
        will be used as the target workspace path for each file.
      - Otherwise, fall back to `UploadFile.filename` (legacy behavior).

    Rationale:
      Some HTTP clients may sanitize the `filename` field
      (e.g., dropping directory components). Providing `paths` as an
      explicit form field is more reliable.
    """
    if paths and len(paths) != len(files):
        raise HTTPException(
            status_code=400,
            detail="`paths` length must match `files` length",
        )

    out: List[Dict[str, Any]] = []

    for idx, uf in enumerate(files):
        # choose target path
        relpath = paths[idx] if paths else uf.filename

        if not relpath:
            raise HTTPException(400, detail="missing target path for a part")

        target = ensure_within_workspace(relpath)
        await _makedirs(os.path.dirname(target))

        if await _exists(target) and await _isdir(target):
            raise HTTPException(
                status_code=409,
                detail=f"target exists and is a directory: {relpath}",
            )

        await _write_uploadfile_to_path(uf, target)
        out.append(await entry_info(target))

    return JSONResponse(out)


@router.get("/list")
async def list_dir(
    path: str = Query(...),
    depth: Optional[int] = Query(1, ge=1),
):
    full_path = ensure_within_workspace(path)

    if not await _exists(full_path) or not await _isdir(full_path):
        raise HTTPException(404, detail="not found")

    paths = await _list_dir_recursive(full_path, depth)

    entries: List[Dict[str, Any]] = []
    for p in paths:
        if await _exists(p):
            entries.append(await entry_info(p))

    return JSONResponse(entries)


@router.get("/exists")
async def exists(path: str = Query(...)):
    full_path = ensure_within_workspace(path)
    return JSONResponse({"exists": await _exists(full_path)})


@router.delete("/entry")
async def remove(path: str = Query(...)):
    full_path = ensure_within_workspace(path)

    if not await _exists(full_path):
        return Response(status_code=204)

    if await _isdir(full_path) and not await _islink(full_path):
        await _rmtree(full_path)
    else:
        await _remove_file(full_path)

    return Response(status_code=204)


@router.post("/move")
async def move(request: Request):
    body = await request.json()
    source = body.get("source")
    destination = body.get("destination")

    if not source or not destination:
        raise HTTPException(400, detail="source and destination are required")

    src = ensure_within_workspace(source)
    dst = ensure_within_workspace(destination)

    if not await _exists(src):
        raise HTTPException(404, detail="source not found")

    await _makedirs(os.path.dirname(dst))
    await _replace(src, dst)

    return JSONResponse(await entry_info(dst))


@router.post("/mkdir")
async def mkdir(request: Request):
    body = await request.json()
    path = body.get("path")
    if not path:
        raise HTTPException(400, detail="path is required")

    full_path = ensure_within_workspace(path)

    if await _exists(full_path):
        if not await _isdir(full_path):
            raise HTTPException(
                409,
                detail="path exists and is not a directory",
            )
        return JSONResponse({"created": False})

    await _makedirs(full_path)
    return JSONResponse({"created": True})
