# -*- coding: utf-8 -*-
"""Deployment state management."""

import os
import json
import shutil
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime

from agentscope_runtime.cli.state.schema import (
    Deployment,
    StateFileSchema,
    format_timestamp,
)


class DeploymentStateManager:
    """Manages deployment state persistence."""

    def __init__(self, state_dir: Optional[str] = None):
        """
        Initialize state manager.

        Args:
            state_dir: Custom state directory (defaults to ~/.as-runtime)
        """
        if state_dir is None:
            state_dir = os.path.expanduser("~/.as-runtime")

        self.state_dir = Path(state_dir)
        self.state_file = self.state_dir / "deployments.json"
        self._ensure_state_dir()

    def _ensure_state_dir(self) -> None:
        """Ensure state directory exists."""
        self.state_dir.mkdir(parents=True, exist_ok=True)

    def _backup_state_file(self) -> None:
        """Create backup of state file before modifications."""
        if self.state_file.exists():
            backup_file = (
                self.state_dir
                / f"deployments.backup.{int(datetime.now().timestamp())}.json"
            )
            shutil.copy2(self.state_file, backup_file)

            # Keep only last 5 backups
            backups = sorted(self.state_dir.glob("deployments.backup.*.json"))
            if len(backups) > 5:
                for old_backup in backups[:-5]:
                    old_backup.unlink()

    def _read_state(self) -> Dict[str, Any]:
        """Read state file with validation."""
        if not self.state_file.exists():
            return StateFileSchema.create_empty()

        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Validate and migrate if needed
            data = StateFileSchema.migrate_if_needed(data)

            if not StateFileSchema.validate(data):
                raise ValueError("Invalid state file format")

            return data

        except (json.JSONDecodeError, ValueError) as e:
            # State file is corrupted, return empty state
            # Original file is kept as-is for manual recovery
            print(
                f"Warning: State file is corrupted ({e}). Starting with empty state.",
            )
            return StateFileSchema.create_empty()

    def _write_state(self, data: Dict[str, Any]) -> None:
        """Write state file atomically."""
        # Validate before writing
        if not StateFileSchema.validate(data):
            raise ValueError("Invalid state data")

        # Backup existing state
        self._backup_state_file()

        # Write to temporary file first
        temp_file = self.state_file.with_suffix(".tmp")
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        # Atomic rename
        temp_file.replace(self.state_file)

    def save(self, deployment: Deployment) -> None:
        """
        Save deployment metadata.

        Args:
            deployment: Deployment instance to save
        """
        state = self._read_state()
        state["deployments"][deployment.id] = deployment.to_dict()
        self._write_state(state)

    def get(self, deploy_id: str) -> Optional[Deployment]:
        """
        Retrieve deployment by ID.

        Args:
            deploy_id: Deployment ID

        Returns:
            Deployment instance or None if not found
        """
        state = self._read_state()
        deploy_data = state["deployments"].get(deploy_id)

        if deploy_data is None:
            return None

        return Deployment.from_dict(deploy_data)

    def list(
        self,
        status: Optional[str] = None,
        platform: Optional[str] = None,
    ) -> List[Deployment]:
        """
        List all deployments with optional filtering.

        Args:
            status: Filter by status (e.g., 'running', 'stopped')
            platform: Filter by platform (e.g., 'local', 'k8s')

        Returns:
            List of Deployment instances
        """
        state = self._read_state()
        deployments = [
            Deployment.from_dict(data)
            for data in state["deployments"].values()
        ]

        # Apply filters
        if status:
            deployments = [d for d in deployments if d.status == status]

        if platform:
            deployments = [d for d in deployments if d.platform == platform]

        # Sort by created_at (newest first)
        deployments.sort(key=lambda d: d.created_at, reverse=True)

        return deployments

    def update_status(self, deploy_id: str, status: str) -> None:
        """
        Update deployment status.

        Args:
            deploy_id: Deployment ID
            status: New status value

        Raises:
            KeyError: If deployment not found
        """
        state = self._read_state()

        if deploy_id not in state["deployments"]:
            raise KeyError(f"Deployment not found: {deploy_id}")

        state["deployments"][deploy_id]["status"] = status
        self._write_state(state)

    def remove(self, deploy_id: str) -> None:
        """
        Delete deployment record.

        Args:
            deploy_id: Deployment ID

        Raises:
            KeyError: If deployment not found
        """
        state = self._read_state()

        if deploy_id not in state["deployments"]:
            raise KeyError(f"Deployment not found: {deploy_id}")

        del state["deployments"][deploy_id]
        self._write_state(state)

    def exists(self, deploy_id: str) -> bool:
        """Check if deployment exists."""
        state = self._read_state()
        return deploy_id in state["deployments"]

    def clear(self) -> None:
        """Clear all deployments (use with caution)."""
        self._backup_state_file()
        self._write_state(StateFileSchema.create_empty())

    def export_to_file(self, output_file: str) -> None:
        """Export state to a file."""
        state = self._read_state()
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)

    def import_from_file(self, input_file: str, merge: bool = True) -> None:
        """
        Import state from a file.

        Args:
            input_file: Path to state file to import
            merge: If True, merge with existing state; if False, replace
        """
        with open(input_file, "r", encoding="utf-8") as f:
            import_data = json.load(f)

        # Validate imported data
        if not StateFileSchema.validate(import_data):
            raise ValueError("Invalid import file format")

        if merge:
            # Merge with existing state
            state = self._read_state()
            state["deployments"].update(import_data["deployments"])
        else:
            # Replace entire state
            state = import_data

        self._write_state(state)
