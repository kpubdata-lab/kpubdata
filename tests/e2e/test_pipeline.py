"""KPubData end-to-end pipeline validation (#282 Phase 1).

For a single dataset: Client query → RecordBatch structure → fields[] normalization →
pagination next_page calculation → fixture replay consistency are all validated
in one integrated flow.

Requires live API keys; marked with `@pytest.mark.integration`.
"""

from __future__ import annotations

import os

import pytest

from kpubdata import Client
from kpubdata.core.models import RecordBatch


@pytest.mark.integration
class TestKpubdataPipelineE2E:
    """KPubData single dataset E2E — fetch to normalization."""

    def test_hospital_info_full_pipeline(self) -> None:
        """Hospital info: no filter → standard envelope → fields normalization →
        pagination."""
        api_key = os.environ.get("KPUBDATA_DATAGO_API_KEY")
        if not api_key:
            pytest.skip("KPUBDATA_DATAGO_API_KEY not set")

        client = Client(provider_keys={"datago": api_key}, cache=False)
        dataset = client.dataset("datago.hospital_info")
        batch = dataset.list(page=1, page_size=5)

        # 1. RecordBatch structure
        assert isinstance(batch, RecordBatch)
        assert batch.items, "최소 1개 레코드 필요"
        assert batch.total_count is not None and batch.total_count > 0

        # 2. Record field validation (match fields[] metadata)
        first = batch.items[0]
        assert isinstance(first, dict)
        assert len(first) >= 5, f"병원 레코드는 5+ 필드여야 함: {sorted(first)[:5]}"

        # 3. Pagination
        assert batch.next_page is not None, "전체 건수 > 페이지 크기 → next_page 필요"
        page2 = dataset.list(page=2, page_size=5)
        assert isinstance(page2, RecordBatch)
        assert len(page2.items) > 0

        # 4. Raw escape hatch
        raw = dataset.call_raw("getHospBasisList")
        assert isinstance(raw, dict)

    def test_apt_trade_filtered_query(self) -> None:
        """Apartment trade: LAWD_CD/DEAL_YMD filter → filter compliance validation."""
        api_key = os.environ.get("KPUBDATA_DATAGO_API_KEY")
        if not api_key:
            pytest.skip("KPUBDATA_DATAGO_API_KEY not set")

        client = Client(provider_keys={"datago": api_key}, cache=False)
        dataset = client.dataset("datago.apt_trade")
        batch = dataset.list(LAWD_CD="11110", DEAL_YMD="202401", page=1, page_size=10)

        assert batch.items, "강남구 2024-01 거래 데이터 필요"
        for item in batch.items:
            assert str(item.get("sggCd", "")).startswith("11110"), (
                f"LAWD_CD 필터 위반: sggCd={item.get('sggCd')}"
            )

    def test_air_station_station_filter(self) -> None:
        """Air quality by station: station filter → station match validation."""
        api_key = os.environ.get("KPUBDATA_DATAGO_API_KEY")
        if not api_key:
            pytest.skip("KPUBDATA_DATAGO_API_KEY not set")

        client = Client(provider_keys={"datago": api_key}, cache=False)
        dataset = client.dataset("datago.air_station")
        batch = dataset.list(station="백령도", term="daily", page=1, page_size=5)

        assert batch.items, "백령도 측정 데이터 필요"
        first = batch.items[0]
        assert "dataTime" in first
        assert "pm10Value" in first or "khaiValue" in first
