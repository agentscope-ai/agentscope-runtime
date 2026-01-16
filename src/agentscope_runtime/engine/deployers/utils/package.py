# -*- coding: utf-8 -*-
# pylint:disable=unused-argument

"""
Project-based packaging utilities for AgentApp and Runner deployment.

This module provides packaging utilities that support:
- Function-based AgentApp deployment with decorators
- Runner-based deployment with entrypoint files
- Entire project directory packaging
- Smart dependency caching
- CLI-style and object-style deployment patterns
"""

import inspect
import logging
import os
import shutil
import zipfile
from pathlib import Path
from typing import Optional, List, Tuple, Union

from jinja2 import Environment, FileSystemLoader, TemplateNotFound
from pydantic import BaseModel

logger = logging.getLogger(__name__)

DEPLOYMENT_ZIP = "deployment.zip"
TEMPLATES_DIR = Path(__file__).parent / "templates"
DEFAULT_ENTRYPOINT_FILE = "runtime_main.py"

# Default workspace for build artifacts
DEFAULT_BUILD_WORKSPACE = Path(os.getcwd()) / ".agentscope_runtime" / "builds"


def generate_build_directory(
    platform: str = "unknown",
    workspace: Optional[Path] = None,
) -> Path:
    """
    Generate a platform-aware build directory with timestamp and random suffix.

    Args:
        platform: Deployment platform (k8s, modelstudio, agentrun, local, etc.)
        workspace: Custom workspace directory (defaults to
                DEFAULT_BUILD_WORKSPACE)

    Returns:
        Path: Generated build directory path

    Example:
        >>> build_dir = generate_build_directory("modelstudio")
        >>> # Returns: .agentscope_runtime/builds/modelstudio_20251207_xxx
    """
    import random
    import time

    if workspace is None:
        workspace = DEFAULT_BUILD_WORKSPACE

    workspace.mkdir(parents=True, exist_ok=True)

    # Generate timestamp-based name with random suffix
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    random_suffix = "".join(random.choices("0123456789abcdef", k=6))
    build_name = f"{platform}_{timestamp}_{random_suffix}"

    return workspace / build_name


def _get_template_env() -> Environment:
    """
    Get Jinja2 environment for template rendering.

    Returns:
        Jinja2 Environment configured with the templates directory
    """
    return Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        trim_blocks=True,
        lstrip_blocks=True,
    )


# ===== Data Models =====


class RuntimeParameter(BaseModel):
    """Configuration for a runtime parameter."""

    name: str  # Parameter name (e.g., "log_level")
    type: str  # Parameter type: "str", "int", "bool", "float"
    default: Union[str, int, bool, float, None]  # Default value
    help: Optional[str] = None  # Help text for CLI argument
    cli_name: Optional[str] = None  # CLI argument name (defaults to --{name})


class EntrypointInfo(BaseModel):
    """Information about the generated entrypoint."""

    module_name: str  # Module to import from (e.g., "app_deploy")
    object_name: str  # Object name to import (e.g., "agent_app")
    object_type: str  # "app" or "runner"
    host: str = "0.0.0.0"  # Default host for the service
    port: int = 8090  # Default port for the service
    extra_parameters: List[
        RuntimeParameter
    ] = []  # Additional runtime parameters


class ProjectInfo(BaseModel):
    """Information about a project to be packaged."""

    project_dir: str  # Absolute path to project root directory
    entrypoint_file: str  # Relative path to entrypoint file (if applicable)
    entrypoint_handler: str  # actual object name, e.g., "agent_app"
    handler_type: Optional[str] = None  # Handler type ("app" or "runner")
    is_directory_entrypoint: bool = False  # True if packaging entire directory


# ===== Project Directory Extraction =====


def project_dir_extractor(
    app=None,
    runner=None,
) -> ProjectInfo:
    """
    Extract project directory information from app or runner object.

    This function inspects the call stack to find where the app or runner
    was defined and extracts the project root directory and object name.

    Args:
        app: AgentApp instance (optional)
        runner: Runner instance (optional)

    Returns:
        ProjectInfo with project directory, entrypoint file, and handler name

    Raises:
        ValueError: If neither app nor runner is provided or project dir
        cannot be determined
    """
    if app is None and runner is None:
        raise ValueError("Either app or runner must be provided")

    target_obj = app if app is not None else runner
    target_type = "app" if app is not None else "runner"

    # Get the source file where the object was defined
    frame = inspect.currentframe()
    caller_frame = frame.f_back if frame else None

    project_file = None
    object_name = None  # Store the actual object name

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
                frame_globals.items(),
            ):
                if var_value is target_obj:
                    project_file = frame_filename
                    object_name = var_name  # Capture the actual object name!
                    break

            if project_file:
                break

        except (AttributeError, TypeError) as e:
            logger.warning(
                f"Ignore Attribute or Type error: {e}",
            )

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
    logger.info(
        f"Detected {target_type} object name: {object_name}",
    )

    return ProjectInfo(
        project_dir=project_dir,
        entrypoint_file=entrypoint_file,
        entrypoint_handler=object_name,  # Actual object name (e.g.,
        # "agent_app")
        handler_type=target_type,  # Type: "app" or "runner"
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
        ValueError: If specification format is invalid or file/dir doesn't
        exist
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
            entrypoint_handler="app",  # Default handler name
            handler_type="app",  # Default type
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
        entrypoint_handler=handler,  # Handler name
        handler_type="app",  # Assume app type for entrypoint-style
        is_directory_entrypoint=False,
    )


