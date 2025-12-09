# -*- coding: utf-8 -*-
"""Base agent loader class."""
# pylint: disable=too-many-branches

import importlib.util
import os
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Optional

from agentscope_runtime.cli.utils.validators import validate_agent_source
from agentscope_runtime.engine.app.agent_app import AgentApp


class AgentLoadError(Exception):
    """Raised when agent loading fails."""


class AgentLoader(ABC):
    """Base class for agent loaders."""

    @abstractmethod
    def load(self, source: str) -> AgentApp:
        """Load AgentApp from source."""


class FileLoader:
    """Load AgentApp from Python file."""

    def load(self, file_path: str) -> AgentApp:
        """
        Load AgentApp from Python file.

        Args:
            file_path: Path to Python file

        Returns:
            AgentApp instance

        Raises:
            AgentLoadError: If loading fails
        """
        if not os.path.isfile(file_path):
            raise AgentLoadError(f"File not found: {file_path}")

        if not file_path.endswith(".py"):
            raise AgentLoadError(f"File must be a Python file: {file_path}")

        abs_path = os.path.abspath(file_path)

        try:
            # Load module from file
            spec = importlib.util.spec_from_file_location(
                "agent_module",
                abs_path,
            )
            if spec is None or spec.loader is None:
                raise AgentLoadError(f"Cannot load module from {abs_path}")

            module = importlib.util.module_from_spec(spec)

            # Add parent directory to sys.path temporarily
            parent_dir = str(Path(abs_path).parent)
            if parent_dir not in sys.path:
                sys.path.insert(0, parent_dir)
                remove_from_path = True
            else:
                remove_from_path = False

            try:
                spec.loader.exec_module(module)
            finally:
                if remove_from_path:
                    sys.path.remove(parent_dir)

            # Look for AgentApp instance
            agent_app = self._find_agent_app(module, file_path)
            return agent_app

        except Exception as e:
            raise AgentLoadError(
                f"Failed to load agent from {abs_path}: {e}",
            ) from e

    def _find_agent_app(self, module: Any, file_path: str) -> AgentApp:
        """Find AgentApp instance in module."""
        candidates = []

        # Look for exported variables
        for attr_name in ["agent_app", "app"]:
            if hasattr(module, attr_name):
                attr_value = getattr(module, attr_name)
                if isinstance(attr_value, AgentApp):
                    candidates.append((attr_name, attr_value))

        # Look for factory functions
        for attr_name in [
            "create_app",
            "create_agent_app",
            "get_app",
            "get_agent_app",
        ]:
            if hasattr(module, attr_name):
                attr_value = getattr(module, attr_name)
                if callable(attr_value):
                    try:
                        # Try calling with no arguments
                        result = attr_value()
                        if isinstance(result, AgentApp):
                            candidates.append((f"{attr_name}()", result))
                    except Exception:
                        # Factory function requires arguments, skip
                        pass

        # Look for any AgentApp instances as last resort
        for attr_name in dir(module):
            if not attr_name.startswith("_"):  # Skip private attributes
                attr_value = getattr(module, attr_name)
                if isinstance(attr_value, AgentApp):
                    if not any(
                        attr_name == candidate[0] for candidate in candidates
                    ):
                        candidates.append((attr_name, attr_value))

        if not candidates:
            raise AgentLoadError(
                f"No AgentApp found in {file_path}.\n"
                "Expected: 'agent_app' or 'app' variable, "
                "or 'create_app'/'create_agent_app' function",
            )

        if len(candidates) > 1:
            candidate_names = [name for name, _ in candidates]
            raise AgentLoadError(
                f"Multiple AgentApp instances found in {file_path}: "
                f"{candidate_names}\n"
                "Please ensure only one AgentApp is exported",
            )

        name, agent_app = candidates[0]
        return agent_app


