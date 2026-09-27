"""Test module.

This file defines test scenarios and helper objects at
``tests/unit/providers/sgis/test_auth.py``.
It verifies core flows, exceptions, and edge cases for regression
prevention and public contract validation.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest

from kpubdata.config import KPubDataConfig
from kpubdata.exceptions import AuthError, ConfigError
from kpubdata.providers.sgis.auth import SgisAuthClient
from kpubdata.transport.http import HttpTransport


def _fixture_path(name: str) -> Path:
    """
    Internal helper to process fixture path.

    Args:
        name (str): Input value provided by caller.

    Returns:
        Path: Computed result or return value from downstream calls.

    Raises:
        Exceptions from implementation or downstream dependencies may be
        raised as-is.
    """
    return Path(__file__).resolve().parents[3] / "fixtures" / "sgis" / name


def _load_fixture(name: str) -> dict[str, object]:
    """
    Internal helper to process load fixture.

    Args:
        name (str): Input value provided by caller.

    Returns:
        dict[str, object]: Computed result or return value from downstream
        calls.

    Raises:
        Exceptions from implementation or downstream dependencies may be
        raised as-is.
    """
    payload = cast(object, json.loads(_fixture_path(name).read_text(encoding="utf-8")))
    if isinstance(payload, dict):
        return cast(dict[str, object], payload)
    raise ValueError(f"Fixture must be object: {name}")


class _FakeResponse:
    """
    Class that encapsulates _FakeResponse role and state.

    This class manages _FakeResponse state and behavior together at
    ``tests/unit/providers/sgis/test_auth.py``. Main method: __init__.

    Attributes:
        Properties defined in constructor and class body are shared as
        common context by downstream methods.
    """

    def __init__(self, payload: dict[str, object]) -> None:
        """
        Initialize internal state for instance.

        Args:
            payload (dict[str, object]): Input value provided by caller.

        Returns:
            None: Computed result or return value from downstream calls.

        Raises:
            Exceptions from implementation or downstream dependencies may be
            raised as-is.
        """
        self.headers: dict[str, str] = {"content-type": "application/json"}
        self.text: str = json.dumps(payload, ensure_ascii=False)
        self.content: bytes = self.text.encode("utf-8")


class _FakeTransport:
    """
    Class that encapsulates _FakeTransport role and state.

    This class manages _FakeTransport state and behavior together at
    ``tests/unit/providers/sgis/test_auth.py``. Main methods: __init__, request.

    Attributes:
        Properties defined in constructor and class body are shared as
        common context by downstream methods.
    """

    def __init__(self, responses: list[_FakeResponse]) -> None:
        """Initialize the fake transport with queued responses.

        Args:
            responses: Responses served in order, one per call.
        """
        self._responses: list[_FakeResponse] = list(responses)
        self.calls: list[dict[str, object]] = []

    def request(self, method: str, url: str, **kwargs: object) -> _FakeResponse:
        """
        Perform request operation.

        Args:
            method (str): Input value provided by caller.
            url (str): Input value provided by caller.
            **kwargs (object): Input value provided by caller.

        Returns:
            _FakeResponse: Computed result or return value from downstream
            calls.

        Raises:
            Exceptions from implementation or downstream dependencies may be
            raised as-is.
        """
        self.calls.append({"method": method, "url": url, **kwargs})
        if not self._responses:
            raise AssertionError("No fixture responses remaining")
        return self._responses.pop(0)


def _build_auth_client(
    responses: list[_FakeResponse],
    *,
    provider_key: str,
) -> tuple[SgisAuthClient, _FakeTransport]:
    """"""
    transport = _FakeTransport(responses)
    config = KPubDataConfig(provider_keys={"sgis": provider_key})
    return (
        SgisAuthClient(
            config=config,
            transport=cast(HttpTransport, cast(object, transport)),
        ),
        transport,
    )


# Verifies scenario tested by test_get_access_token_uses_consumer_secret_env.
def test_get_access_token_uses_consumer_secret_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """"""
    monkeypatch.setenv("KPUBDATA_SGIS_CONSUMER_SECRET", "env-secret")
    auth_client, transport = _build_auth_client(
        [_FakeResponse(_load_fixture("auth_success.json"))],
        provider_key="consumer-key-only",
    )

    token = auth_client.get_access_token()

    assert token == "test-access-token-1"
    request_params = cast(dict[str, str], transport.calls[0]["params"])
    assert request_params["consumer_key"] == "consumer-key-only"
    assert request_params["consumer_secret"] == "env-secret"


# Verifies scenario tested by test_get_access_token_uses_key_and_secret_from_provider_key.
def test_get_access_token_uses_key_and_secret_from_provider_key() -> None:
    """"""
    auth_client, transport = _build_auth_client(
        [_FakeResponse(_load_fixture("auth_success.json"))],
        provider_key="consumer-key:consumer-secret",
    )

    token = auth_client.get_access_token()

    assert token == "test-access-token-1"
    request_params = cast(dict[str, str], transport.calls[0]["params"])
    assert request_params["consumer_key"] == "consumer-key"
    assert request_params["consumer_secret"] == "consumer-secret"


# Verifies scenario tested by test_get_access_token_raises_on_auth_error.
def test_get_access_token_raises_on_auth_error() -> None:
    """"""
    auth_client, _ = _build_auth_client(
        [_FakeResponse(_load_fixture("error_invalid_token.json"))],
        provider_key="consumer-key:consumer-secret",
    )

    with pytest.raises(AuthError):
        _ = auth_client.get_access_token()


# Verifies scenario tested by test_get_access_token_caches_until_invalidate.
def test_get_access_token_caches_until_invalidate() -> None:
    """"""
    auth_client, transport = _build_auth_client(
        [_FakeResponse(_load_fixture("auth_success.json"))],
        provider_key="consumer-key:consumer-secret",
    )

    first = auth_client.get_access_token()
    second = auth_client.get_access_token()

    assert first == second
    assert len(transport.calls) == 1


# Verifies scenario tested by test_get_access_token_refreshes_after_invalidate.
def test_get_access_token_refreshes_after_invalidate() -> None:
    """"""
    auth_success = _load_fixture("auth_success.json")
    auth_success_2 = dict(auth_success)
    auth_success_2["result"] = {
        "accessToken": "test-access-token-2",
        "accessTimeout": "4102444800",
    }

    auth_client, transport = _build_auth_client(
        [_FakeResponse(auth_success), _FakeResponse(auth_success_2)],
        provider_key="consumer-key:consumer-secret",
    )

    first = auth_client.get_access_token()
    auth_client.invalidate()
    second = auth_client.get_access_token()

    assert first == "test-access-token-1"
    assert second == "test-access-token-2"
    assert len(transport.calls) == 2


# Verifies scenario tested by test_get_access_token_requires_secret_when_env_missing.
def test_get_access_token_requires_secret_when_env_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """The token exchange must fail clearly when the consumer secret is absent from env."""
    monkeypatch.delenv("KPUBDATA_SGIS_CONSUMER_SECRET", raising=False)
    auth_client, _ = _build_auth_client(
        [_FakeResponse(_load_fixture("auth_success.json"))],
        provider_key="consumer-key-only",
    )

    with pytest.raises(ConfigError):
        _ = auth_client.get_access_token()
