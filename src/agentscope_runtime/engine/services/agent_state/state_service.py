# -*- coding: utf-8 -*-
import copy

from abc import abstractmethod
from typing import Dict, Any, Optional

from ..base import ServiceWithLifecycleManager


class StateService(ServiceWithLifecycleManager):
    """
    Abstract base class for agent state management services.

    Stores and manages agent states organized by user_id, session_id,
    and round_id. Supports saving, retrieving, listing, and deleting states.
    """

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass

    @abstractmethod
    async def save_state(
        self,
        user_id: str,
        state: Dict[str, Any],
        session_id: Optional[str] = None,
        round_id: Optional[int] = None,
    ) -> int:
        """
        Save serialized state data for a specific user/session.

        If round_id is provided, store the state in that round.
        If round_id is None, append as a new round with automatically
        assigned round_id.

        Args:
            user_id: The unique ID of the user.
            state: A dictionary representing serialized agent state.
            session_id: Optional session/conversation ID. Defaults to
                "default".
            round_id: Optional conversation round number.

        Returns:
            The round_id in which the state was saved.
        """

    @abstractmethod
    async def export_state(
        self,
        user_id: str,
        session_id: Optional[str] = None,
        round_id: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve serialized state data for a user/session.

        If round_id is provided, return that round's state.
        If round_id is None, return the latest round's state.

        Args:
            user_id: The unique ID of the user.
            session_id: Optional session/conversation ID.
            round_id: Optional round number.

        Returns:
            A dictionary representing the agent state, or None if not found.
        """


class InMemoryStateService(StateService):
    """
    In-memory implementation of StateService using dictionaries
    for sparse round storage.

    - Multiple users, sessions, and non-contiguous round IDs are supported.
    - If round_id is None when saving, a new round is appended automatically.
    - If round_id is None when exporting, the latest round is returned.
    """

    _DEFAULT_SESSION_ID = "default"

    def __init__(self) -> None:
        # Structure:
        # { user_id: { session_id: { round_id: state_dict } } }
        self._store: Optional[
            Dict[str, Dict[str, Dict[int, Dict[str, Any]]]]
        ] = None
        self._health = False

    async def start(self) -> None:
        """Initialize the in-memory store."""
        if self._store is None:
            self._store = {}
        self._health = True

    async def stop(self) -> None:
        """Clear all in-memory state data."""
        if self._store is not None:
            self._store.clear()
        self._store = None
        self._health = False

    async def health(self) -> bool:
        """Service health check."""
        return self._health

    async def save_state(
        self,
        user_id: str,
        state: Dict[str, Any],
        session_id: Optional[str] = None,
        round_id: Optional[int] = None,
    ) -> int:
        """
        Save serialized state in sparse dict storage.

        If round_id is None, a new round_id will be assigned
        as (max existing round_id + 1) or 1 if none exist.
        Otherwise, the given round_id will be overwritten.

        Returns:
            The round_id where the state was saved.
        """
        if self._store is None:
            raise RuntimeError("Service not started")

        sid = session_id or self._DEFAULT_SESSION_ID

        self._store.setdefault(user_id, {})
        self._store[user_id].setdefault(sid, {})

        rounds_dict = self._store[user_id][sid]

        # Auto-generate round_id if not provided
        if round_id is None:
            if rounds_dict:
                round_id = max(rounds_dict.keys()) + 1
            else:
                round_id = 1

        # Store a deep copy so caller modifications don't affect saved state
        rounds_dict[round_id] = copy.deepcopy(state)

        return round_id

    async def export_state(
        self,
        user_id: str,
        session_id: Optional[str] = None,
        round_id: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve state data for given user/session/round.

        If round_id is None: return the latest round.
        If round_id is provided: return that round's state.

        Returns:
            Dictionary representing the agent state, or None if not found.
        """
        if self._store is None:
            raise RuntimeError("Service not started")

        sid = session_id or self._DEFAULT_SESSION_ID
        sessions = self._store.get(user_id, {})
        rounds_dict = sessions.get(sid, {})

        if not rounds_dict:
            return None

        if round_id is None:
            # Get the latest round_id
            latest_round_id = max(rounds_dict.keys())
            return rounds_dict[latest_round_id]

        return rounds_dict.get(round_id)
