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
    """Only the false claim is pinned; the description may be reworded freely."""
    assert "CI read this file" not in document["description"]


def lower_bound(spec: str) -> tuple[int, ...]:
    """The ``>=`` bound of a ``>=a.b.c,<d.e`` range as the matrix writes it."""
    match = re.search(r">=\s*([\d.]+)", spec)
    assert match, f"no lower bound in {spec!r}"
    return tuple(int(part) for part in match.group(1).split("."))


def test_exactly_one_range_is_supported_and_this_version_is_not_behind_it(
    document: dict[str, Any],
) -> None:
    """The package may be ahead of the supported range, never behind it.

    The supported row is Builder's pin, and Builder pins only a released kpubdata
    (``docs/compatibility.md`` §5.1, Independence Rule 12): kpubdata goes out first, the
    pin moves after it, and this row is updated with the application release. So a
    kpubdata release pull request raises the version past the row's upper bound, and
    that is the normal order, not a mismatch. This used to require the version to be
    inside the range, which made a release pull request fail its own gate (#780): the
    row would have had to claim a pin Builder did not have yet.

    What cannot happen is the version sitting below the range Builder asks for.
    """
    supported = [row for row in document["matrix"] if row["status"] == "supported"]

    assert len(supported) == 1
    assert _version() >= lower_bound(supported[0]["kpubdata"])


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


@pytest.mark.parametrize(
    ("version", "expected"),
    [
        # The release that follows the supported range: ahead of it, allowed.
        ((0, 9, 0), True),
        ((0, 8, 0), True),
        ((0, 8, 7), True),
        # Behind what Builder asks for: never.
        ((0, 7, 9), False),
    ],
)
def test_a_version_ahead_of_the_supported_range_passes_and_one_behind_does_not(
    version: tuple[int, ...], expected: bool
) -> None:
    assert (version >= lower_bound(">=0.8.0,<0.9")) is expected
