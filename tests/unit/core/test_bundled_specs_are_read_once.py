"""The in-package specs are read once per process, and each caller gets its own (#822).

A client read and validated every spec file again for each provider it resolved:
listing every provider's datasets read 350 files for 25 specs.
"""

from __future__ import annotations

import shutil
import threading
from collections.abc import Iterator
from pathlib import Path

import pytest

from kpubdata import Client, discover_specs
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
