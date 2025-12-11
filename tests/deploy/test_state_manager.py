# -*- coding: utf-8 -*-
# pylint: disable=protected-access,redefined-outer-name
"""
Unit tests for DeploymentStateManager.
"""
import json
import shutil
import tempfile
from pathlib import Path

import pytest

from agentscope_runtime.engine.deployers.state import (
    DeploymentStateManager,
    Deployment,
)


@pytest.fixture
def temp_state_dir():
    """Create a temporary directory for state files."""
    temp_dir = Path(tempfile.mkdtemp())
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def state_manager(temp_state_dir):
    """Create a DeploymentStateManager instance for testing."""
    return DeploymentStateManager(state_dir=str(temp_state_dir))


@pytest.fixture
def sample_deployment():
    """Create a sample deployment for testing."""
    return Deployment(
        id="test-deploy-1",
        platform="local",
        url="http://localhost:8080",
        agent_source="/path/to/agent.py",
        created_at="2024-01-01T00:00:00",
        status="running",
        token=None,
        config={"key": "value"},
    )


@pytest.fixture
def sample_deployment_2():
    """Create another sample deployment for testing."""
    return Deployment(
        id="test-deploy-2",
        platform="k8s",
        url="http://localhost:8090",
        agent_source="/path/to/agent2.py",
        created_at="2024-01-02T00:00:00",
        status="running",
        token="test-token",
        config={"key2": "value2"},
    )


