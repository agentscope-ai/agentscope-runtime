# -*- coding: utf-8 -*-
# pylint:disable=too-many-boolean-expressions, too-many-nested-blocks
# pylint:disable=too-many-return-statements, unused-variable
# pylint:disable=cell-var-from-loop, too-many-branches, too-many-statements

import ast
import hashlib
import inspect
import os
import re
import shutil
import tarfile
import tempfile
from pathlib import Path
from typing import List, Optional, Any, Tuple, Dict

from pydantic import BaseModel

try:
    import tomllib  # Python 3.11+
except ImportError:
    try:
        import tomli as tomllib  # type: ignore[no-redef]
    except ImportError:
        tomllib = None

from .service_utils.fastapi_templates import FastAPITemplateManager
from .service_utils.service_config import ServicesConfig

# Default template will be loaded from template file


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


def _prepare_custom_endpoints_for_template(
    custom_endpoints: Optional[List[Dict]],
    temp_dir: str,
) -> Tuple[Optional[List[Dict]], List[str]]:
    """
    Prepare custom endpoints for template rendering.
    Copy handler source directories to ensure all dependencies are available.

    Args:
        custom_endpoints: List of custom endpoint configurations
        temp_dir: Temporary directory where files will be copied

    Returns:
        Tuple of:
        - Prepared endpoint configurations with file information
        - List of copied directory names (for sys.path setup)
    """
    if not custom_endpoints:
        return None, []

    prepared_endpoints = []
    handler_dirs_copied = set()  # Track copied directories to avoid duplicates
    copied_dir_names = []  # Track directory names for sys.path

    for endpoint in custom_endpoints:
        prepared_endpoint = {
            "path": endpoint.get("path", "/unknown"),
            "methods": endpoint.get("methods", ["POST"]),
            "module": endpoint.get("module"),
            "function_name": endpoint.get("function_name"),
        }

        # Try to get handler source file if handler is provided
        handler = endpoint.get("handler")
        if handler and callable(handler):
            try:
                # Get the source file of the handler
                handler_file = inspect.getfile(handler)
                handler_name = handler.__name__

                # Skip if it's a built-in or from site-packages
                if (
                    not handler_file.endswith(".py")
                    or "site-packages" in handler_file
                ):
                    raise ValueError("Handler from non-user code")

                # Get the directory containing the handler file
                handler_dir = os.path.dirname(os.path.abspath(handler_file))

                # Copy the entire working directory if not already copied
                if handler_dir not in handler_dirs_copied:
                    # Create a subdirectory name for this handler's context
                    dir_name = os.path.basename(handler_dir)
                    if not dir_name or dir_name == ".":
                        dir_name = "handler_context"

                    # Sanitize directory name
                    dir_name = re.sub(r"[^a-zA-Z0-9_]", "_", dir_name)

                    # Ensure unique directory name
                    counter = 1
                    base_dir_name = dir_name
                    dest_context_dir = os.path.join(temp_dir, dir_name)
                    while os.path.exists(dest_context_dir):
                        dir_name = f"{base_dir_name}_{counter}"
                        dest_context_dir = os.path.join(temp_dir, dir_name)
                        counter += 1

                    # Copy entire directory structure
                    # Exclude common non-essential directories
                    ignore_patterns = shutil.ignore_patterns(
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
                    )

                    shutil.copytree(
                        handler_dir,
                        dest_context_dir,
                        ignore=ignore_patterns,
                        dirs_exist_ok=True,
                    )

                    handler_dirs_copied.add(handler_dir)
                    copied_dir_names.append(dir_name)
                else:
                    # Find the existing copied directory name
                    for existing_dir in os.listdir(temp_dir):
                        existing_path = os.path.join(temp_dir, existing_dir)
                        if os.path.isdir(existing_path):
                            # Check if this is the directory we already copied
                            original_handler_basename = os.path.basename(
                                handler_dir,
                            )
                            if existing_dir.startswith(
                                re.sub(
                                    r"[^a-zA-Z0-9_]",
                                    "_",
                                    original_handler_basename,
                                ),
                            ):
                                dir_name = existing_dir
                                break
                    else:
                        # Fallback if not found
                        dir_name = re.sub(
                            r"[^a-zA-Z0-9_]",
                            "_",
                            os.path.basename(handler_dir),
                        )

                # Calculate the module path relative to the handler directory
                handler_file_rel = os.path.relpath(handler_file, handler_dir)
                # Convert file path to module path
                module_parts = os.path.splitext(handler_file_rel)[0].split(
                    os.sep,
                )
                if module_parts[-1] == "__init__":
                    module_parts = module_parts[:-1]

                # Construct the full import path
                if module_parts:
                    module_path = f"{dir_name}.{'.'.join(module_parts)}"
                else:
                    module_path = dir_name

                # Set the module and function name for template
                prepared_endpoint["handler_module"] = module_path
                prepared_endpoint["function_name"] = handler_name

            except (OSError, TypeError, ValueError) as e:
                # If source file extraction fails, try module/function_name
                import traceback

                print(f"Warning: Failed to copy handler directory: {e}")
                traceback.print_exc()

        # Add inline code if no handler module/function available
        if not prepared_endpoint.get("handler_module") and (
            not prepared_endpoint["module"]
            or not prepared_endpoint["function_name"]
        ):
            prepared_endpoint["inline_code"] = endpoint.get(
                "inline_code",
                'lambda request: {"error": "Handler not available"}',
            )

        prepared_endpoints.append(prepared_endpoint)

    return prepared_endpoints, copied_dir_names


