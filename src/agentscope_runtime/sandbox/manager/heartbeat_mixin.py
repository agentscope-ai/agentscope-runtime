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
    """Decorator factory that updates session heartbeat derived from identity.

    This decorator extracts ``identity`` (or the argument named by
    ``identity_arg``) from the wrapped function call, resolves
    ``session_ctx_id``, updates heartbeat, and triggers restore when needed.

    .. important:: Any exceptions raised during the touch process are ignored.

    Args:
        identity_arg (`str`):
            The keyword/parameter name that carries the identity.

    Returns:
        `callable`:
            A decorator that wraps the target function (sync or async).
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
    """Mixin that provides heartbeat, recycle markers, and a distributed lock.

    This mixin stores heartbeat timestamps and recycle markers in
    ``ContainerModel`` records persisted through ``container_mapping``.
    It also supports a Redis-based distributed lock for reaping/heartbeat
    operations.

    .. important:: The host class must provide required attributes/methods.

    Host class requirements:
        - ``self.container_mapping`` (Mapping-like with set/get/delete/scan)
        - ``self.session_mapping`` (Mapping-like with set/get/delete/scan)
        - ``self.get_info(identity) -> dict`` compatible with
          ``ContainerModel(**dict)``
        - ``self.config.redis_enabled`` (`bool`)
        - ``self.config.heartbeat_lock_ttl`` (`int`)
        - ``self.redis_client`` (redis client or ``None``)
        - ``self.restore_session(session_ctx_id)`` (optional, for restore)

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
        """List container names bound to the given session context id.

        Args:
            session_ctx_id (`str`):
                The session context id.

        Returns:
            `List[str]`:
                A list of container names for the session, or an empty list.
        """
        if not session_ctx_id:
            return []
        # session_mapping stores container_name list
        try:
            return self.session_mapping.get(session_ctx_id) or []
        except Exception as e:
            logger.warning(
                f"_list_container_names_by_session "
                f"failed for session_ctx_id={session_ctx_id}: {e}",
                exc_info=True,
            )
            return []

    def _load_container_model(self, identity: str) -> Optional[ContainerModel]:
        """Load a `ContainerModel` from storage by container identity.

        Args:
            identity (`str`):
                The container identity (typically container name).

        Returns:
            `Optional[ContainerModel]`:
                The loaded model, or ``None`` if it cannot be loaded.
        """
        try:
            info_dict = self.get_info(identity)
            return ContainerModel(**info_dict)
        except Exception as e:
            logger.debug(f"_load_container_model failed for {identity}: {e}")
            return None

    def _save_container_model(self, model: ContainerModel) -> None:
        """Persist a `ContainerModel` back into ``container_mapping``.

        Args:
            model (`ContainerModel`):
                The model to persist.

        Returns:
            `None`:
                No return value.
        """
        # IMPORTANT: persist back into container_mapping
        self.container_mapping.set(model.container_name, model.model_dump())

    # ---------- heartbeat ----------
    def update_heartbeat(
        self,
        session_ctx_id: str,
        ts: Optional[float] = None,
    ) -> float:
        """Update heartbeat timestamp for all RUNNING containers of a session.

        The timestamp is written into ``ContainerModel.last_active_at`` and
        ``updated_at`` is refreshed.

        Args:
            session_ctx_id (`str`):
                The session context id.
            ts (`Optional[float]`, optional):
                The timestamp to write. If ``None``, uses ``time.time()``.

        Returns:
            `float`:
                The timestamp that was written.
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
        """Get session-level heartbeat as max(last_active_at) of RUNNING items.

        Args:
            session_ctx_id (`str`):
                The session context id.

        Returns:
            `Optional[float]`:
                The maximum heartbeat timestamp, or ``None`` if unavailable.
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
        """Mark all containers of a session as recycled.

        This only updates stored metadata; it does not stop/remove containers.

        Args:
            session_ctx_id (`str`):
                The session context id.
            ts (`Optional[float]`, optional):
                The recycle timestamp. If ``None``, uses ``time.time()``.
            reason (`str`):
                The recycle reason.

        Returns:
            `float`:
                The timestamp that was written.
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

    def clear_container_recycle_marker(
        self,
        identity: str,
        *,
        set_state: Optional[ContainerState] = None,
    ) -> None:
        """Clear recycle marker for a single container and set its state.

        This resets:
            - ``recycled_at`` to ``None``
            - ``recycle_reason`` to ``None``

        .. important:: This only updates the stored record; it does not manage
           real container lifecycle and session mapping.

        Args:
            identity (`str`):
                The container identity.
            set_state (`ContainerState`):
                The state to set on the container record.

        Returns:
            `None`:
                No return value.
        """
        model = self._load_container_model(identity)
        if not model:
            return

        model.recycled_at = None
        model.recycle_reason = None
        if set_state:
            model.state = set_state

        model.updated_at = time.time()
        self._save_container_model(model)

    def needs_restore(self, session_ctx_id: str) -> bool:
        """Check whether any container in the session is marked for restore.

        A session is considered needing restore if any bound container is in
        ``ContainerState.RECYCLED`` or has ``recycled_at`` set.

        Args:
            session_ctx_id (`str`):
                The session context id.

        Returns:
            `bool`:
                ``True`` if restore is needed, otherwise ``False``.
        """
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
        """Resolve ``session_ctx_id`` from a container identity.

        It prefers the top-level ``session_ctx_id`` field on `ContainerModel`,
        and falls back to ``meta['session_ctx_id']`` for older payloads.

        Args:
            identity (`str`):
                The container identity.

        Returns:
            `Optional[str]`:
                The resolved session context id, or ``None`` if not found.
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
        """Build the Redis key used for heartbeat locking.

        Args:
            session_ctx_id (`str`):
                The session context id.

        Returns:
            `str`:
                The redis lock key.
        """
        return f"heartbeat_lock:{session_ctx_id}"

    def acquire_heartbeat_lock(self, session_ctx_id: str) -> Optional[str]:
        """Acquire a heartbeat lock for a session.

        In Redis mode, it uses ``SET key token NX EX ttl``.
        In non-Redis mode, it returns a fixed token ``"inmemory"``.

        Args:
            session_ctx_id (`str`):
                The session context id.

        Returns:
            `Optional[str]`:
                The lock token if acquired, otherwise ``None``.
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
        """Release a heartbeat lock if the token matches.

        It uses a Lua script to ensure only the owner token can release the
        lock.
        If Redis does not support ``EVAL``, it falls back to a GET+DEL check.

        Args:
            session_ctx_id (`str`):
                The session context id.
            token (`str`):
                The lock token returned by `acquire_heartbeat_lock`.

        Returns:
            `bool`:
                ``True`` if the lock was released (or non-Redis mode), else
                ``False``.
        """
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
