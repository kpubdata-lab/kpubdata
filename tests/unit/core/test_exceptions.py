"""Tests for the exception hierarchy."""

from __future__ import annotations

import pytest

from kpubdata.exceptions import (
    AuthError,
    ConfigError,
    DatasetNotFoundError,
    ProviderNotRegisteredError,
    ProviderResponseError,
    PublicDataError,
    RateLimitError,
    ServiceUnavailableError,
    TransportError,
    TransportTimeoutError,
    UnsupportedCapabilityError,
)


class TestPublicDataError:
    """
    Class encapsulating TestPublicDataError role.

    This class ``tests/unit/core/test_exceptions.py`` within module TestPublicDataErrormanages its state and behavior together.
    Key methods: test_message, test_context_attrs, test_repr.

    Property description:
        Properties defined in constructor and class body are reused by sub-methods in shared context.
    """

    # Explains scenario validated by test message test.
    def test_message(self) -> None:
        """
        Verify test message scenario.

        Returns:
            None: returns computation result or value from sub-call.

        Raises:
            can propagate exceptions from sub-dependencies as-is.

        Example:
            Verify expected behavior described by test name is maintained without regression.
        """
        err = PublicDataError("boom")
        assert str(err) == "boom"

    # test context attrs Explains scenario validated by test.
    def test_context_attrs(self) -> None:
        """
        test context attrs Verify scenario.

        Returns:
            None: returns computation result or value from sub-call.

        Raises:
            can propagate exceptions from sub-dependencies as-is.

        Example:
            Verify expected behavior described by test name is maintained without regression.
        """
        err = PublicDataError(
            "fail",
            provider="datago",
            dataset_id="datago.apt",
            operation="list",
            status_code=500,
            provider_code="ERR01",
            retryable=True,
            detail={"raw": "data"},
        )
        assert err.provider == "datago"
        assert err.dataset_id == "datago.apt"
        assert err.status_code == 500
        assert err.retryable is True

    # test repr Explains scenario validated by test.
    def test_repr(self) -> None:
        """
        test repr Verify scenario.

        Returns:
            None: returns computation result or value from sub-call.

        Raises:
            can propagate exceptions from sub-dependencies as-is.

        Example:
            Verify expected behavior described by test name is maintained without regression.
        """
        err = PublicDataError("fail", provider="x", status_code=404)
        r = repr(err)
        assert "PublicDataError" in r
        assert "x" in r
        assert "404" in r


class TestTransportError:
    """
    Class encapsulating TestTransportError role.

    This class ``tests/unit/core/test_exceptions.py`` within module TestTransportErrormanages its state and behavior together.
    Key methods: test_retryable_default, test_retryable_override.

    Property description:
        Properties defined in constructor and class body are reused by sub-methods in shared context.
    """

    # test retryable default Explains scenario validated by test.
    def test_retryable_default(self) -> None:
        """
        test retryable default Verify scenario.

        Returns:
            None: returns computation result or value from sub-call.

        Raises:
            can propagate exceptions from sub-dependencies as-is.

        Example:
            Verify expected behavior described by test name is maintained without regression.
        """
        err = TransportError("network issue")
        assert err.retryable is True

    # test retryable override Explains scenario validated by test.
    def test_retryable_override(self) -> None:
        """
        test retryable override Verify scenario.

        Returns:
            None: returns computation result or value from sub-call.

        Raises:
            can propagate exceptions from sub-dependencies as-is.

        Example:
            Verify expected behavior described by test name is maintained without regression.
        """
        err = TransportError("permanent", retryable=False)
        assert err.retryable is False


class TestHierarchy:
    """
    Class encapsulating TestHierarchy role.

    This class ``tests/unit/core/test_exceptions.py`` within module TestHierarchymanages its state and behavior together.
    Key methods: test_transport_timeout_is_transport, test_rate_limit_is_transport, test_service_unavailable_is_transport, test_all_inherit_base, test_catch_base.

    Property description:
        Properties defined in constructor and class body are reused by sub-methods in shared context.
    """

    # test transport timeout is transport Explains scenario validated by test.
    def test_transport_timeout_is_transport(self) -> None:
        """
        test transport timeout is transport Verify scenario.

        Returns:
            None: returns computation result or value from sub-call.

        Raises:
            can propagate exceptions from sub-dependencies as-is.

        Example:
            Verify expected behavior described by test name is maintained without regression.
        """
        assert issubclass(TransportTimeoutError, TransportError)

    # test rate limit is transport Explains scenario validated by test.
    def test_rate_limit_is_transport(self) -> None:
        """
        test rate limit is transport Verify scenario.

        Returns:
            None: returns computation result or value from sub-call.

        Raises:
            can propagate exceptions from sub-dependencies as-is.

        Example:
            Verify expected behavior described by test name is maintained without regression.
        """
        assert issubclass(RateLimitError, TransportError)

    # test service unavailable is transport Explains scenario validated by test.
    def test_service_unavailable_is_transport(self) -> None:
        """
        test service unavailable is transport Verify scenario.

        Returns:
            None: returns computation result or value from sub-call.

        Raises:
            can propagate exceptions from sub-dependencies as-is.

        Example:
            Verify expected behavior described by test name is maintained without regression.
        """
        assert issubclass(ServiceUnavailableError, TransportError)

    # test all inherit base Explains scenario validated by test.
    def test_all_inherit_base(self) -> None:
        """
        test all inherit base Verify scenario.

        Returns:
            None: returns computation result or value from sub-call.

        Raises:
            can propagate exceptions from sub-dependencies as-is.

        Example:
            Verify expected behavior described by test name is maintained without regression.
        """
        for cls in [
            ConfigError,
            AuthError,
            TransportError,
            TransportTimeoutError,
            RateLimitError,
            ServiceUnavailableError,
            ProviderResponseError,
            UnsupportedCapabilityError,
            DatasetNotFoundError,
            ProviderNotRegisteredError,
        ]:
            assert issubclass(cls, PublicDataError), f"{cls} should inherit PublicDataError"

    # test catch base Explains scenario validated by test.
    def test_catch_base(self) -> None:
        """
        test catch base Verify scenario.

        Returns:
            None: returns computation result or value from sub-call.

        Raises:
            can propagate exceptions from sub-dependencies as-is.

        Example:
            Verify expected behavior described by test name is maintained without regression.
        """
        with pytest.raises(PublicDataError):
            raise DatasetNotFoundError("not found", dataset_id="x.y")
