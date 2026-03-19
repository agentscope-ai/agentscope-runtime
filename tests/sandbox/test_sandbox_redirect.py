# -*- coding: utf-8 -*-
# pylint: disable=unused-argument,protected-access,redefined-outer-name
"""
Unit tests for container redirect mechanism (Issue #451 fix).

Tests verify that:
1. After restore_session, old container is marked as REPLACED with redirect
2. get_info() automatically follows redirects
3. Client can continue using old sandbox_id after restore
4. Redirect loop detection works
5. Chain redirects work
"""

import time
import pytest

from agentscope_runtime.sandbox.manager.sandbox_manager import SandboxManager
from agentscope_runtime.sandbox.model import (
    SandboxManagerEnvConfig,
    ContainerModel,
    ContainerState,
)
from agentscope_runtime.sandbox.enums import SandboxType


class StubContainerClient:
    """Stub docker client for testing"""

    def __init__(self):
        self._by_id = {}  # id -> dict
        self._by_name = {}  # name -> id
        self._next = 1
        self.stopped = []
        self.removed = []

    def create(
        self,
        image,
        name,
        ports,
        volumes,
        environment,
        runtime_config=None,
    ):
        cid = f"cid-{self._next}"
        self._next += 1
        self._by_id[cid] = {"name": name, "status": "running"}
        self._by_name[name] = cid
        return cid, [18080 + self._next], "127.0.0.1", "http"

    def inspect(self, identity):
        cid = self._by_name.get(identity, identity)
        return self._by_id.get(cid)

    def get_status(self, identity):
        cid = self._by_name.get(identity, identity)
        obj = self._by_id.get(cid)
        return None if obj is None else obj["status"]

    def start(self, container_id):
        if container_id in self._by_id:
            self._by_id[container_id]["status"] = "running"

    def stop(self, container_id, timeout=1):
        if container_id in self._by_id:
            self._by_id[container_id]["status"] = "exited"
        self.stopped.append(container_id)

    def remove(self, container_id, force=True):
        self.removed.append(container_id)
        obj = self._by_id.pop(container_id, None)
        if obj:
            name = obj["name"]
            self._by_name.pop(name, None)


class StubRuntimeClient:
    """Stub runtime client for testing"""

    def check_health(self):
        return {"status": "ok"}

    def list_tools(self, tool_type=None, **kwargs):
        return [{"name": "dummy_tool"}]

    def call_tool(self, tool_name=None, arguments=None):
        return {"tool": tool_name, "result": "ok"}

    def add_mcp_servers(self, server_configs, overwrite=False):
        return {"ok": True, "count": len(server_configs)}


@pytest.fixture()
def mgr(monkeypatch):
    """Create SandboxManager with stub clients"""
    # Stub ContainerClientFactory
    stub_cc = StubContainerClient()
    from agentscope_runtime.common.container_clients import (
        ContainerClientFactory,
    )

    monkeypatch.setattr(
        ContainerClientFactory,
        "create_client",
        lambda *args, **kwargs: stub_cc,
        raising=True,
    )

    # Stub storage operations
    from agentscope_runtime.sandbox.manager.storage import LocalStorage

    monkeypatch.setattr(
        LocalStorage,
        "upload_folder",
        lambda *a, **k: None,
        raising=True,
    )
    monkeypatch.setattr(
        LocalStorage,
        "download_folder",
        lambda *a, **k: None,
        raising=True,
    )

    # Stub runtime client
    monkeypatch.setattr(
        SandboxManager,
        "_establish_connection",
        lambda self, identity: StubRuntimeClient(),
        raising=True,
    )

    cfg = SandboxManagerEnvConfig(
        redis_enabled=False,
        file_system="local",
        container_deployment="docker",
        pool_size=0,
        default_mount_dir="sessions_mount_dir",
        heartbeat_timeout=1,
        watcher_scan_interval=0,
        heartbeat_lock_ttl=2,
    )

    m = SandboxManager(config=cfg, default_type=SandboxType.BASE)
    m._stub_cc = stub_cc
    try:
        yield m
    finally:
        m.cleanup()


