"""Titles carry the change type; the `type:*` label is derived from them (POLICY 2.1.3).

One parser serves the pull request check and the issue labeller in all three
repositories, so its accept/reject line is pinned here.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "scripts" / "conventional_title.py"


def _load_script():
    """Load the script as a module (scripts/ is not a package)."""
    spec = importlib.util.spec_from_file_location("conventional_title", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["conventional_title"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def script():
    return _load_script()


@pytest.mark.parametrize(
    ("title", "kind", "scope", "breaking", "label"),
    [
        (
            "fix(localdata): empty wrapper becomes a phantom row",
            "fix",
            "localdata",
            False,
            "type:bug",
        ),
        ("feat: add kpubdata probe", "feat", None, False, "type:feature"),
        ("feat(core)!: cast whole columns", "feat", "core", True, "type:feature"),
        ("docs: write the CHANGELOG in English", "docs", None, False, "type:docs"),
        ("ci: require one aggregate gate", "ci", None, False, "type:chore"),
        ("i18n: translate core layer to English", "i18n", None, False, "type:chore"),
        ("chore(deps): move to kpubdata 0.7", "chore", "deps", False, "type:chore"),
        ("fix(release): 한국어 설명도 된다", "fix", "release", False, "type:bug"),
    ],
)
def test_valid_titles(script, title, kind, scope, breaking, label) -> None:
    parsed = script.parse(title)
    assert (parsed.type, parsed.scope, parsed.breaking, parsed.label) == (
        kind,
        scope,
        breaking,
        label,
    )


@pytest.mark.parametrize(
    "title",
    [
        "[Bug] localdata returns a phantom row",  # the old issue template prefix
        "GOV-01: record the policy",  # a backlog serial number, not a type
        "Fix: capitalised type",
        "fix:no space after the colon",
        "fix(): empty scope",
        "fix: ",
        "feature: not a Conventional Commits type",
        "localdata returns a phantom row",
    ],
)
def test_invalid_titles(script, title: str) -> None:
    with pytest.raises(script.TitleError):
        script.parse(title)


def test_githubs_revert_button_is_a_revert(script) -> None:
    parsed = script.parse('Revert "fix(core): stop discarding problems"')
    assert (parsed.type, parsed.label) == ("revert", "type:chore")


def test_unknown_type_names_the_allowed_ones(script) -> None:
    with pytest.raises(script.TitleError, match="feat, fix, docs"):
        script.parse("feature: add a thing")


def test_every_type_maps_to_a_policy_label(script) -> None:
    """POLICY 2.1 names four kinds; no type may invent a fifth label."""
    for kind in script.TYPES:
        assert script.parse(f"{kind}: something").label in script.ALL_LABELS


def test_main_prints_github_output_lines(script, capsys) -> None:
    assert script.main(["fix(core): stop discarding problems"]) == 0
    assert capsys.readouterr().out.splitlines() == [
        "type=fix",
        "scope=core",
        "breaking=false",
        "label=type:bug",
    ]


def test_main_fails_with_an_annotation(script, capsys) -> None:
    assert script.main(["[Bug] something broke"]) == 1
    assert capsys.readouterr().err.startswith("::error::")
