"""Do not cache rejections that arrive as HTTP 200.

Many Korean public APIs signal failures via response body envelope, not
status code — quota exceeded (22), unregistered key (30), gateway rejections
all return 200. When transport cached by status alone, transient quota
overages locked in for 24 hours, and that cache propagated through
kpubdata-builder's Bronze fetch to scheduled builds publishing empty data
as "success".
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

_JSON = "application/json"
_XML = "text/xml"


class TestRecognisingAnErrorEnvelope:
    @pytest.mark.parametrize(
        ("label", "body", "content_type"),
        [
            ("서비스 한도 초과", b'{"response":{"header":{"resultCode":"22"}}}', _JSON),
            (
                "게이트웨이 미등록 키",
                b'{"OpenAPI_ServiceResponse":{"cmmMsgHeader":{"returnReasonCode":"30"}}}',
                _JSON,
            ),
            ("최상단 resultCode", b'{"resultCode":"12"}', _JSON),
            (
                "XML 한도 초과",
                b"<response><header><resultCode>22</resultCode></header></response>",
                _XML,
            ),
            (
                "XML 게이트웨이",
                b"<cmmMsgHeader><returnReasonCode>30</returnReasonCode></cmmMsgHeader>",
                _XML,
            ),
        ],
    )
    def test_failures_are_recognised(self, label: str, body: bytes, content_type: str) -> None:
        assert is_upstream_error_envelope(body, content_type), label

    @pytest.mark.parametrize(
        ("label", "body", "content_type"),
        [
            ("정상 00", b'{"response":{"header":{"resultCode":"00"}}}', _JSON),
            ("정상 000", b'{"response":{"header":{"resultCode":"000"}}}', _JSON),
            ("정수 0", b'{"response":{"header":{"resultCode":0}}}', _JSON),
            ("코드 없음", b'{"data":[1,2,3]}', _JSON),
            ("깨진 JSON", b"{oops", _JSON),
            ("숫자 아닌 코드", b'{"resultCode":"OK"}', _JSON),
            ("바이너리", b"\x00\x01", "application/octet-stream"),
            (
                "XML 정상",
                b"<response><header><resultCode>00</resultCode></header></response>",
                _XML,
            ),
        ],
    )
    def test_everything_else_is_left_alone(
        self, label: str, body: bytes, content_type: str
    ) -> None:
        """Unknowns are cached (asymmetric: false positive = cache miss,
        false negative = wrong response for a day).
        """
        assert not is_upstream_error_envelope(body, content_type), label


class TestTheCacheHonoursIt:
    def _transport(self, tmp_path: Path) -> HttpTransport:
        return HttpTransport(TransportConfig(max_retries=0), cache=ResponseCache(tmp_path))

    def _counting_send(self, body: bytes, calls: list[int]) -> Any:
        def _send(self: object, request: httpx.Request, **_kwargs: Any) -> httpx.Response:
            calls.append(1)
            return httpx.Response(
                200, content=body, headers={"content-type": _JSON}, request=request
            )

        return _send

    def test_a_quota_error_is_requested_again(self, tmp_path: Path) -> None:
        calls: list[int] = []
        body = json.dumps({"response": {"header": {"resultCode": "22"}}}).encode()
        transport = self._transport(tmp_path)

        with patch("kpubdata.transport.http.httpx.Client.send", self._counting_send(body, calls)):
            _ = transport.request("GET", "https://x/limited", params={"q": "1"})
            _ = transport.request("GET", "https://x/limited", params={"q": "1"})

        assert len(calls) == 2, "한도 초과가 캐시되면 하루 동안 고착된다"

    def test_a_good_response_is_still_cached(self, tmp_path: Path) -> None:
        calls: list[int] = []
        body = json.dumps({"response": {"header": {"resultCode": "00"}, "body": {}}}).encode()
        transport = self._transport(tmp_path)

        with patch("kpubdata.transport.http.httpx.Client.send", self._counting_send(body, calls)):
            _ = transport.request("GET", "https://x/ok", params={"q": "1"})
            _ = transport.request("GET", "https://x/ok", params={"q": "1"})

        assert len(calls) == 1


class TestNoStoreRequests:
    """Requests where the response itself is a credential are not cached."""

    def test_the_body_never_reaches_disk(self, tmp_path: Path) -> None:
        body = json.dumps(
            {"errCd": 0, "result": {"accessToken": "TOKEN-ABC", "accessTimeout": "1790000000000"}}
        ).encode()
        calls: list[int] = []
        transport = HttpTransport(TransportConfig(max_retries=0), cache=ResponseCache(tmp_path))

        def _send(self: object, request: httpx.Request, **_kwargs: Any) -> httpx.Response:
            calls.append(1)
            return httpx.Response(
                200, content=body, headers={"content-type": _JSON}, request=request
            )

        with patch("kpubdata.transport.http.httpx.Client.send", _send):
            _ = transport.request("GET", "https://sgis/auth", params={"k": "v"}, no_store=True)
            _ = transport.request("GET", "https://sgis/auth", params={"k": "v"}, no_store=True)

        assert len(calls) == 2, "force_refresh 가 캐시를 읽으면 만료된 토큰이 돌아온다"
        on_disk = [p for p in tmp_path.rglob("*") if p.is_file() and b"TOKEN-ABC" in p.read_bytes()]
        assert not on_disk, "access token 이 ~/.cache 에 평문으로 남으면 안 된다"


class TestRetryableComesFromTheStatusCode:
    """Marking 4xx as retryable causes callers to re-send with bad keys."""

    @pytest.mark.parametrize("status_code", [400, 401, 403, 404])
    def test_client_errors_are_not_retryable(self, status_code: int) -> None:
        from kpubdata.exceptions import TransportError

        assert TransportError("x", status_code=status_code).retryable is False

    @pytest.mark.parametrize("status_code", [408, 425, 429, 500, 503])
    def test_transient_failures_stay_retryable(self, status_code: int) -> None:
        from kpubdata.exceptions import TransportError

        assert TransportError("x", status_code=status_code).retryable is True

    def test_a_failure_with_no_status_is_still_retryable(self) -> None:
        """Connection failures·timeouts have no status code — still worth retry."""
        from kpubdata.exceptions import TransportError

        assert TransportError("connection refused").retryable is True

    def test_an_explicit_value_still_wins(self) -> None:
        from kpubdata.exceptions import TransportError

        assert TransportError("x", status_code=403, retryable=True).retryable is True


class TestTheCachePreservesContentType:
    """Cache hit must produce same result as cache miss (#480 second fault).

    Cache stored body bytes only, so hit lost Content-Type and type
    inference ran again. XML got decoded as JSON this way — same request
    returned different answers based on cache state.
    """

    _XML = b"<response><header><resultCode>00</resultCode></header><body><items/></body></response>"

    def _transport(self, tmp_path: Path) -> HttpTransport:
        return HttpTransport(TransportConfig(max_retries=0), cache=ResponseCache(tmp_path))

    def _xml_send(self) -> Any:
        def _send(self: object, request: httpx.Request, **_kwargs: Any) -> httpx.Response:
            return httpx.Response(
                200,
                content=TestTheCachePreservesContentType._XML,
                headers={"content-type": "text/xml; charset=utf-8"},
                request=request,
            )

        return _send

    def test_xml_is_still_xml_on_a_cache_hit(self, tmp_path: Path) -> None:
        from kpubdata.transport.decode import detect_content_type

        transport = self._transport(tmp_path)

        with patch("kpubdata.transport.http.httpx.Client.send", self._xml_send()):
            miss = transport.request("GET", "https://x/y", params={"q": "1"})
            hit = transport.request("GET", "https://x/y", params={"q": "1"})

        assert detect_content_type(miss) == "xml"
        assert detect_content_type(hit) == detect_content_type(miss)

    def test_an_entry_without_a_stored_type_still_reads(self, tmp_path: Path) -> None:
        """Legacy cache entries lack content_type key — read them as before."""
        import base64
        import json
        import time

        cache = ResponseCache(tmp_path)
        cache.set("legacy", b"body", 3600, "text/xml")
        # Delete content_type key to revert to old format.
        path = next(p for p in tmp_path.rglob("*") if p.is_file())
        payload = json.loads(path.read_text(encoding="utf-8"))
        del payload["content_type"]
        payload["created_at"] = time.time()
        path.write_text(json.dumps(payload), encoding="utf-8")

        stored = cache.get("legacy")

        assert stored == (base64.b64decode(payload["body_b64"]), "")
