# -*- coding: utf-8 -*-
import asyncio
import inspect
import time
import secrets
from typing import Optional, List
from functools import wraps

import logging
from redis.exceptions import ResponseError

from ..model import ContainerModel, ContainerState

logger = logging.getLogger(__name__)


def touch_session(identity_arg: str = "identity"):
    """
    Sugar decorator: update heartbeat for session_ctx_id derived from identity.

    Requirements on self:
      - get_session_ctx_id_by_identity(identity) -> Optional[str]
      - update_heartbeat(session_ctx_id)
      - needs_restore(session_ctx_id) -> bool
      - restore_session(session_ctx_id)  # currently stubbed (pass)
    """

    def decorator(func):
        if asyncio.iscoroutinefunction(func):

            @wraps(func)
            async def async_wrapper(self, *args, **kwargs):
                try:
                    bound = inspect.signature(func).bind_partial(
                        self,
                        *args,
                        **kwargs,
                    )
                    identity = bound.arguments.get(identity_arg)
                    if identity is not None:
                        session_ctx_id = self.get_session_ctx_id_by_identity(
                            identity,
                        )
                        if session_ctx_id:
                            self.update_heartbeat(session_ctx_id)
                            if self.needs_restore(session_ctx_id):
                                if hasattr(self, "restore_session"):
                                    self.restore_session(session_ctx_id)
                except Exception as e:
                    logger.debug(f"touch_session failed (ignored): {e}")

                return await func(self, *args, **kwargs)

            return async_wrapper

        @wraps(func)
        def sync_wrapper(self, *args, **kwargs):
            try:
                bound = inspect.signature(func).bind_partial(
                    self,
                    *args,
                    **kwargs,
                )
                identity = bound.arguments.get(identity_arg)
                if identity is not None:
                    session_ctx_id = self.get_session_ctx_id_by_identity(
                        identity,
                    )
                    if session_ctx_id:
                        self.update_heartbeat(session_ctx_id)
                        if self.needs_restore(session_ctx_id):
                            if hasattr(self, "restore_session"):
                                self.restore_session(session_ctx_id)
            except Exception as e:
                logger.debug(f"touch_session failed (ignored): {e}")

            return func(self, *args, **kwargs)

        return sync_wrapper

    return decorator


