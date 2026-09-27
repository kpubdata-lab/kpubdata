"""Test module.

This module defines tests and helpers for the surrounding test suite.
"""

from __future__ import annotations

import json
import logging
from typing import cast

import pytest

from kpubdata.config import KPubDataConfig
from kpubdata.exceptions import ConfigError, InvalidRequestError
from kpubdata.providers.datago.adapter import DataGoAdapter
from kpubdata.transport.http import HttpTransport


class FakeResponse:
    """Tests for FakeResponse.

    This class groups related test cases and helpers for FakeResponse.
    """

    def __init__(self, payload: object, content_type: str = "application/json") -> None:
        """
        Initialize with payload.

        Args:
            payload (object): Input parameter.
            content_type (str): Input parameter.

        Returns:
            None: Result.

        Raises:
            Exceptions propagated."""
        self.headers: dict[str, str] = {"content-type": content_type}
        self.text: str = json.dumps(payload)
        self.content: bytes = self.text.encode()


class FakeTransport:
    """Tests for FakeTransport.

    This class groups related test cases and helpers for FakeTransport.
    """

    def __init__(self, responses: list[FakeResponse]) -> None:
        """
        Initialize with payload.

        Args:
            responses (list[FakeResponse]): Input parameter.

        Returns:
            None: Result.

        Raises:
            Exceptions propagated."""
        self._responses: list[FakeResponse] = list(responses)
        self.calls: list[dict[str, object]] = []

    def request(self, method: str, url: str, **kwargs: object) -> FakeResponse:
        """
        Execute a mock HTTP request.

        Args:
            method (str): Input parameter.
            url (str): Input parameter.
            **kwargs (object): Input parameter.

        Returns:
            FakeResponse: Result.

        Raises:
            Exceptions propagated."""
        self.calls.append({"method": method, "url": url, **kwargs})
        return self._responses.pop(0)


def _success_envelope() -> dict[str, object]:
    """_success_envelope

    Validates the scenario described by the test name.
    """
    return {
        "response": {
            "header": {"resultCode": "00", "resultMsg": "OK"},
            "body": {"items": {"item": [{"x": "1"}]}, "totalCount": 1},
        }
    }


def _build_adapter(responses: list[FakeResponse]) -> tuple[DataGoAdapter, FakeTransport]:
    """_build_adapter

    Validates the scenario described by the test name.
    """
    transport = FakeTransport(responses)
    config = KPubDataConfig(provider_keys={"datago": "test-key"})
    adapter = DataGoAdapter(
        config=config,
        transport=cast(HttpTransport, cast(object, transport)),
    )
    return adapter, transport