def _auto_detect_entrypoint(project_dir: str) -> str:
    """
    Auto-detect entrypoint file in a directory.

    Looks for common entrypoint file names in priority order:
    - app.py
    - main.py
    - __main__.py
    - chat.py
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
        "chat.py",
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


# ===== Main Template Generation =====
def _generate_app_main_template(entrypoint_info: EntrypointInfo) -> str:
    """
    Generate main.py template for AgentApp using Jinja2.

    Args:
        entrypoint_info: Information about the entrypoint

    Returns:
        String content for main.py

    Raises:
        RuntimeError: If template file not found
    """
    try:
        env = _get_template_env()
        template = env.get_template("app_main.py.j2")

        # Convert RuntimeParameter objects to dicts for Jinja2
        extra_params_dicts = [
            param.model_dump() for param in entrypoint_info.extra_parameters
        ]

        return template.render(
            module_name=entrypoint_info.module_name,
            object_name=entrypoint_info.object_name,
            host=entrypoint_info.host,
            port=entrypoint_info.port,
            extra_parameters=extra_params_dicts,
        )
    except TemplateNotFound as e:
        raise RuntimeError(
            f"Template 'app_main.py.j2' not found in {TEMPLATES_DIR}",
        ) from e


def _generate_runner_main_template(entrypoint_info: EntrypointInfo) -> str:
    """
    Generate main.py template for Runner using Jinja2.

    The template wraps the Runner in an AgentApp so it can be deployed as a
    service.

    Args:
        entrypoint_info: Information about the entrypoint

    Returns:
        String content for main.py

    Raises:
        RuntimeError: If template file not found
    """
    try:
        env = _get_template_env()
        template = env.get_template("runner_main.py.j2")

        # Use app_name from entrypoint_info or default to object_name
        app_name = (
            entrypoint_info.app_name or f"{entrypoint_info.object_name}_app"
        )
        app_description = (
            entrypoint_info.app_description
            or f"Service for {entrypoint_info.object_name}"
        )

        # Convert RuntimeParameter objects to dicts for Jinja2
        extra_params_dicts = [
            param.model_dump() for param in entrypoint_info.extra_parameters
        ]

        return template.render(
            module_name=entrypoint_info.module_name,
            object_name=entrypoint_info.object_name,
            app_name=app_name,
            app_description=app_description,
            host=entrypoint_info.host,
            port=entrypoint_info.port,
            extra_parameters=extra_params_dicts,
        )
    except TemplateNotFound as e:
        raise RuntimeError(
            f"Template 'runner_main.py.j2' not found in {TEMPLATES_DIR}",
        ) from e


def generate_main_template(entrypoint_info: EntrypointInfo) -> str:
    """
    Generate main.py template based on object type using Jinja2 templates.

    Args:
        entrypoint_info: Information about the entrypoint

    Returns:
        String content for main.py

    Raises:
        ValueError: If object_type is not supported
        RuntimeError: If template rendering fails
    """
    if entrypoint_info.object_type == "app":
        return _generate_app_main_template(entrypoint_info)
    elif entrypoint_info.object_type == "runner":
        return _generate_runner_main_template(entrypoint_info)
    else:
        raise ValueError(
            f"Unsupported object type: {entrypoint_info.object_type}. "
            f"Expected 'app' or 'runner'",
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
        "logs",
        ".agentscope_runtime",  # Ignore build workspace
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
    host: str = "0.0.0.0",
    port: int = 8090,
    extra_parameters: Optional[List[RuntimeParameter]] = None,
    requirements: Optional[List[str]] = None,
    platform: str = "unknown",
    **kwargs,
) -> Tuple[str, ProjectInfo]:
    """
    Package an AgentApp or Runner for deployment.

    This function supports two deployment patterns:

    1. Object-style: package(app=my_app) or package(runner=my_runner)
    2. Entrypoint-style: package(entrypoint="app.py") or
       package(entrypoint="project_dir/")

    For object-style deployment, this function will:

    1. Extract the project directory containing the app/runner.
    2. Generate a new main.py that imports and runs the app/runner.
    3. Package the project with the generated main.py as entrypoint.

    Build directory naming:

    - When output_dir=None (default), creates workspace directory with
      platform-aware naming.
    - Directory format: cwd/.agentscope_runtime/builds/
      <platform>_<timestamp>_<code>/
    - Explicit output_dir uses the provided path.

    Args:
        app: AgentApp instance (for object-style deployment).
        runner: Runner instance (for object-style deployment).
        entrypoint: Entrypoint specification (for CLI-style deployment).
        output_dir: Output directory (creates temp dir if None).
        host: Default host for the service (default: "0.0.0.0").
        port: Default port for the service (default: 8090).
        extra_parameters: Additional runtime parameters to expose via CLI.
        requirements: Additional pip requirements.
        platform: Deployment platform (k8s, modelstudio, agentrun, local).
        **kwargs: Additional keyword arguments (ignored).

    Returns:
        Tuple of (package_path, project_info).

        - package_path: Path to the deployment package directory.
        - project_info: ProjectInfo with project metadata.

    Raises:
        ValueError: If neither app/runner nor entrypoint is provided.
        RuntimeError: If packaging fails.

    Example::

        extra_params = [
            RuntimeParameter(
                name="log_level",
                type="str",
                default="info",
                help="Logging level",
            ),
            RuntimeParameter(
                name="workers",
                type="int",
                default=4,
                help="Number of worker threads",
            ),
        ]
        package(app=my_app, extra_parameters=extra_params, platform="k8s")
    """
    # Determine project info and target object
    target_obj = None
    if entrypoint:
        project_info = parse_entrypoint(entrypoint)
    elif app or runner:
        project_info = project_dir_extractor(app=app, runner=runner)
        target_obj = app if app is not None else runner
    else:
        raise ValueError(
            "Either app/runner or entrypoint must be provided",
        )

    logger.info(f"Packaging project from: {project_info.project_dir}")

    # Create output directory with platform-aware naming
    if output_dir is None:
        output_dir = str(generate_build_directory(platform))
        os.makedirs(output_dir, exist_ok=True)
    else:
        os.makedirs(output_dir, exist_ok=True)

    output_path = Path(output_dir)
    module_name = project_info.entrypoint_file.split(".", maxsplit=1)[0]
    # For object-style deployment, generate main.py template
    generated_main = False
    if target_obj is not None:
        entrypoint_info = EntrypointInfo(
            module_name=module_name,
            object_type=project_info.handler_type,
            object_name=project_info.entrypoint_handler,
            host=host,
            port=port,
            extra_parameters=extra_parameters or [],
        )

        # Generate main.py content
        main_content = generate_main_template(entrypoint_info)

        # Create temporary directory for modified source
        temp_source_dir = output_path / "temp_source"
        temp_source_dir.mkdir(exist_ok=True)

        # Copy original project to temp directory
        shutil.copytree(
            project_info.project_dir,
            temp_source_dir,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns(*_get_default_ignore_patterns()),
        )

        # Write generated main.py to temp directory
        main_py_path = temp_source_dir / DEFAULT_ENTRYPOINT_FILE
        with open(main_py_path, "w", encoding="utf-8") as f:
            f.write(main_content)

        # Update project_info to use generated main.py
        project_info.entrypoint_file = DEFAULT_ENTRYPOINT_FILE
        project_info.entrypoint_handler = entrypoint_info.object_name
        # Use object name
        project_info.handler_type = entrypoint_info.object_type  # Use type
        project_info.project_dir = str(temp_source_dir)

        generated_main = True
        logger.info(
            f"Generated main.py template for {entrypoint_info.object_type}: "
            f"{entrypoint_info.object_name}",
        )
        logger.info(
            f"Service will start on {host}:{port} by default",
        )
        if extra_parameters:
            logger.info(
                f"Added {len(extra_parameters)} extra runtime parameters",
            )

    # Package code
    deployment_zip = output_path / DEPLOYMENT_ZIP
    package_code(
        Path(project_info.project_dir),
        deployment_zip,
    )

    # Clean up temporary directory if created
    if generated_main:
        temp_source_dir = Path(project_info.project_dir)
        if temp_source_dir.exists() and temp_source_dir.parent == output_path:
            shutil.rmtree(temp_source_dir)

    # Report size
    size_mb = deployment_zip.stat().st_size / (1024 * 1024)
    logger.info(f"Deployment package ready: {size_mb:.2f} MB")

    return str(output_path), project_info
