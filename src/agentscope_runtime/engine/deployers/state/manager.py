# -*- coding: utf-8 -*-
"""Deployment state management."""

import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

from agentscope_runtime.engine.deployers.state.schema import (
    Deployment,
    StateFileSchema,
)


class DeploymentStateManager:
    """Manages deployment state persistence."""

    def __init__(self, state_dir: Optional[str] = None):
        """
        Initialize state manager.

        Args:
            state_dir: Custom state directory (defaults to
            ~/.agentscope-runtime)
        """
        if state_dir is None:
            state_dir = os.path.expanduser("~/.agentscope-runtime")

        self.state_dir = Path(state_dir)
        self.state_file = self.state_dir / "deployments.json"
        self._ensure_state_dir()

    def _ensure_state_dir(self) -> None:
        """Ensure state directory exists."""
        self.state_dir.mkdir(parents=True, exist_ok=True)

    def _backup_state_file(self) -> None:
        """Create backup of state file before modifications.

        Maintains one backup per day. If a backup for today already exists,
        it will be overwritten. Old backups (older than 30 days) are cleaned up
        """
        if self.state_file.exists():
            # Use date-based filename: deployments.backup.YYYYMMDD.json
            today = datetime.now().strftime("%Y%m%d")
            backup_file = self.state_dir / f"deployments.backup.{today}.json"

            # Overwrite today's backup if it exists (one backup per day)
            shutil.copy2(self.state_file, backup_file)

            # Clean up old backups (older than 30 days)
            self._cleanup_old_backups(days_to_keep=30)

    def _cleanup_old_backups(self, days_to_keep: int = 30) -> None:
        """Clean up backup files older than specified days.

        Args:
            days_to_keep: Number of days to keep backups (default: 30)
        """
        from datetime import timedelta

        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        cutoff_date_str = cutoff_date.strftime("%Y%m%d")

        # Find all backup files with date format
        backups = list(self.state_dir.glob("deployments.backup.*.json"))

        for backup_file in backups:
            # Extract date from filename: deployments.backup.YYYYMMDD.json
            try:
                # Get the date part (between "backup." and ".json")
                date_str = backup_file.stem.split("backup.")[-1]

                # Validate date format (8 digits: YYYYMMDD)
                if len(date_str) == 8 and date_str.isdigit():
                    backup_date_str = date_str

                    # Compare dates as strings (YYYYMMDD format allows
                    # string comparison)
                    if backup_date_str < cutoff_date_str:
                        backup_file.unlink()
            except (ValueError, IndexError):
                # If filename doesn't match expected format, skip it
                # (might be old format backups)
                continue

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
                # If validation fails, try to preserve existing deployments
                # by only validating the structure, not individual deployments
                if isinstance(data, dict) and "deployments" in data:
                    # Keep the deployments dict even if some entries are
                    # invalid. This prevents data loss when only some
                    # entries are corrupted
                    valid_deployments = {}
                    for deploy_id, deploy_data in data.get(
                        "deployments",
                        {},
                    ).items():
                        try:
                            # Try to validate individual deployment
                            Deployment.from_dict(deploy_data)
                            valid_deployments[deploy_id] = deploy_data
                        except (TypeError, KeyError) as e:
                            # Skip invalid deployments but keep valid ones
                            print(
                                f"Warning: Skipping invalid deployment "
                                f"{deploy_id} in state file: {e}",
                            )
                    # Return state with only valid deployments
                    # IMPORTANT: Only return empty if ALL deployments are
                    # invalid. This prevents accidental data loss
                    return {
                        "version": data.get(
                            "version",
                            StateFileSchema.VERSION,
                        ),
                        "deployments": valid_deployments,
                    }
                raise ValueError("Invalid state file format")

            return data

        except (json.JSONDecodeError, ValueError) as e:
            # State file is corrupted, return empty state
            # Original file is kept as-is for manual recovery
            print(
                f"Warning: State file is corrupted ({e}). Starting with "
                f"empty state.",
            )
            return StateFileSchema.create_empty()

    def _write_state(
        self,
        data: Dict[str, Any],
        allow_empty: bool = False,
    ) -> None:
        """
        Write state file atomically.

        Args:
            data: State data to write
            allow_empty: If True, allow writing empty state even when file
                        has data.
                        Used for explicit operations like clear() or remove().
        """
        # Safety check: prevent writing empty state if file already exists
        # with data. This prevents accidental data loss, unless explicitly
        # allowed
        if not allow_empty and self.state_file.exists():
            try:
                existing_state = self._read_state()
                existing_count = len(existing_state.get("deployments", {}))
                new_count = len(data.get("deployments", {}))

                # If we're writing empty state but file had data, this is
                # suspicious unless explicitly allowed  (e.g., from clear()
                # or remove())
                if existing_count > 0 and new_count == 0:
                    raise ValueError(
                        f"Attempted to write empty state when {existing_count}"
                        f" deployments exist. This may indicate data loss. "
                        f"Aborting write to prevent data loss.",
                    )
            except ValueError as e:
                # Re-raise ValueError from safety check (data loss prevention)
                raise ValueError(
                    f"Attempted to write empty state when {existing_count}",
                ) from e
            except Exception:
                # If we can't read existing state due to file errors,
                # proceed with caution but still validate the new data
                pass

        # Validate before writing
        if not StateFileSchema.validate(data):
            raise ValueError("Invalid state data")

        # Serialize new data to compare with existing file
        new_content = json.dumps(data, indent=2, sort_keys=True)

        # Check if content actually changed before backing up
        # Use the same read logic as _read_state to ensure consistency
        if self.state_file.exists():
            try:
                # Read existing file using the same method as _read_state
                # to ensure we're comparing apples to apples
                with open(self.state_file, "r", encoding="utf-8") as f:
                    existing_data = json.load(f)

                # Normalize the existing data the same way _read_state does
                existing_data = StateFileSchema.migrate_if_needed(
                    existing_data,
                )

                # Serialize for comparison
                existing_content = json.dumps(
                    existing_data,
                    indent=2,
                    sort_keys=True,
                )

                # Only backup if content changed
                if existing_content != new_content:
                    self._backup_state_file()
            except (json.JSONDecodeError, IOError, ValueError):
                # If file is corrupted or unreadable, backup anyway
                # This ensures we don't lose data if file is corrupted
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

        # Safety check: if state is empty, don't proceed
        # This prevents accidentally writing empty state
        if not state.get("deployments"):
            raise KeyError(
                f"Deployment not found: {deploy_id} "
                f"(state file is empty or corrupted)",
            )

        if deploy_id not in state["deployments"]:
            raise KeyError(f"Deployment not found: {deploy_id}")

        # Make a copy to avoid modifying the original dict in place
        # This ensures we don't accidentally lose data
        state["deployments"][deploy_id] = dict(state["deployments"][deploy_id])
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

        # Allow empty state if this was the last deployment (legitimate
        # removal)
        allow_empty = len(state["deployments"]) == 0
        self._write_state(state, allow_empty=allow_empty)

    def exists(self, deploy_id: str) -> bool:
        """Check if deployment exists."""
        state = self._read_state()
        return deploy_id in state["deployments"]

    def clear(self) -> None:
        """Clear all deployments (use with caution)."""
        # Allow empty state for explicit clear operation
        # Backup will be created automatically by _write_state() if content
        # changes
        self._write_state(StateFileSchema.create_empty(), allow_empty=True)

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
