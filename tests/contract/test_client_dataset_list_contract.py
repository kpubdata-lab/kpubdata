"""Client.dataset(key).list(**params).items consumer contract test.

This test verifies core contracts that consumers like kpubdata-builder depend on:
- Client.dataset(key).list(**params).items property exists
- items is iterable
- each item is a dict
- keyword fetch parameter propagates to adapter/transport layers
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock, patch

import httpx

from kpubdata import Client
from kpubdata.core.models import RecordBatch


def _fixture_path(name: str) -> Path:
    """
    Internal helper for fixture path handling.
    """
    return Path(__file__).resolve().parents[1] / "fixtures" / "datago" / name


def _load_fixture_bytes(name: str) -> bytes:
    """
    Internal helper for fixture bytes loading.
    """
    return _fixture_path(name).read_bytes()


def _build_mock_response(fixture_name: str) -> httpx.Response:
    """
    Creates httpx.Response from fixture data.
    """
    data = _load_fixture_bytes(fixture_name)
    return httpx.Response(
        status_code=200,
        content=data,
        request=httpx.Request("GET", "http://example.com"),
    )


class TestClientDatasetListContract:
    """
    Verifies Client.dataset(key).list(**params).items contract.

    Verifies core contracts that consumers like kpubdata-builder depend on:
    1. items property exists and is iterable
    2. each item is a dict
    3. keyword parameter propagates to adapter layer
    """

    @patch("httpx.Client.send")
    def test_list_returns_record_batch(self, mock_request: Mock) -> None:
        """
        Verifies that dataset.list() returns a RecordBatch object.
        """
        mock_request.return_value = _build_mock_response("success_single_page.json")
        client = Client(provider_keys={"datago": "test-key"}, cache=False)
        dataset = client.dataset("datago.village_fcst")
        batch = dataset.list()

        # Verify RecordBatch type
        assert isinstance(batch, RecordBatch)
        assert batch.dataset is not None

    @patch("httpx.Client.send")
    def test_list_items_attribute_exists(self, mock_request: Mock) -> None:
        """
        Verifies that Client.dataset(key).list(**params).items property exists.
        """
        mock_request.return_value = _build_mock_response("success_single_page.json")
        client = Client(provider_keys={"datago": "test-key"}, cache=False)
        dataset = client.dataset("datago.village_fcst")
        batch = dataset.list()

        # Verify items property exists
        assert hasattr(batch, "items")
        assert batch.items is not None

    @patch("httpx.Client.send")
    def test_list_items_is_iterable(self, mock_request: Mock) -> None:
        """
        Verifies that items property is iterable.
        """
        mock_request.return_value = _build_mock_response("success_single_page.json")
        client = Client(provider_keys={"datago": "test-key"}, cache=False)
        dataset = client.dataset("datago.village_fcst")
        batch = dataset.list()

        # Verify items is iterable
        item_count = 0
        for _item in batch.items:
            item_count += 1

        assert item_count > 0

    @patch("httpx.Client.send")
    def test_list_items_are_dicts(self, mock_request: Mock) -> None:
        """
        Verifies that each item in items is a dict.
        """
        mock_request.return_value = _build_mock_response("success_single_page.json")
        client = Client(provider_keys={"datago": "test-key"}, cache=False)
        dataset = client.dataset("datago.village_fcst")
        batch = dataset.list()

        # Verify all items are dicts
        for item in batch.items:
            assert isinstance(item, dict), f"Expected dict, got {type(item)}"

    @patch("httpx.Client.send")
    def test_list_items_with_filter_parameters(self, mock_request: Mock) -> None:
        """
        Verifies that keyword filter parameters propagate to transport layer.
        """
        mock_request.return_value = _build_mock_response("success_single_page.json")
        client = Client(provider_keys={"datago": "test-key"}, cache=False)
        dataset = client.dataset("datago.village_fcst")

        # Call with keyword filter parameter
        batch = dataset.list(page=1, page_size=10)

        # Verify result is returned correctly
        assert batch is not None
        assert hasattr(batch, "items")
        assert isinstance(batch.items, list)

        # Verify HTTP call was made
        assert mock_request.called
        assert mock_request.call_count >= 1

        # Verify actual HTTP request parameters
        call_args = mock_request.call_args
        assert call_args is not None

        # In streaming send path (#271), params are merged into built Request URL
        request_obj = call_args.args[0] if call_args.args else None
        assert request_obj is not None, "HTTP 요청이 전달되지 않음"
        params = dict(request_obj.url.params)

        # DataGo adapter converts canonical 'page' to 'pageNo'
        assert "pageNo" in params, "pageNo 파라미터가 요청에 없음"
        assert params["pageNo"] == "1", "pageNo 값이 1이어야 함"

        # DataGo adapter converts canonical 'page_size' to 'numOfRows'
        assert "numOfRows" in params, "numOfRows 파라미터가 요청에 없음"
        assert params["numOfRows"] == "10", "numOfRows 값이 10이어야 함"

    @patch("httpx.Client.send")
    def test_list_items_with_empty_result(self, mock_request: Mock) -> None:
        """
        Verifies that items contract is maintained even with empty results.
        """
        mock_request.return_value = _build_mock_response("success_empty.json")
        client = Client(provider_keys={"datago": "test-key"}, cache=False)
        dataset = client.dataset("datago.village_fcst")
        batch = dataset.list()

        # Verify items contract even with empty result
        assert hasattr(batch, "items")
        assert isinstance(batch.items, list)
        assert len(batch.items) == 0

    @patch("httpx.Client.send")
    def test_list_items_representative_dataset_contract(self, mock_request: Mock) -> None:
        """
        Verifies that items property behaves consistently across representative dataset.
        """
        mock_request.return_value = _build_mock_response("success_single_page.json")
        client = Client(provider_keys={"datago": "test-key"}, cache=False)

        # Verify representative dataset follows contract
        dataset_key = "datago.village_fcst"
        dataset = client.dataset(dataset_key)
        batch = dataset.list()

        # Verify items contract is maintained
        assert hasattr(batch, "items"), f"Dataset {dataset_key} missing items attribute"
        assert isinstance(batch.items, list), f"Dataset {dataset_key} items is not a list"

        for item in batch.items:
            assert isinstance(item, dict), f"Dataset {dataset_key} has non-dict item"
