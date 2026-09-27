"""Test module.

This file ``tests/unit/transport/test_transport_requirements.py`` defines test scenarios and helper objects.
For regression prevention and public contract validation verify core flows, exceptions, and edge conditions.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from kpubdata.transport.http import HttpTransport, TransportConfig, TransportRequirements


# Explains scenario for: test transport requirements defaults.
def test_transport_requirements_defaults() -> None:
    """
    Verify: test transport requirements defaults scenario.

    Returns:
        None: returns computation result or value from sub-call.

    Raises:
        can propagate exceptions from sub-dependencies as-is.

    Example:
        Verify expected behavior described by test name is maintained without regression.
    """
    requirements = TransportRequirements()

    assert requirements.verify_ssl is None
    assert requirements.headers is None
    assert requirements.ssl_context_factory is None


# test with requirements merges headers without mutating base config Explains scenario validated by test.
def test_with_requirements_merges_headers_without_mutating_base_config() -> None:
    """
    test with requirements merges headers without mutating base config Verify scenario.

    Returns:
        None: returns computation result or value from sub-call.

    Raises:
        can propagate exceptions from sub-dependencies as-is.

    Example:
        Verify expected behavior described by test name is maintained without regression.
    """
    config = TransportConfig(
        timeout=12.0,
        max_retries=5,
        retry_backoff_factor=0.25,
        headers={"User-Agent": "kpubdata", "Accept": "application/json"},
    )
    requirements = TransportRequirements(headers={"Accept": "application/xml", "X-Test": "1"})

    transport = HttpTransport.with_requirements(config, requirements)

    with patch("kpubdata.transport.http.httpx.Client") as client_cls:
        _ = transport.client

    client_cls.assert_called_once_with(
        timeout=12.0,
        headers={
            "User-Agent": "kpubdata",
            "Accept": "application/xml",
            "X-Test": "1",
        },
        follow_redirects=True,
        verify=True,
    )
    assert config.headers == {"User-Agent": "kpubdata", "Accept": "application/json"}


# test build client calls ssl context factory when provided Explains scenario validated by test.
def test_build_client_calls_ssl_context_factory_when_provided() -> None:
    """
    test build client calls ssl context factory when provided Verify scenario.

    Returns:
        None: returns computation result or value from sub-call.

    Raises:
        can propagate exceptions from sub-dependencies as-is.

    Example:
        Verify expected behavior described by test name is maintained without regression.
    """
    ssl_context = MagicMock(name="ssl_context")
    ssl_context_factory = MagicMock(return_value=ssl_context)
    transport = HttpTransport(
        requirements=TransportRequirements(ssl_context_factory=ssl_context_factory),
    )

    with patch("kpubdata.transport.http.httpx.Client") as client_cls:
        _ = transport.client

    ssl_context_factory.assert_called_once_with()
    client_cls.assert_called_once_with(
        timeout=30.0,
        headers={},
        follow_redirects=True,
        verify=ssl_context,
    )


# test build client passes verify false when ssl verification disabled Explains scenario validated by test.
def test_build_client_passes_verify_false_when_ssl_verification_disabled() -> None:
    """
    test build client passes verify false when ssl verification disabled Verify scenario.

    Returns:
        None: returns computation result or value from sub-call.

    Raises:
        can propagate exceptions from sub-dependencies as-is.

    Example:
        Verify expected behavior described by test name is maintained without regression.
    """
    transport = HttpTransport(requirements=TransportRequirements(verify_ssl=False))

    with patch("kpubdata.transport.http.httpx.Client") as client_cls:
        _ = transport.client

    client_cls.assert_called_once_with(
        timeout=30.0,
        headers={},
        follow_redirects=True,
        verify=False,
    )
