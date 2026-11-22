"""Client and catalog refuse bad options and argument types with canonical errors.

Public discovery methods used to leak AttributeError/TypeError for an argument of
the wrong type, ``Client(...)`` accepted invalid options and failed at the first
call (``env_keys="no"`` was truthy and turned the environment fallback on), and
``probe``/``probe_all`` matched provider names case-sensitively while the rest of
the client lowercases them.
"""

from __future__ import annotations

from typing import cast

import pytest

from kpubdata.client import Client
from kpubdata.exceptions import (
    ConfigError,
    DatasetNotFoundError,
    InvalidRequestError,
    ProviderNotRegisteredError,
)
from kpubdata.transport.cache import ResponseCache


@pytest.fixture
def client() -> Client:
    return Client(provider_keys={}, env_keys=False)


def test_dataset_with_non_str_id_is_dataset_not_found(client: Client) -> None:
    with pytest.raises(DatasetNotFoundError):
        _ = client.dataset(cast(str, None))
    with pytest.raises(DatasetNotFoundError):
        _ = client.dataset(cast(str, 42))


def test_search_with_non_str_text_is_invalid_request(client: Client) -> None:
    with pytest.raises(InvalidRequestError):
        _ = client.datasets.search(cast(str, None))


@pytest.mark.parametrize("threshold", ["a", None, True, float("nan")])
def test_search_with_bad_threshold_is_invalid_request(client: Client, threshold: object) -> None:
    with pytest.raises(InvalidRequestError):
        _ = client.datasets.search("x", threshold=cast(float, threshold))


def test_search_still_accepts_an_int_threshold(client: Client) -> None:
    assert client.datasets.search("apt_trade", threshold=1)


def test_list_with_non_str_provider_is_invalid_request(client: Client) -> None:
    with pytest.raises(InvalidRequestError):
        _ = client.datasets.list(provider=cast(str, 1))
    with pytest.raises(InvalidRequestError):
        _ = client.datasets.search("x", provider=cast(str, 1))


def test_probe_with_non_str_id_is_invalid_request(client: Client) -> None:
    with pytest.raises(InvalidRequestError):
        _ = client.probe(cast(str, None))


def test_probe_all_with_non_str_provider_is_invalid_request(client: Client) -> None:
    with pytest.raises(InvalidRequestError):
        _ = client.probe_all(provider=cast(str, 1))


@pytest.mark.parametrize(
    ("option", "value"),
    [
        ("env_keys", "no"),
        ("env_keys", "false"),
        ("env_keys", 0),
        ("env_keys", None),
        ("cache", "yes"),
        ("cache", 1),
        ("cache", None),
        ("max_retries", "3"),
        ("max_retries", True),
        ("max_retries", -1),
        ("max_retries", 1.5),
        ("timeout", "30"),
        ("timeout", True),
        ("timeout", 0),
        ("timeout", -1.0),
        ("timeout", float("inf")),
        ("timeout", float("nan")),
        ("cache_ttl_seconds", "60"),
        ("cache_ttl_seconds", False),
        ("cache_ttl_seconds", -1),
        ("cache_ttl_seconds", 1.5),
        ("provider_keys", "datago=key"),
        ("provider_keys", {"datago": 123}),
        ("provider_keys", {1: "key"}),
    ],
)
def test_client_refuses_invalid_option_at_construction(option: str, value: object) -> None:
    kwargs: dict[str, object] = {option: value}
    with pytest.raises(ConfigError, match=option):
        _ = Client(**kwargs)


def test_env_keys_string_does_not_turn_on_environment_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("KPUBDATA_DATAGO_API_KEY", "operator-key")
    with pytest.raises(ConfigError):
        _ = Client(provider_keys={}, env_keys=cast(bool, "no"))


def test_client_still_accepts_genuine_option_values(tmp_path: object) -> None:
    from pathlib import Path

    cache = ResponseCache(base_dir=cast(Path, tmp_path))
    client = Client(
        provider_keys={"datago": "key"},
        timeout=5,
        max_retries=0,
        cache=cache,
        cache_ttl_seconds=0,
        env_keys=False,
    )
    client.close()
    Client(cache=True, timeout=1.5).close()


def test_probe_matches_the_provider_case_insensitively(client: Client) -> None:
    lower = client.probe("datago.apt_trade")
    upper = client.probe("DATAGO.apt_trade")
    assert lower is not None
    assert upper is not None
    assert upper.dataset_id == lower.dataset_id == "datago.apt_trade"
    assert upper.status == "auth_unknown"


def test_probe_all_matches_the_provider_case_insensitively(client: Client) -> None:
    lower = client.probe_all(provider="datago")
    mixed = client.probe_all(provider="DataGo")
    assert lower
    assert [r.dataset_id for r in mixed] == [r.dataset_id for r in lower]


def test_probe_all_with_unknown_provider_raises_like_list(client: Client) -> None:
    with pytest.raises(ProviderNotRegisteredError):
        _ = client.datasets.list(provider="nope")
    with pytest.raises(ProviderNotRegisteredError):
        _ = client.probe_all(provider="nope")


def test_probe_with_unknown_id_still_returns_none(client: Client) -> None:
    assert client.probe("nope.nothing") is None
    assert client.probe("datago.no_such_dataset") is None
