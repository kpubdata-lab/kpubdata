"""Retry helpers that back off exponentially."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from typing import TypeVar

T = TypeVar("T")

logger = logging.getLogger("kpubdata.transport")


def with_retry(
    fn: Callable[[], T],
    *,
    max_retries: int = 3,
    backoff_factor: float = 0.5,
    retryable_exceptions: tuple[type[BaseException], ...] = (),
    sleep: Callable[[float], None] = time.sleep,
) -> T:
    """Call ``fn``, retrying with exponential backoff.

    Args:
        fn: The callable to run.
        max_retries: How many retries to make after the first attempt.
        backoff_factor: Base factor for the exponential backoff.
        retryable_exceptions: Exception types that should trigger a retry.
        sleep: How to wait between retries. Defaults to ``time.sleep``; tests
            inject a fake and the async wrapper passes ``asyncio.sleep`` (#270).

    Returns:
        Whatever ``fn`` returned.

    Raises:
        BaseException: Re-raises the last exception ``fn`` raised.
        ValueError: If the retry configuration is invalid.
    """
    if max_retries < 0:
        msg = "max_retries must be >= 0"
        raise ValueError(msg)
    if backoff_factor < 0:
        msg = "backoff_factor must be >= 0"
        raise ValueError(msg)

    total_attempts = max_retries + 1
    for attempt in range(1, total_attempts + 1):
        try:
            return fn()
        except retryable_exceptions as exc:
            if attempt >= total_attempts:
                raise

            delay = backoff_factor * (2 ** (attempt - 1))
            logger.debug(
                "Retrying operation after exception",
                extra={
                    "attempt": attempt,
                    "max_retries": max_retries,
                    "delay_seconds": delay,
                    "exception_type": type(exc).__name__,
                },
            )
            sleep(delay)

    msg = "unreachable retry state"
    raise RuntimeError(msg)


async def with_retry_async(
    fn: Callable[[], Awaitable[T]],
    *,
    max_retries: int = 3,
    backoff_factor: float = 0.5,
    retryable_exceptions: tuple[type[BaseException], ...] = (),
) -> T:
    """The async counterpart of ``with_retry``; waits with ``asyncio.sleep`` (#270).

    It does not block the event loop, so FastAPI/asyncio consumers such as
    Builder do not stall. The retry policy and exception semantics are identical
    to the synchronous version.
    """
    if max_retries < 0:
        msg = "max_retries must be >= 0"
        raise ValueError(msg)
    if backoff_factor < 0:
        msg = "backoff_factor must be >= 0"
        raise ValueError(msg)

    total_attempts = max_retries + 1
    for attempt in range(1, total_attempts + 1):
        try:
            return await fn()
        except retryable_exceptions as exc:
            if attempt >= total_attempts:
                raise

            delay = backoff_factor * (2 ** (attempt - 1))
            logger.debug(
                "Retrying async operation after exception",
                extra={
                    "attempt": attempt,
                    "max_retries": max_retries,
                    "delay_seconds": delay,
                    "exception_type": type(exc).__name__,
                },
            )
            await asyncio.sleep(delay)

    msg = "unreachable retry state"
    raise RuntimeError(msg)


__all__ = ["with_retry", "with_retry_async"]
