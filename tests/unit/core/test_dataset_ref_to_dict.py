"""``DatasetRef.to_dict()`` is the JSON form of a dataset reference (#784).

``dataclasses.asdict`` cannot serialise a reference (``raw_metadata`` is a
``mappingproxy``), so a consumer read ``raw_metadata`` directly — a layout with no
stability promise. The key list below is the promise; ``docs/compatibility.md`` states it.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import json
from pathlib import Path
from types import MappingProxyType

import pytest

from kpubdata import Client, DatasetRef, Operation, Representation

#: The keys of ``to_dict()``, in order. Removing or renaming one is a breaking change.
KEYS = (
    "id",
    "provider",
    "dataset_key",
    "name",
    "description",
    "tags",
    "source_url",
    "representation",
    "operations",
    "status",
    "query_support",
    "license",
    "request_parameters",
    "application",
    "verified_at",
)

_DOC = Path(__file__).resolve().parents[3] / "docs" / "compatibility.md"


@pytest.fixture(scope="module")
def client() -> Client:
    return Client(provider_keys={}, env_keys=False)


def test_asdict_still_cannot_do_this(client: Client) -> None:
    """The reason the method exists."""
    with pytest.raises(TypeError):
        dataclasses.asdict(client.dataset("datago.apt_trade").ref)


def test_every_dataset_serialises_with_the_same_keys(client: Client) -> None:
    payloads = [ref.to_dict() for ref in client.datasets.list()]

    assert payloads
    assert json.loads(json.dumps(payloads)) == payloads
    assert {tuple(payload) for payload in payloads} == {KEYS}


def test_the_documented_key_list_is_the_real_one() -> None:
    text = _DOC.read_text(encoding="utf-8")
    section = text[text.index("`DatasetRef.to_dict()` 의 키") :]
    section = section[: section.index("키 추가는 호환 변경")]

    assert [key for key in KEYS if f"`{key}`" not in section] == []


def test_a_spec_dataset_carries_status_licence_parameters(client: Client) -> None:
    payload = client.dataset("datago.apt_trade").ref.to_dict()

    assert payload["id"] == "datago.apt_trade"
    assert payload["status"] == "live_verified"
    assert payload["representation"] == "api_json"
    assert payload["operations"] == ["list", "raw", "schema"]
    assert isinstance(payload["license"], dict)
    assert payload["license"]["redistribution"] == "allowed"
    assert isinstance(payload["request_parameters"], list)
    assert [param["name"] for param in payload["request_parameters"]] == ["LAWD_CD", "DEAL_YMD"]
    assert payload["request_parameters"][0]["required"] is True
    assert isinstance(payload["verified_at"], str)
    assert dt.date.fromisoformat(payload["verified_at"])


def test_a_dataset_awaiting_an_application_says_so(client: Client) -> None:
    payload = client.dataset("datago.dur_usjnt_taboo").ref.to_dict()

    assert payload["application"] == {
        "required": True,
        "url": "https://www.data.go.kr/data/15059486/openapi.do",
    }


def test_nothing_declared_is_none_not_an_empty_value() -> None:
    ref = DatasetRef(
        id="x.y",
        provider="x",
        dataset_key="y",
        name="Y",
        representation=Representation.API_JSON,
        operations=frozenset({Operation.LIST}),
        raw_metadata=MappingProxyType({"base_url": "http://internal", "fields": ("a",)}),
    )

    payload = ref.to_dict()

    assert payload["status"] is None
    assert payload["license"] is None
    assert payload["query_support"] is None
    assert payload["request_parameters"] is None
    assert payload["application"] is None
    assert payload["verified_at"] is None
    # Provider metadata outside the declared keys stays out.
    assert "http://internal" not in json.dumps(payload)
