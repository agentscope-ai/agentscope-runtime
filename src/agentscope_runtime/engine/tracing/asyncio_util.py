# -*- coding: utf-8 -*-
from typing import AsyncIterable, AsyncIterator, Tuple, TypeVar

T_co = TypeVar("T_co", covariant=True)


async def aenumerate(
    asequence: AsyncIterable[T_co],
    start: int = 0,
) -> AsyncIterator[Tuple[int, T_co]]:
    """Asynchronously enumerate an async iterator from a given start value.

    Args:
        asequence (AsyncIterable[T_co]): The async iterable to enumerate.
        start (int): The starting value for enumeration. Defaults to 0.

    Yields:
        Tuple[int, T_co]: A tuple containing the index and the item from the
        async iterable.
    """
    n = start
    async for elem in asequence:
        yield n, elem
        n += 1