class TestDeploymentStateManagerBasic:
    """Test basic operations of DeploymentStateManager."""

    def test_init_default_dir(self, temp_state_dir):
        """Test initialization with default directory."""
        # Test custom directory (using temp directory to avoid affecting
        # real files)
        manager = DeploymentStateManager(state_dir=str(temp_state_dir))
        assert manager.state_dir == temp_state_dir
        assert manager.state_file == temp_state_dir / "deployments.json"

        # Test default directory path
        # We check the expected path by inspecting the default behavior
        # but use temp directory for all actual operations to avoid
        # affecting real files
        import os

        original_home = os.path.expanduser("~")
        expected_default_dir = Path(original_home) / ".agentscope-runtime"

        # Create manager with default dir to verify path (will create
        # directory)
        manager_default = DeploymentStateManager()
        assert manager_default.state_dir == expected_default_dir
        assert (
            manager_default.state_file
            == expected_default_dir / "deployments.json"
        )

        # Clean up: remove the default directory if it was created and is empty
        # This ensures tests don't leave artifacts in the real home directory
        if manager_default.state_dir.exists():
            try:
                # Check if directory is empty (only .agentscope dir itself,
                # no files)
                contents = list(manager_default.state_dir.iterdir())
                if not contents:
                    # Directory is empty, safe to remove
                    manager_default.state_dir.rmdir()
            except (OSError, PermissionError):
                # Ignore errors - directory might be in use or have
                # permissions issues
                pass

    def test_init_custom_dir(self, temp_state_dir):
        """Test initialization with custom directory."""
        manager = DeploymentStateManager(state_dir=str(temp_state_dir))
        assert manager.state_dir == temp_state_dir
        assert manager.state_file == temp_state_dir / "deployments.json"
        assert manager.state_dir.exists()

    def test_save_and_get(self, state_manager, sample_deployment):
        """Test saving and retrieving a deployment."""
        # Save deployment
        state_manager.save(sample_deployment)

        # Retrieve deployment
        retrieved = state_manager.get(sample_deployment.id)
        assert retrieved is not None
        assert retrieved.id == sample_deployment.id
        assert retrieved.platform == sample_deployment.platform
        assert retrieved.url == sample_deployment.url
        assert retrieved.status == sample_deployment.status
        assert retrieved.config == sample_deployment.config

    def test_get_nonexistent(self, state_manager):
        """Test retrieving a non-existent deployment."""
        result = state_manager.get("nonexistent-id")
        assert result is None

    def test_update_status(self, state_manager, sample_deployment):
        """Test updating deployment status."""
        # Save deployment
        state_manager.save(sample_deployment)

        # Update status
        state_manager.update_status(sample_deployment.id, "stopped")

        # Verify status updated
        retrieved = state_manager.get(sample_deployment.id)
        assert retrieved.status == "stopped"
        # Verify other fields are preserved
        assert retrieved.id == sample_deployment.id
        assert retrieved.platform == sample_deployment.platform
        assert retrieved.url == sample_deployment.url
        assert retrieved.config == sample_deployment.config

    def test_update_status_preserves_all_fields(
        self,
        state_manager,
        sample_deployment,
    ):
        """Test that update_status preserves all fields, not just status."""
        # Save deployment with all fields
        state_manager.save(sample_deployment)

        # Update status
        state_manager.update_status(sample_deployment.id, "stopped")

        # Verify ALL fields are preserved
        retrieved = state_manager.get(sample_deployment.id)
        assert retrieved.id == sample_deployment.id
        assert retrieved.platform == sample_deployment.platform
        assert retrieved.url == sample_deployment.url
        assert retrieved.agent_source == sample_deployment.agent_source
        assert retrieved.created_at == sample_deployment.created_at
        assert retrieved.token == sample_deployment.token
        assert retrieved.config == sample_deployment.config
        assert retrieved.status == "stopped"  # Only status changed

    def test_update_status_nonexistent(self, state_manager):
        """Test updating status of non-existent deployment."""
        with pytest.raises(KeyError, match="Deployment not found"):
            state_manager.update_status(
                "nonexistent-id",
                "stopped",
            )

    def test_remove(self, state_manager, sample_deployment):
        """Test removing a deployment."""
        # Save deployment
        state_manager.save(sample_deployment)

        # Remove deployment
        state_manager.remove(sample_deployment.id)

        # Verify removed
        assert state_manager.get(sample_deployment.id) is None
        assert not state_manager.exists(sample_deployment.id)

    def test_remove_nonexistent(self, state_manager):
        """Test removing a non-existent deployment."""
        with pytest.raises(KeyError, match="Deployment not found"):
            state_manager.remove("nonexistent-id")

    def test_exists(self, state_manager, sample_deployment):
        """Test checking if deployment exists."""
        assert not state_manager.exists(sample_deployment.id)
        state_manager.save(sample_deployment)
        assert state_manager.exists(sample_deployment.id)

    def test_list_all(
        self,
        state_manager,
        sample_deployment,
        sample_deployment_2,
    ):
        """Test listing all deployments."""
        state_manager.save(sample_deployment)
        state_manager.save(sample_deployment_2)

        deployments = state_manager.list()
        assert len(deployments) == 2
        deploy_ids = {d.id for d in deployments}
        assert sample_deployment.id in deploy_ids
        assert sample_deployment_2.id in deploy_ids

    def test_list_filter_by_status(
        self,
        state_manager,
        sample_deployment,
        sample_deployment_2,
    ):
        """Test listing deployments filtered by status."""
        state_manager.save(sample_deployment)
        state_manager.save(sample_deployment_2)
        state_manager.update_status(sample_deployment.id, "stopped")

        running = state_manager.list(status="running")
        assert len(running) == 1
        assert running[0].id == sample_deployment_2.id

        stopped = state_manager.list(status="stopped")
        assert len(stopped) == 1
        assert stopped[0].id == sample_deployment.id

    def test_list_filter_by_platform(
        self,
        state_manager,
        sample_deployment,
        sample_deployment_2,
    ):
        """Test listing deployments filtered by platform."""
        state_manager.save(sample_deployment)
        state_manager.save(sample_deployment_2)

        local = state_manager.list(platform="local")
        assert len(local) == 1
        assert local[0].id == sample_deployment.id

        k8s = state_manager.list(platform="k8s")
        assert len(k8s) == 1
        assert k8s[0].id == sample_deployment_2.id


