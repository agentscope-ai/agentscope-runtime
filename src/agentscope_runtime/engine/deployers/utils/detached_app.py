# -*- coding: utf-8 -*-
# pylint:disable=too-many-return-statements

"""Shared helpers for building detached deployment bundles."""

from __future__ import annotations
import os

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
from .wheel_packager import _parse_pyproject_toml

try:
    import tomllib  # Python 3.11+
except ImportError:
    try:
        import tomli as tomllib  # type: ignore[no-redef]
    except ImportError:
        tomllib = None

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
    use_local_runtime: Optional[bool] = None,
    **kwargs,
) -> Tuple[str, ProjectInfo]:
    """
    Create a detached bundle directory ready for execution.

    Args:
        app: AgentApp instance to deploy
        runner: Runner instance to deploy
        requirements: Additional pip requirements (string or list)
        extra_packages: Additional Python packages to include
        output_dir: Output directory (creates temp dir if None)
        dockerfile_path: Optional custom Dockerfile path to include
        use_local_runtime: If True, build and include local runtime wheel.
                          If None (default), auto-detect based on version.
                          Useful for development when runtime is not released.

    Returns:
        Tuple of (project_root_path, project_info)
    """

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
        **kwargs,
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

    # Auto-detect if not specified
    if use_local_runtime is None:
        package_version = _get_package_version()
        use_local_runtime = _is_dev_version(package_version)

    _append_additional_requirements(
        project_root,
        normalized_requirements,
        use_local_runtime=use_local_runtime,
    )

    if not project_info.entrypoint_file:
        raise RuntimeError("Unable to determine entrypoint file for project")

    entry_script = project_info.entrypoint_file

    if dockerfile_path:
        dest = project_root / "Dockerfile"
        with open(dockerfile_path, "r", encoding="utf-8") as f:
            content = f.read()

        new_content = content.replace(
            DEFAULT_ENTRYPOINT_FILE,
            project_info.entrypoint_file,
        )
        with open(dest, "w", encoding="utf-8") as f:
            f.write(new_content)
        os.remove(dockerfile_path)

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
    use_local_runtime: bool = False,
) -> None:
    """
    Append requirements to requirements.txt.

    For dev versions or when use_local_runtime=True, builds a wheel from
    local source and places it in wheels/ subdirectory.

    Args:
        extraction_dir: Directory where requirements.txt will be written
        additional_requirements: Additional user requirements
        use_local_runtime: If True, build and use local runtime wheel.
                          Useful for development when runtime is not released.
    """
    req_path = extraction_dir / "requirements.txt"
    package_version = _get_package_version()

    # Auto-detect if we should use local runtime
    should_use_local = use_local_runtime or (
        package_version and _is_dev_version(package_version)
    )

    with open(str(req_path), "w", encoding="utf-8") as f:
        if should_use_local:
            # Create wheels subdirectory
            # Get base requirements from pyproject.toml
            runtime_source = _get_runtime_source_path()
            base_requirements = []

            if runtime_source:
                pyproject_path = runtime_source / "pyproject.toml"
                try:
                    base_requirements = _parse_pyproject_toml(pyproject_path)
                except Exception:
                    # Fallback to manual
                    base_requirements = _get_unversioned_requirements()

            wheels_dir = extraction_dir / "wheels"
            wheels_dir.mkdir(exist_ok=True)

            # Build wheel and place it in wheels/
            wheel_filename = _build_and_copy_wheel(wheels_dir)
            if wheel_filename:
                # Use path relative to extraction_dir
                # In Docker: wheels/agentscope_runtime-0.2.0-py3-none-any.whl
                base_requirements.append(
                    f"./wheels/{wheel_filename}",
                )
        elif package_version:
            # Use versioned requirements for released versions
            base_requirements = [
                "fastapi",
                "uvicorn",
                f"agentscope-runtime=={package_version}",
                f"agentscope-runtime[sandbox]=={package_version}",
                f"agentscope-runtime[deployment]=={package_version}",
                "pydantic",
                "jinja2",  # For template rendering
                "psutil",  # For process management
                "redis",  # For process management
                "celery",  # For task queue
            ]
        else:
            # Fallback to unversioned if version cannot be determined
            base_requirements = _get_unversioned_requirements()

        if not additional_requirements:
            additional_requirements = []

        # Combine base requirements with user requirements
        all_requirements = sorted(
            list(
                set(
                    base_requirements + additional_requirements,
                ),
            ),
        )
        for req in all_requirements:
            f.write(f"{req}\n")


