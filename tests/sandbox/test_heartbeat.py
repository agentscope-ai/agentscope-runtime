# -*- coding: utf-8 -*-
# pylint: disable=unused-argument,protected-access,redefined-outer-name
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
    """
    Stub docker client:
    - create/start/stop/remove/inspect/get_status are enough for SandboxManager
    """

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
        # return: _id, ports, ip, *rest
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
    def check_health(self):
        return {"status": "ok"}

    def list_tools(self, tool_type=None, **kwargs):
        return [{"name": "dummy"}]

    def call_tool(self, tool_name=None, arguments=None):
        return {"tool": tool_name, "ok": True}

    def add_mcp_servers(self, server_configs, overwrite=False):
        return {"ok": True, "count": len(server_configs)}


@pytest.fixture()
def mgr(monkeypatch):
    # 1) stub ContainerClientFactory.create_client
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

    # 2) make storage operations no-op
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

    # 3) make runtime http client no-op (so touch_session can run)
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
    # expose stub client for assertions about stop/remove calls
    m._stub_cc = stub_cc
    try:
        yield m
    finally:
        # avoid leftovers
        m.cleanup()


def _force_expire_session(
    mgr: SandboxManager,
    session_ctx_id: str,
    seconds_ago: float = 100,
):
    # Set last_active_at of all RUNNING containers in this session to a very
    # old timestamp
    for cname in mgr.get_session_mapping(session_ctx_id):
        cm = ContainerModel(**mgr.get_info(cname))
        cm.last_active_at = time.time() - seconds_ago
        cm.updated_at = time.time()
        mgr.container_mapping.set(cm.container_name, cm.model_dump())


def test_heartbeat_reap_then_touch_auto_restore_flow(mgr: SandboxManager):
    session = "sess-1"

    # 1) Create a session-bound container (real SandboxManager.create logic)
    cname = mgr.create(
        sandbox_type=SandboxType.BASE,
        meta={"session_ctx_id": session},
    )
    assert cname is not None

    cm = ContainerModel(**mgr.get_info(cname))
    assert cm.state == ContainerState.RUNNING
    assert cm.session_ctx_id == session
    assert mgr.get_heartbeat(session) is not None
    assert mgr.needs_restore(session) is False

    # 2) touch_session: calling check_health will update_heartbeat
    hb0 = mgr.get_heartbeat(session)
    time.sleep(0.01)
    mgr.check_health(cname)
    hb1 = mgr.get_heartbeat(session)
    assert hb1 >= hb0

    # 3) Expire heartbeat + scan => triggers reap_session (stop/remove +
    # mark RECYCLED)
    _force_expire_session(mgr, session, seconds_ago=100)
    metrics = mgr.scan_heartbeat_once()
    assert metrics["reaped_sessions"] == 1

    # old container should be stopped/removed
    assert mgr._stub_cc.stopped, "reap should call stop"
    assert mgr._stub_cc.removed, "reap should call remove"

    # should require restore
    assert mgr.needs_restore(session) is True

    # 4) touch_session again: should auto restore_session (decorator logic)
    #    here identity=old cname; get_info can still load the model (still
    #    in container_mapping)
    mgr.check_health(cname)

    assert mgr.needs_restore(session) is False

    # 5) after restore, session_mapping should point to a "new container"
    new_list = mgr.get_session_mapping(session)
    assert new_list, "session_mapping should exist after restore"
    assert (
        new_list[0] != cname
    ), "restored container should be a new container name"

    new_cm = ContainerModel(**mgr.get_info(new_list[0]))
    assert new_cm.state == ContainerState.RUNNING
    assert new_cm.session_ctx_id == session

    # new container should also be touchable
    mgr.list_tools(new_list[0])
    assert mgr.get_heartbeat(session) is not None


def test_scan_branches_no_running_and_no_heartbeat(mgr: SandboxManager):
    # skipped_no_running_containers: session mapping contains only WARM
    # containers
    s1 = "s_no_running"
    mgr.session_mapping.set(s1, ["c_warm"])
    mgr.container_mapping.set(
        "c_warm",
        ContainerModel(
            session_id="sid",
            container_id="cid",
            container_name="c_warm",
            url="http://127.0.0.1:1",
            ports=[1],
            mount_dir="",
            storage_path="",
            runtime_token="t",
            version="fake",
            meta={"session_ctx_id": s1},
            timeout=0,
            sandbox_type="base",
            session_ctx_id=s1,
            state=ContainerState.WARM,
            updated_at=time.time(),
        ).model_dump(),
    )

    # skipped_no_heartbeat: RUNNING but last_active_at=None
    s2 = "s_no_hb"
    mgr.session_mapping.set(s2, ["c_nohb"])
    cm = ContainerModel(**mgr.container_mapping.get("c_warm"))
    cm.container_name = "c_nohb"
    cm.session_id = "sid2"
    cm.container_id = "cid2"
    cm.state = ContainerState.RUNNING
    cm.session_ctx_id = s2
    cm.meta = {"session_ctx_id": s2}
    cm.last_active_at = None
    mgr.container_mapping.set("c_nohb", cm.model_dump())

    metrics = mgr.scan_heartbeat_once()
    assert metrics["skipped_no_running_containers"] >= 1
    assert metrics["skipped_no_heartbeat"] >= 1