class TestDeploymentStateManagerBackup:
    """Test backup functionality."""

    def test_backup_created_on_save(self, state_manager, sample_deployment):
        """Test that backup is created when saving."""
        # Initial save should not create backup (no existing file)
        state_manager.save(sample_deployment)
        backups = list(
            state_manager.state_dir.glob("deployments.backup.*.json"),
        )
        assert len(backups) == 0

        # Second save should create backup
        sample_deployment.status = "stopped"
        state_manager.save(sample_deployment)
        backups = list(
            state_manager.state_dir.glob("deployments.backup.*.json"),
        )
        assert len(backups) == 1

    def test_backup_not_created_if_no_change(
        self,
        state_manager,
        sample_deployment,
    ):
        """Test that backup is NOT created if content doesn't change."""
        # Save deployment
        state_manager.save(sample_deployment)
        backups_before = list(
            state_manager.state_dir.glob("deployments.backup.*.json"),
        )

        # Save again with same data (no change)
        state_manager.save(sample_deployment)
        backups_after = list(
            state_manager.state_dir.glob("deployments.backup.*.json"),
        )

        # No new backup should be created
        assert len(backups_after) == len(backups_before)

    def test_backup_created_on_update_status(
        self,
        state_manager,
        sample_deployment,
    ):
        """Test that backup is created when updating status."""
        state_manager.save(sample_deployment)

        # Update status (content changes)
        state_manager.update_status(sample_deployment.id, "stopped")
        backups_after = list(
            state_manager.state_dir.glob("deployments.backup.*.json"),
        )

        # Backup should be created (or overwrite today's backup if it exists)
        # Since we just saved, there should be 1 backup now
        assert len(backups_after) == 1

    def test_backup_created_on_remove(
        self,
        state_manager,
        sample_deployment,
    ):
        """Test that backup is created when removing deployment."""
        state_manager.save(sample_deployment)

        state_manager.remove(sample_deployment.id)
        backups_after = list(
            state_manager.state_dir.glob("deployments.backup.*.json"),
        )

        # Backup should be created (or overwrite today's backup if it exists)
        # Since we just saved, there should be 1 backup now
        assert len(backups_after) == 1

    def test_backup_one_per_day(self, state_manager, sample_deployment):
        """Test that only one backup is maintained per day."""
        from datetime import datetime

        # First save (no backup created since no existing file)
        state_manager.save(sample_deployment)
        initial_backups = list(
            state_manager.state_dir.glob("deployments.backup.*.json"),
        )
        assert len(initial_backups) == 0, "First save should not create backup"

        # Create multiple saves with different content on the same day
        # All should result in only one backup file (today's backup)
        for i in range(7):
            # Create a new deployment object with modified fields to ensure
            # content changes
            modified_deployment = Deployment(
                id=sample_deployment.id,
                platform=sample_deployment.platform,
                url=sample_deployment.url,
                agent_source=sample_deployment.agent_source,
                created_at=sample_deployment.created_at,
                status=f"status-{i}",
                token=sample_deployment.token,
                config={
                    "iteration": i,
                    "timestamp": f"ts-{i}",
                    "unique": f"unique-{i}",  # Add unique field to ensure
                    # content changes
                },
            )
            state_manager.save(modified_deployment)

            # After each save, there should still be only one backup (today's)
            backups = list(
                state_manager.state_dir.glob("deployments.backup.*.json"),
            )
            assert len(backups) == 1, (
                f"Iteration {i}: Expected 1 backup (one per day), "
                f"got {len(backups)}. "
                f"Backups: {[b.name for b in backups]}"
            )

            # Verify backup filename format: deployments.backup.YYYYMMDD.json
            backup = backups[0]
            assert backup.name.startswith("deployments.backup.")
            assert backup.name.endswith(".json")
            date_str = backup.name.replace("deployments.backup.", "").replace(
                ".json",
                "",
            )
            assert (
                len(date_str) == 8 and date_str.isdigit()
            ), f"Backup filename should be in format YYYYMMDD, got: {date_str}"

            # Verify it's today's date
            today_str = datetime.now().strftime("%Y%m%d")
            assert (
                date_str == today_str
            ), f"Backup should be for today ({today_str}), got: {date_str}"

    def test_backup_overwrites_same_day(
        self,
        state_manager,
        sample_deployment,
    ):
        """Test that multiple backups on the same day overwrite each other."""

        # First save doesn't create backup (no existing file)
        state_manager.save(sample_deployment)
        backups_after_first = list(
            state_manager.state_dir.glob("deployments.backup.*.json"),
        )
        assert (
            len(backups_after_first) == 0
        ), "First save should not create backup"

        # Second save creates today's backup (file now exists)
        sample_deployment.status = "stopped"
        state_manager.save(sample_deployment)
        backups_after_second = list(
            state_manager.state_dir.glob("deployments.backup.*.json"),
        )
        assert (
            len(backups_after_second) == 1
        ), "Second save should create backup"

        first_backup = backups_after_second[0]

        # Third save should overwrite today's backup, not create a new one
        sample_deployment.status = "running"
        state_manager.save(sample_deployment)

        backups_after_third = list(
            state_manager.state_dir.glob("deployments.backup.*.json"),
        )
        assert (
            len(backups_after_third) == 1
        ), "Should still have only one backup"

        second_backup = backups_after_third[0]
        # Should be the same file (same date)
        assert first_backup.name == second_backup.name, (
            f"Backup should be overwritten, not create new file. "
            f"Expected: {first_backup.name}, Got: {second_backup.name}"
        )
        # But content should be different (file size might differ)
        # The important thing is that we still have only one backup

    def test_old_backups_cleaned_up(
        self,
        state_manager,
        sample_deployment,
    ):
        """Test that old backups are cleaned up."""
        from datetime import datetime, timedelta

        # First, create the state file so that backup creation will be
        # triggered
        state_manager.save(sample_deployment)

        # Create fake old backup files (older than 30 days)
        old_date = (datetime.now() - timedelta(days=35)).strftime("%Y%m%d")
        old_backup = (
            state_manager.state_dir / f"deployments.backup.{old_date}.json"
        )
        old_backup.write_text('{"old": "backup"}')

        # Create a recent backup (within 30 days)
        recent_date = (datetime.now() - timedelta(days=10)).strftime("%Y%m%d")
        recent_backup = (
            state_manager.state_dir / f"deployments.backup.{recent_date}.json"
        )
        recent_backup.write_text('{"recent": "backup"}')

        # Verify backups exist before cleanup
        backups_before = list(
            state_manager.state_dir.glob("deployments.backup.*.json"),
        )
        backup_names_before = [b.name for b in backups_before]
        assert (
            old_backup.name in backup_names_before
        ), "Old backup should exist before cleanup"
        assert (
            recent_backup.name in backup_names_before
        ), "Recent backup should exist before cleanup"

        # Trigger backup creation (this will also trigger cleanup)
        # Since state file exists, this will create today's backup and
        # trigger cleanup
        sample_deployment.status = "stopped"
        state_manager.save(sample_deployment)

        # Check that old backup was deleted but recent backup remains
        backups_after = list(
            state_manager.state_dir.glob("deployments.backup.*.json"),
        )
        backup_names_after = [b.name for b in backups_after]

        assert old_backup.name not in backup_names_after, (
            f"Old backup ({old_backup.name}) should be deleted. "
            f"Remaining backups: {backup_names_after}"
        )
        assert recent_backup.name in backup_names_after, (
            f"Recent backup ({recent_backup.name}) should be kept. "
            f"Remaining backups: {backup_names_after}"
        )

        # Today's backup should also exist
        today_str = datetime.now().strftime("%Y%m%d")
        today_backup_name = f"deployments.backup.{today_str}.json"
        assert today_backup_name in backup_names_after, (
            f"Today's backup ({today_backup_name}) should exist. "
            f"Remaining backups: {backup_names_after}"
        )