class HeartbeatMixin:
    """
    Mixin providing:
      - heartbeat timestamp read/write (stored on
        ContainerModel.last_active_at)
      - recycled (restore-required) marker (stored on
        ContainerModel.state/recycled_at)
      - redis distributed lock for reaping

    Host class must provide:
      - self.container_mapping (Mapping-like with set/get/delete/scan)
      - self.session_mapping (Mapping-like with set/get/delete/scan)
      - self.get_info(identity) -> dict compatible with ContainerModel(**dict)
      - self.config.redis_enabled (bool)
      - self.config.heartbeat_lock_ttl (int)
      - self.redis_client (redis client or None)
      - self.restore_session (for restore session)
    """

    _REDIS_RELEASE_LOCK_LUA = """if redis.call("GET", KEYS[1]) == ARGV[1] then
  return redis.call("DEL", KEYS[1])
else
  return 0
end
"""

    def _list_container_names_by_session(
        self,
        session_ctx_id: str,
    ) -> List[str]:
        if not session_ctx_id:
            return []
        # session_mapping stores container_name list
        try:
            return self.session_mapping.get(session_ctx_id) or []
        except Exception:
            return []

    def _load_container_model(self, identity: str) -> Optional[ContainerModel]:
        try:
            info_dict = self.get_info(identity)
            return ContainerModel(**info_dict)
        except Exception as e:
            logger.debug(f"_load_container_model failed for {identity}: {e}")
            return None

    def _save_container_model(self, model: ContainerModel) -> None:
        # IMPORTANT: persist back into container_mapping
        self.container_mapping.set(model.container_name, model.model_dump())

    # ---------- heartbeat ----------
    def update_heartbeat(
        self,
        session_ctx_id: str,
        ts: Optional[float] = None,
    ) -> float:
        """
        Update heartbeat timestamp onto ALL containers bound to session_ctx_id.
        Returns the timestamp written.
        """
        if not session_ctx_id:
            raise ValueError("session_ctx_id is required")

        ts = float(ts if ts is not None else time.time())
        now = time.time()

        container_names = self._list_container_names_by_session(session_ctx_id)
        for cname in list(container_names):
            model = self._load_container_model(cname)
            if not model:
                continue

            # only update heartbeat for RUNNING containers
            if model.state != ContainerState.RUNNING:
                continue

            model.last_active_at = ts
            model.updated_at = now

            # keep session_ctx_id consistent (migration safety)
            model.session_ctx_id = session_ctx_id

            self._save_container_model(model)

        return ts

    def get_heartbeat(self, session_ctx_id: str) -> Optional[float]:
        """
        Return session-level heartbeat = max(last_active_at) among bound
        containers.
        """
        if not session_ctx_id:
            return None

        container_names = self._list_container_names_by_session(session_ctx_id)
        last_vals = []
        for cname in list(container_names):
            model = self._load_container_model(cname)
            if not model:
                continue

            if model.state != ContainerState.RUNNING:
                continue

            if model.last_active_at is not None:
                last_vals.append(float(model.last_active_at))

        return max(last_vals) if last_vals else None

    # ---------- recycled marker ----------
    def mark_session_recycled(
        self,
        session_ctx_id: str,
        ts: Optional[float] = None,
        reason: str = "heartbeat_timeout",
    ) -> float:
        """
        Mark ALL containers bound to session_ctx_id as recycled.
        (Does not stop/remove containers here; reap_session will do that.)
        """
        if not session_ctx_id:
            raise ValueError("session_ctx_id is required")

        ts = float(ts if ts is not None else time.time())
        now = time.time()

        container_names = self._list_container_names_by_session(session_ctx_id)
        for cname in list(container_names):
            model = self._load_container_model(cname)
            if not model:
                continue

            # if already released, don't flip back
            if model.state == ContainerState.RELEASED:
                continue

            model.state = ContainerState.RECYCLED
            model.recycled_at = ts
            model.recycle_reason = reason
            model.updated_at = now

            model.session_ctx_id = session_ctx_id
            self._save_container_model(model)

        return ts

    def clear_session_recycled(self, session_ctx_id: str) -> None:
        """
        Clear recycled marker on containers (if any) for this session.
        Usually called when session is allocated a new running container.
        """
        if not session_ctx_id:
            return

        now = time.time()
        container_names = self._list_container_names_by_session(session_ctx_id)
        for cname in list(container_names):
            model = self._load_container_model(cname)
            if not model:
                continue
            if model.state == ContainerState.RECYCLED:
                model.state = ContainerState.RUNNING
            model.recycled_at = None
            model.recycle_reason = None
            model.updated_at = now
            model.session_ctx_id = session_ctx_id
            self._save_container_model(model)

    def needs_restore(self, session_ctx_id: str) -> bool:
        if not session_ctx_id:
            return False

        container_names = self._list_container_names_by_session(session_ctx_id)
        for cname in list(container_names):
            model = self._load_container_model(cname)
            if not model:
                continue
            if (
                model.state == ContainerState.RECYCLED
                or model.recycled_at is not None
            ):
                return True
        return False

    # ---------- helpers ----------
    def get_session_ctx_id_by_identity(self, identity: str) -> Optional[str]:
        """
        Resolve session_ctx_id from a container identity.
        """
        try:
            info_dict = self.get_info(identity)
        except RuntimeError as exc:
            logger.debug(
                f"get_session_ctx_id_by_identity: container not found for "
                f"identity {identity}: {exc}",
            )

            return None

        info = ContainerModel(**info_dict)

        # NEW: prefer top-level field
        if info.session_ctx_id:
            return info.session_ctx_id

        # fallback for older payloads
        return (info.meta or {}).get("session_ctx_id")

    # ---------- redis distributed lock ----------
    def _heartbeat_lock_key(self, session_ctx_id: str) -> str:
        return f"heartbeat_lock:{session_ctx_id}"

    def acquire_heartbeat_lock(self, session_ctx_id: str) -> Optional[str]:
        """
        Returns lock token if acquired, else None.
        In non-redis mode returns 'inmemory'.
        """
        if not self.config.redis_enabled or self.redis_client is None:
            return "inmemory"

        key = self._heartbeat_lock_key(session_ctx_id)
        token = secrets.token_hex(16)
        ok = self.redis_client.set(
            key,
            token,
            nx=True,
            ex=int(self.config.heartbeat_lock_ttl),
        )
        return token if ok else None

    def release_heartbeat_lock(self, session_ctx_id: str, token: str) -> bool:
        if not self.config.redis_enabled or self.redis_client is None:
            return True

        key = self._heartbeat_lock_key(session_ctx_id)
        try:
            res = self.redis_client.eval(
                self._REDIS_RELEASE_LOCK_LUA,
                1,
                key,
                token,
            )
            return bool(res)
        except ResponseError as e:
            msg = str(e).lower()
            if "unknown command" in msg and "eval" in msg:
                val = self.redis_client.get(key)
                if val == token:
                    return bool(self.redis_client.delete(key))
                return False
            logger.warning(f"Failed to release heartbeat lock {key}: {e}")
            raise
        except Exception as e:
            logger.warning(f"Failed to release heartbeat lock {key}: {e}")
            return False