class PackageConfig(BaseModel):
    """Configuration for project packaging"""

    requirements: Optional[List[str]] = None
    extra_packages: Optional[List[str]] = None
    output_dir: Optional[str] = None
    endpoint_path: Optional[str] = "/process"
    deployment_mode: Optional[str] = "standalone"  # New: deployment mode
    services_config: Optional[
        ServicesConfig
    ] = None  # New: services configuration
    protocol_adapters: Optional[List[Any]] = None  # New: protocol adapters
    custom_endpoints: Optional[
        List[Dict]
    ] = None  # New: custom endpoints configuration
    # Celery configuration parameters
    broker_url: Optional[str] = None
    backend_url: Optional[str] = None
    enable_embedded_worker: bool = False


def _find_agent_source_file(
    agent_obj: Any,
    agent_name: str,
    caller_frame,
) -> str:
    """
    Find the file that contains the agent instance definition (where the
    agent variable is assigned).
    This prioritizes finding where the agent instance was created rather
    than where the class is defined.
    """

    # Method 1: Search through the call stack to find where the agent
    # instance was defined
    frame = caller_frame
    found_files = []  # Store potential files for analysis
    agent_names_in_frames = []  # Store agent names found in each frame

    while frame:
        try:
            frame_filename = frame.f_code.co_filename

            # Skip internal/system files and focus on user code
            if (
                not frame_filename.endswith(".py")
                or "site-packages" in frame_filename
            ):
                frame = frame.f_back
                continue

            # Check if this frame contains our agent variable
            frame_locals = frame.f_locals
            frame_globals = frame.f_globals

            # Look for the agent object (by identity, not name) in both
            # locals and globals
            found_agent_name = None
            for var_name, var_value in frame_locals.items():
                if var_value is agent_obj:
                    found_agent_name = var_name
                    break

            if not found_agent_name:
                for var_name, var_value in frame_globals.items():
                    if var_value is agent_obj:
                        found_agent_name = var_name
                        break

            if found_agent_name:
                # Found the frame where this agent instance exists
                found_files.append(frame_filename)
                agent_names_in_frames.append(found_agent_name)

        except (AttributeError, TypeError):
            # Handle any errors in frame inspection
            pass

        frame = frame.f_back

    # Method 2: Analyze found files to determine which one contains the
    # actual instance definition
    # Reverse the order to prioritize files found later in the stack (
    # typically user code)
    for i, file_path in enumerate(reversed(found_files)):
        # Get the corresponding agent name for this file
        agent_name_in_file = agent_names_in_frames[len(found_files) - 1 - i]

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Check if this file contains an import statement for the agent
            # If so, we should look for the original source file
            import_patterns = [
                rf"^[^\#]*from\s+(\w+)\s+import\s+.*"
                rf"{re.escape(agent_name_in_file)}",
                rf"^[^\#]*from\s+([\w.]+)\s+import\s+.*"
                rf"{re.escape(agent_name_in_file)}",
            ]

            # Check if this file imports the agent from another module
            lines = content.split("\n")
            for line in lines:
                for import_pattern in import_patterns:
                    match = re.search(import_pattern, line)
                    if match:
                        module_name = match.group(1)
                        # Try to find the source module file
                        current_dir = os.path.dirname(file_path)

                        # Convert dotted module name to filesystem path
                        module_path = module_name.replace(".", os.sep)

                        # Try different possible paths for the source module
                        possible_paths = [
                            # Same directory - simple module name
                            os.path.join(
                                current_dir,
                                f"{module_name}.py",
                            ),
                            # Same directory - dotted path
                            os.path.join(
                                current_dir,
                                f"{module_path}.py",
                            ),
                            # Package in same directory
                            os.path.join(
                                current_dir,
                                module_name,
                                "__init__.py",
                            ),
                            # Package with dotted path
                            os.path.join(
                                current_dir,
                                module_path,
                                "__init__.py",
                            ),
                            # Parent directory - simple module name
                            os.path.join(
                                os.path.dirname(current_dir),
                                f"{module_name}.py",
                            ),
                            # Parent directory - dotted path
                            os.path.join(
                                os.path.dirname(current_dir),
                                f"{module_path}.py",
                            ),
                            # Current working directory - simple module name
                            os.path.join(
                                os.getcwd(),
                                f"{module_name}.py",
                            ),
                            # Current working directory - dotted path
                            os.path.join(
                                os.getcwd(),
                                f"{module_path}.py",
                            ),
                            # Current working directory - package
                            os.path.join(
                                os.getcwd(),
                                module_path,
                                "__init__.py",
                            ),
                        ]

                        for source_path in possible_paths:
                            if os.path.exists(source_path):
                                # Check if this source file contains the
                                # actual assignment
                                try:
                                    with open(
                                        source_path,
                                        "r",
                                        encoding="utf-8",
                                    ) as src_f:
                                        src_content = src_f.read()

                                    # Look for the assignment in the source
                                    # file
                                    assignment_patterns = [
                                        rf"^[^\#]*{re.escape(agent_name_in_file)}"  # noqa E501
                                        rf"\s*=\s*\w+\(",
                                        rf"^[^\#]*{re.escape(agent_name_in_file)}"  # noqa E501
                                        rf"\s*=\s*[\w.]+\(",
                                    ]

                                    src_lines = src_content.split("\n")
                                    for src_line in src_lines:
                                        if (
                                            not src_line.strip()
                                            or src_line.strip().startswith("#")
                                            or src_line.strip().startswith(
                                                "def ",
                                            )
                                            or src_line.strip().startswith(
                                                "from ",
                                            )
                                            or src_line.strip().startswith(
                                                "import ",
                                            )
                                            or src_line.strip().startswith(
                                                "class ",
                                            )
                                        ):
                                            continue

                                        for (
                                            assign_pattern
                                        ) in assignment_patterns:
                                            if re.search(
                                                assign_pattern,
                                                src_line,
                                            ):
                                                if "=" in src_line:
                                                    left_side = src_line.split(
                                                        "=",
                                                    )[0]
                                                    if (
                                                        agent_name_in_file
                                                        in left_side
                                                        and "("
                                                        not in left_side
                                                    ):
                                                        indent_level = len(
                                                            src_line,
                                                        ) - len(
                                                            src_line.lstrip(),
                                                        )
                                                        if indent_level <= 4:
                                                            return source_path

                                except (OSError, UnicodeDecodeError):
                                    continue
                        break  # Found import, no need to check other patterns

            # If no import found, check if this file itself contains the
            # assignment
            assignment_patterns = [
                # direct assignment: agent_name = ClassName(
                rf"^[^\#]*{re.escape(agent_name_in_file)}\s*=\s*\w+\(",
                # module assignment: agent_name = module.ClassName(
                rf"^[^\#]*{re.escape(agent_name_in_file)}\s*=\s*[\w.]+\(",
            ]

            # Look for actual variable assignment (not function parameters
            # or imports)
            for line_num, line in enumerate(lines):
                stripped_line = line.strip()
                # Skip comments, empty lines, function definitions, and imports
                if (
                    not stripped_line
                    or stripped_line.startswith("#")
                    or stripped_line.startswith("def ")
                    or stripped_line.startswith("from ")
                    or stripped_line.startswith("import ")
                    or stripped_line.startswith("class ")
                ):
                    continue

                # Check if this line contains the agent assignment
                for pattern in assignment_patterns:
                    if re.search(pattern, line):
                        # Double check that this is a real assignment,
                        # not inside function parameters by checking if the
                        # line has '=' and the agent_name is on the left side
                        if "=" in line:
                            left_side = line.split("=")[0]
                            if (
                                agent_name_in_file in left_side
                                and "(" not in left_side
                            ):
                                # Additional context check: make sure this
                                # is not indented too much (likely inside a
                                # function if heavily indented)
                                indent_level = len(line) - len(line.lstrip())
                                if (
                                    indent_level <= 4
                                ):  # Top level or minimal indentation
                                    return file_path

        except (OSError, UnicodeDecodeError):
            # If we can't read the file, continue to next file
            continue

    # Method 3: If no assignment pattern found, return the first found file
    if found_files:
        return found_files[0]

    # Method 4: Fall back to original caller-based approach if stack search
    # fails
    caller_filename = caller_frame.f_code.co_filename
    caller_dir = os.path.dirname(caller_filename)

    # Check if we have the import information in the caller's globals
    # Look for module objects that might contain the agent
    for var_name, var_obj in caller_frame.f_globals.items():
        if hasattr(var_obj, "__file__") and hasattr(var_obj, agent_name):
            # This looks like a module that contains our agent
            if getattr(var_obj, agent_name, None) is caller_frame.f_locals.get(
                agent_name,
            ):
                return var_obj.__file__

    # If direct lookup failed, try to parse the import statements
    try:
        with open(caller_filename, "r", encoding="utf-8") as f:
            content = f.read()

        tree = ast.parse(content)

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                # Look for "from module_name import agent_name"
                if node.names and node.module:
                    for alias in node.names:
                        imported_name = (
                            alias.asname if alias.asname else alias.name
                        )
                        if imported_name == agent_name:
                            # Found the import statement
                            module_path = os.path.join(
                                caller_dir,
                                f"{node.module}.py",
                            )
                            if os.path.exists(module_path):
                                return module_path
                            # Try relative import
                            if node.level > 0:  # relative import
                                parent_path = caller_dir
                                for _ in range(node.level - 1):
                                    parent_path = os.path.dirname(parent_path)
                                module_path = os.path.join(
                                    parent_path,
                                    f"{node.module}.py",
                                )
                                if os.path.exists(module_path):
                                    return module_path

            elif isinstance(node, ast.Import):
                # Look for "import module_name" where agent might be
                # module_name.agent_name
                for alias in node.names:
                    module_name = alias.asname if alias.asname else alias.name
                    if module_name in caller_frame.f_globals:
                        module_obj = caller_frame.f_globals[module_name]
                        if hasattr(module_obj, "__file__") and hasattr(
                            module_obj,
                            agent_name,
                        ):
                            return module_obj.__file__

    except Exception as e:
        # If parsing fails, we'll fall back to the caller file
        print(e)

    return caller_filename


