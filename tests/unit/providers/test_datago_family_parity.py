"""Pin the fact that localdata and semas genuinely share one contract (#470 regression guard).

The two adapters were two 375-line copies. A name-normalized comparison
showed zero lines of difference — and that exact state is what created
#470: the branch treating data.go.kr ``"03"`` (NODATA) as success existed
only in semas, so a common no-result query raised an exception in
localdata alone. Nowhere in the code said "fix one and you must fix the
other".

They now inherit one shared base. This test locks that fact in as a
contract.
"""

from __future__ import annotations

from typing import Any

import pytest

from kpubdata.providers._datago_family import DataGoFamilyAdapter
from kpubdata.providers.localdata.adapter import LocaldataAdapter
from kpubdata.providers.semas.adapter import SemasAdapter

_ADAPTERS = (LocaldataAdapter, SemasAdapter)


def _envelope(result_code: str, items: object = None) -> dict[str, object]:
    body: dict[str, object] = {} if items is None else {"items": items}
    return {"response": {"header": {"resultCode": result_code, "resultMsg": "m"}, "body": body}}


class TestBothShareTheImplementation:
    @pytest.mark.parametrize("adapter_cls", _ADAPTERS)
    def test_it_is_the_shared_base(self, adapter_cls: type[Any]) -> None:
        assert issubclass(adapter_cls, DataGoFamilyAdapter)

    @pytest.mark.parametrize("adapter_cls", _ADAPTERS)
    def test_it_declares_its_own_identity(self, adapter_cls: type[Any]) -> None:
        adapter = adapter_cls()

        assert adapter.name == adapter_cls.provider_name
        assert adapter.list_datasets(), "카탈로그가 비면 안 된다"
        assert all(d.id.startswith(f"{adapter.name}.") for d in adapter.list_datasets())


class TestTheEnvelopeRulesMatch:
    """The heart of #470 — both providers must react identically to the same resultCode."""

    @pytest.mark.parametrize("adapter_cls", _ADAPTERS)
    def test_nodata_is_a_success(self, adapter_cls: type[Any]) -> None:
        """``03`` means "no data matches the filter" — not a failed call."""
        _body, items = adapter_cls()._validate_envelope(_envelope("03", [{"x": 1}]), "x")

        assert items == []

    @pytest.mark.parametrize("adapter_cls", _ADAPTERS)
    def test_success_returns_items(self, adapter_cls: type[Any]) -> None:
        _body, items = adapter_cls()._validate_envelope(_envelope("00", [{"x": 1}]), "x")

        assert items == [{"x": 1}]

    @pytest.mark.parametrize("adapter_cls", _ADAPTERS)
    @pytest.mark.parametrize(
        ("code", "exception_name"),
        [("30", "AuthError"), ("22", "RateLimitError")],
    )
    def test_real_errors_still_raise(
        self, adapter_cls: type[Any], code: str, exception_name: str
    ) -> None:
        with pytest.raises(Exception) as excinfo:  # noqa: B017 - compares type names only
            _ = adapter_cls()._validate_envelope(_envelope(code), "x")

        assert type(excinfo.value).__name__ == exception_name


class TestItemNormalisationMatches:
    """The spot where #482 fixed only one side and grew a ghost row (reverted in #483)."""

    @pytest.mark.parametrize("adapter_cls", _ADAPTERS)
    @pytest.mark.parametrize(
        ("wrapper", "expected"),
        [
            ({"item": [{"a": 1}, {"a": 2}]}, [{"a": 1}, {"a": 2}]),
            ({"item": {"a": 1}}, [{"a": 1}]),
            ({"item": None}, []),
            ({}, []),
            ({"a": 1}, [{"a": 1}]),
        ],
    )
    def test_shapes_normalise_identically(
        self, adapter_cls: type[Any], wrapper: object, expected: list[dict[str, object]]
    ) -> None:
        assert adapter_cls()._normalize_items(wrapper) == expected


class TestLoggingStaysPerProvider:
    """A shared implementation must still log under each provider's own logger.

    Operators filter by ``kpubdata.provider.localdata``. Sharing one logger
    while extracting the base silently empties that filter.
    """

    @pytest.mark.parametrize("adapter_cls", _ADAPTERS)
    def test_the_logger_is_named_after_the_provider(self, adapter_cls: type[Any]) -> None:
        adapter = adapter_cls()

        assert adapter._logger.name == f"kpubdata.provider.{adapter_cls.provider_name}"

    @pytest.mark.parametrize("adapter_cls", _ADAPTERS)
    def test_messages_name_the_provider(
        self, adapter_cls: type[Any], caplog: pytest.LogCaptureFixture
    ) -> None:
        import logging

        adapter = adapter_cls()
        caplog.set_level(logging.DEBUG, logger=f"kpubdata.provider.{adapter_cls.provider_name}")

        with pytest.raises(Exception):  # noqa: B017 - only checks logging
            _ = adapter.get_dataset("does-not-exist")

        expected = f"{adapter_cls.provider_name.capitalize()} dataset not found"
        assert any(record.getMessage() == expected for record in caplog.records)
