"""No workflow merges a pull request on its own (#895).

A Dependabot auto-merge workflow was proposed. Required checks and branch protection
still apply to a merge a workflow makes, but a workflow that merges skips the person:
`R3 review` only asks for an approval on pull requests labelled `review:R3`, and the
branch requires no approving review otherwise. So the repository holds that nothing in
`.github/` merges, enables auto-merge or approves a pull request. Adding one is a
decision for a person, made by changing this test in the same pull request.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

MERGING = re.compile(
    r"gh\s+pr\s+merge"
    r"|gh\s+pr\s+review\b[^\n]*--approve"
    r"|enablePullRequestAutoMerge"
    r"|pulls/[^\s/]+/merge\b"
    r"|dependabot/fetch-metadata",
    re.IGNORECASE,
)


def _merging_lines(root: Path, paths: list[str]) -> list[str]:
    found = []
    for path in paths:
        text = (root / path).read_text(encoding="utf-8", errors="replace")
        for number, line in enumerate(text.splitlines(), start=1):
            if line.lstrip().startswith("#"):
                continue
            if MERGING.search(line):
                found.append(f"{path}:{number}: {line.strip()}")
    return found


def _tracked_github_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", ".github"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return [path for path in result.stdout.splitlines() if path.endswith((".yml", ".yaml"))]


def test_no_workflow_or_action_merges_or_approves_a_pull_request() -> None:
    paths = _tracked_github_files()
    assert paths, "git ls-files found no workflow"
    assert _merging_lines(REPO_ROOT, paths) == []


def test_the_scan_catches_an_auto_merge_workflow(tmp_path: Path) -> None:
    workflow = tmp_path / "dependabot-auto-merge.yml"
    workflow.write_text(
        "jobs:\n"
        "  merge:\n"
        "    if: github.actor == 'dependabot[bot]'\n"
        "    steps:\n"
        "      - uses: dependabot/fetch-metadata@v2\n"
        '      - run: gh pr merge --auto --squash "$PR_URL"\n'
        '      - run: gh pr review --approve "$PR_URL"\n',
        encoding="utf-8",
    )
    found = _merging_lines(tmp_path, [workflow.name])
    assert len(found) == 3
