"""The workflow action pin gate has to actually refuse (ported from kpubdata-builder#1003).

A gate nobody has watched fail is a gate nobody knows works, so most of these feed it a
movable reference and expect a violation.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT = _ROOT / "scripts" / "check_action_pins.py"

_SHA = "5fda3b95a4ea91299a34e894583c3862153e4b97"
_OTHER_SHA = "3d3c42e5aac5ba805825da76410c181273ba90b1"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("_action_pin_gate", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


gate = _load()


def _workflow(tmp_path: Path, steps: str) -> Path:
    path = tmp_path / "wf.yml"
    path.write_text(f"jobs:\n  a:\n    steps:\n{steps}", encoding="utf-8")
    return path


@pytest.mark.parametrize(
    "line",
    [
        "      - uses: kpubdata-lab/kpubdata/.github/actions/r3-review@main\n",
        "        uses: kpubdata-lab/kpubdata/.github/actions/release-notes@main\n",
        "      - uses: actions/checkout@v7\n",
        "      - uses: actions/checkout@v7.0.1  # v7.0.1\n",
        '      - uses: "actions/setup-python@v7"\n',
        "      - uses: 'astral-sh/setup-uv@v7'\n",
        # A short SHA can be ambiguous and is resolved like a ref name.
        "      - uses: actions/checkout@3d3c42e\n",
        "      - uses: actions/checkout\n",
        "      - uses: docker://alpine:3.20\n",
        "    uses: org/repo/.github/workflows/reusable.yml@main\n",
        # Valid YAML a line pattern does not match: a flow mapping and a quoted key.
        "      - {uses: actions/checkout@v7}\n",
        '      - "uses": actions/checkout@v7\n',
        "      - 'uses': actions/checkout@v7\n",
        "      - {name: checkout, uses: actions/checkout@v7, with: {fetch-depth: 0}}\n",
    ],
)
def test_movable_reference_is_refused(tmp_path: Path, line: str) -> None:
    path = _workflow(tmp_path, line)

    violations = gate.check([path])

    assert len(violations) == 1
    assert violations[0].line == 4
    assert gate.main([str(path)]) == 1


@pytest.mark.parametrize(
    "line",
    [
        f"      - uses: kpubdata-lab/kpubdata/.github/actions/r3-review@{_SHA}  # main\n",
        f"      - uses: actions/checkout@{_OTHER_SHA}  # v7.0.1\n",
        f'      - uses: "actions/checkout@{_OTHER_SHA}"\n',
        "    uses: ./.github/workflows/publish-dataset.yml\n",
        "      - uses: docker://alpine@sha256:" + "a" * 64 + "\n",
        # Not a step: text that only mentions a ref is not run.
        """      - run: "echo 'uses: actions/checkout@v7'"\n""",
        "      # - uses: actions/checkout@v7\n",
        f"      - {{uses: actions/checkout@{_OTHER_SHA}}}\n",
        f'      - "uses": actions/checkout@{_OTHER_SHA}\n',
    ],
)
def test_pinned_or_local_reference_passes(tmp_path: Path, line: str) -> None:
    path = _workflow(tmp_path, line)

    assert gate.check([path]) == []
    assert gate.main([str(path)]) == 0


def test_repository_workflows_are_pinned() -> None:
    paths = gate.default_paths(_ROOT)

    assert any(p.name == "release.yml" for p in paths)
    assert gate.check(paths) == []


def test_a_composite_action_step_in_a_flow_mapping_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "action.yml"
    path.write_text(
        "runs:\n  using: composite\n  steps:\n    - {uses: actions/checkout@v7}\n",
        encoding="utf-8",
    )

    assert [violation.line for violation in gate.check([path])] == [4]


def test_a_file_that_is_not_yaml_is_refused(tmp_path: Path) -> None:
    """Its references cannot be listed, so it cannot be called pinned."""
    path = tmp_path / "wf.yml"
    path.write_text("jobs:\n  a: [unclosed\n", encoding="utf-8")

    violations = gate.check([path])

    assert len(violations) == 1
    assert "not valid YAML" in violations[0].reason
    assert gate.main([str(path)]) == 1
