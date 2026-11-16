"""Regression coverage for provider-specific transport settings (#971)."""

from __future__ import annotations

import ssl
from dataclasses import fields

from kpubdata.transport.http import HttpTransport, TransportConfig, TransportRequirements


def test_provider_transport_preserves_every_base_config_field() -> None:
    """Provider header requirements must not reset TLS, retry or redirect policy."""
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    base = TransportConfig(
        timeout=4.0,
        max_retries=7,
        retry_backoff_factor=0.125,
        headers={"X-Base": "one"},
        verify_ssl=False,
        ssl_context=context,
        cache_ttl_seconds=73,
        max_response_bytes=1234,
        max_retry_delay=3.0,
        follow_credentialed_redirects=True,
    )
    requirements = TransportRequirements(headers={"X-Provider": "two"})

    transport = HttpTransport.with_requirements(base, requirements)

    for item in fields(TransportConfig):
        if item.name != "headers":
            assert getattr(transport._config, item.name) == getattr(base, item.name)

    assert transport._config is not base
    assert transport._config.headers == {"X-Base": "one", "X-Provider": "two"}
    assert base.headers == {"X-Base": "one"}
    assert transport._resolve_verify(requirements) is context
    assert transport.cache_ttl_seconds == 73


def test_provider_specific_headers_override_without_mutating_base() -> None:
    """Transport-specific header merges preserve unrelated configuration."""
    base = TransportConfig(
        headers={"Accept": "application/json", "X-Shared": "old"},
        max_retry_delay=1.5,
        follow_credentialed_redirects=False,
    )
    requirements = TransportRequirements(
        verify_ssl=True,
        headers={"Accept": "application/xml", "X-Extra": "new"},
    )
    transport = HttpTransport.with_requirements(base, requirements)

    assert transport._config.headers == {
        "Accept": "application/xml",
        "X-Shared": "old",
        "X-Extra": "new",
    }
    assert base.headers == {"Accept": "application/json", "X-Shared": "old"}
    assert transport._config.max_retry_delay == 1.5
    assert transport._config.follow_credentialed_redirects is False