class TestDeploymentStateManagerDataLossPrevention:
    """Test data loss prevention mechanisms."""

    def test_update_status_empty_state_raises_error(self, state_manager):
        """Test that update_status raises error on empty state."""
        # Try to update status when state file is empty
        with pytest.raises(
            KeyError,
            match="state file is empty or corrupted",
        ):
            state_manager.update_status("any-id", "stopped")

    def test_write_empty_state_when_file_has_data_raises_error(
        self,
        state_manager,
        sample_deployment,
    ):
        """Test that writing empty state when file has data raises error."""
        # Save a deployment
        state_manager.save(sample_deployment)

        # Try to write empty state directly (should be prevented)
        from agentscope_runtime.engine.deployers.state.schema import (
            StateFileSchema,
        )

        empty_state = StateFileSchema.create_empty()
        with pytest.raises(
            ValueError,
            match="Attempted to write empty state",
        ):
            state_manager._write_state(empty_state)

    def test_update_status_preserves_other_deployments(
        self,
        state_manager,
        sample_deployment,
        sample_deployment_2,
    ):
        """Test that update_status preserves other deployments."""
        # Save two deployments
        state_manager.save(sample_deployment)
        state_manager.save(sample_deployment_2)

        # Update status of first deployment
        state_manager.update_status(sample_deployment.id, "stopped")

        # Verify both deployments still exist
        assert state_manager.get(sample_deployment.id) is not None
        assert state_manager.get(sample_deployment_2.id) is not None

        # Verify second deployment is unchanged
        retrieved_2 = state_manager.get(sample_deployment_2.id)
        assert retrieved_2.status == "running"
        assert retrieved_2.id == sample_deployment_2.id

    def test_multiple_updates_preserve_data(
        self,
        state_manager,
        sample_deployment,
    ):
        """Test that multiple status updates preserve all data."""
        state_manager.save(sample_deployment)

        # Update status multiple times
        for status in ["stopped", "running", "stopped", "running"]:
            state_manager.update_status(sample_deployment.id, status)
            retrieved = state_manager.get(sample_deployment.id)
            assert retrieved.status == status
            # Verify all other fields are preserved
            assert retrieved.id == sample_deployment.id
            assert retrieved.platform == sample_deployment.platform
            assert retrieved.url == sample_deployment.url
            assert retrieved.config == sample_deployment.config