def _extract_agent_name_from_source(
    agent_file_path: str,
    agent_obj: Any,
) -> str:
    """
    Extract the actual variable name of the agent from the source file by
    looking for variable assignments and trying to match the object type.

    Args:
        agent_file_path: Path to the source file containing agent definition
        agent_obj: The agent object to match

    Returns:
        str: The variable name used in the source file, or "agent" as fallback
    """
    try:
        with open(agent_file_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Get the class name of the agent object
        agent_class_name = agent_obj.__class__.__name__

        lines = content.split("\n")
        potential_names = []

        for line in lines:
            stripped_line = line.strip()
            # Skip comments, empty lines, function definitions, and imports
            if (
                not stripped_line
                or stripped_line.startswith("#")
                or stripped_line.startswith("def ")
                or stripped_line.startswith("from ")
                or stripped_line.startswith("import ")
                or stripped_line.startswith("class ")
            ):
                continue

            # Look for variable assignment patterns: var_name = ...
            if "=" in line:
                left_side = line.split("=")[0].strip()
                right_side = line.split("=", 1)[1].strip()

                # Make sure it's a simple variable assignment (not inside
                # parentheses or functions)
                if (
                    left_side
                    and "(" not in left_side
                    and left_side.isidentifier()
                    and not left_side.startswith("_")
                ):  # Skip private variables
                    # Check indentation level - should be top level or
                    # minimal indentation
                    indent_level = len(line) - len(line.lstrip())
                    if indent_level <= 4:  # Top level or minimal indentation
                        # Check if the right side contains the agent class name
                        if agent_class_name in right_side:
                            # This is likely our agent assignment
                            potential_names.insert(0, left_side)
                        # # Also check for assignments that might create the
                        # agent through constructor calls
                        # elif "(" in right_side:
                        #     potential_names.append(left_side)

        # Return the first potential name found (prioritizing class name
        # matches)
        if potential_names:
            return potential_names[0]

    except (OSError, UnicodeDecodeError):
        pass

    return "agent"  # fallback


def _calculate_directory_hash(directory_path: str) -> str:
    """
    Calculate a hash representing the entire contents of a directory.

    Args:
        directory_path: Path to the directory to hash

    Returns:
        str: SHA256 hash of the directory contents
    """
    hasher = hashlib.sha256()

    if not os.path.exists(directory_path):
        return ""

    # Walk through directory and hash all file contents and paths
    for root, dirs, files in sorted(os.walk(directory_path)):
        # Sort to ensure consistent ordering
        dirs.sort()
        files.sort()

        for filename in files:
            file_path = os.path.join(root, filename)

            # Hash the relative path
            rel_path = os.path.relpath(file_path, directory_path)
            hasher.update(rel_path.encode("utf-8"))

            # Hash the file contents
            try:
                with open(file_path, "rb") as f:
                    for chunk in iter(lambda: f.read(4096), b""):
                        hasher.update(chunk)
            except (OSError, IOError):
                # Skip files that can't be read
                continue

    return hasher.hexdigest()


def _compare_directories(old_dir: str, new_dir: str) -> bool:
    """
    Compare two directories to see if their contents are identical.

    Args:
        old_dir: Path to the old directory
        new_dir: Path to the new directory

    Returns:
        bool: True if directories have identical contents, False otherwise
    """
    old_hash = _calculate_directory_hash(old_dir)
    new_hash = _calculate_directory_hash(new_dir)

    return old_hash == new_hash and old_hash != ""


def package_project(
    agent: Any,
    config: PackageConfig,
    dockerfile_path: Optional[str] = None,
    template: Optional[str] = None,  # Use template file by default
) -> Tuple[str, bool]:
    """
    Package a project with agent and dependencies into a temporary directory.

    Args:
        agent: The agent object to be packaged
        config: The configuration of the package
        dockerfile_path: Path to the Docker file
        template: User override template string
            (if None, uses standalone template file)

    Returns:
        Tuple[str, bool]: A tuple containing:
            - str: Path to the directory containing the packaged project
            - bool: True if the directory was updated,
                False if no update was needed
    """
    # Create temporary directory
    original_temp_dir = temp_dir = None
    if config.output_dir is None:
        temp_dir = tempfile.mkdtemp(prefix="agentscope_package_")
        needs_update = True  # New directory always needs update
    else:
        temp_dir = config.output_dir
        # Check if directory exists and has content
        if os.path.exists(temp_dir) and os.listdir(temp_dir):
            # Directory exists and has content, create a temporary directory
            # first to generate new content for comparison
            original_temp_dir = temp_dir
            temp_dir = tempfile.mkdtemp(prefix="agentscope_package_new_")
            # copy docker file to this place
            if dockerfile_path:
                shutil.copy(
                    dockerfile_path,
                    os.path.join(
                        temp_dir,
                        "Dockerfile",
                    ),
                )
            needs_update = None  # Will be determined after comparison
        else:
            # Directory doesn't exist or is empty, needs update
            needs_update = True
            # Create directory if it doesn't exist
            if not os.path.exists(temp_dir):
                os.makedirs(temp_dir)

    try:
        # Extract agent variable name from the caller's frame
        frame = inspect.currentframe()
        caller_frame = frame.f_back
        agent_name = None

        # Look for the agent variable name in caller's locals and globals
        for var_name, var_value in caller_frame.f_locals.items():
            if var_value is agent:
                agent_name = var_name
                break

        if not agent_name:
            for var_name, var_value in caller_frame.f_globals.items():
                if var_value is agent:
                    agent_name = var_name
                    break

        if not agent_name:
            agent_name = "agent"  # fallback name

        # Find the source file for the agent
        agent_file_path = _find_agent_source_file(
            agent,
            agent_name,
            caller_frame,
        )

        if not os.path.exists(agent_file_path):
            raise ValueError(
                f"Unable to locate agent source file: {agent_file_path}",
            )

        # Extract the actual agent variable name from the source file
        actual_agent_name = _extract_agent_name_from_source(
            agent_file_path,
            agent,
        )

        # Use the actual name from source file for the template
        agent_name = actual_agent_name

        # Copy agent file to temp directory as agent_file.py
        agent_dest_path = os.path.join(temp_dir, "agent_file.py")
        shutil.copy2(agent_file_path, agent_dest_path)

        # Copy extra package files
        if config.extra_packages:
            # Get the base directory from the agent_file_path for relative path
            # calculation
            caller_dir = os.path.dirname(agent_file_path)

            for extra_path in config.extra_packages:
                if os.path.isfile(extra_path):
                    # Calculate relative path from caller directory
                    if os.path.isabs(extra_path):
                        try:
                            # Try to get relative path from caller directory
                            rel_path = os.path.relpath(extra_path, caller_dir)
                            # If the relative path goes up beyond the caller
                            # directory, just use filename
                            if rel_path.startswith(".."):
                                dest_path = os.path.join(
                                    temp_dir,
                                    os.path.basename(extra_path),
                                )
                            else:
                                dest_path = os.path.join(temp_dir, rel_path)
                        except ValueError:
                            # If relative path calculation fails (e.g.,
                            # different drives on Windows)
                            dest_path = os.path.join(
                                temp_dir,
                                os.path.basename(extra_path),
                            )
                    else:
                        # If it's already a relative path, use it as is
                        dest_path = os.path.join(temp_dir, extra_path)

                    # Create destination directory if it doesn't exist
                    dest_dir = os.path.dirname(dest_path)
                    if dest_dir and not os.path.exists(dest_dir):
                        os.makedirs(dest_dir)

                    # Copy file to destination
                    shutil.copy2(extra_path, dest_path)

                elif os.path.isdir(extra_path):
                    # Calculate relative path for directory
                    if os.path.isabs(extra_path):
                        try:
                            rel_path = os.path.relpath(extra_path, caller_dir)
                            if rel_path.startswith(".."):
                                dest_path = os.path.join(
                                    temp_dir,
                                    os.path.basename(extra_path),
                                )
                            else:
                                dest_path = os.path.join(temp_dir, rel_path)
                        except ValueError:
                            dest_path = os.path.join(
                                temp_dir,
                                os.path.basename(extra_path),
                            )
                    else:
                        dest_path = os.path.join(temp_dir, extra_path)

                    # Copy directory to destination
                    shutil.copytree(extra_path, dest_path, dirs_exist_ok=True)

        # Use template manager for better template handling
        template_manager = FastAPITemplateManager()

        # Convert protocol_adapters to string representation for template
        protocol_adapters_str = None
        if config.protocol_adapters:
            # For standalone deployment, we need to generate code that
            # creates the adapters
            # This is a simplified approach - in practice, you might want
            # more sophisticated serialization
            adapter_imports = []
            adapter_instances = []
            for i, adapter in enumerate(config.protocol_adapters):
                adapter_class = adapter.__class__
                adapter_module = adapter_class.__module__
                adapter_name = adapter_class.__name__

                # Add import
                adapter_imports.append(
                    f"from {adapter_module} import {adapter_name}",
                )

                # Add instance creation (simplified - doesn't handle
                # complex constructor args)
                adapter_instances.append(f"{adapter_name}(agent=agent)")

            # Create the protocol_adapters array string
            if adapter_instances:
                imports_str = "\n".join(adapter_imports)
                instances_str = "[" + ", ".join(adapter_instances) + "]"
                protocol_adapters_str = (
                    f"# Protocol adapter imports\n{imports_str}\n\n"
                    f"# Protocol adapters\nprotocol_adapters = {instances_str}"
                )

        # Convert celery_config to string representation for template
        celery_config_str = None
        config_lines = []

        # Generate celery configuration code
        config_lines.append("# Celery configuration")

        if config.broker_url:
            config_lines.append(
                f'celery_config["broker_url"] = "{config.broker_url}"',
            )

        if config.backend_url:
            config_lines.append(
                f'celery_config["backend_url"] = "{config.backend_url}"',
            )

        if config.enable_embedded_worker:
            config_lines.append(
                f'celery_config["enable_embedded_worker"] = '
                f"{config.enable_embedded_worker}",
            )

        if config_lines:
            celery_config_str = "\n".join(config_lines)

        # Prepare custom endpoints and get copied directory names
        (
            custom_endpoints_data,
            handler_dirs,
        ) = _prepare_custom_endpoints_for_template(
            config.custom_endpoints,
            temp_dir,
        )

        # Render template - use template file by default,
        # or user-provided string
        if template is None:
            # Use standalone template file
            main_content = template_manager.render_standalone_template(
                agent_name=agent_name,
                endpoint_path=config.endpoint_path or "/process",
                deployment_mode=config.deployment_mode or "standalone",
                protocol_adapters=protocol_adapters_str,
                celery_config=celery_config_str,
                custom_endpoints=custom_endpoints_data,
                handler_dirs=handler_dirs,
            )
        else:
            # Use user-provided template string
            main_content = template_manager.render_template_from_string(
                template,
                agent_name=agent_name,
                endpoint_path=config.endpoint_path,
                deployment_mode=config.deployment_mode or "standalone",
                protocol_adapters=protocol_adapters_str,
                celery_config=celery_config_str,
                custom_endpoints=custom_endpoints_data,
                handler_dirs=handler_dirs,
            )

        # Write main.py
        main_file_path = os.path.join(temp_dir, "main.py")
        with open(main_file_path, "w", encoding="utf-8") as f:
            f.write(main_content)

        # Generate requirements.txt with unified dependencies
        requirements_path = os.path.join(temp_dir, "requirements.txt")
        with open(requirements_path, "w", encoding="utf-8") as f:
            # Get the current package version
            package_version = _get_package_version()

            # Add base requirements for the unified runtime
            if package_version:
                base_requirements = [
                    "fastapi",
                    "uvicorn",
                    f"agentscope-runtime=={package_version}",
                    f"agentscope-runtime[sandbox]=={package_version}",
                    f"agentscope-runtime[deployment]=={package_version}",
                    "pydantic",
                    "jinja2",  # For template rendering
                    "psutil",
                    "redis",  # For process management
                ]
            else:
                # Fallback to unversioned if version cannot be determined
                base_requirements = [
                    "fastapi",
                    "uvicorn",
                    "agentscope-runtime",
                    "agentscope-runtime[sandbox]",
                    "agentscope-runtime[deployment]",
                    "pydantic",
                    "jinja2",  # For template rendering
                    "psutil",  # For process management
                    "redis",  # For process management
                ]
            if not config.requirements:
                config.requirements = []

            # Add Celery requirements if Celery is configured
            celery_requirements = []
            if (
                config.broker_url
                or config.backend_url
                or config.enable_embedded_worker
            ):
                celery_requirements = ["celery", "redis"]

            # Combine base requirements with user requirements and Celery
            # requirements
            all_requirements = sorted(
                list(
                    set(
                        base_requirements
                        + config.requirements
                        + celery_requirements,
                    ),
                ),
            )
            for req in all_requirements:
                f.write(f"{req}\n")

        # Generate services configuration file if specified
        if config.services_config:
            config_path = os.path.join(temp_dir, "services_config.json")
            import json

            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config.services_config.model_dump(), f, indent=2)

        # If we need to determine if update is needed (existing directory case)
        if needs_update is None and original_temp_dir is not None:
            # Compare the original directory with the new content
            if _compare_directories(original_temp_dir, temp_dir):
                # Content is identical, no update needed
                needs_update = False
                # Clean up the temporary new directory and return
                # original directory
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir)
                return original_temp_dir, needs_update
            else:
                # Content is different, update needed
                needs_update = True
                # Replace the content in the original directory
                # First, clear the original directory
                for item in os.listdir(original_temp_dir):
                    item_path = os.path.join(original_temp_dir, item)
                    if os.path.isdir(item_path):
                        shutil.rmtree(item_path)
                    else:
                        os.remove(item_path)

                # Copy new content to original directory
                for item in os.listdir(temp_dir):
                    src_path = os.path.join(temp_dir, item)
                    dst_path = os.path.join(original_temp_dir, item)
                    if os.path.isdir(src_path):
                        shutil.copytree(src_path, dst_path)
                    else:
                        shutil.copy2(src_path, dst_path)

                # Clean up temporary directory
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir)
                return original_temp_dir, needs_update

        return temp_dir, needs_update or True

    except Exception as e:
        # Clean up on error
        if os.path.exists(temp_dir) and temp_dir != config.output_dir:
            shutil.rmtree(temp_dir)
        # If we're using a temporary directory for comparison, clean it up
        if (
            original_temp_dir
            and temp_dir != original_temp_dir
            and os.path.exists(temp_dir)
        ):
            shutil.rmtree(temp_dir)
        raise e


