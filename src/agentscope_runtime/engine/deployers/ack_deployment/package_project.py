# -*- coding: utf-8 -*-
# pylint:disable=line-too-long, too-many-boolean-expressions
# pylint:disable=too-many-nested-blocks, too-many-return-statements
# pylint:disable=too-many-branches, unused-import, too-many-statements
# pylint:disable=unused-variable

import os
import shutil
import tempfile
import inspect
import ast
import importlib.util
import tarfile
from typing import List, Optional, Any
from pathlib import Path


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
            import re

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

                        # Try different possible paths for the source module
                        possible_paths = [
                            os.path.join(
                                current_dir,
                                f"{module_name}.py",
                            ),  # Same directory
                            os.path.join(
                                current_dir,
                                module_name,
                                "__init__.py",
                            ),  # Package
                            os.path.join(
                                os.path.dirname(current_dir),
                                f"{module_name}.py",
                            ),  # Parent directory
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
                                        rf"^[^\#]*{re.escape(agent_name_in_file)}\s*=\s*\w+\(",  # noqa E501
                                        rf"^[^\#]*{re.escape(agent_name_in_file)}\s*=\s*[\w.]+\(",  # noqa E501
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


def package_project(
    agent: Any,
    requirements: Optional[List[str]] = None,
    extras_package: Optional[List[str]] = None,
) -> str:
    """
    Package a project with agent and dependencies into a temporary directory.

    Args:
        agent: The agent object to be packaged
        requirements: List of pip package requirements
        extras_package: List of extra files/directories to include

    Returns:
        str: Path to the temporary directory containing the packaged project
    """
    # Create temporary directory
    temp_dir = tempfile.mkdtemp(prefix="agentscope_package_")

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
        if extras_package:
            # Get the base directory from the caller for relative path
            # calculation
            caller_filename = caller_frame.f_code.co_filename
            caller_dir = os.path.dirname(caller_filename)

            for extra_path in extras_package:
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

        # Define the template content inline
        template_content = """import asyncio
import os
from fastapi import FastAPI
from agentscope_runtime.engine import Runner
from agentscope_runtime.engine.schemas.agent_schemas import AgentRequest
from agentscope_runtime.engine.services.context_manager import ContextManager
from agentscope_runtime.engine.services.session_history_service import (
    InMemorySessionHistoryService,
)
from agentscope_runtime.engine.services.memory_service import (
    InMemoryMemoryService)
from agent_file import {{agent_name}} as agent

app = FastAPI()

# 初始化全局变量
runner = None


@app.on_event("startup")
async def startup_event():
    global runner

    # 创建上下文管理器和运行器
    session_history_service = InMemorySessionHistoryService()
    memory_service = InMemoryMemoryService()
    context_manager = ContextManager(
        session_history_service=session_history_service,
        memory_service=memory_service
    )
    await context_manager.__aenter__()
    runner = Runner(
        agent=agent,
        context_manager=context_manager
    )


@app.on_event("shutdown")
async def shutdown_event():
    global runner
    if runner and runner.context_manager:
        await runner.context_manager.__aexit__(None, None, None)


@app.get("/")
def read_root():
    return {"Hello": "World"}


@app.get("/chat")
async def chat(message: str):
    global runner
    if not runner:
        return {"error": "Runner not initialized"}

    # 创建请求
    request = AgentRequest(
        input=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": message,
                    },
                ],
            },
        ],
    )

    # 收集流式响应
    response_text = ""
    async for message in runner.stream_query(request=request):
        if hasattr(message, "text"):
            response_text += message.text

    return {"response": response_text}
"""

        # Replace placeholder in template
        main_content = template_content.replace("{{agent_name}}", agent_name)

        # Write main.py
        main_file_path = os.path.join(temp_dir, "main.py")
        with open(main_file_path, "w", encoding="utf-8") as f:
            f.write(main_content)

        # Generate requirements.txt
        if requirements:
            requirements_path = os.path.join(temp_dir, "requirements.txt")
            with open(requirements_path, "w", encoding="utf-8") as f:
                # Add base requirements for the runtime
                base_requirements = [
                    "fastapi",
                    "uvicorn",
                    "agentscope-runtime",
                ]

                # Combine base requirements with user requirements
                all_requirements = list(set(base_requirements + requirements))

                for req in all_requirements:
                    f.write(f"{req}\n")

        return temp_dir

    except Exception as e:
        # Clean up on error
        if os.path.exists(temp_dir):
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