class TestDeploymentStateManagerCorruptionHandling:
    """Test handling of corrupted state files."""

    def test_read_corrupted_json(self, state_manager):
        """Test reading corrupted JSON file."""
        # Write invalid JSON
        state_manager.state_file.write_text("{ invalid json }")

        # Should return empty state
        state = state_manager._read_state()
        assert state == {"version": "1.0", "deployments": {}}

    def test_read_invalid_structure(self, state_manager):
        """Test reading file with invalid structure."""
        # Write invalid structure
        state_manager.state_file.write_text('{"invalid": "structure"}')

        # Should return empty state
        state = state_manager._read_state()
        assert state == {"version": "1.0", "deployments": {}}

    def test_read_partially_corrupted_preserves_valid(
        self,
        state_manager,
        sample_deployment,
    ):
        """Test that partially corrupted file preserves valid deployments."""
        # Save a valid deployment
        state_manager.save(sample_deployment)

        # Manually corrupt the file by adding invalid deployment
        state = json.loads(state_manager.state_file.read_text())
        state["deployments"]["invalid-deploy"] = {
            "id": "invalid-deploy",
            # Missing required fields
        }
        state_manager.state_file.write_text(json.dumps(state))

        # Should preserve valid deployment
        retrieved_state = state_manager._read_state()
        assert sample_deployment.id in retrieved_state["deployments"]
        assert "invalid-deploy" not in retrieved_state["deployments"]

    def test_read_missing_required_fields_preserves_others(
        self,
        state_manager,
        sample_deployment,
    ):
        """Test that deployments with missing required fields are skipped."""
        # Save a valid deployment
        state_manager.save(sample_deployment)

        # Manually add deployment with missing required field
        state = json.loads(state_manager.state_file.read_text())
        state["deployments"]["incomplete-deploy"] = {
            "id": "incomplete-deploy",
            "platform": "local",
            # Missing url, agent_source, created_at
        }
        state_manager.state_file.write_text(json.dumps(state))

        # Should preserve valid deployment, skip invalid one
        retrieved_state = state_manager._read_state()
        assert sample_deployment.id in retrieved_state["deployments"]
        assert "incomplete-deploy" not in retrieved_state["deployments"]


