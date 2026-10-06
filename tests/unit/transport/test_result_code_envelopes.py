"""A refusal named by a word is not cached either (#838).

Seoul Open Data, BOK ECOS, NEIS and LOFIN answer HTTP 200 with ``RESULT: {CODE, MESSAGE}``
and codes that are words: ``INFO-000`` success, ``INFO-200`` no data, ``INFO-100`` /
``ERROR-290`` an invalid key, and so on. The cache's check read numeric codes only and
left every word alone, so an invalid-key answer was kept for the cache's lifetime like a
success.

Each provider's cases are its own recorded fixtures where the repository has one.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import httpx
import pytest

from kpubdata.transport._envelope import is_upstream_error_envelope
from kpubdata.transport.cache import ResponseCache
from kpubdata.transport.http import HttpTransport, TransportConfig

_FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"
_JSON = "application/json; charset=UTF-8"
_XML = "application/xml"


def _fixture(name: str) -> bytes:
    return (_FIXTURES / name).read_bytes()


def _result(code: str) -> bytes:
    return json.dumps({"RESULT": {"CODE": code, "MESSAGE": "m"}}).encode()


@pytest.mark.parametrize(
    "name",
    [
        "bok/error_auth.json",  # {"RESULT": {"CODE": "ERROR"}}
        "seoul/error_auth.json",  # {"<service>": {"RESULT": {"CODE": "INFO-100"}}}
        "neis/auth_error.json",  # {"RESULT": {"CODE": "ERROR-290"}}
        "lofin/error_auth.json",  # {"RESULT": [{"CODE": "ERROR-290"}]}
    ],
)
def test_each_providers_recorded_error_is_a_refusal(name: str) -> None:
    assert is_upstream_error_envelope(_fixture(name), _JSON), name


@pytest.mark.parametrize(
    "name",
    [
        # Success, in every shape the family answers it in.
        "bok/success_single_page.json",
        "seoul/bike_station_master_success.json",
        "seoul/citydata.json",
        "neis/school_info.json",
        "lofin/success_single_page.json",
        # "No data" is an ordinary empty answer, not an error.
        "bok/success_empty.json",
        "seoul/empty_response.json",
        "neis/empty_result.json",
    ],
)
def test_each_providers_recorded_success_and_no_data_are_not(name: str) -> None:
    assert not is_upstream_error_envelope(_fixture(name), _JSON), name


@pytest.mark.parametrize(
    "code",
    [
        "INFO-100",
        "INFO-300",
        "INFO-400",
        "INFO-500",
        "ERROR",
        "ERROR-290",
        "ERROR-300",
        "ERROR-601",
    ],
)
def test_the_codes_the_adapters_treat_as_errors_are_refusals(code: str) -> None:
    assert is_upstream_error_envelope(_result(code), _JSON)
    # Seoul's top-level form spells the field differently.
    seoul = json.dumps({"RESULT": {"RESULT.CODE": code, "RESULT.MESSAGE": "m"}}).encode()
    assert is_upstream_error_envelope(seoul, _JSON)


@pytest.mark.parametrize(
    "code",
    [
        "INFO-000",
        "INFO-200",
        # Words nobody listed: not judged, as before.
        "INFO-999",
        "WARN-100",
        "OK",
        "ERROR-",
        "ERROR-abc",
        "MY-ERROR-290",
        "",
    ],
)
def test_success_no_data_and_unknown_words_are_left_alone(code: str) -> None:
    assert not is_upstream_error_envelope(_result(code), _JSON), code


@pytest.mark.parametrize(
    "body",
    [
        # A row that happens to have a column called RESULT or CODE is data.
        {"rows": [{"RESULT": "ERROR-290"}]},
        {"service": {"row": [{"CODE": "ERROR-290"}]}},
        {"RESULT": "ERROR-290"},
        {"RESULT": {"CODE": 290}},
        {"RESULT": []},
        {"a": {"b": {"RESULT": {"CODE": "ERROR-290"}}}},
    ],
)
def test_the_code_is_read_only_where_an_error_answer_carries_it(body: dict[str, Any]) -> None:
    assert not is_upstream_error_envelope(json.dumps(body).encode(), _JSON)


def test_a_numeric_code_still_decides_when_both_are_present() -> None:
    """Negative: the existing check comes first and is not overridden."""
    body = {"response": {"header": {"resultCode": "00"}}, "RESULT": {"CODE": "ERROR-290"}}

    assert not is_upstream_error_envelope(json.dumps(body).encode(), _JSON)


def test_the_xml_form_is_read_too() -> None:
    refused = b"<svc><RESULT><CODE>INFO-100</CODE><MESSAGE>x</MESSAGE></RESULT></svc>"
    no_data = b"<svc><RESULT><CODE>INFO-200</CODE><MESSAGE>x</MESSAGE></RESULT></svc>"

    assert is_upstream_error_envelope(refused, _XML)
    assert not is_upstream_error_envelope(no_data, _XML)


class TestTheCacheHonoursIt:
    """Through the transport: what is requested again and what is served from the cache."""

    def _run(self, tmp_path: Path, bodies: list[bytes]) -> tuple[list[bytes], int]:
        """Request the same URL once per body offered; what came back, and how many
        requests reached the network."""
        sent: list[int] = []
        queue = list(bodies)

        def _send(_self: object, request: httpx.Request, **_kwargs: Any) -> httpx.Response:
            sent.append(1)
            return httpx.Response(
                200, content=queue.pop(0), headers={"content-type": _JSON}, request=request
            )

        transport = HttpTransport(TransportConfig(max_retries=0), cache=ResponseCache(tmp_path))
        with patch("kpubdata.transport.http.httpx.Client.send", _send):
            answers = [
                transport.request("GET", "https://x/data", params={"q": "1"}).content
                for _ in bodies
            ]
        return answers, len(sent)

    def test_an_invalid_key_answer_is_requested_again_and_the_good_one_is_then_kept(
        self, tmp_path: Path
    ) -> None:
        refused = _fixture("neis/auth_error.json")
        good = _fixture("neis/school_info.json")

        answers, requests = self._run(tmp_path, [refused, good, good])

        # The refusal was not served again; the good answer that followed was cached.
        assert answers == [refused, good, good]
        assert requests == 2

    def test_no_data_is_cached_like_any_good_answer(self, tmp_path: Path) -> None:
        empty = _fixture("seoul/empty_response.json")

        answers, requests = self._run(tmp_path, [empty, empty])

        assert answers == [empty, empty]
        assert requests == 1

    def test_an_unknown_word_is_cached_as_before(self, tmp_path: Path) -> None:
        unknown = _result("INFO-999")

        _answers, requests = self._run(tmp_path, [unknown, unknown])

        assert requests == 1