def _get_package_version() -> str:
    """
    Get the package version from pyproject.toml file.

    Returns:
        str: The version string, or empty string if not found
    """
    # Try to find pyproject.toml in the current directory and parent
    # directories
    current_dir = Path(__file__).parent
    for _ in range(6):  # Look up to 6 levels up
        pyproject_path = current_dir / "pyproject.toml"
        if pyproject_path.exists():
            break
        current_dir = current_dir.parent
    else:
        # Also try the current working directory
        pyproject_path = Path(os.getcwd()) / "pyproject.toml"
        if not pyproject_path.exists():
            return ""

    try:
        # Use tomllib to parse
        with open(pyproject_path, "rb") as f:
            data = tomllib.load(f)
        project = data.get("project", {})
        return project.get("version", "")
    except Exception:
        return ""


def _is_dev_version(version: str) -> bool:
    """
    Check if version is a development version.

    Development versions include: 0.2.0.dev0, 0.2.0-dev, 0.2.0a1, etc.

    Args:
        version: Version string to check

    Returns:
        bool: True if this is a development version
    """
    if not version:
        return False

    dev_indicators = [".dev", "-dev", "dev", "alpha", "beta", "rc", "a", "b"]
    version_lower = version.lower()

    return any(indicator in version_lower for indicator in dev_indicators)


def _get_runtime_source_path() -> Optional[Path]:
    """
    Find the agentscope-runtime source code root directory.

    Strategy:
    1. Start from current file location (__file__)
    2. Walk up directories to find pyproject.toml
    3. Verify it's the agentscope-runtime project

    Returns:
        Path: Path to source root, or None if not found
    """
    current_file = Path(__file__).resolve()

    # Walk up the directory tree (up to 10 levels)
    for parent in [current_file] + list(current_file.parents)[:10]:
        pyproject_path = parent / "pyproject.toml"

        if pyproject_path.exists():
            try:
                with open(pyproject_path, "rb") as f:
                    data = tomllib.load(f)

                # Check if this is agentscope-runtime project
                project_name = data.get("project", {}).get("name", "")
                if project_name == "agentscope-runtime":
                    return parent
            except Exception:
                continue

    return None


def _build_and_copy_wheel(wheels_dir: Path) -> Optional[str]:
    """
    Build a wheel from local agentscope-runtime source and copy to wheels_dir.

    Args:
        wheels_dir: Target directory where wheel will be placed

    Returns:
        str: Wheel filename if successful, None otherwise
    """
    import logging
    import subprocess

    logger = logging.getLogger(__name__)

    runtime_source = _get_runtime_source_path()

    if not runtime_source:
        logger.warning(
            "Could not locate agentscope-runtime source directory. "
            "Falling back to unversioned requirements.",
        )
        return None

    logger.info(f"Building wheel from source: {runtime_source}")

    try:
        # Create a temporary build directory
        with tempfile.TemporaryDirectory() as temp_build_dir:
            # Build wheel using python -m build or pip wheel
            # Try using 'build' module first (recommended)
            try:
                result = subprocess.run(
                    [
                        "python",
                        "-m",
                        "build",
                        "--wheel",
                        "--outdir",
                        temp_build_dir,
                    ],
                    cwd=str(runtime_source),
                    capture_output=True,
                    text=True,
                    timeout=120,
                    check=False,
                )

                if result.returncode != 0:
                    logger.error(f"Wheel build failed: {result.stderr}")
                    return None

            except (ImportError, FileNotFoundError):
                # Fallback to pip wheel
                logger.info("'build' module not found, using pip wheel")
                result = subprocess.run(
                    ["pip", "wheel", "--no-deps", "-w", temp_build_dir, "."],
                    cwd=str(runtime_source),
                    capture_output=True,
                    text=True,
                    timeout=120,
                    check=False,
                )

                if result.returncode != 0:
                    logger.error(f"Wheel build failed: {result.stderr}")
                    return None

            # Find the generated wheel file
            wheel_files = list(
                Path(temp_build_dir).glob("agentscope_runtime-*.whl"),
            )

            if not wheel_files:
                logger.error("No wheel file generated")
                return None

            wheel_file = wheel_files[0]
            wheel_filename = wheel_file.name

            # Copy wheel to wheels_dir
            dest_wheel = wheels_dir / wheel_filename
            shutil.copy2(wheel_file, dest_wheel)

            logger.info(f"Wheel built and copied to: {dest_wheel}")
            return wheel_filename

    except subprocess.TimeoutExpired:
        logger.error("Wheel build timed out")
        return None
    except Exception as e:
        logger.error(f"Failed to build wheel: {e}")
        return None


def _get_unversioned_requirements() -> List[str]:
    """
    Get unversioned base requirements as fallback.

    Returns:
        List[str]: List of base requirements without version constraints
    """
    return [
        "fastapi",
        "uvicorn",
        "agentscope-runtime",
        "agentscope-runtime[sandbox]",
        "agentscope-runtime[deployment]",
        "pydantic",
        "jinja2",  # For template rendering
        "psutil",  # For process management
        "redis",  # For process management
        "celery",  # For task queue
    ]


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
            # Ignore invalid JSON and fall back to default entry script
            pass
    return DEFAULT_ENTRYPOINT_FILE
