"""Verify that basic paths work without optional extras.

CI always runs with --extra dev, so it misses dependencies wrongly marked
optional. The krx adapter imported pandas at the top level, breaking
client.datasets.list() for users without krx. Since krx requires no auth,
it's always in the provider manifest, and listing without a provider
instantiates every adapter.
"""

from __future__ import annotations

import builtins
import importlib
import sys
from collections.abc import Iterator
from types import ModuleType
from typing import Any

import pytest

_OPTIONAL_MODULES = ("pandas", "pykrx")

# typing_extensions is optional ONLY on Python 3.12+. With marker
# python_version < '3.12', it's actually installed on 3.11 and earlier.
# On those versions, stdlib lacks override so blocking it fails as expected—
# that's correct behavior, not a bug. Only test 3.12+ without it.
_TYPING_EXTENSIONS_IS_OPTIONAL = sys.version_info >= (3, 12)


@pytest.fixture()
def without_optional_extras() -> Iterator[None]:
    """Simulate environment without optional extras installed."""
    real_import = builtins.__import__

    blocked_roots = set(_OPTIONAL_MODULES)
    if _TYPING_EXTENSIONS_IS_OPTIONAL:
        blocked_roots.add("typing_extensions")

    def _blocked(name: str, *args: Any, **kwargs: Any) -> ModuleType:
        root = name.split(".", 1)[0]
        if root in blocked_roots:
            raise ImportError(f"No module named {root!r}")
        return real_import(name, *args, **kwargs)

    saved = {
        key: value
        for key, value in sys.modules.items()
        if key.split(".", 1)[0] in {*blocked_roots, "kpubdata"}
    }
    for key in list(saved):
        del sys.modules[key]
    builtins.__import__ = _blocked
    try:
        yield
    finally:
        builtins.__import__ = real_import
        for key in [k for k in sys.modules if k.split(".", 1)[0] == "kpubdata"]:
            del sys.modules[key]
        sys.modules.update(saved)


class TestPandasIsReallyOptional:
    def test_the_krx_adapter_module_imports(self, without_optional_extras: None) -> None:
        module = importlib.import_module("kpubdata.providers.krx.adapter")

        assert module.KrxAdapter is not None

    def test_listing_every_dataset_works(self, without_optional_extras: None) -> None:
        """This is the actual call that was breaking—kpubdata datasets list."""
        client_module = importlib.import_module("kpubdata.client")

        datasets = client_module.Client().datasets.list()

        assert datasets, "catalog must not be empty"

    def test_krx_still_lists_its_own_datasets(self, without_optional_extras: None) -> None:
        module = importlib.import_module("kpubdata.providers.krx.adapter")

        assert module.KrxAdapter().list_datasets()

    def test_actually_using_krx_explains_what_to_install(
        self, without_optional_extras: None
    ) -> None:
        """Fails loudly—explains what to install instead of silent failure."""
        module = importlib.import_module("kpubdata.providers.krx.adapter")
        exceptions = importlib.import_module("kpubdata.exceptions")

        with pytest.raises(exceptions.ConfigError, match=r"kpubdata\[krx\]"):
            module._pandas()


@pytest.mark.skipif(
    not _TYPING_EXTENSIONS_IS_OPTIONAL,
    reason="On 3.11 and earlier typing_extensions is declared dependency; "
    "blocking it fails as expected",
)
class TestTypingExtensionsIsReallyOptional:
    """Python 3.12+ new installs have no typing_extensions.

    override (3.12+) and dataclass_transform (3.11+) are stdlib so one
    marker cannot match both. kpubdata._typing branches by version.
    """

    def test_importing_the_package_works(self, without_optional_extras: None) -> None:
        client_module = importlib.import_module("kpubdata.client")

        assert client_module.Client is not None

    def test_every_module_that_needed_it_imports(self, without_optional_extras: None) -> None:
        for name in (
            "kpubdata.client",
            "kpubdata.transport.http",
            "kpubdata.core.dataset",
            "kpubdata.core.capability",
        ):
            assert importlib.import_module(name) is not None
