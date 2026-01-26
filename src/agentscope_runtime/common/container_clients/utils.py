# -*- coding: utf-8 -*-
import logging
from typing import Dict, Optional, List

from ..collections import RedisMapping, InMemoryMapping

logger = logging.getLogger(__name__)


class SessionManager:
    """Manager for sessions that handles creation, retrieval,
    updating, and deletion of sessions.
    """

    def __init__(self, config):
        """Initialize the session manager with an empty session dictionary."""
        self.config = config

        if self.config.redis_enabled:
            import redis

            redis_client = redis.Redis(
                host=self.config.redis_server,
                port=self.config.redis_port,
                db=self.config.redis_db,
                username=self.config.redis_user,
                password=self.config.redis_password,
                decode_responses=True,
            )
            try:
                redis_client.ping()
            except ConnectionError as e:
                raise RuntimeError(
                    "Unable to connect to the Redis server.",
                ) from e

            self.sessions = RedisMapping(
                redis_client,
                prefix="container_session_manager",  # TODO: Configurable
            )
        else:
            self.sessions = InMemoryMapping()

        logger.debug("Session Manager initialized")

    def create_session(self, session_id: str, session_data: Dict):
        """Create a new session with the given session_id and session_data."""
        self.sessions.set(session_id, session_data)
        logger.debug(f"Created session: {session_id}")

    def get_session(self, session_id: str) -> Optional[Dict]:
        """Retrieve session data by session_id."""
        return self.sessions.get(session_id)

    def update_session(self, session_id: str, updates: Dict):
        """Update an existing session with new data."""
        if self.sessions.get(session_id):
            self.sessions.set(session_id, updates)
            logger.debug(f"Updated session: {session_id}")

    def delete_session(self, session_id: str):
        """Delete a session by session_id."""
        if self.sessions.get(session_id):
            self.sessions.delete(session_id)
            logger.debug(f"Deleted session: {session_id}")

    def list_sessions(self) -> List[str]:
        """List all session IDs."""
        return list(self.sessions.scan())