def create_tar_gz(
    directory_path: str,
    output_path: Optional[str] = None,
) -> str:
    """
    Package a directory into a tar.gz file.

    Args:
        directory_path: Path to the directory to package
        output_path: Optional output path for the tar.gz file. If not provided,
                    will create the tar.gz in the same parent directory as
                    the source directory

    Returns:
        str: Path to the created tar.gz file

    Raises:
        ValueError: If the directory doesn't exist
        OSError: If there's an error creating the tar.gz file
    """
    if not os.path.exists(directory_path):
        raise ValueError(f"Directory does not exist: {directory_path}")

    if not os.path.isdir(directory_path):
        raise ValueError(f"Path is not a directory: {directory_path}")

    # Generate output path if not provided
    if output_path is None:
        dir_name = os.path.basename(os.path.normpath(directory_path))
        parent_dir = os.path.dirname(directory_path)
        output_path = os.path.join(parent_dir, f"{dir_name}.tar.gz")

    try:
        with tarfile.open(output_path, "w:gz") as tar:
            # Add all contents of the directory to the tar file
            for root, dirs, files in os.walk(directory_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    # Calculate the archive name (relative to the source
                    # directory)
                    arcname = os.path.relpath(file_path, directory_path)
                    tar.add(file_path, arcname=arcname)

                # Also add empty directories
                for dir_name in dirs:
                    dir_path = os.path.join(root, dir_name)
                    if not os.listdir(dir_path):  # Empty directory
                        arcname = os.path.relpath(dir_path, directory_path)
                        tar.add(dir_path, arcname=arcname)

        return output_path

    except Exception as e:
        # Clean up partial file if it exists
        if os.path.exists(output_path):
            try:
                os.remove(output_path)
            except OSError:
                pass
        raise OSError(f"Failed to create tar.gz file: {str(e)}") from e
