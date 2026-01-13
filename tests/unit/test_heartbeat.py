# -*- coding: utf-8 -*-
# pylint: disable=unused-argument
import time

from agentscope_runtime.common.collections import InMemoryMapping
from agentscope_runtime.sandbox.manager.heartbeat_mixin import (
    HeartbeatMixin,
    touch_session,
)


class _FakeConfig:
    redis_enabled = False
    heartbeat_timeout = 1
    heartbeat_scan_interval = 0
    heartbeat_lock_ttl = 3


class FakeManager(HeartbeatMixin):
    def __init__(self):
        self.config = _FakeConfig()
        self.redis_client = None

        self.heartbeat_mapping = InMemoryMapping()
        self.recycled_mapping = InMemoryMapping()
        self.session_mapping = InMemoryMapping()
        self.container_mapping = InMemoryMapping()

        self.reaped_sessions = []

    # --- minimal APIs required by mixin/decorator ---
    def get_info(self, identity):
        obj = self.container_mapping.get(identity)
        if obj is None:
            raise RuntimeError(f"container not found: {identity}")
        return obj

    def create_for_session(self, identity: str, session_ctx_id: str):
        # minimal container record compatible with
        # get_session_ctx_id_by_identity()
        self.container_mapping.set(
            identity,
            {"meta": {"session_ctx_id": session_ctx_id}},
        )
        env_ids = self.session_mapping.get(session_ctx_id) or []
        if identity not in env_ids:
            env_ids.append(identity)
        self.session_mapping.set(session_ctx_id, env_ids)

        # mimic step-7 behavior
        self.update_heartbeat(session_ctx_id)
        self.clear_session_recycled(session_ctx_id)

    def list_session_keys(self):
        return list(self.session_mapping.scan())

    def get_session_mapping(self, session_ctx_id: str):
        return self.session_mapping.get(session_ctx_id) or []

    def reap_session(
        self,
        session_ctx_id: str,
        reason: str = "heartbeat_timeout",
    ) -> bool:
        # minimal reap side effects
        self.reaped_sessions.append((session_ctx_id, reason))
        self.mark_session_recycled(session_ctx_id)
        self.delete_heartbeat(session_ctx_id)
        self.session_mapping.delete(session_ctx_id)
        return True

    def scan_heartbeat_once(self):
        now = time.time()
        timeout = int(self.config.heartbeat_timeout)

        for session_ctx_id in self.list_session_keys():
            last_active = self.get_heartbeat(session_ctx_id)
            if last_active is None:
                continue
            if now - last_active <= timeout:
                continue

            token = self.acquire_heartbeat_lock(session_ctx_id)
            if not token:
                continue
            try:
                last_active2 = self.get_heartbeat(session_ctx_id)
                if last_active2 is None:
                    continue
                if time.time() - last_active2 <= timeout:
                    continue
                self.reap_session(session_ctx_id, reason="heartbeat_timeout")
            finally:
                self.release_heartbeat_lock(session_ctx_id, token)

    # --- a method to trigger touch_session ---
    @touch_session(identity_arg="identity")
    def ping(self, identity: str):
        return True


def test_heartbeat_inmemory_basic():
    mgr = FakeManager()
    session_ctx_id = "s1"
    identity = "c1"

    mgr.create_for_session(identity=identity, session_ctx_id=session_ctx_id)

    t0 = mgr.get_heartbeat(session_ctx_id)
    assert t0 is not None
    assert mgr.needs_restore(session_ctx_id) is False

    # touch via decorator updates heartbeat
    time.sleep(0.01)
    mgr.ping(identity=identity)
    t1 = mgr.get_heartbeat(session_ctx_id)
    assert t1 is not None
    assert t1 >= t0

    # wait until timeout -> scan should reap
    time.sleep(mgr.config.heartbeat_timeout + 0.1)
    mgr.scan_heartbeat_once()

    assert mgr.get_heartbeat(session_ctx_id) is None
    assert mgr.needs_restore(session_ctx_id) is True
    assert (session_ctx_id, "heartbeat_timeout") in mgr.reaped_sessions
    assert session_ctx_id not in mgr.list_session_keys()


def test_heartbeat_watcher_inmemory_real_manager(monkeypatch):
    """
    Test watcher thread itself (in-memory mode):
    - create writes heartbeat
    - watcher reaps after timeout automatically
    """
    from agentscope_runtime.sandbox.manager.sandbox_manager import (
        SandboxManager,
    )
    from agentscope_runtime.sandbox.model import SandboxManagerEnvConfig

    cfg = SandboxManagerEnvConfig(
        redis_enabled=False,
        file_system="local",
        container_deployment="docker",  # won't be used due to monkeypatch
        pool_size=0,
        default_mount_dir="sessions_mount_dir",
        heartbeat_timeout=1,
        heartbeat_scan_interval=1,  # enable watcher
        heartbeat_lock_ttl=3,
    )
    mgr = SandboxManager(config=cfg)

    session_ctx_id = "watcher_session_ctx"
    container_name = "watcher_container"

    # fake create
    def _fake_create(
        self,
        sandbox_type=None,
        mount_dir=None,
        storage_path=None,
        environment=None,
        meta=None,
    ):
        meta = meta or {}
        model_dict = {
            "session_id": "sid1",
            "container_id": "cid1",
            "container_name": container_name,
            "url": "http://127.0.0.1:1",
            "ports": [1],
            "mount_dir": "",
            "storage_path": "",
            "runtime_token": "token",
            "version": "fake",
            "meta": meta,
            "timeout": 0,
        }
        self.container_mapping.set(container_name, model_dict)

        if meta and meta.get("session_ctx_id"):
            scid = meta["session_ctx_id"]
            env_ids = self.session_mapping.get(scid) or []
            if container_name not in env_ids:
                env_ids.append(container_name)
            self.session_mapping.set(scid, env_ids)
            self.update_heartbeat(scid)
            self.clear_session_recycled(scid)

        return container_name

    # fake release
    def _fake_release(self, identity):
        c = self.container_mapping.get(identity)
        if c is None:
            return True
        self.container_mapping.delete(identity)
        meta = c.get("meta") or {}
        scid = meta.get("session_ctx_id")
        if scid:
            self.session_mapping.delete(scid)
        return True

    monkeypatch.setattr(SandboxManager, "create", _fake_create, raising=True)
    monkeypatch.setattr(SandboxManager, "release", _fake_release, raising=True)

    try:
        mgr.create(meta={"session_ctx_id": session_ctx_id})
        assert mgr.get_heartbeat(session_ctx_id) is not None

        mgr.start_heartbeat_watcher()

        # wait long enough for: timeout + (at least one scan interval)
        time.sleep(cfg.heartbeat_timeout + cfg.heartbeat_scan_interval + 0.5)

        assert mgr.get_heartbeat(session_ctx_id) is None
        assert mgr.needs_restore(session_ctx_id) is True
        assert session_ctx_id not in mgr.list_session_keys()
    finally:
        mgr.stop_heartbeat_watcher()
