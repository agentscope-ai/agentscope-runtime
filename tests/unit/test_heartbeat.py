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
