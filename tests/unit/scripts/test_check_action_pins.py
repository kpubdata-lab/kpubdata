"""The action pin gate catches tag/branch refs and passes SHA pins (#875)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]


def _load():
    spec = importlib.util.spec_from_file_location("_check_action_pins", _ROOT / "scripts" / "check_action_pins.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_a_tag_or_branch_ref_offends() -> None:
    module = _load()
    text = "jobs:\n  a:\n    steps:\n      - uses: actions/checkout@v7\n      - uses: pypa/gh-action-pypi-publish@release/v1\n"
    offenders = module._offenders(text)
    assert len(offenders) == 2
    assert offenders[0] == (4, "actions/checkout@v7 is not pinned by SHA")
    assert offenders[1] == (5, "pypa/gh-action-pypi-publish@release/v1 is not pinned by SHA")


def test_sha_local_and_container_refs_pass() -> None:
    module = _load()
    text = (
        "jobs:\n  a:\n    steps:\n"
        "      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1  # v7\n"
        "      - uses: ./.github/actions/release-window\n"
        "      - uses: docker://alpine:3.20\n"
        "      - run: echo hi\n"
    )
    assert module._offenders(text) == []


def test_every_workflow_in_this_repository_passes_the_gate() -> None:
    module = _load()
    for path in sorted((_ROOT / ".github/workflows").glob("*.yml")):
        assert module._offenders(path.read_text(encoding="utf-8")) == [], path.name
