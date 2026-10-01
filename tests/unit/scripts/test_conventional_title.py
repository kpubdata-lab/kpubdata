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
        ("build: pin uv to 0.9", "build", None, False, "type:chore"),
        ("perf(core)!: stream pages instead of buffering", "perf", "core", True, "type:chore"),
        ("revert: undo the cache change", "revert", None, False, "type:chore"),
        (
            'fix(spec): keep "0766" as text, not `int`',
            "fix",
            "spec",
            False,
            "type:bug",
        ),
        ("chore(deps): move to kpubdata 0.7", "chore", "deps", False, "type:chore"),
        ("fix: keep C# interop working", "fix", None, False, "type:bug"),
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
        "i18n: translate core layer to English",  # dropped on 2026-09-29
        "feat!:",
        "[WIP] fix: something",
        "docs: establish the release policy (#528)",  # #699: squash adds the PR number
        "feat(core): cast whole columns (#481)",
        "fix: keep leading zeros (#574) ",  # trailing space still counts after strip()
        "fix: 한글 제목",  # #742: the title is English
        "fix: refuse the key (studio#418)",  # #742: repo-prefixed reference
        "fix: close the gap from #123 review",  # #742: bare mid-sentence reference
    ],
)
def test_invalid_titles(script, title: str) -> None:
    with pytest.raises(script.TitleError):
        script.parse(title)


def test_githubs_revert_button_is_a_revert(script) -> None:
    parsed = script.parse('Revert "fix(core): stop discarding problems"')
    assert (parsed.type, parsed.label) == ("revert", "type:chore")


def test_revert_of_a_numbered_title_still_parses(script) -> None:
    """GitHub revert titles end with a quote, so the trailing-number rule cannot hit them."""
    parsed = script.parse('Revert "docs: establish the release policy (#528)"')
    assert parsed.type == "revert"


def test_revert_of_a_hangul_title_still_parses(script) -> None:
    """The revert button copies the old title verbatim; refusing it would block undo."""
    parsed = script.parse('Revert "fix(release): 한국어 설명도 된다"')
    assert parsed.type == "revert"


def test_mid_title_issue_reference_is_refused(script) -> None:
    """#742: a bare mid-sentence reference is as wrong as the trailing tag."""
    with pytest.raises(script.TitleError, match="Closes #123"):
        script.parse("fix: adapters registered twice since #612 are deduped")


def test_repo_prefixed_reference_error_names_the_remedy(script) -> None:
    with pytest.raises(script.TitleError, match="studio#418"):
        script.parse("fix: refuse the key (studio#418)")


def test_hangul_error_names_the_remedy(script) -> None:
    with pytest.raises(script.TitleError, match="body"):
        script.parse("fix(release): 한국어 설명도 된다")


def test_numbered_title_error_names_the_remedy(script) -> None:
    with pytest.raises(script.TitleError, match="Closes #123"):
        script.parse("docs: establish the release policy (#528)")


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


@pytest.mark.parametrize(
    "title",
    [
        "fix(x\nlabel<<EOF\ntype:bug\nEOF\nz): y",  # #628: a scope carrying output lines
        "fix: first line\nsecond=line",
        "fix: carriage\rreturn",
        'Revert "fix: x"\nlabel=type:bug',
    ],
)
def test_a_title_with_a_line_break_is_refused(script, title: str) -> None:
    """A line break would let a title write its own lines into $GITHUB_OUTPUT (#628)."""
    with pytest.raises(script.TitleError, match="single line"):
        script.parse(title)


def test_main_never_prints_more_than_the_four_output_lines(script, capsys) -> None:
    """Whatever the title holds, stdout is exactly the four key=value lines."""
    assert script.main(['fix(api): accept `$(id)` and "quotes" as plain text']) == 0
    out = capsys.readouterr().out.splitlines()
    assert [line.split("=", 1)[0] for line in out] == ["type", "scope", "breaking", "label"]


# --- Pull request titles (POLICY 2.1.3, #741) ---------------------------------------
# A pull request title becomes the commit title on main, so it also has a length limit
# and may not carry an issue URL. These are titles the 2026-10-01 audit found passing.


@pytest.mark.parametrize(
    ("title", "reason"),
    [
        ("fix: 한글 제목", "English"),
        ("feat(api): accept the studio shape (studio#418)", "issue reference"),
        ("fix: handle #123 in the middle of a title", "issue reference"),
        ("fix: see https://github.com/yeongseon/kpubdata/issues/699", "URL"),
        ("fix: see https://github.com/yeongseon/kpubdata/pull/704", "URL"),
        ("fix: " + "x" * 150, "at most 100"),
    ],
)
def test_a_pull_request_title_refuses_what_a_commit_title_may_not_carry(
    script, title: str, reason: str
) -> None:
    with pytest.raises(script.TitleError, match=reason):
        script.parse(title, pull_request=True)


def test_the_length_and_url_rules_apply_only_to_pull_request_titles(script) -> None:
    script.parse("fix: " + "x" * 150)
    script.parse("fix: see https://github.com/yeongseon/kpubdata/issues/699")


@pytest.mark.parametrize(
    "title",
    [
        "fix(localdata): empty wrapper becomes a phantom row",
        "chore(deps): bump pyjwt from 2.14.0 to 2.15.0",
        "chore(deps): bump the npm_and_yarn group across 1 directory with 3 updates",
        "fix(spec): support `#` in parameter names",
        "chore: release v0.8.0",
        # GitHub's Revert button quotes the reverted squash commit, numbers and all.
        'Revert "fix(core): an old title with its numbers (#12) (#34)"',
        'Revert "fix: 한국어로 된 옛 제목 (#12)"',
        "fix: " + "x" * 95,
    ],
)
def test_a_pull_request_title_that_follows_the_rules_passes(script, title: str) -> None:
    script.parse(title, pull_request=True)


def test_the_length_limit_is_inclusive(script) -> None:
    title = "fix: " + "x" * (script.MAX_PR_TITLE_LENGTH - len("fix: "))
    assert len(title) == script.MAX_PR_TITLE_LENGTH
    script.parse(title, pull_request=True)
    with pytest.raises(script.TitleError):
        script.parse(title + "x", pull_request=True)


def test_the_cli_applies_the_pull_request_rules_only_when_asked(script, capsys) -> None:
    long_title = "fix: " + "x" * 150
    assert script.main([long_title]) == 0
    assert script.main(["--pull-request", long_title]) == 1
    assert "at most 100" in capsys.readouterr().err
