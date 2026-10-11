"""Every external host the SDK can call is listed in docs/compliance/data-flows.md (#846)."""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlparse

from kpubdata._hosts import PROVIDER_ALLOWED_HOSTS

_ROOT = Path(__file__).resolve().parents[3]
_DOC = (_ROOT / "docs" / "compliance" / "data-flows.md").read_text(encoding="utf-8")
_BASE_URL = re.compile(r"^\s*base_url:\s*[\"']?(\S+?)[\"']?\s*$", re.MULTILINE)


def _spec_hosts() -> set[str]:
    hosts: set[str] = set()
    for path in (_ROOT / "src" / "kpubdata" / "specs").rglob("*.yaml"):
        for url in _BASE_URL.findall(path.read_text(encoding="utf-8")):
            host = urlparse(url).hostname
            if host:
                hosts.add(host)
    return hosts


def test_allowlisted_hosts_are_in_the_data_flow_table() -> None:
    wanted = {h.lstrip(".") for hosts in PROVIDER_ALLOWED_HOSTS.values() for h in hosts}
    missing = sorted(h for h in wanted if h not in _DOC)
    assert not missing, f"add to docs/compliance/data-flows.md: {missing}"


def test_spec_base_url_hosts_are_in_the_data_flow_table() -> None:
    hosts = _spec_hosts()
    assert hosts, "no spec base_url found; the pattern is stale"
    missing = sorted(h for h in hosts if h not in _DOC)
    assert not missing, f"add to docs/compliance/data-flows.md: {missing}"