def test_get_info_follows_single_redirect(mgr: SandboxManager):
    """
    Test that get_info() automatically follows a single redirect.
    """
    # Create old container marked as REPLACED
    old_cm = ContainerModel(
        session_id="test_session",
        container_id="old_cid",
        container_name="sandbox_old",
        url="http://old:8080",
        ports=[8080],
        state=ContainerState.REPLACED,
        redirect_to="sandbox_new",
    )
    mgr.container_mapping.set("sandbox_old", old_cm.model_dump())

    # Create new container
    new_cm = ContainerModel(
        session_id="test_session",
        container_id="new_cid",
        container_name="sandbox_new",
        url="http://new:8080",
        ports=[8080],
        state=ContainerState.RUNNING,
    )
    mgr.container_mapping.set("sandbox_new", new_cm.model_dump())

    # get_info with old container name should return new container
    result = mgr.get_info("sandbox_old")
    result_cm = ContainerModel(**result)

    assert result_cm.container_name == "sandbox_new"
    assert result_cm.state == ContainerState.RUNNING
    assert result_cm.container_id == "new_cid"


def test_get_info_no_redirect_for_running_container(mgr: SandboxManager):
    """
    Test that get_info() returns directly for RUNNING containers
    (no redirect).
    """
    cm = ContainerModel(
        session_id="test_session",
        container_id="running_cid",
        container_name="sandbox_running",
        url="http://running:8080",
        ports=[8080],
        state=ContainerState.RUNNING,
    )
    mgr.container_mapping.set("sandbox_running", cm.model_dump())

    result = mgr.get_info("sandbox_running")
    result_cm = ContainerModel(**result)

    assert result_cm.container_name == "sandbox_running"
    assert result_cm.state == ContainerState.RUNNING


def test_get_info_chain_redirect(mgr: SandboxManager):
    """
    Test that get_info() follows chain redirects (A -> B -> C).
    """
    # Create redirect chain: A -> B -> C
    cm_a = ContainerModel(
        session_id="test",
        container_id="a",
        container_name="sandbox_a",
        url="http://a:8080",
        ports=[8080],
        state=ContainerState.REPLACED,
        redirect_to="sandbox_b",
    )
    mgr.container_mapping.set("sandbox_a", cm_a.model_dump())

    cm_b = ContainerModel(
        session_id="test",
        container_id="b",
        container_name="sandbox_b",
        url="http://b:8080",
        ports=[8080],
        state=ContainerState.REPLACED,
        redirect_to="sandbox_c",
    )
    mgr.container_mapping.set("sandbox_b", cm_b.model_dump())

    cm_c = ContainerModel(
        session_id="test",
        container_id="c",
        container_name="sandbox_c",
        url="http://c:8080",
        ports=[8080],
        state=ContainerState.RUNNING,
    )
    mgr.container_mapping.set("sandbox_c", cm_c.model_dump())

    # Query A should return C
    result = mgr.get_info("sandbox_a")
    result_cm = ContainerModel(**result)

    assert result_cm.container_name == "sandbox_c"
    assert result_cm.state == ContainerState.RUNNING


def test_get_info_redirect_loop_detection(mgr: SandboxManager):
    """
    Test that get_info() detects and raises error for redirect loops.
    """
    # Create circular redirect: X -> Y -> X
    cm_x = ContainerModel(
        session_id="test",
        container_id="x",
        container_name="sandbox_x",
        url="http://x:8080",
        ports=[8080],
        state=ContainerState.REPLACED,
        redirect_to="sandbox_y",
    )
    mgr.container_mapping.set("sandbox_x", cm_x.model_dump())

    cm_y = ContainerModel(
        session_id="test",
        container_id="y",
        container_name="sandbox_y",
        url="http://y:8080",
        ports=[8080],
        state=ContainerState.REPLACED,
        redirect_to="sandbox_x",
    )
    mgr.container_mapping.set("sandbox_y", cm_y.model_dump())

    # Should raise RuntimeError for redirect loop
    with pytest.raises(RuntimeError, match="Redirect loop detected"):
        mgr.get_info("sandbox_x")


