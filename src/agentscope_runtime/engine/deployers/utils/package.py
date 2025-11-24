# -*- coding: utf-8 -*-
"""
Project-based packaging utilities for AgentApp and Runner deployment.

This module provides packaging utilities that support:
- Function-based AgentApp deployment with decorators
- Runner-based deployment with entrypoint files
- Entire project directory packaging
- Smart dependency caching
- CLI-style and object-style deployment patterns
"""

import hashlib
import inspect
import logging
import os
import re
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import Optional, List, Dict, Tuple, Union

from pydantic import BaseModel

try:
    import tomllib  # Python 3.11+
except ImportError:
    try:
        import tomli as tomllib  # type: ignore[no-redef]
    except ImportError:
        tomllib = None

logger = logging.getLogger(__name__)

DEPLOYMENT_ZIP = "deployment.zip"

# ===== Data Models =====


class ProjectInfo(BaseModel):
    """Information about a project to be packaged."""

    project_dir: str  # Absolute path to project root directory
    entrypoint_file: Optional[
        str
    ] = None  # Relative path to entrypoint file (if applicable)
    entrypoint_handler: Optional[
        str
    ] = None  # Handler name (e.g., "app" or "runner")
    is_directory_entrypoint: bool = False  # True if packaging entire directory


class DependencyInfo(BaseModel):
    """Information about project dependencies."""

    requirements_file: Optional[str] = None  # Path to requirements.txt
    pyproject_file: Optional[str] = None  # Path to pyproject.toml
    dependency_hash: Optional[str] = None  # Hash for cache validation
    has_dependencies: bool = False  # Whether dependencies were found


# ===== Project Directory Extraction =====


def project_dir_extractor(
    app=None,
    runner=None,
) -> ProjectInfo:
    """
    Extract project directory information from app or runner object.

    This function inspects the call stack to find where the app or runner
    was defined and extracts the project root directory.

    Args:
        app: AgentApp instance (optional)
        runner: Runner instance (optional)

    Returns:
        ProjectInfo with project directory and entrypoint information

    Raises:
        ValueError: If neither app nor runner is provided or project dir cannot be determined
    """
    if app is None and runner is None:
        raise ValueError("Either app or runner must be provided")

    target_obj = app if app is not None else runner
    target_type = "app" if app is not None else "runner"

    # Get the source file where the object was defined
    frame = inspect.currentframe()
    caller_frame = frame.f_back if frame else None

    project_file = None

    # Try to find the file where the object was created
    while caller_frame:
        try:
            frame_filename = caller_frame.f_code.co_filename

            # Skip internal/system files and focus on user code
            if (
                not frame_filename.endswith(".py")
                or "site-packages" in frame_filename
                or "agentscope_runtime" in frame_filename
            ):
                caller_frame = caller_frame.f_back
                continue

            # Check if this frame contains our target object
            frame_locals = caller_frame.f_locals
            frame_globals = caller_frame.f_globals

            # Look for the object (by identity) in locals and globals
            for var_name, var_value in list(frame_locals.items()) + list(
                frame_globals.items()
            ):
                if var_value is target_obj:
                    project_file = frame_filename
                    break

            if project_file:
                break

        except (AttributeError, TypeError):
            pass

        caller_frame = caller_frame.f_back

    if not project_file or not os.path.exists(project_file):
        raise ValueError(
            f"Unable to locate source file for {target_type} object",
        )

    # The project directory is the directory containing the file
    project_dir = os.path.dirname(os.path.abspath(project_file))
    entrypoint_file = os.path.basename(project_file)

    logger.info(
        f"Extracted project dir from {target_type}: {project_dir}",
    )

    return ProjectInfo(
        project_dir=project_dir,
        entrypoint_file=entrypoint_file,
        entrypoint_handler=target_type,  # "app" or "runner"
        is_directory_entrypoint=False,
    )


# ===== Entrypoint Parsing =====


def parse_entrypoint(spec: str) -> ProjectInfo:
    """
    Parse entrypoint specification into ProjectInfo.

    Supported formats:
    - "app.py" - File with default handler name "app"
    - "app.py:my_handler" - File with specific handler name
    - "project_dir/" - Directory (will auto-detect entrypoint)

    Args:
        spec: Entrypoint specification string

    Returns:
        ProjectInfo with parsed information

    Raises:
        ValueError: If specification format is invalid or file/dir doesn't exist
    """
    spec = spec.strip()

    # Check if it's a directory entrypoint
    if spec.endswith("/") or os.path.isdir(spec):
        project_dir = os.path.abspath(spec.rstrip("/"))
        if not os.path.exists(project_dir):
            raise ValueError(f"Directory not found: {project_dir}")

        # Auto-detect entrypoint file in directory
        entrypoint_file = _auto_detect_entrypoint(project_dir)

        return ProjectInfo(
            project_dir=project_dir,
            entrypoint_file=entrypoint_file,
            entrypoint_handler="app",  # Default handler
            is_directory_entrypoint=True,
        )

    # Parse file-based entrypoint with optional handler
    if ":" in spec:
        file_part, handler = spec.split(":", 1)
    else:
        file_part = spec
        handler = "app"  # Default handler name

    # Resolve file path
    file_path = os.path.abspath(file_part)
    if not os.path.exists(file_path):
        raise ValueError(f"Entrypoint file not found: {file_path}")

    project_dir = os.path.dirname(file_path)
    entrypoint_file = os.path.basename(file_path)

    return ProjectInfo(
        project_dir=project_dir,
        entrypoint_file=entrypoint_file,
        entrypoint_handler=handler,
        is_directory_entrypoint=False,
    )


