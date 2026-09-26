"""The one allowlist of hosts a provider credential may be sent to (#519).

A spec declares both where to call (``endpoint.base_url``) and which credential
to attach (``auth.provider_key``). Nothing used to check that the two agreed, so
a spec could name any host and the executor would send the project's provider
key there. ``providers/datago/adapter.py`` already had this check for
``datago.generic``'s ``base_url_override``; the spec path did not have it.

That split is the actual defect. The list lives here so both paths read the same
one -- the same failure mode as the three divergent copies of the sensitive
parameter names (see ``transport/_sensitive.py``).

The gate is fail-closed. A provider with no entry cannot receive a credential at
all, because "we forgot to list this provider" must not read as "any host is
fine". Deployments that legitimately need another host (a proxy, a staging
gateway) add it through ``KPUBDATA_<PROVIDER>_EXTRA_HOSTS``.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from urllib.parse import urlparse

__all__ = [
    "PROVIDER_ALLOWED_HOSTS",
    "extra_hosts_env_var",
    "host_is_allowed",
    "hosts_for",
]

#: Exact hostnames, plus ``.suffix`` entries that match any subdomain.
#:
#: Collected from the shipped specs, adapters and catalogues rather than from
#: documentation, so the list reflects what the code actually calls. Adding a
#: host here is a change to where credentials may travel, which is why the
#: governance policy treats it as a review-gated path.
PROVIDER_ALLOWED_HOSTS: Mapping[str, frozenset[str]] = {
    # data.go.kr and the gateways that front it
    "datago": frozenset({".data.go.kr", "data.go.kr", "api.odcloud.kr", "openapi.its.go.kr"}),
    "localdata": frozenset({".data.go.kr", "data.go.kr"}),
    "semas": frozenset({".data.go.kr", "data.go.kr"}),
    # Bank of Korea ECOS
    "bok": frozenset({"ecos.bok.or.kr"}),
    "kosis": frozenset({"kosis.kr", ".kosis.kr"}),
    "krx": frozenset({"data.krx.co.kr"}),
    "kipris": frozenset({"kipo-api.kipi.or.kr"}),
    "law": frozenset({"www.law.go.kr", "law.go.kr"}),
    "lofin": frozenset({"www.lofin365.go.kr", "lofin365.go.kr"}),
    "neis": frozenset({"open.neis.go.kr"}),
    "seoul": frozenset({"openapi.seoul.go.kr", "swopenapi.seoul.go.kr"}),
    "sgis": frozenset({"sgisapi.kostat.go.kr"}),
    "fds": frozenset({"openapi.foodsafetykorea.go.kr"}),
    "korean": frozenset({"stdict.korean.go.kr"}),
}


def extra_hosts_env_var(provider: str) -> str:
    """Name of the environment variable that widens ``provider``'s allowlist.

    ``datago`` keeps the name it already had (#261); the pattern generalises to
    every provider.
    """
    return f"KPUBDATA_{provider.strip().upper()}_EXTRA_HOSTS"


def hosts_for(provider: str) -> frozenset[str]:
    """Allowed hosts for ``provider``, including the environment additions."""
    declared = PROVIDER_ALLOWED_HOSTS.get(provider.strip().casefold(), frozenset())
    raw = os.environ.get(extra_hosts_env_var(provider), "")
    extra = {entry.strip().casefold() for entry in raw.split(",") if entry.strip()}
    return declared | frozenset(extra)


def host_is_allowed(provider: str, url_or_host: str) -> bool:
    """Whether ``provider``'s credential may be sent to this host.

    Accepts a full URL or a bare hostname. An unparseable value, an empty host
    and a provider with no entry all answer False -- every uncertain case is a
    refusal, because the cost of guessing wrong is a leaked credential.
    """
    candidate = url_or_host.strip()
    if not candidate:
        return False
    host = urlparse(candidate).hostname if "//" in candidate else candidate
    if not host:
        return False
    host = host.casefold().rstrip(".")
    allowed = hosts_for(provider)
    if not allowed:
        return False
    for entry in allowed:
        if entry.startswith("."):
            # A suffix entry matches subdomains, and the bare domain as well:
            # ".data.go.kr" covers "apis.data.go.kr" and "data.go.kr".
            if host == entry[1:] or host.endswith(entry):
                return True
        elif host == entry:
            return True
    return False