def test_restore_session_marks_old_as_replaced(mgr: SandboxManager):
    """
    Test that restore_session marks old container as REPLACED and sets
    redirect_to.
    """
    session_ctx_id = "test_session_restore"

    # Create and immediately mark as RECYCLED
    old_name = mgr.create(
        sandbox_type=SandboxType.BASE,
        meta={"session_ctx_id": session_ctx_id},
    )
    assert old_name is not None

    # Mark as RECYCLED
    old_cm = ContainerModel(**mgr.get_info(old_name))
    old_cm.state = ContainerState.RECYCLED
    old_cm.recycled_at = time.time()
    old_cm.recycle_reason = "test"
    mgr.container_mapping.set(old_name, old_cm.model_dump())

    # Restore session
    mgr.restore_session(session_ctx_id)

    # Get the raw old container data (without following redirect)
    old_data = mgr.container_mapping.get(old_name)
    assert old_data is not None

    old_cm_after = ContainerModel(**old_data)
    assert old_cm_after.state == ContainerState.REPLACED
    assert old_cm_after.redirect_to is not None
    assert old_cm_after.redirect_to != old_name

    # Verify new container exists and is RUNNING
    new_containers = mgr.get_session_mapping(session_ctx_id)
    assert len(new_containers) > 0
    new_name = new_containers[0]

    new_cm = ContainerModel(**mgr.get_info(new_name))
    assert new_cm.state == ContainerState.RUNNING
    assert new_cm.session_ctx_id == session_ctx_id


def test_client_can_use_old_sandbox_id_after_restore(mgr: SandboxManager):
    """
    Test that client can continue using old sandbox_id after restore
    (Issue #451 main scenario).
    """
    session_ctx_id = "test_client_compatibility"

    # Create container
    old_sandbox_id = mgr.create(
        sandbox_type=SandboxType.BASE,
        meta={"session_ctx_id": session_ctx_id},
    )
    assert old_sandbox_id is not None

    # Mark as RECYCLED (simulate heartbeat timeout)
    old_cm = ContainerModel(**mgr.get_info(old_sandbox_id))
    old_cm.state = ContainerState.RECYCLED
    old_cm.recycled_at = time.time()
    old_cm.recycle_reason = "heartbeat_timeout"
    mgr.container_mapping.set(old_sandbox_id, old_cm.model_dump())

    # Restore session
    mgr.restore_session(session_ctx_id)

    # Client still uses old_sandbox_id - should work through redirect
    result = mgr.get_info(old_sandbox_id)
    result_cm = ContainerModel(**result)
    assert result_cm.state == ContainerState.RUNNING
    assert result_cm.session_ctx_id == session_ctx_id

    # API calls with old_sandbox_id should work
    health_result = mgr.check_health(old_sandbox_id)
    assert health_result is not None

    tools_result = mgr.list_tools(old_sandbox_id)
    assert tools_result is not None


def test_needs_restore_ignores_replaced_state(mgr: SandboxManager):
    """
    Test that needs_restore() returns False for REPLACED containers
    (they don't need restore, already have redirect).
    """
    session_ctx_id = "test_needs_restore"

    # Create a container marked as REPLACED
    cm = ContainerModel(
        session_id="test",
        container_id="replaced_cid",
        container_name="sandbox_replaced",
        url="http://replaced:8080",
        ports=[8080],
        state=ContainerState.REPLACED,
        redirect_to="sandbox_new",
        session_ctx_id=session_ctx_id,
    )
    mgr.container_mapping.set("sandbox_replaced", cm.model_dump())
    mgr.session_mapping.set(session_ctx_id, ["sandbox_replaced"])

    # needs_restore should return False for REPLACED
    assert mgr.needs_restore(session_ctx_id) is False