def _auto_detect_entrypoint(project_dir: str) -> str:
    """
    Auto-detect entrypoint file in a directory.

    Looks for common entrypoint file names in priority order:
    - app.py
    - main.py
    - __main__.py
    - run.py
    - runner.py

    Args:
        project_dir: Directory to search

    Returns:
        Name of detected entrypoint file (relative to project_dir)

    Raises:
        ValueError: If no entrypoint file is found
    """
    candidates = [
        "app.py",
        "main.py",
        "__main__.py",
        "run.py",
        "runner.py",
    ]

    for candidate in candidates:
        candidate_path = os.path.join(project_dir, candidate)
        if os.path.exists(candidate_path):
            logger.info(f"Auto-detected entrypoint: {candidate}")
            return candidate

    raise ValueError(
        f"No entrypoint file found in {project_dir}. "
        f"Expected one of: {', '.join(candidates)}",
    )


# ===== Dependency Detection =====


def detect_dependencies(project_dir: Path) -> DependencyInfo:
    """
    Detect dependency files (requirements.txt or pyproject.toml) in project.

    Args:
        project_dir: Project directory path

    Returns:
        DependencyInfo with detected dependency information
    """
    project_dir = Path(project_dir).resolve()

    requirements_file = None
    pyproject_file = None

    # Check for requirements.txt
    req_path = project_dir / "requirements.txt"
    if req_path.exists():
        requirements_file = str(req_path)

    # Check for pyproject.toml
    pyproject_path = project_dir / "pyproject.toml"
    if pyproject_path.exists():
        pyproject_file = str(pyproject_path)

    has_dependencies = (
        requirements_file is not None or pyproject_file is not None
    )

    # Calculate hash for caching
    dependency_hash = None
    if has_dependencies:
        dependency_hash = _calculate_dependency_hash(
            requirements_file,
            pyproject_file,
        )

    return DependencyInfo(
        requirements_file=requirements_file,
        pyproject_file=pyproject_file,
        dependency_hash=dependency_hash,
        has_dependencies=has_dependencies,
    )


def _calculate_dependency_hash(
    requirements_file: Optional[str],
    pyproject_file: Optional[str],
) -> str:
    """
    Calculate combined hash of dependency files for cache validation.

    Args:
        requirements_file: Path to requirements.txt (if exists)
        pyproject_file: Path to pyproject.toml (if exists)

    Returns:
        SHA256 hash string
    """
    hasher = hashlib.sha256()

    if requirements_file and os.path.exists(requirements_file):
        with open(requirements_file, "rb") as f:
            hasher.update(f.read())

    if pyproject_file and os.path.exists(pyproject_file):
        with open(pyproject_file, "rb") as f:
            hasher.update(f.read())

    return hasher.hexdigest()


# ===== Package Caching =====


