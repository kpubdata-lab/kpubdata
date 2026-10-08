"""The in-package specs are read once per process, and each caller gets its own (#822).

A client read and validated every spec file again for each provider it resolved:
listing every provider's datasets read 350 files for 25 specs.
Each client copies only its own provider's specs, and libyaml parses them when present.
"""

from __future__ import annotations

import shutil
import threading
from collections.abc import Iterator
from pathlib import Path

import pytest
import yaml

from kpubdata import Client, bootstrap, discover_specs
from kpubdata.core import spec as spec_module


@pytest.fixture()
def reads(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[Path]]:
    """Every spec file read from here on, starting from nothing remembered."""
    seen: list[Path] = []
    real = spec_module.load_spec_file

    def counted(path: Path) -> spec_module.SpecDefinition:
        seen.append(path)
        return real(path)

    monkeypatch.setattr(spec_module, "load_spec_file", counted)
    spec_module._forget_bundled_specs()
    yield seen
    spec_module._forget_bundled_specs()


def _use(provider: str, dataset_id: str) -> None:
    client = Client(provider_keys={provider: "placeholder"}, env_keys=False)
    try:
        client.dataset(dataset_id)
    finally:
        client.close()


def test_a_second_client_reads_no_spec_file(reads: list[Path]) -> None:
    _use("datago", "datago.apt_trade")
    first = len(reads)
    _use("datago", "datago.apt_rent")
    _use("localdata", "localdata.bakery")

    assert first == len(discover_specs()) > 0
    assert len(reads) == first
    # Each file once, not once per provider.
    assert len(set(reads)) == len(reads)


def test_listing_every_provider_reads_each_file_once(reads: list[Path]) -> None:
    client = Client(env_keys=False)
    try:
        assert list(client.datasets.list())
    finally:
        client.close()

    assert len(reads) == len(set(reads)) == len(discover_specs())


def test_changing_what_was_returned_does_not_reach_the_next_caller(reads: list[Path]) -> None:
    """Negative: a spec is frozen but holds dictionaries, and a list can be emptied."""
    first = discover_specs()
    target = next(spec for spec in first if spec.id == "datago.apt_trade")
    before = dict(target.raw_metadata)
    target.raw_metadata["injected"] = "by a caller"
    target.raw_metadata.pop(next(iter(before)), None)
    first.clear()

    again = discover_specs()

    fresh = next(spec for spec in again if spec.id == "datago.apt_trade")
    assert fresh.raw_metadata == before
    assert fresh is not target
    assert len(again) == len(reads)


def test_a_directory_the_caller_names_is_read_every_time(tmp_path: Path, reads: list[Path]) -> None:
    """Its files are the caller's: one that changes between calls is seen."""
    source = next(spec_module._default_specs_dir().rglob("apt_trade.yaml"))
    copied = tmp_path / "apt_trade.yaml"
    shutil.copy(source, copied)

    assert [spec.title for spec in discover_specs(tmp_path)] == [discover_specs(tmp_path)[0].title]
    original = discover_specs(tmp_path)[0].title
    copied.write_text(
        copied.read_text(encoding="utf-8").replace(original, "a title changed on disk"),
        encoding="utf-8",
    )

    assert discover_specs(tmp_path)[0].title == "a title changed on disk"
    assert reads.count(copied) == 4
    assert discover_specs(tmp_path / "missing") == []


def test_threads_that_ask_first_at_once_read_each_file_once(reads: list[Path]) -> None:
    start = threading.Barrier(8)
    counts: list[int] = []

    def ask() -> None:
        start.wait(timeout=10)
        counts.append(len(discover_specs()))

    threads = [threading.Thread(target=ask) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    assert len(counts) == 8 and len(set(counts)) == 1
    assert len(reads) == len(set(reads)) == counts[0]


@pytest.mark.skipif(not hasattr(yaml, "CSafeLoader"), reason="PyYAML built without libyaml")
def test_the_c_loader_reads_every_bundled_spec_as_the_python_loader_does(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """YAML 1.1 dates, numbers and booleans resolve the same way in both loaders."""
    files = spec_module._iter_yaml_files(spec_module._default_specs_dir())
    loaded: dict[str, list[spec_module.SpecDefinition]] = {}
    for loader in (yaml.SafeLoader, yaml.CSafeLoader):
        monkeypatch.setattr(spec_module, "_SafeLoader", loader)
        loaded[loader.__name__] = [spec_module.load_spec_file(path) for path in files]

    assert files
    assert loaded["CSafeLoader"] == loaded["SafeLoader"]


def test_every_call_returns_equal_specs_that_are_not_the_same_objects(reads: list[Path]) -> None:
    first = discover_specs()
    again = discover_specs()

    assert first == again
    assert all(a is not b for a, b in zip(first, again, strict=True))
    assert len(reads) == len(first)


def test_a_client_holds_its_own_copy_of_its_provider_specs(reads: list[Path]) -> None:
    """Negative: changing the specs one client was given reaches no other client."""
    first = bootstrap._specs_for_provider("datago")
    target = next(spec for spec in first if spec.id == "datago.apt_trade")
    before = dict(target.raw_metadata)
    target.raw_metadata["injected"] = "by a caller"

    again = bootstrap._specs_for_provider("datago")
    fresh = next(spec for spec in again if spec.id == "datago.apt_trade")

    assert fresh.raw_metadata == before
    assert fresh is not target
    assert {spec.provider for spec in again} == {"datago"}
    assert [spec.id for spec in again] == [
        spec.id for spec in discover_specs() if spec.provider == "datago"
    ]


def test_a_client_copies_only_its_own_provider_specs(
    reads: list[Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Copying every spec for each provider was most of the time a listing took."""
    copied: list[str] = []
    real = bootstrap.copy.deepcopy

    def counted(value: list[spec_module.SpecDefinition]) -> list[spec_module.SpecDefinition]:
        copied.extend(spec.id for spec in value)
        return real(value)

    monkeypatch.setattr(bootstrap.copy, "deepcopy", counted)
    _use("datago", "datago.apt_trade")

    datago = [spec.id for spec in spec_module._shared_bundled_specs() if spec.provider == "datago"]
    assert copied == datago
