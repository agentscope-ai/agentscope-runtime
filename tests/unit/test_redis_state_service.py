# -*- coding: utf-8 -*-
# pylint: disable=redefined-outer-name, protected-access
import asyncio
import pytest
import pytest_asyncio
import fakeredis.aioredis
from agentscope_runtime.engine.services.agent_state import (
    RedisStateService,
)


@pytest_asyncio.fixture
async def state_service() -> RedisStateService:
    """Provides an instance of RedisStateService for testing."""
    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    # Set ttl_seconds=None to maintain the original test behavior (no TTL)
    service = RedisStateService(redis_client=fake_redis, ttl_seconds=None)
    await service.start()
    # check redis
    healthy = await service.health()
    if not healthy:
        raise RuntimeError(
            "Redis is unavailable(default：localhost:6379)",
        )
    try:
        yield service
    finally:
        await service.stop()


@pytest.fixture
def user_id() -> str:
    """Provides a sample user ID."""
    return "test_user"


@pytest.mark.asyncio
async def test_service_lifecycle():
    """Test service lifecycle (start, health, stop)."""
    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    service = RedisStateService(redis_client=fake_redis, ttl_seconds=None)
    await service.start()
    assert await service.health() is True
    await service.stop()
    assert await service.health() is False


@pytest.mark.asyncio
async def test_save_and_export_state(
    state_service: RedisStateService,
    user_id: str,
) -> None:
    """Tests saving and exporting state."""
    state = {"key": "value", "number": 42}
    round_id = await state_service.save_state(user_id, state)
    assert round_id == 1

    exported = await state_service.export_state(user_id)
    assert exported is not None
    assert exported == state


@pytest.mark.asyncio
async def test_save_state_with_session_id(
    state_service: RedisStateService,
    user_id: str,
) -> None:
    """Tests saving state with a specific session ID."""
    session_id = "session1"
    state = {"session": "specific"}
    round_id = await state_service.save_state(
        user_id,
        state,
        session_id=session_id,
    )
    assert round_id == 1

    exported = await state_service.export_state(
        user_id,
        session_id=session_id,
    )
    assert exported is not None
    assert exported == state


@pytest.mark.asyncio
async def test_save_state_with_round_id(
    state_service: RedisStateService,
    user_id: str,
) -> None:
    """Tests saving state with a specific round ID."""
    state1 = {"round": 1}
    state2 = {"round": 2}

    round_id1 = await state_service.save_state(user_id, state1, round_id=10)
    assert round_id1 == 10

    round_id2 = await state_service.save_state(user_id, state2, round_id=20)
    assert round_id2 == 20

    exported1 = await state_service.export_state(user_id, round_id=10)
    assert exported1 == state1

    exported2 = await state_service.export_state(user_id, round_id=20)
    assert exported2 == state2


@pytest.mark.asyncio
async def test_export_state_returns_latest(
    state_service: RedisStateService,
    user_id: str,
) -> None:
    """Tests that export_state returns the latest round when round_id is
    None."""
    state1 = {"round": 1}
    state2 = {"round": 2}
    state3 = {"round": 3}

    await state_service.save_state(user_id, state1)
    await state_service.save_state(user_id, state2)
    await state_service.save_state(user_id, state3)

    exported = await state_service.export_state(user_id)
    assert exported is not None
    assert exported == state3


@pytest.mark.asyncio
async def test_export_state_nonexistent(
    state_service: RedisStateService,
    user_id: str,
) -> None:
    """Tests exporting state that doesn't exist."""
    exported = await state_service.export_state(user_id)
    assert exported is None

    exported_with_round = await state_service.export_state(
        user_id,
        round_id=999,
    )
    assert exported_with_round is None


@pytest.mark.asyncio
async def test_multiple_rounds_auto_increment(
    state_service: RedisStateService,
    user_id: str,
) -> None:
    """Tests that round IDs auto-increment when not specified."""
    state1 = {"round": 1}
    state2 = {"round": 2}
    state3 = {"round": 3}

    round_id1 = await state_service.save_state(user_id, state1)
    round_id2 = await state_service.save_state(user_id, state2)
    round_id3 = await state_service.save_state(user_id, state3)

    assert round_id1 == 1
    assert round_id2 == 2
    assert round_id3 == 3

    exported1 = await state_service.export_state(user_id, round_id=1)
    exported2 = await state_service.export_state(user_id, round_id=2)
    exported3 = await state_service.export_state(user_id, round_id=3)

    assert exported1 == state1
    assert exported2 == state2
    assert exported3 == state3


