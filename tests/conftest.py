"""Opt-in synthetic HTTPS endpoints for tests that exercise mocked provider responses."""

from dataclasses import replace

import pytest


@pytest.fixture
def https_mock_endpoints(monkeypatch: pytest.MonkeyPatch) -> None:
    """Clone endpoint metadata for mocked traffic; leave bundled evidence untouched.

    This fixture is never enabled globally or for transport safety/replay tests.
    It asserts nothing about live provider HTTPS support.
    """
    from kpubdata import bootstrap
    from kpubdata.core import spec
    from kpubdata.core.models import DatasetRef
    from kpubdata.providers import _common

    original_specs = spec._shared_bundled_specs
    original_ref = _common.build_dataset_ref

    def https_specs() -> tuple[spec.SpecDefinition, ...]:
        return tuple(
            replace(
                item,
                endpoint=replace(
                    item.endpoint, base_url=item.endpoint.base_url.replace("http://", "https://", 1)
                ),
            )
            for item in original_specs()
        )

    def https_ref(provider: str, entry: dict[str, object]) -> DatasetRef:
        copied = dict(entry)
        base_url = copied.get("base_url")
        if isinstance(base_url, str):
            copied["base_url"] = base_url.replace("http://", "https://", 1)
        return original_ref(provider, copied)

    monkeypatch.setattr(spec, "_shared_bundled_specs", https_specs)
    monkeypatch.setattr(bootstrap, "_shared_bundled_specs", https_specs)
    monkeypatch.setattr(_common, "build_dataset_ref", https_ref)