class PackageCache:
    """Cache manager for dependency packages."""

    def __init__(self, cache_dir: Path):
        """
        Initialize package cache.

        Args:
            cache_dir: Directory for caching artifacts
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    @property
    def dependencies_zip(self) -> Path:
        """Path to cached dependencies.zip."""
        return self.cache_dir / "dependencies.zip"

    @property
    def dependencies_hash_file(self) -> Path:
        """Path to hash file for dependencies."""
        return self.cache_dir / "dependencies.hash"

    def should_rebuild_dependencies(
        self,
        dependency_info: DependencyInfo,
        force: bool = False,
    ) -> bool:
        """
        Determine if dependencies need rebuilding.

        Args:
            dependency_info: Dependency information
            force: Force rebuild flag

        Returns:
            True if dependencies should be rebuilt
        """
        if force:
            logger.info("Force rebuild requested")
            return True

        if not self.dependencies_zip.exists():
            logger.info("No cached dependencies found, will build")
            return True

        if not self.dependencies_hash_file.exists():
            logger.info("No hash file found, will rebuild")
            return True

        current_hash = dependency_info.dependency_hash
        stored_hash = self.dependencies_hash_file.read_text().strip()

        if current_hash != stored_hash:
            logger.info("Dependencies changed, will rebuild")
            logger.debug(f"  Previous hash: {stored_hash[:12]}")
            logger.debug(f"  Current hash:  {current_hash[:12]}")
            return True

        logger.info("Using cached dependencies (no changes detected)")
        return False

    def save_dependencies_hash(self, dependency_info: DependencyInfo) -> None:
        """
        Save dependency hash for future comparisons.

        Args:
            dependency_info: Dependency information with hash
        """
        if dependency_info.dependency_hash:
            self.dependencies_hash_file.write_text(
                dependency_info.dependency_hash,
            )


# ===== Project Packaging =====


def _get_default_ignore_patterns() -> List[str]:
    """
    Get default ignore patterns for project packaging.

    Returns:
        List of ignore patterns (similar to .dockerignore)
    """
    return [
        "__pycache__",
        "*.pyc",
        "*.pyo",
        ".git",
        ".gitignore",
        ".pytest_cache",
        ".mypy_cache",
        ".tox",
        "venv",
        "env",
        ".venv",
        ".env",
        "node_modules",
        ".DS_Store",
        "*.egg-info",
        "build",
        "dist",
        ".cache",
        "*.swp",
        "*.swo",
        "*~",
        ".idea",
        ".vscode",
        "*.log",
    ]


def _should_ignore(path: str, patterns: List[str]) -> bool:
    """
    Check if path should be ignored based on patterns.

    Args:
        path: Path to check (relative)
        patterns: List of ignore patterns

    Returns:
        True if path should be ignored
    """
    path_parts = Path(path).parts

    for pattern in patterns:
        # Check if any part of the path matches the pattern
        if pattern in path_parts:
            return True

        # Check wildcard patterns
        if "*" in pattern:
            import fnmatch

            if fnmatch.fnmatch(path, pattern):
                return True

    return False


def package_code(
    source_dir: Path,
    output_zip: Path,
    ignore_patterns: Optional[List[str]] = None,
) -> None:
    """
    Package project source code into a zip file.

    Args:
        source_dir: Source directory to package
        output_zip: Output zip file path
        ignore_patterns: Optional ignore patterns (uses defaults if None)
    """
    if ignore_patterns is None:
        ignore_patterns = _get_default_ignore_patterns()

    logger.info(f"Packaging source code from {source_dir}")

    with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(source_dir):
            # Filter directories
            dirs[:] = [
                d
                for d in dirs
                if not _should_ignore(
                    os.path.relpath(os.path.join(root, d), source_dir),
                    ignore_patterns,
                )
            ]

            # Add files
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, source_dir)

                if _should_ignore(arcname, ignore_patterns):
                    continue

                zipf.write(file_path, arcname)

    logger.info(f"Source code packaged: {output_zip}")


def _merge_zips(
    dependencies_zip: Optional[Path],
    code_zip: Path,
    output_zip: Path,
) -> None:
    """
    Merge dependencies and code zips into a deployment package.

    Args:
        dependencies_zip: Path to dependencies.zip (optional)
        code_zip: Path to code.zip
        output_zip: Path to output deployment.zip
    """
    logger.info("Merging packages into deployment.zip...")

    with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED) as out:
        # Layer 1: Dependencies
        if dependencies_zip and dependencies_zip.exists():
            with zipfile.ZipFile(dependencies_zip, "r") as dep:
                for item in dep.namelist():
                    out.writestr(item, dep.read(item))

        # Layer 2: Code (overwrites conflicts)
        with zipfile.ZipFile(code_zip, "r") as code:
            for item in code.namelist():
                out.writestr(item, code.read(item))

    logger.info(f"Deployment package created: {output_zip}")


# ===== Main Package Function =====


def package(
    app=None,
    runner=None,
    entrypoint: Optional[str] = None,
    output_dir: Optional[str] = None,
    **kwargs,
) -> Tuple[str, ProjectInfo]:
    """
    Package an AgentApp or Runner for deployment.

    This function supports two deployment patterns:
    1. Object-style: package(app=my_app) or package(runner=my_runner)
    2. Entrypoint-style: package(entrypoint="app.py") or package(entrypoint="project_dir/")

    Args:
        app: AgentApp instance (for object-style deployment)
        runner: Runner instance (for object-style deployment)
        entrypoint: Entrypoint specification (for CLI-style deployment)
        output_dir: Output directory (creates temp dir if None)

    Returns:
        Tuple of (package_path, project_info)
        - package_path: Path to the deployment package directory
        - project_info: ProjectInfo with project metadata

    Raises:
        ValueError: If neither app/runner nor entrypoint is provided
        RuntimeError: If packaging fails
    """
    # Determine project info
    if entrypoint:
        project_info = parse_entrypoint(entrypoint)
    elif app or runner:
        project_info = project_dir_extractor(app=app, runner=runner)
    else:
        raise ValueError(
            "Either app/runner or entrypoint must be provided",
        )

    logger.info(f"Packaging project from: {project_info.project_dir}")

    # Create output directory
    if output_dir is None:
        output_dir = tempfile.mkdtemp(prefix="agentscope_package_")
    else:
        os.makedirs(output_dir, exist_ok=True)

    output_path = Path(output_dir)

    # Package code
    deployment_zip = output_path / DEPLOYMENT_ZIP
    package_code(
        Path(project_info.project_dir),
        deployment_zip,
    )

    # Report size
    size_mb = deployment_zip.stat().st_size / (1024 * 1024)
    logger.info(f"Deployment package ready: {size_mb:.2f} MB")

    return str(output_path), project_info
