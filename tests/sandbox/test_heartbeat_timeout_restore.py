# -*- coding: utf-8 -*-
"""
Integration test: heartbeat timeout -> reap -> touch -> restore ->
run_shell_command works again.

This test verifies:
1) A sandbox container bound to a session_ctx_id can execute run_shell_command.
2) After heartbeat timeout, the session is reaped and the container is
    marked RECYCLED.
3) When the user "comes back" (touch heartbeat),
    restore_session() can bring up a new container.
4) The restored container is RUNNING and can execute run_shell_command.

Run:
    pytest -q test_heartbeat_timeout_restore.py
"""

import time
import pytest

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

        # The old container model should be marked as RECYCLED
        old_cm = ContainerModel(**mgr.get_info(old_name))
        assert old_cm.state == ContainerState.RECYCLED
        assert old_cm.recycle_reason == "heartbeat_timeout"

        # Old container should not be usable anymore (it was stopped/removed)
        with pytest.raises(Exception):
            mgr.call_tool(
                old_name,
                "run_shell_command",
                {"command": "echo should-fail"},
            )

        # 3) User comes back: touch heartbeat + restore the session
        mgr.update_heartbeat(session_ctx_id)
        mgr.restore_session(session_ctx_id)

        # 4) Session mapping should now contain restored container(s)
        env_ids = mgr.get_session_mapping(session_ctx_id)
        assert env_ids, "Expected restored container(s), got empty mapping"

        new_name = env_ids[0]
        new_cm = ContainerModel(**mgr.get_info(new_name))
        assert new_cm.state == ContainerState.RUNNING

        # Restored container should be able to run a shell command again
        r1 = mgr.call_tool(
            new_name,
            "run_shell_command",
            {"command": "echo new-ok"},
        )
        assert "new-ok" in str(r1)