@pytest.mark.asyncio
async def test_ttl_expiration():
    """Test that state data expires after TTL."""
    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    # Use a short TTL for quick test completion
    service = RedisStateService(
        redis_client=fake_redis,
        ttl_seconds=1,  # 1 second TTL
    )
    await service.start()

    try:
        user_id = "ttl_test_user"
        state = {"key": "value"}

        # Save state
        await service.save_state(user_id, state)
        key = service._session_key(user_id, "default")

        # Immediately verify state exists
        exported = await service.export_state(user_id)
        assert exported is not None
        assert exported == state

        # Verify key exists and has TTL
        ttl = await fake_redis.ttl(key)
        assert ttl > 0, "Key should have a TTL set"
        assert ttl <= 1, "TTL should be 1 second or less"

        # Wait for TTL to expire (wait 1.5 seconds to ensure expiration)
        await asyncio.sleep(1.5)

        # Verify data has been deleted (key does not exist or has expired)
        key_exists = await fake_redis.exists(key)
        assert key_exists == 0, "Key should be expired and deleted"

        # Verify export_state returns None after expiry
        exported_after_expiry = await service.export_state(user_id)
        assert (
            exported_after_expiry is None
        ), "State should return None after expiry"

    finally:
        await service.stop()


@pytest.mark.asyncio
async def test_ttl_refresh_on_write():
    """Test that TTL is refreshed when new state is written."""
    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    service = RedisStateService(
        redis_client=fake_redis,
        ttl_seconds=2,  # 2 seconds TTL
    )
    await service.start()

    try:
        user_id = "ttl_refresh_user"
        key = service._session_key(user_id, "default")

        # First write
        state1 = {"round": 1}
        await service.save_state(user_id, state1)

        # Check TTL
        ttl1 = await fake_redis.ttl(key)
        assert 0 < ttl1 <= 2

        # Wait 1 second (TTL should decrease)
        await asyncio.sleep(1.1)

        # Second write (should refresh TTL)
        state2 = {"round": 2}
        await service.save_state(user_id, state2)

        # Verify TTL is refreshed (should be close to 2 seconds)
        ttl2 = await fake_redis.ttl(key)
        assert 0 < ttl2 <= 2
        # TTL should be refreshed, so it should be longer than the
        #  remaining time after waiting
        # Since we waited 1.1 seconds, if TTL was not refreshed,
        #  remaining time should be < 1 second
        # If refreshed, remaining time should be close to 2 seconds
        assert ttl2 > 1.5, "TTL should be refreshed to close to 2 seconds"

        # Verify both states exist
        exported1 = await service.export_state(user_id, round_id=1)
        exported2 = await service.export_state(user_id, round_id=2)
        assert exported1 == state1, "First state should exist"
        assert exported2 == state2, "Second state should exist"

    finally:
        await service.stop()


@pytest.mark.asyncio
async def test_ttl_refresh_on_read():
    """Test that TTL is refreshed when state is accessed."""
    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    service = RedisStateService(
        redis_client=fake_redis,
        ttl_seconds=2,  # 2 seconds TTL
    )
    await service.start()

    try:
        user_id = "ttl_refresh_read_user"
        key = service._session_key(user_id, "default")

        # Save state
        state = {"key": "value"}
        await service.save_state(user_id, state)

        # Check initial TTL
        ttl1 = await fake_redis.ttl(key)
        assert 0 < ttl1 <= 2

        # Wait 1 second (TTL should decrease)
        await asyncio.sleep(1.1)

        # Export state (should refresh TTL)
        exported = await service.export_state(user_id)

        # Verify TTL is refreshed
        ttl2 = await fake_redis.ttl(key)
        assert 0 < ttl2 <= 2
        assert ttl2 > 1.5, "TTL should be refreshed to close to 2 seconds"

        assert exported is not None
        assert exported == state

    finally:
        await service.stop()


@pytest.mark.asyncio
async def test_ttl_disabled():
    """Test that when ttl_seconds is None, data never expires."""
    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    service = RedisStateService(
        redis_client=fake_redis,
        ttl_seconds=None,  # Disable TTL
    )
    await service.start()

    try:
        user_id = "no_ttl_user"
        key = service._session_key(user_id, "default")

        # Save state
        state = {"key": "value"}
        await service.save_state(user_id, state)

        # Verify key exists and has no TTL
        # (TTL returns -1 when no expiration is set)
        ttl = await fake_redis.ttl(key)
        assert ttl == -1, "Key should not have TTL when ttl_seconds is None"

        # Wait for a while
        await asyncio.sleep(0.5)

        # Verify data still exists
        key_exists = await fake_redis.exists(key)
        assert key_exists == 1, "Key should still exist without TTL"

        exported = await service.export_state(user_id)
        assert exported is not None, "State should still be available"
        assert exported == state

    finally:
        await service.stop()
