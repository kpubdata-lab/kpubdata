"""How the live smoke treats a dataset still awaiting its usage application (#896).

The helper lives in the integration module because only live tests call it; these
tests pin its three outcomes without a network call.
"""

from __future__ import annotations

import pytest

from kpubdata import Client
from kpubdata.core.models import RecordBatch
from kpubdata.exceptions import AuthError
from tests.integration import test_datago_live as live


def _denied() -> RecordBatch:
    raise AuthError("data.go.kr returned 403")


def _answered() -> RecordBatch:
    refs = Client(provider_keys={}, env_keys=False).datasets.list()
    ref = next(ref for ref in refs if ref.id == "datago.mid_fcst")
    return RecordBatch(items=[{"a": 1}], dataset=ref)


def test_a_403_is_expected_while_the_metadata_awaits_approval(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(live, "_awaiting_application", lambda _dataset_id: True)
    with pytest.raises(pytest.xfail.Exception, match="usage application"):
        live._list_or_await_application("datago.mid_fcst", _denied)


def test_an_answer_while_the_metadata_awaits_approval_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(live, "_awaiting_application", lambda _dataset_id: True)
    with pytest.raises(pytest.fail.Exception, match="dataset_metadata.json"):
        live._list_or_await_application("datago.mid_fcst", _answered)


def test_a_403_for_any_other_dataset_still_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(live, "_awaiting_application", lambda _dataset_id: False)
    with pytest.raises(AuthError):
        live._list_or_await_application("datago.apt_trade", _denied)


def test_the_metadata_is_read_from_the_installed_package() -> None:
    assert live._awaiting_application("datago.mid_fcst") is True
    assert live._awaiting_application("datago.apt_trade") is False
    assert live._awaiting_application("datago.no_such_dataset") is False
