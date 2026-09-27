"""Allow the synthetic hosts these spec fixtures use (#519).

The executor now refuses to attach a provider credential to a host that is not
on that provider's allowlist. The spec fixtures here call invented hosts --
``example.test``, ``x.test``, ``api.bok.go.kr`` -- while declaring a real
``provider_key``, so without this they would all be refused.

Widening the list through the documented environment variable is exactly the
escape hatch a deployment behind a proxy would use, so exercising it here keeps
the tests honest about the mechanism. What must not happen is putting these
hosts in ``kpubdata._hosts``: that would ship a test host as a production
destination for credentials.

``tests/unit/core/test_host_allowlist.py`` deliberately does *not* rely on this
fixture -- it asserts the refusal.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

#: Hosts invented by the spec fixtures in this directory.
_FIXTURE_HOSTS = "example.test,x.test,api.bok.go.kr"


@pytest.fixture(autouse=True)
def _allow_fixture_hosts(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    for provider in ("datago", "test", "bok"):
        monkeypatch.setenv(f"KPUBDATA_{provider.upper()}_EXTRA_HOSTS", _FIXTURE_HOSTS)
    yield
