# -*- coding: utf-8 -*-
import asyncio
import inspect
import time
import secrets
from typing import Optional
from functools import wraps

import logging
from redis.exceptions import ResponseError

from ..model import ContainerModel

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
                            self.restore_session(session_ctx_id)
            except Exception as e:
                logger.debug(f"touch_session failed (ignored): {e}")

            return func(self, *args, **kwargs)

        return sync_wrapper

    return decorator


class HeartbeatMixin:
    """
    Mixin providing:
      - heartbeat timestamp read/write
      - recycled (restore-required) marker
      - redis distributed lock for reaping

    Host class must provide:
      - self.heartbeat_mapping, self.recycled_mapping
        (Mapping-like with set/get/delete)
      - self.get_info(identity) -> dict compatible with ContainerModel(**dict)
      - self.config.redis_enabled (bool)
      - self.config.heartbeat_lock_ttl (int)
      - self.redis_client (redis client or None)
    """

    _REDIS_RELEASE_LOCK_LUA = """if redis.call("GET", KEYS[1]) == ARGV[1] then
  return redis.call("DEL", KEYS[1])
else
  return 0
end
"""

    # ---------- heartbeat ----------
    def update_heartbeat(
        self,
        session_ctx_id: str,
        ts: Optional[float] = None,
    ) -> float:
        """
        heartbeat_mapping[session_ctx_id] = last_active_timestamp
        (unix seconds).
        """
        if not session_ctx_id:
            raise ValueError("session_ctx_id is required")
        ts = float(ts if ts is not None else time.time())
        self.heartbeat_mapping.set(session_ctx_id, ts)
        return ts

    def get_heartbeat(self, session_ctx_id: str) -> Optional[float]:
        val = (
            self.heartbeat_mapping.get(session_ctx_id)
            if session_ctx_id
            else None
        )
        return float(val) if val is not None else None

    def delete_heartbeat(self, session_ctx_id: str) -> None:
        if session_ctx_id:
            self.heartbeat_mapping.delete(session_ctx_id)

    # ---------- recycled marker ----------
    def mark_session_recycled(
        self,
        session_ctx_id: str,
        ts: Optional[float] = None,
    ) -> float:
        """
        recycled_mapping[session_ctx_id] = recycled_timestamp (unix seconds).
        """
        if not session_ctx_id:
            raise ValueError("session_ctx_id is required")
        ts = float(ts if ts is not None else time.time())
        self.recycled_mapping.set(session_ctx_id, ts)
        return ts

    def clear_session_recycled(self, session_ctx_id: str) -> None:
        if session_ctx_id:
            self.recycled_mapping.delete(session_ctx_id)

    def needs_restore(self, session_ctx_id: str) -> bool:
        if not session_ctx_id:
            return False
        return self.recycled_mapping.get(session_ctx_id) is not None

    def restore_session(self, session_ctx_id: str) -> None:
        """
        Stub for snapshot/restore phase.
        Called when a session is marked recycled (needs_restore == True).
        """
        logger.warning(
            f"restore_session({session_ctx_id}) called but not implemented "
            f"yet.",
        )
        # NOTE: keep recycled mark for now, so future requests still
        # indicate restore needed. If you prefer "warn once", uncomment next
        # line:
        # self.clear_session_recycled(session_ctx_id)

    # ---------- helpers ----------
    def get_session_ctx_id_by_identity(self, identity: str) -> Optional[str]:
        """
        Resolve session_ctx_id from a container identity.
        Returns None if the container cannot be found (get_info raises
        RuntimeError), which is an expected situation for recycled/removed
        containers during heartbeat touches.
        """
        try:
            info_dict = self.get_info(identity)
        except RuntimeError as exc:
            # Missing container is a normal condition during heartbeat checks.
            logger.debug(
                "get_session_ctx_id_by_identity: container not found for "
                "identity %s: %s",
                identity,
                exc,
            )
            return None
        info = ContainerModel(**info_dict)
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
