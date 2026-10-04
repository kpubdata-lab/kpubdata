"""data.go.kr's NODATA_ERROR (resultCode 03) is an empty result on every path (#787).

"No record matched" came back as an empty batch from localdata and semas (#470) and as
``ProviderResponseError`` from the datago envelope parser and from the spec executor,
so the same answer was a result or an exception depending on how the dataset was
declared. One test per path, each on a 03 response.
"""

from __future__ import annotations

import json
import pathlib

import pytest

from kpubdata.core.executor import (
    SpecExecutor,
    build_spec_dataset_ref,
    check_payload_error,
    extract_items,
)
from kpubdata.core.models import DatasetRef, Query
from kpubdata.core.representation import Representation
from kpubdata.core.spec import SpecDefinition, load_spec_file
from kpubdata.exceptions import ProviderResponseError
from kpubdata.providers.datago.envelope import DataGoEnvelopeParser
from kpubdata.providers.localdata.adapter import LocaldataAdapter
from kpubdata.providers.semas.adapter import SemasAdapter
from tests.unit.core.test_executor import FakeResponse, FakeTransport, _make_executor

_SPECS = pathlib.Path(__file__).resolve().parents[2] / "src" / "kpubdata" / "specs"

_HEADER = {"resultCode": "03", "resultMsg": "NODATA_ERROR"}
#: The standard envelope a filter with no match gets back.
_STANDARD = {"response": {"header": _HEADER, "body": {"totalCount": 0}}}


def _datago_ref(envelope_style: str | None) -> DatasetRef:
    metadata = {} if envelope_style is None else {"envelope_style": envelope_style}
    return DatasetRef(
        id="datago.sample",
        provider="datago",
        dataset_key="sample",
        name="sample",
        representation=Representation.API_JSON,
        operations=frozenset(),
        raw_metadata=metadata,
    )


@pytest.fixture()
def spec() -> SpecDefinition:
    return load_spec_file(_SPECS / "datago" / "apt_trade.yaml")


class TestTheDatagoEnvelopeParser:
    """Path 2 of #787: ``providers/datago/envelope.py``."""

    def test_standard_envelope(self) -> None:
        body, items = DataGoEnvelopeParser().parse(dict(_STANDARD), _datago_ref(None))

        assert items == []
        assert body == {"totalCount": 0}

    def test_gyeonggi_msg_envelope(self) -> None:
        payload: dict[str, object] = {
            "response": {
                "msgHeader": {"resultCode": 3, "resultMessage": "NODATA_ERROR"},
                "msgBody": {},
            }
        }

        _body, items = DataGoEnvelopeParser().parse(payload, _datago_ref("gyeonggi_msg"))

        assert items == []

    def test_its_flat_envelope(self) -> None:
        payload: dict[str, object] = {"resultCode": 3, "resultMsg": "NODATA_ERROR"}

        _body, items = DataGoEnvelopeParser().parse(payload, _datago_ref("its_flat"))

        assert items == []

    def test_another_code_still_raises(self) -> None:
        payload = {"response": {"header": {"resultCode": "04", "resultMsg": "HTTP_ERROR"}}}

        with pytest.raises(ProviderResponseError) as excinfo:
            DataGoEnvelopeParser().parse(payload, _datago_ref(None))

        assert excinfo.value.provider_code == "04"


class TestTheSpecPath:
    """Path 3 of #787: ``check_payload_error``, which queries and ``make verify`` share."""

    def test_the_check_passes_and_no_items_come_out(self, spec: SpecDefinition) -> None:
        check_payload_error(spec, dict(_STANDARD))

        assert extract_items(spec, dict(_STANDARD)) == []

    def test_a_query_returns_an_empty_batch(self, spec: SpecDefinition) -> None:
        transport = FakeTransport([FakeResponse(json.dumps(_STANDARD).encode("utf-8"))])
        executor: SpecExecutor = _make_executor(transport)

        batch = executor.query(spec, build_spec_dataset_ref(spec), Query(page=1, page_size=10))

        assert batch.items == []
        assert batch.total_count == 0
        assert batch.next_page is None

    def test_another_code_still_raises(self, spec: SpecDefinition) -> None:
        payload = {"response": {"header": {"resultCode": "04", "resultMsg": "HTTP_ERROR"}}}

        with pytest.raises(ProviderResponseError) as excinfo:
            check_payload_error(spec, payload)

        assert excinfo.value.provider_code == "04"


class TestTheDatagoFamilyAdapters:
    """Path 1 of #787: localdata and semas, where #470 put the rule first."""

    @pytest.mark.parametrize("adapter_cls", [LocaldataAdapter, SemasAdapter])
    def test_nodata_is_empty(self, adapter_cls: type[LocaldataAdapter | SemasAdapter]) -> None:
        _body, items = adapter_cls()._validate_envelope(dict(_STANDARD), "sample")

        assert items == []
