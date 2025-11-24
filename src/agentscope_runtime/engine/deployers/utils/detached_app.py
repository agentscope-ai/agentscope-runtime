# -*- coding: utf-8 -*-
"""Shared helpers for building detached deployment bundles."""

from __future__ import annotations

import json
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Type, Union

from .app_runner_utils import ensure_runner_from_app
from .package import package, ProjectInfo, DEFAULT_ENTRYPOINT_FILE
from ..adapter.protocol_adapter import ProtocolAdapter
from .package import DEPLOYMENT_ZIP

PROJECT_SUBDIR = ".agentscope_runtime"
CONFIG_FILENAME = "deploy_config.json"
META_FILENAME = "bundle_meta.json"


def build_detached_app(
    *,
    app=None,
    runner=None,
    requirements: Optional[Union[str, List[str]]] = None,
    extra_packages: Optional[List[str]] = None,
    output_dir: Optional[str] = None,
    dockerfile_path: Optional[str] = None,
) -> Tuple[str, ProjectInfo]:
    """Create a detached bundle directory ready for execution."""

    if app is not None and runner is None:
        runner = ensure_runner_from_app(app)

    if runner is None and app is None:
        raise ValueError("Either app or runner must be provided")

    normalized_requirements = _normalize_requirements(requirements)

    if output_dir:
        build_root = Path(output_dir)
        if build_root.exists():
            shutil.rmtree(build_root)
        build_root.mkdir(parents=True, exist_ok=True)
    else:
        build_root = Path(
            tempfile.mkdtemp(
                prefix="agentscope_runtime_detached_",
            ),
        )

    package_path, project_info = package(
        app=app,
        runner=None if app is not None else runner,
        output_dir=str(build_root),
        extra_packages=extra_packages,
    )

    workspace_root = Path(package_path)
    project_root = workspace_root / PROJECT_SUBDIR
    project_root.mkdir(parents=True, exist_ok=True)

    deployment_zip = workspace_root / DEPLOYMENT_ZIP
    if not deployment_zip.exists():
        raise RuntimeError(
            f"deployment.zip not found in packaged output: {deployment_zip}",
        )

    with zipfile.ZipFile(deployment_zip, "r") as archive:
        archive.extractall(project_root)

    if normalized_requirements:
        _append_additional_requirements(
            project_root,
            normalized_requirements,
        )

    if not project_info.entrypoint_file:
        raise RuntimeError("Unable to determine entrypoint file for project")

    entry_script = project_info.entrypoint_file

    if dockerfile_path:
        dest = project_root / "Dockerfile"
        shutil.copyfile(dockerfile_path, dest)

    _write_bundle_meta(project_root, entry_script)

    return str(project_root), project_info


def _normalize_requirements(
    requirements: Optional[Union[str, List[str]]],
) -> List[str]:
    if requirements is None:
        return []
    if isinstance(requirements, str):
        return [requirements]
    return [str(item) for item in requirements]


def _append_additional_requirements(
    extraction_dir: Path,
    additional_requirements: List[str],
) -> None:
    req_path = extraction_dir / "requirements.txt"
    existing: List[str] = []
    if req_path.exists():
        existing = [
            line.strip()
            for line in req_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    merged = existing[:]
    for requirement in additional_requirements:
        if requirement not in merged:
            merged.append(requirement)

    req_path.write_text("\n".join(merged) + "\n", encoding="utf-8")


def _serialize_protocol_adapters(
    adapters: Optional[list[ProtocolAdapter]],
) -> List[Dict[str, str]]:
    serialized: List[Dict[str, str]] = []
    if not adapters:
        return serialized

    for adapter in adapters:
        adapter_cls = adapter.__class__
        serialized.append(
            {
                "module": adapter_cls.__module__,
                "class": adapter_cls.__name__,
            },
        )
    return serialized


def _serialize_request_model(
    request_model: Optional[Type],
) -> Optional[Dict[str, str]]:
    if request_model is None:
        return None

    return {
        "module": request_model.__module__,
        "class": request_model.__name__,
    }


def _serialize_custom_endpoints(
    custom_endpoints: Optional[List[Dict]],
) -> List[Dict[str, Any]]:
    serialized: List[Dict[str, Any]] = []
    if not custom_endpoints:
        return serialized

    for endpoint in custom_endpoints:
        handler = endpoint.get("handler")
        serialized.append(
            {
                "path": endpoint.get("path"),
                "methods": endpoint.get("methods"),
                "module": getattr(
                    handler,
                    "__module__",
                    endpoint.get("module"),
                ),
                "function_name": getattr(
                    handler,
                    "__name__",
                    endpoint.get("function_name"),
                ),
            },
        )

    return serialized


def _write_bundle_meta(bundle_dir: Path, entry_script: str) -> None:
    meta_path = bundle_dir / META_FILENAME
    meta = {"entry_script": entry_script}
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")


def get_bundle_entry_script(bundle_dir: Union[str, Path]) -> str:
    meta_path = Path(bundle_dir) / META_FILENAME
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            script = meta.get("entry_script")
            if script:
                return script
        except json.JSONDecodeError:
            pass
    return DEFAULT_ENTRYPOINT_FILE