class ProjectLoader:
    """Load AgentApp from project directory."""

    def load(
        self,
        project_dir: str,
        entrypoint: Optional[str] = None,
    ) -> AgentApp:
        """
        Load AgentApp from project directory.

        Args:
            project_dir: Path to project directory
            entrypoint: Optional entrypoint file name (e.g., "app.py",
            "main.py")

        Returns:
            AgentApp instance

        Raises:
            AgentLoadError: If loading fails
        """
        if not os.path.isdir(project_dir):
            raise AgentLoadError(f"Directory not found: {project_dir}")

        # If entrypoint is specified, use it directly
        if entrypoint:
            file_path = os.path.join(project_dir, entrypoint)
            if not os.path.isfile(file_path):
                raise AgentLoadError(
                    f"Entrypoint file not found: {file_path}",
                )
            file_loader = FileLoader()
            return file_loader.load(file_path)

        # Look for entry point files in order of preference
        entry_files = ["app.py", "agent.py", "main.py"]

        for entry_file in entry_files:
            file_path = os.path.join(project_dir, entry_file)
            if os.path.isfile(file_path):
                file_loader = FileLoader()
                return file_loader.load(file_path)

        raise AgentLoadError(
            f"No entry point found in {project_dir}.\n"
            f"Expected one of: {entry_files}",
        )


class DeploymentLoader:
    """Load AgentApp from deployment metadata."""

    def __init__(self, state_manager):
        """Initialize with state manager."""
        self.state_manager = state_manager

    def load(self, deploy_id: str) -> AgentApp:
        """
        Load AgentApp from deployment ID.

        Args:
            deploy_id: Deployment ID

        Returns:
            AgentApp instance

        Raises:
            AgentLoadError: If loading fails
        """
        # Get deployment metadata
        deployment = self.state_manager.get(deploy_id)
        if deployment is None:
            raise AgentLoadError(f"Deployment not found: {deploy_id}")

        # Load agent from original source
        source = deployment.agent_source

        # Determine source type and delegate to appropriate loader
        source_type, normalized_source = validate_agent_source(source)

        if source_type == "file":
            loader = FileLoader()
        elif source_type == "directory":
            loader = ProjectLoader()
        else:
            raise AgentLoadError(
                f"Cannot load from deployment with source type: {source_type}",
            )

        return loader.load(normalized_source)


class UnifiedAgentLoader:
    """Unified loader that handles all source types."""

    def __init__(self, state_manager=None):
        """Initialize with optional state manager."""
        self.state_manager = state_manager
        self.file_loader = FileLoader()
        self.project_loader = ProjectLoader()
        if state_manager:
            self.deployment_loader = DeploymentLoader(state_manager)
        else:
            self.deployment_loader = None

    def load(self, source: str, entrypoint: Optional[str] = None) -> AgentApp:
        """
        Load AgentApp from any source type.

        Args:
            source: Path to file/directory or deployment ID
            entrypoint: Optional entrypoint file name for directory sources

        Returns:
            AgentApp instance

        Raises:
            AgentLoadError: If loading fails
        """
        try:
            source_type, normalized_source = validate_agent_source(source)

            if source_type == "deployment_id":
                if self.deployment_loader is None:
                    raise AgentLoadError(
                        "Cannot load from deployment ID: state manager not "
                        "available",
                    )
                return self.deployment_loader.load(normalized_source)
            elif source_type == "file":
                if entrypoint:
                    raise AgentLoadError(
                        "The --entrypoint option is only applicable for "
                        "directory sources, not file sources",
                    )
                return self.file_loader.load(normalized_source)
            elif source_type == "directory":
                return self.project_loader.load(
                    normalized_source,
                    entrypoint=entrypoint,
                )
            else:
                raise AgentLoadError(f"Unknown source type: {source_type}")

        except Exception as e:
            if isinstance(e, AgentLoadError):
                raise
            raise AgentLoadError(
                f"Failed to load agent from {source}: {e}",
            ) from e