def test_needs_restore_true_for_recycled_state(mgr: SandboxManager):
    """
    Test that needs_restore() returns True for RECYCLED containers.
    """
    session_ctx_id = "test_needs_restore_recycled"

    # Create a container marked as RECYCLED
    cm = ContainerModel(
        session_id="test",
        container_id="recycled_cid",
        container_name="sandbox_recycled",
        url="http://recycled:8080",
        ports=[8080],
        state=ContainerState.RECYCLED,
        recycled_at=time.time(),
        recycle_reason="test",
        session_ctx_id=session_ctx_id,
    )
    mgr.container_mapping.set("sandbox_recycled", cm.model_dump())
    mgr.session_mapping.set(session_ctx_id, ["sandbox_recycled"])

    # needs_restore should return True for RECYCLED
    assert mgr.needs_restore(session_ctx_id) is True


def test_cleanup_skips_replaced_containers(mgr: SandboxManager):
    """
    Test that cleanup() skips REPLACED containers (terminal state).
    """
    cm = ContainerModel(
        session_id="test",
        container_id="replaced_cid",
        container_name="sandbox_replaced_cleanup",
        url="http://replaced:8080",
        ports=[8080],
        state=ContainerState.REPLACED,
        redirect_to="sandbox_new",
    )
    mgr.container_mapping.set("sandbox_replaced_cleanup", cm.model_dump())

    # Record stop/remove calls before cleanup
    stop_count_before = len(mgr._stub_cc.stopped)
    remove_count_before = len(mgr._stub_cc.removed)

    # Cleanup should skip REPLACED containers
    mgr.cleanup()

    # REPLACED container should not be stopped/removed
    # (no new stop/remove calls)
    assert len(mgr._stub_cc.stopped) == stop_count_before
    assert len(mgr._stub_cc.removed) == remove_count_before


def test_scan_released_cleanup_handles_replaced(mgr: SandboxManager):
    """
    Test that scan_released_cleanup_once() can cleanup expired REPLACED
    containers.
    """
    # Set a short TTL for testing
    mgr.config.released_key_ttl = 1

    # Create a REPLACED container with old updated_at
    # Use proper prefix to match the scan pattern
    old_time = time.time() - 10  # 10 seconds ago
    container_name = f"{mgr.prefix}expired_replaced"
    cm = ContainerModel(
        session_id="test",
        container_id="expired_replaced",
        container_name=container_name,
        url="http://expired:8080",
        ports=[8080],
        state=ContainerState.REPLACED,
        redirect_to="sandbox_new",
        updated_at=old_time,
    )
    mgr.container_mapping.set(container_name, cm.model_dump())

    # Scan should delete the expired REPLACED container
    result = mgr.scan_released_cleanup_once()
    assert result["deleted"] >= 1

    # Container should be deleted from mapping
    assert mgr.container_mapping.get(container_name) is None


