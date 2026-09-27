"""Verify alignment between builtin provider manifest and supported (#332).

Providers marked as supported in SUPPORTED_DATA.md must be registered in the
builtin manifest so Client() resolves datasets without network calls—locking
alignment between documentation/UI and runtime behavior.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from kpubdata.client import Client
from kpubdata.providers.manifest import BUILTIN_PROVIDERS

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SUPPORTED = _REPO_ROOT / "SUPPORTED_DATA.md"


def _supported_providers() -> set[str]:
    # Table format: | supported | validation | ... | provider (`provider`) | ...
    text = _SUPPORTED.read_text(encoding="utf-8")
    rows = [
        line
        for line in text.splitlines()
        if line.startswith("| supported ") or line.startswith("| partially supported ")
    ]
    providers = set()
    for row in rows:
        match = re.search(r"\(`([a-z_]+)`\)", row)
        if match:
            providers.add(match.group(1))
    return providers


def test_every_supported_doc_provider_is_builtin() -> None:
    """Every provider in supported documentation is in builtin manifest."""
    documented = _supported_providers()
    builtin = {name for name, _module, _cls in BUILTIN_PROVIDERS}
    missing = documented - builtin
    assert not missing, (
        f"SUPPORTED_DATA.md marked as supported but not in builtin manifest: {sorted(missing)}"
    )


@pytest.mark.parametrize("provider", sorted(_supported_providers()))
def test_supported_provider_resolves_without_network(provider: str) -> None:
    """Supported providers resolve without network in Client()."""
    client = Client()
    entries = client.datasets.list(provider=provider)
    assert entries, f"provider {provider!r} has no datasets"

    dataset = client.dataset(f"{provider}.{entries[0].dataset_key}")
    assert dataset._ref.dataset_key == entries[0].dataset_key

    # Issue #332 reproduction: verify SGIS resolves without network.
    if provider == "sgis":
        sgis = client.dataset("sgis.boundary.sido")
        assert sgis._ref.dataset_key == "boundary.sido"
