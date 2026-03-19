# -*- coding: utf-8 -*-
"""
Integration test: heartbeat timeout -> reap -> auto-restore ->
run_shell_command works with old sandbox_id (Issue #451 fix).

This test verifies:
1) A sandbox container bound to a session_ctx_id can execute run_shell_command
2) After heartbeat timeout, the session is reaped and container is RECYCLED
3) Client continues using old sandbox_id to call API (touch_session decorator
   auto-restores)
4) Old sandbox_id still works through redirect mechanism (Issue #451 fix)
5) Old container is marked as REPLACED with redirect_to set
6) New container is RUNNING and can execute run_shell_command

Run:
    pytest -q test_heartbeat_timeout_restore.py
"""

import time

from agentscope_runtime.sandbox.manager.server.app import get_config
from agentscope_runtime.sandbox.manager.sandbox_manager import SandboxManager
from agentscope_runtime.sandbox.enums import SandboxType
from agentscope_runtime.sandbox.model import ContainerModel, ContainerState


def test_heartbeat_reap_then_restore_run_shell():
    # Prepare manager config for a fast heartbeat/reap cycle
    config = get_config()
    config.allow_mount_dir = True
    config.redis_enabled = False

    # Keep timeouts small so the test finishes quickly
    config.heartbeat_timeout = 30  # seconds of inactivity to trigger reap
    config.watcher_scan_interval = 3  # scan interval in seconds

    session_ctx_id = f"hb-restore-{int(time.time())}"
    meta = {"session_ctx_id": session_ctx_id}

    with SandboxManager(config=config, default_type=SandboxType.BASE) as mgr:
        # Start heartbeat watcher explicitly (not started automatically)
        mgr.start_watcher()

        # Create a session-bound sandbox (required for heartbeat tracking)
        old_name = mgr.create_from_pool(
            sandbox_type=SandboxType.BASE.value,
            meta=meta,
        ) or mgr.create(sandbox_type=SandboxType.BASE.value, meta=meta)
        assert old_name, "Failed to create sandbox container"

        # 1) Old container should be able to run a shell command
        r0 = mgr.call_tool(
            old_name,
            "run_shell_command",
            {"command": "echo old-ok"},
        )
        assert "old-ok" in str(r0)

        # 2) Wait long enough for heartbeat timeout + watcher reap
        time.sleep(
            config.heartbeat_timeout + config.watcher_scan_interval + 5,
        )

        # Get raw container data to verify it's RECYCLED (without redirect)
        old_data = mgr.container_mapping.get(old_name)
        assert old_data is not None
        old_cm_recycled = ContainerModel(**old_data)
        assert old_cm_recycled.state == ContainerState.RECYCLED
        assert old_cm_recycled.recycle_reason == "heartbeat_timeout"

        # 3) Client continues using old sandbox_id (doesn't know it's recycled)
        #    This triggers auto-restore via touch_session decorator
        #    Issue #451 fix: old sandbox_id should still work!
        r1 = mgr.call_tool(
            old_name,  # Still using old sandbox_id!
            "run_shell_command",
            {"command": "echo after-auto-restore"},
        )
        assert "after-auto-restore" in str(r1)

        # 4) Verify old container is now marked as REPLACED (not deleted)
        old_data_after = mgr.container_mapping.get(old_name)
        assert (
            old_data_after is not None
        ), "Old container should not be deleted"
        old_cm_replaced = ContainerModel(**old_data_after)
        assert old_cm_replaced.state == ContainerState.REPLACED
        assert (
            old_cm_replaced.redirect_to is not None
        ), "redirect_to should be set"

        # 5) Verify new container exists and is RUNNING
        env_ids = mgr.get_session_mapping(session_ctx_id)
        assert env_ids, "Expected restored container(s), got empty mapping"

        new_name = env_ids[0]
        assert new_name != old_name, "Should be a new container"
        assert (
            new_name == old_cm_replaced.redirect_to
        ), "redirect_to should point to new container"

        new_cm = ContainerModel(**mgr.get_info(new_name))
        assert new_cm.state == ContainerState.RUNNING

        # 6) Verify old sandbox_id still works (through redirect)
        r2 = mgr.call_tool(
            old_name,  # Still using old sandbox_id!
            "run_shell_command",
            {"command": "echo final-test"},
        )
        assert "final-test" in str(r2)