class TestDataGoGenericDataset:
    """Tests for TestDataGoGenericDataset.

    This class groups related test cases and helpers for TestDataGoGenericDataset.
    """

    # test generic dataset in catalogue Describes the scenario verified by the test.
    def test_generic_dataset_in_catalogue(self) -> None:
        """
        test generic dataset in catalogue Validates the scenario described by the test name.

        Returns:
            None: Result.

        Raises:
            Exceptions propagated."""
        adapter = DataGoAdapter()

        dataset = adapter.get_dataset("generic")

        assert dataset.id == "datago.generic"
        assert dataset.dataset_key == "generic"
        assert dataset.raw_metadata.get("generic") is True

    # test call raw with base url builds url Describes the scenario verified by the test.
    def test_call_raw_with_base_url_builds_url(self) -> None:
        """
        test call raw with base url builds url Validates the scenario described by the test name.

        Returns:
            None: Result.

        Raises:
            Exceptions propagated."""
        adapter, transport = _build_adapter([FakeResponse(_success_envelope())])
        dataset = adapter.get_dataset("generic")

        adapter.call_raw(
            dataset,
            "getVilageFcst",
            {
                "_base_url": "http://apis.data.go.kr/1360000/VilageFcstInfoService_2.0",
                "base_date": "20250401",
                "nx": "55",
            },
        )

        call = transport.calls[0]
        assert (
            call["url"] == "http://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getVilageFcst"
        )
        params = cast(dict[str, str], call["params"])
        assert params["serviceKey"] == "test-key"
        assert params["base_date"] == "20250401"
        assert params["nx"] == "55"
        assert "_base_url" not in params

    # test call raw strips trailing slash from base url Describes the scenario verified by the test.
    def test_call_raw_strips_trailing_slash_from_base_url(self) -> None:
        """
        test call raw strips trailing slash from base url Validates the scenario described by the test name.

        Returns:
            None: Result.

        Raises:
            Exceptions propagated."""
        adapter, transport = _build_adapter([FakeResponse(_success_envelope())])
        dataset = adapter.get_dataset("generic")

        adapter.call_raw(
            dataset,
            "getX",
            {"_base_url": "http://apis.data.go.kr/foo/bar/"},
        )

        assert transport.calls[0]["url"] == "http://apis.data.go.kr/foo/bar/getX"

    # test call raw missing base url raises Describes the scenario verified by the test.
    def test_call_raw_missing_base_url_raises(self) -> None:
        """
        test call raw missing base url raises Validates the scenario described by the test name.

        Returns:
            None: Result.

        Raises:
            Exceptions propagated."""
        adapter, _ = _build_adapter([])
        dataset = adapter.get_dataset("generic")

        with pytest.raises(InvalidRequestError, match="_base_url"):
            adapter.call_raw(dataset, "getX", {})

    # test call raw missing base url logs debug Describes the scenario verified by the test.
    def test_call_raw_missing_base_url_logs_debug(self, caplog: pytest.LogCaptureFixture) -> None:
        """
        test call raw missing base url logs debug Validates the scenario described by the test name.

        Args:
            caplog (pytest.LogCaptureFixture): Input parameter.

        Returns:
            None: Result.

        Raises:
            Exceptions propagated."""
        adapter, _ = _build_adapter([])
        dataset = adapter.get_dataset("generic")

        caplog.set_level(logging.DEBUG, logger="kpubdata.provider.datago")
        with pytest.raises(InvalidRequestError, match="_base_url"):
            adapter.call_raw(dataset, "getX", {})

        record = next(
            record
            for record in caplog.records
            if record.getMessage() == "Datago.generic missing _base_url in call_raw params"
        )
        assert record.__dict__["dataset_id"] == dataset.id

    # test call raw envelope skip allows non standard payload Describes the scenario verified by the test.
    def test_call_raw_envelope_skip_allows_non_standard_payload(self) -> None:
        """
        test call raw envelope skip allows non standard payload Validates the scenario described by the test name.

        Returns:
            None: Result.

        Raises:
            Exceptions propagated."""
        non_standard = {"items": [{"a": 1}]}
        adapter, _ = _build_adapter([FakeResponse(non_standard)])
        dataset = adapter.get_dataset("generic")

        result = adapter.call_raw(
            dataset,
            "getX",
            {
                "_base_url": "http://apis.data.go.kr/foo/bar",
                "_envelope": False,
            },
        )

        assert result == non_standard

    # test call raw with service key param override Describes the scenario verified by the test.
    def test_call_raw_with_service_key_param_override(self) -> None:
        """
        test call raw with service key param override Validates the scenario described by the test name.

        Returns:
            None: Result.

        Raises:
            Exceptions propagated."""
        adapter, transport = _build_adapter([FakeResponse(_success_envelope())])
        dataset = adapter.get_dataset("generic")

        adapter.call_raw(
            dataset,
            "getX",
            {
                "_base_url": "http://apis.data.go.kr/foo/bar",
                "_service_key_param": "ServiceKey",
            },
        )

        params = cast(dict[str, str], transport.calls[0]["params"])
        assert params["ServiceKey"] == "test-key"
        assert "serviceKey" not in params

    # test call raw requires api key Describes the scenario verified by the test.
    def test_call_raw_requires_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """
        test call raw requires api key Validates the scenario described by the test name.

        Args:
            monkeypatch (pytest.MonkeyPatch): Input parameter.

        Returns:
            None: Result.

        Raises:
            Exceptions propagated."""
        monkeypatch.delenv("KPUBDATA_DATAGO_API_KEY", raising=False)
        transport = FakeTransport([])
        adapter = DataGoAdapter(
            config=KPubDataConfig(),
            transport=cast(HttpTransport, cast(object, transport)),
        )
        dataset = adapter.get_dataset("generic")

        with pytest.raises(ConfigError):
            adapter.call_raw(
                dataset,
                "getX",
                {"_base_url": "http://apis.data.go.kr/foo/bar"},
            )

    # test list on generic raises Describes the scenario verified by the test.
    def test_list_on_generic_raises(self) -> None:
        """
        test list on generic raises Validates the scenario described by the test name.

        Returns:
            None: Result.

        Raises:
            Exceptions propagated."""
        from kpubdata.core.models import Query

        adapter, _ = _build_adapter([])
        dataset = adapter.get_dataset("generic")

        with pytest.raises(InvalidRequestError, match="generic"):
            adapter.query_records(dataset, Query())

    # test envelope must be bool Describes the scenario verified by the test.
    def test_envelope_must_be_bool(self) -> None:
        """
        test envelope must be bool Validates the scenario described by the test name.

        Returns:
            None: Result.

        Raises:
            Exceptions propagated."""
        adapter, _ = _build_adapter([FakeResponse(_success_envelope())])
        dataset = adapter.get_dataset("generic")

        with pytest.raises(InvalidRequestError, match="_envelope"):
            adapter.call_raw(
                dataset,
                "getX",
                {
                    "_base_url": "http://apis.data.go.kr/foo/bar",
                    "_envelope": "false",
                },
            )

    # test envelope rejects int Describes the scenario verified by the test.
    def test_envelope_rejects_int(self) -> None:
        """
        test envelope rejects int Validates the scenario described by the test name.

        Returns:
            None: Result.

        Raises:
            Exceptions propagated."""
        adapter, _ = _build_adapter([FakeResponse(_success_envelope())])
        dataset = adapter.get_dataset("generic")

        with pytest.raises(InvalidRequestError, match="_envelope"):
            adapter.call_raw(
                dataset,
                "getX",
                {
                    "_base_url": "http://apis.data.go.kr/foo/bar",
                    "_envelope": 0,
                },
            )

    # test non data go kr host logs warning Describes the scenario verified by the test.
    def test_non_allowlisted_host_is_blocked(self, caplog: pytest.LogCaptureFixture) -> None:
        """non-whitelisted hosts not called InvalidRequestErrorblocked with(#261)."""
        import logging

        from kpubdata.exceptions import InvalidRequestError

        adapter, _ = _build_adapter([FakeResponse(_success_envelope())])
        dataset = adapter.get_dataset("generic")

        with (
            caplog.at_level(logging.WARNING, logger="kpubdata.provider.datago"),
            pytest.raises(InvalidRequestError, match="data.go.kr hosts"),
        ):
            adapter.call_raw(
                dataset,
                "getX",
                {"_base_url": "http://example.com/foo"},
            )

        # URL raw not in logs(hostonly) — serviceKey query leakage prevention(#260).
        assert any("blocked non-allowlisted host" in record.message for record in caplog.records)
        for record in caplog.records:
            assert "http://example.com/foo" not in record.getMessage()

    def test_extra_hosts_env_extends_allowlist(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """KPUBDATA_DATAGO_EXTRA_HOSTShosts expanded via allow(#261)."""
        adapter, transport = _build_adapter([FakeResponse(_success_envelope())])
        dataset = adapter.get_dataset("generic")
        monkeypatch.setenv("KPUBDATA_DATAGO_EXTRA_HOSTS", "proxy.internal.example")

        adapter.call_raw(dataset, "getX", {"_base_url": "http://proxy.internal.example/api"})

        assert transport.calls[0]["url"].startswith("http://proxy.internal.example/api/")

    # test data go kr host no warning Describes the scenario verified by the test.
    def test_data_go_kr_host_no_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        """
        test data go kr host no warning Validates the scenario described by the test name.

        Args:
            caplog (pytest.LogCaptureFixture): Input parameter.

        Returns:
            None: Result.

        Raises:
            Exceptions propagated."""
        import logging

        adapter, _ = _build_adapter([FakeResponse(_success_envelope())])
        dataset = adapter.get_dataset("generic")

        with caplog.at_level(logging.WARNING, logger="kpubdata.provider.datago"):
            adapter.call_raw(
                dataset,
                "getX",
                {"_base_url": "http://apis.data.go.kr/foo/bar"},
            )

        assert not any("non-data.go.kr" in record.message for record in caplog.records)