class TestDeploymentStateManagerImportExport:
    """Test import/export functionality."""

    def test_export_to_file(
        self,
        state_manager,
        sample_deployment,
        temp_state_dir,
    ):
        """Test exporting state to file."""
        state_manager.save(sample_deployment)

        export_file = temp_state_dir / "exported.json"
        state_manager.export_to_file(str(export_file))

        assert export_file.exists()
        exported_data = json.loads(export_file.read_text())
        assert sample_deployment.id in exported_data["deployments"]

    def test_import_from_file_merge(
        self,
        state_manager,
        sample_deployment,
        sample_deployment_2,
        temp_state_dir,
    ):
        """Test importing state with merge."""
        # Save one deployment
        state_manager.save(sample_deployment)

        # Export and add another deployment
        export_file = temp_state_dir / "exported.json"
        state_manager.export_to_file(str(export_file))

        exported_data = json.loads(export_file.read_text())
        exported_data["deployments"][
            sample_deployment_2.id
        ] = sample_deployment_2.to_dict()
        export_file.write_text(json.dumps(exported_data))

        # Import with merge
        state_manager.import_from_file(str(export_file), merge=True)

        # Both deployments should exist
        assert state_manager.get(sample_deployment.id) is not None
        assert state_manager.get(sample_deployment_2.id) is not None

    def test_import_from_file_replace(
        self,
        state_manager,
        sample_deployment,
        sample_deployment_2,
        temp_state_dir,
    ):
        """Test importing state with replace."""
        # Save one deployment
        state_manager.save(sample_deployment)

        # Create export with only second deployment
        export_data = {
            "version": "1.0",
            "deployments": {
                sample_deployment_2.id: sample_deployment_2.to_dict(),
            },
        }
        export_file = temp_state_dir / "exported.json"
        export_file.write_text(json.dumps(export_data))

        # Import with replace
        state_manager.import_from_file(str(export_file), merge=False)

        # Only second deployment should exist
        assert state_manager.get(sample_deployment.id) is None
        assert state_manager.get(sample_deployment_2.id) is not None

    def test_import_invalid_file_raises_error(
        self,
        state_manager,
        temp_state_dir,
    ):
        """Test importing invalid file raises error."""
        invalid_file = temp_state_dir / "invalid.json"
        invalid_file.write_text('{"invalid": "structure"}')

        with pytest.raises(ValueError, match="Invalid import file format"):
            state_manager.import_from_file(str(invalid_file))


class TestDeploymentStateManagerClear:
    """Test clear functionality."""

    def test_clear(
        self,
        state_manager,
        sample_deployment,
        sample_deployment_2,
    ):
        """Test clearing all deployments."""
        state_manager.save(sample_deployment)
        state_manager.save(sample_deployment_2)

        state_manager.clear()

        assert len(state_manager.list()) == 0
        assert state_manager.get(sample_deployment.id) is None
        assert state_manager.get(sample_deployment_2.id) is None

    def test_clear_creates_backup(
        self,
        state_manager,
        sample_deployment,
    ):
        """Test that clear creates a backup."""
        state_manager.save(sample_deployment)

        backups_before = list(
            state_manager.state_dir.glob("deployments.backup.*.json"),
        )
        state_manager.clear()
        backups_after = list(
            state_manager.state_dir.glob("deployments.backup.*.json"),
        )

        assert len(backups_after) == len(backups_before) + 1


class TestDeploymentStateManagerEdgeCases:
    """Test edge cases and error conditions."""

    def test_save_overwrites_existing(
        self,
        state_manager,
        sample_deployment,
    ):
        """Test that save overwrites existing deployment."""
        state_manager.save(sample_deployment)

        # Modify and save again
        sample_deployment.status = "stopped"
        sample_deployment.url = "http://new-url:8080"
        state_manager.save(sample_deployment)

        retrieved = state_manager.get(sample_deployment.id)
        assert retrieved.status == "stopped"
        assert retrieved.url == "http://new-url:8080"

    def test_concurrent_saves(
        self,
        state_manager,
        sample_deployment,
        sample_deployment_2,
    ):
        """Test handling of concurrent saves."""
        # Simulate concurrent saves
        state_manager.save(sample_deployment)
        state_manager.save(sample_deployment_2)

        # Both should be saved
        assert state_manager.get(sample_deployment.id) is not None
        assert state_manager.get(sample_deployment_2.id) is not None

    def test_state_file_atomic_write(self, state_manager, sample_deployment):
        """Test that state file writes are atomic."""
        state_manager.save(sample_deployment)

        # Check that .tmp file doesn't exist after write
        temp_file = state_manager.state_file.with_suffix(".tmp")
        assert not temp_file.exists()

        # State file should exist and be valid
        assert state_manager.state_file.exists()
        data = json.loads(state_manager.state_file.read_text())
        assert sample_deployment.id in data["deployments"]
