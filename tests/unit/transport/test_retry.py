"""Tests for retry utility."""

from __future__ import annotations

import pytest

from kpubdata.transport.retry import with_retry


class TestWithRetry:
    """
    Class encapsulating TestWithRetry role.

    This class ``tests/unit/transport/test_retry.py`` within module TestWithRetrymanages its state and behavior together.
    Key methods: test_success_first_try, test_retry_then_success, test_exhausted_retries, test_non_retryable_raises_immediately, test_invalid_max_retries.

    Property description:
        Properties defined in constructor and class body are reused by sub-methods in shared context.
    """

    # Explains scenario for: test success first try.
    def test_success_first_try(self) -> None:
        """
        Verify: test success first try scenario.

        Returns:
            None: returns computation result or value from sub-call.

        Raises:
            can propagate exceptions from sub-dependencies as-is.

        Example:
            Verify expected behavior described by test name is maintained without regression.
        """
        result = with_retry(lambda: 42, retryable_exceptions=(ValueError,))
        assert result == 42

    # test retry then success Explains scenario validated by test.
    def test_retry_then_success(self) -> None:
        """
        test retry then success Verify scenario.

        Returns:
            None: returns computation result or value from sub-call.

        Raises:
            can propagate exceptions from sub-dependencies as-is.

        Example:
            Verify expected behavior described by test name is maintained without regression.
        """
        calls = {"count": 0}

        def flaky() -> str:
            """
            flaky performs operation.

            Returns:
                str: returns computation result or value from sub-call.

            Raises:
                can propagate exceptions from sub-dependencies as-is.
            """
            calls["count"] += 1
            if calls["count"] < 3:
                raise ValueError("transient")
            return "ok"

        result = with_retry(
            flaky, max_retries=3, backoff_factor=0.0, retryable_exceptions=(ValueError,)
        )
        assert result == "ok"
        assert calls["count"] == 3

    # test exhausted retries Explains scenario validated by test.
    def test_exhausted_retries(self) -> None:
        """
        test exhausted retries Verify scenario.

        Returns:
            None: returns computation result or value from sub-call.

        Raises:
            can propagate exceptions from sub-dependencies as-is.

        Example:
            Verify expected behavior described by test name is maintained without regression.
        """

        def always_fail() -> None:
            """
            always fail performs operation.

            Returns:
                None: returns computation result or value from sub-call.

            Raises:
                can propagate exceptions from sub-dependencies as-is.
            """
            raise ValueError("permanent")

        with pytest.raises(ValueError, match="permanent"):
            with_retry(
                always_fail, max_retries=2, backoff_factor=0.0, retryable_exceptions=(ValueError,)
            )

    # test non retryable raises immediately Explains scenario validated by test.
    def test_non_retryable_raises_immediately(self) -> None:
        """
        test non retryable raises immediately Verify scenario.

        Returns:
            None: returns computation result or value from sub-call.

        Raises:
            can propagate exceptions from sub-dependencies as-is.

        Example:
            Verify expected behavior described by test name is maintained without regression.
        """
        calls = {"count": 0}

        def fail_type() -> None:
            """
            fail type performs operation.

            Returns:
                None: returns computation result or value from sub-call.

            Raises:
                can propagate exceptions from sub-dependencies as-is.
            """
            calls["count"] += 1
            raise TypeError("not retryable")

        with pytest.raises(TypeError):
            with_retry(
                fail_type, max_retries=3, backoff_factor=0.0, retryable_exceptions=(ValueError,)
            )
        assert calls["count"] == 1

    # test invalid max retries Explains scenario validated by test.
    def test_invalid_max_retries(self) -> None:
        """
        test invalid max retries Verify scenario.

        Returns:
            None: returns computation result or value from sub-call.

        Raises:
            can propagate exceptions from sub-dependencies as-is.

        Example:
            Verify expected behavior described by test name is maintained without regression.
        """
        with pytest.raises(ValueError, match="max_retries"):
            with_retry(lambda: None, max_retries=-1, retryable_exceptions=())


class TestPluggableSleepAndAsync:
    """retry wait injection, async version (#270)."""

    def test_injected_sleep_receives_backoff_delays_without_blocking(self) -> None:
        """fake sleep records exponential backoff delay — no actual wait."""
        from kpubdata.transport.retry import with_retry

        delays: list[float] = []
        attempts: list[int] = []

        def flaky() -> str:
            attempts.append(1)
            if len(attempts) < 3:
                raise RuntimeError("transient")
            return "ok"

        result = with_retry(
            flaky,
            max_retries=3,
            backoff_factor=0.25,
            retryable_exceptions=(RuntimeError,),
            sleep=delays.append,
        )

        assert result == "ok"
        assert delays == [0.25, 0.5]

    def test_with_retry_async_uses_asyncio_sleep(self) -> None:
        """async version retries with asyncio.sleep not blocking event loop."""
        import asyncio

        from kpubdata.transport.retry import with_retry_async

        attempts: list[int] = []

        async def flaky() -> str:
            attempts.append(1)
            if len(attempts) < 2:
                raise RuntimeError("transient")
            return "ok"

        result = asyncio.run(
            with_retry_async(
                flaky,
                max_retries=2,
                backoff_factor=0.0,
                retryable_exceptions=(RuntimeError,),
            )
        )

        assert result == "ok"
        assert len(attempts) == 2

    def test_transport_retry_uses_injected_sleep(self, monkeypatch) -> None:
        """HttpTransport retry wait also injectable — validation without real sleep."""
        import httpx

        from kpubdata.transport.http import HttpTransport, TransportConfig

        delays: list[float] = []
        responses = [
            httpx.Response(
                503, text="busy", request=httpx.Request("GET", "https://example.test/r")
            ),
            httpx.Response(200, text="ok", request=httpx.Request("GET", "https://example.test/r")),
        ]
        monkeypatch.setattr(
            "kpubdata.transport.http.httpx.Client.send",
            lambda _self, _request, **_k: responses.pop(0),
        )
        transport = HttpTransport(
            TransportConfig(max_retries=2, retry_backoff_factor=0.5),
            sleep=delays.append,
        )

        response = transport.request("GET", "https://example.test/r")

        assert response.status_code == 200
        assert delays == [0.5]
