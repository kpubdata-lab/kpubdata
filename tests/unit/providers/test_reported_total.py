"""A total count of zero is a count; ``None`` is for a count the provider did not send (#806)."""

from __future__ import annotations

import pytest

from kpubdata.providers._common import reported_total


@pytest.mark.parametrize(("sent", "expected"), [(0, 0), ("0", 0), (37, 37), ("37", 37)])
def test_a_count_the_provider_sent_is_kept(sent: object, expected: int) -> None:
    assert reported_total(sent) == expected


@pytest.mark.parametrize("sent", [None, "", "many", 1.5, True, False, [], {}])
def test_anything_else_is_no_count(sent: object) -> None:
    assert reported_total(sent) is None
