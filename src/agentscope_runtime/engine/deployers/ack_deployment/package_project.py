# -*- coding: utf-8 -*-
import os
import shutil
import tempfile
import inspect
import ast
import importlib.util
import tarfile
from typing import List, Optional, Any
from pathlib import Path


def _find_agent_source_file(agent_name: str, caller_frame) -> str:
    """
    Find the file that contains the agent definition by analyzing the caller's imports.
    """
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
                # Look for "import module_name" where agent might be module_name.agent_name
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
        pass

    return caller_filename


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
        agent_file_path = _find_agent_source_file(agent_name, caller_frame)

        if not os.path.exists(agent_file_path):
            raise ValueError(
                f"Unable to locate agent source file: {agent_file_path}",
            )

        # Copy agent file to temp directory as agent_file.py
        agent_dest_path = os.path.join(temp_dir, "agent_file.py")
        shutil.copy2(agent_file_path, agent_dest_path)

        # Copy extra package files
        if extras_package:
            # Get the base directory from the caller for relative path calculation
            caller_filename = caller_frame.f_code.co_filename
            caller_dir = os.path.dirname(caller_filename)

            for extra_path in extras_package:
                if os.path.isfile(extra_path):
                    # Calculate relative path from caller directory
                    if os.path.isabs(extra_path):
                        try:
                            # Try to get relative path from caller directory
                            rel_path = os.path.relpath(extra_path, caller_dir)
                            # If the relative path goes up beyond the caller directory, just use filename
                            if rel_path.startswith(".."):
                                dest_path = os.path.join(
                                    temp_dir,
                                    os.path.basename(extra_path),
                                )
                            else:
                                dest_path = os.path.join(temp_dir, rel_path)
                        except ValueError:
                            # If relative path calculation fails (e.g., different drives on Windows)
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
                    will create the tar.gz in the same parent directory as the source directory

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
                    # Calculate the archive name (relative to the source directory)
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
        raise OSError(f"Failed to create tar.gz file: {str(e)}")
