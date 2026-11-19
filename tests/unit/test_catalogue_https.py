"""Catalogue endpoints are https unless the provider does not serve it (#893).

The transport refuses a credential-bearing request over http, so a catalogue entry left
on http:// cannot be called live at all. The entries below were checked on 2026-11-19
and stay on http only because the provider gives no working https:

- openapi.seoul.go.kr:8088 answers http; https on that port fails the TLS handshake.
- swopenAPI.seoul.go.kr answers http only; https does not respond.
- kipo-api.kipi.or.kr answers http with a redirect to /503.html; https does not respond.

The list may only shrink. An entry leaves it when its provider serves https, and a new
http:// endpoint fails this test.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

PROVIDERS = Path(__file__).resolve().parents[2] / "src" / "kpubdata" / "providers"

#: Catalogue http:// endpoints whose provider does not serve https, with their count.
HTTP_ONLY = {
    "http://openapi.seoul.go.kr:8088": 6,
    "http://swopenAPI.seoul.go.kr/api/subway": 1,
    "http://kipo-api.kipi.or.kr/openapi/service/patFamInfoSearchService": 1,
}


def _http_urls() -> dict[str, int]:
    counts: dict[str, int] = {}
    for catalogue in sorted(PROVIDERS.glob("*/catalogue.json")):
        text = catalogue.read_text(encoding="utf-8")
        json.loads(text)  # a malformed catalogue must fail here, not hide entries
        for url in re.findall(r'"(http://[^"]+)"', text):
            counts[url] = counts.get(url, 0) + 1
    return counts


def test_no_catalogue_endpoint_is_http_unless_its_provider_has_no_https() -> None:
    unexpected = {url: n for url, n in _http_urls().items() if url not in HTTP_ONLY}
    assert unexpected == {}


def test_the_http_only_list_only_shrinks() -> None:
    found = _http_urls()
    grown = {url: n for url, n in found.items() if url in HTTP_ONLY and n > HTTP_ONLY[url]}
    stale = sorted(url for url in HTTP_ONLY if url not in found)
    assert grown == {}
    assert stale == [], "these now use https: remove them from HTTP_ONLY"


def test_data_go_kr_catalogue_endpoints_are_https() -> None:
    """apis.data.go.kr served all 63 catalogue service paths over https (#893)."""
    assert not [url for url in _http_urls() if "data.go.kr" in url]
