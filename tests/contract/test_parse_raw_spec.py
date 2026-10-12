"""Recorded fixture contract for the public offline parser."""

from __future__ import annotations

import json
from pathlib import Path

from kpubdata import Client

_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures/datago/apt_trade"


def test_recorded_apt_trade_payload_is_parsed_through_public_dataset() -> None:
    raw = json.loads((_FIXTURES / "seoul_gangnam_2024_01.raw.json").read_text(encoding="utf-8"))
    expected = json.loads(
        (_FIXTURES / "seoul_gangnam_2024_01.expected.json").read_text(encoding="utf-8")
    )

    batch = Client(provider_keys={"datago": "test-key"}).dataset("datago.apt_trade").parse_raw(raw)

    assert len(batch.items) == len(expected["items"])
    assert batch.total_count == expected["total_count"]
    assert batch.items[0]["dealAmount"] == 101300
    assert batch.items[0]["bonbun"] == expected["items"][0]["bonbun"]
