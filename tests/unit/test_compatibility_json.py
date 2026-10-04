"""``compatibility.json`` is a record, and the record is kept consistent (#788).

The file said Builder and Studio CI read it to check their kpubdata range; nothing in
any of the three repositories does. It is kept as documentation, so what can be checked
is checked here: its shape, and that its supported range agrees with the version this
package declares and with the pin ``docs/compatibility.md`` states.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_STATUSES = {"supported", "ci-tested", "released"}
_ROW_KEYS = {"kpubdata", "builder", "studio", "status", "note"}


@pytest.fixture(scope="module")
def document() -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads((_ROOT / "compatibility.json").read_text("utf-8"))
    return loaded


def _version() -> tuple[int, ...]:
    text = (_ROOT / "pyproject.toml").read_text("utf-8")
    match = re.search(r'^version = "(\d+)\.(\d+)\.(\d+)"', text, re.MULTILINE)
    assert match
    return tuple(int(part) for part in match.groups())


def in_range(version: tuple[int, ...], spec: str) -> bool:
    """Whether ``version`` satisfies a ``>=a.b.c,<d.e`` range as the matrix writes it."""
    for clause in spec.split(","):
        match = re.fullmatch(r"\s*(>=|<)\s*([\d.]+)\s*", clause)
        assert match, f"unreadable range clause {clause!r}"
        bound = tuple(int(part) for part in match.group(2).split("."))
        padded = bound + (0,) * (len(version) - len(bound))
        if match.group(1) == ">=" and version < padded:
            return False
        if match.group(1) == "<" and version >= padded:
            return False
    return True


def test_the_shape_is_what_a_reader_expects(document: dict[str, Any]) -> None:
    assert document["version"] == 1
    assert document["owner"] == "kpubdata"
    assert document["matrix"]
    for row in document["matrix"]:
        assert set(row) == _ROW_KEYS, row
        assert row["status"] in _STATUSES, row
        assert all(isinstance(row[key], str) and row[key] for key in _ROW_KEYS), row


def test_it_no_longer_claims_a_ci_reads_it(document: dict[str, Any]) -> None:
    assert "CI read this file" not in document["description"]
    assert "no CI" in document["description"]


def test_exactly_one_range_is_supported_and_this_version_is_in_it(
    document: dict[str, Any],
) -> None:
    supported = [row for row in document["matrix"] if row["status"] == "supported"]

    assert len(supported) == 1
    assert in_range(_version(), supported[0]["kpubdata"])


def test_the_supported_range_is_the_pin_the_compatibility_document_states(
    document: dict[str, Any],
) -> None:
    (supported,) = [row for row in document["matrix"] if row["status"] == "supported"]
    text = (_ROOT / "docs" / "compatibility.md").read_text("utf-8")

    assert f"`{supported['kpubdata']}`" in text


@pytest.mark.parametrize(
    ("version", "spec", "expected"),
    [
        ((0, 8, 0), ">=0.8.0,<0.9", True),
        ((0, 8, 7), ">=0.8.0,<0.9", True),
        ((0, 9, 0), ">=0.8.0,<0.9", False),
        ((0, 7, 9), ">=0.8.0,<0.9", False),
    ],
)
def test_the_range_reader(version: tuple[int, ...], spec: str, expected: bool) -> None:
    assert in_range(version, spec) is expected