def test_multiple_restore_creates_redirect_chain(mgr: SandboxManager):
    """
    Test that multiple restores create a redirect chain that still works.
    """
    session_ctx_id = "test_multiple_restore"

    # First container
    first_name = mgr.create(
        sandbox_type=SandboxType.BASE,
        meta={"session_ctx_id": session_ctx_id},
    )
    assert first_name is not None

    # First restore
    first_cm = ContainerModel(**mgr.get_info(first_name))
    first_cm.state = ContainerState.RECYCLED
    first_cm.recycled_at = time.time()
    mgr.container_mapping.set(first_name, first_cm.model_dump())
    mgr.restore_session(session_ctx_id)

    # Verify first container is REPLACED
    first_data = mgr.container_mapping.get(first_name)
    first_cm_after = ContainerModel(**first_data)
    assert first_cm_after.state == ContainerState.REPLACED
    second_name = first_cm_after.redirect_to

    # Second restore
    second_cm = ContainerModel(**mgr.container_mapping.get(second_name))
    second_cm.state = ContainerState.RECYCLED
    second_cm.recycled_at = time.time()
    mgr.container_mapping.set(second_name, second_cm.model_dump())
    mgr.restore_session(session_ctx_id)

    # Verify second container is REPLACED
    second_data = mgr.container_mapping.get(second_name)
    second_cm_after = ContainerModel(**second_data)
    assert second_cm_after.state == ContainerState.REPLACED
    third_name = second_cm_after.redirect_to

    # First container should still redirect to final container
    # (through chain: first -> second -> third)
    result = mgr.get_info(first_name)
    result_cm = ContainerModel(**result)
    assert result_cm.container_name == third_name
    assert result_cm.state == ContainerState.RUNNING


def test_release_follows_redirect(mgr: SandboxManager):
    """
    Test that release() follows redirect and releases the actual container,
    not just the REPLACED stub (Issue #451 - prevent resource leak).
    """
    session_ctx_id = "test_release_redirect"

    # Create and restore to get REPLACED + new container
    old_name = mgr.create(
        sandbox_type=SandboxType.BASE,
        meta={"session_ctx_id": session_ctx_id},
    )
    assert old_name is not None

    # Mark as RECYCLED and restore
    old_cm = ContainerModel(**mgr.get_info(old_name))
    old_cm.state = ContainerState.RECYCLED
    old_cm.recycled_at = time.time()
    old_cm.recycle_reason = "test"
    mgr.container_mapping.set(old_name, old_cm.model_dump())
    mgr.restore_session(session_ctx_id)

    # Get the new container name
    old_data = mgr.container_mapping.get(old_name)
    old_cm_replaced = ContainerModel(**old_data)
    assert old_cm_replaced.state == ContainerState.REPLACED
    new_name = old_cm_replaced.redirect_to
    assert new_name is not None

    # Verify new container exists
    new_data = mgr.container_mapping.get(new_name)
    assert new_data is not None
    new_cm = ContainerModel(**new_data)
    assert new_cm.state == ContainerState.RUNNING

    # Release using old name (REPLACED stub)
    # Should follow redirect and release the actual new container
    success = mgr.release(old_name)
    assert success is True

    # Verify old stub is now marked as RELEASED
    old_data_after = mgr.container_mapping.get(old_name)
    assert old_data_after is not None
    old_cm_after_release = ContainerModel(**old_data_after)
    assert old_cm_after_release.state == ContainerState.RELEASED

    # Verify new container is also marked as RELEASED (not leaked!)
    new_data_after = mgr.container_mapping.get(new_name)
    assert new_data_after is not None
    new_cm_after_release = ContainerModel(**new_data_after)
    assert new_cm_after_release.state == ContainerState.RELEASED

    # Verify containers were stopped/removed
    assert mgr._stub_cc.stopped, "Containers should be stopped"
    assert mgr._stub_cc.removed, "Containers should be removed"


def test_scan_released_cleanup_metric_names(mgr: SandboxManager):
    """
    Test that scan_released_cleanup_once() uses correct metric names.
    """
    mgr.config.released_key_ttl = 1

    # Create a non-terminal container (should be skipped)
    running_name = f"{mgr.prefix}running_test"
    running_cm = ContainerModel(
        session_id="test",
        container_id="running_cid",
        container_name=running_name,
        url="http://running:8080",
        ports=[8080],
        state=ContainerState.RUNNING,
    )
    mgr.container_mapping.set(running_name, running_cm.model_dump())

    # Scan
    result = mgr.scan_released_cleanup_once()

    # Verify metric name is skipped_not_terminal (not skipped_not_released)
    assert "skipped_not_terminal" in result
    assert result["skipped_not_terminal"] >= 1
