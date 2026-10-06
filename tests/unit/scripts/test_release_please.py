"""release-please opens the release pull request, and only that (#819).

It works out the version from commit titles and keeps the pull request open. The
CHANGELOG stays hand-written, the lock file is written by `set_version.py`, and the
tag is made by `release.yml` after the gates — release-please does none of the three.
Each of those is one line of configuration, and losing a line is quiet: the release
would carry commit titles for notes, or be tagged the moment it merged. So the lines
are held here.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
CONFIG = REPO_ROOT / "release-please-config.json"
MANIFEST = REPO_ROOT / ".release-please-manifest.json"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "release-please.yml"
RELEASE = REPO_ROOT / ".github" / "workflows" / "release.yml"
#: The prefix. release-please names the branch `<prefix>--components--<package>`; the
#: first pull request it opened (#830) had that suffix, and an exact match on the bare
#: prefix would have left its merge with no release job.
BRANCH = "release-please--branches--main"
OBSERVED_BRANCH = "release-please--branches--main--components--kpubdata"


def _load_set_version():
    path = REPO_ROOT / "scripts" / "set_version.py"
    spec = importlib.util.spec_from_file_location("set_version", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["set_version"] = module
    spec.loader.exec_module(module)
    return module


def _declared_version() -> str:
    text = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version = "([^"]+)"', text, re.MULTILINE)
    assert match
    return match.group(1)


def test_the_manifest_says_the_version_pyproject_declares() -> None:
    """release-please bumps from the manifest. Behind `pyproject.toml`, it would open a
    pull request for a version that is already out."""
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    assert manifest == {".": _declared_version()}


def test_the_changelog_stays_hand_written_and_the_bump_follows_the_0x_rule() -> None:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))

    assert config["skip-changelog"] is True
    # Breaking raises the minor in 0.x; `feat` already does. Patch-for-minor would
    # make a new feature a patch release, which is not the rule (§5.1).
    assert config["bump-minor-pre-major"] is True
    assert "bump-patch-for-minor-pre-major" not in config
    assert config["packages"] == {".": {"release-type": "python", "package-name": "kpubdata"}}


def test_the_tag_and_title_are_the_ones_release_yml_reads() -> None:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    release = RELEASE.read_text(encoding="utf-8")

    assert config["include-v-in-tag"] is True
    assert config["include-component-in-tag"] is False
    # The release job compares the merged pull request's title with this, literally.
    assert config["pull-request-title-pattern"] == "chore: release v${version}"
    assert '"${TITLE}" != "chore: release ${TAG}"' in release


def test_release_please_neither_tags_nor_labels() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert re.search(r"^\s+skip-github-release: true$", workflow, re.MULTILINE)
    assert re.search(r"^\s+skip-labeling: true$", workflow, re.MULTILINE)
    assert "gh release create" not in workflow
    assert "git tag" not in workflow


def test_the_release_branch_gets_the_lock_file_and_the_dated_changelog() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "uses: ./.github/actions/set-version" in workflow
    assert re.search(
        r"uses: \./\.github/actions/release-notes\n\s+with:\n\s+command: promote", workflow
    )


def test_merging_the_release_please_branch_reaches_the_gated_release_job() -> None:
    release = RELEASE.read_text(encoding="utf-8")

    assert f"startsWith(github.event.pull_request.head.ref, '{BRANCH}')" in release
    assert f"{BRANCH}*) from_release_please=true" in release
    # An exact comparison is what missed the real branch name.
    assert f"head.ref == '{BRANCH}'" not in release
    assert OBSERVED_BRANCH.startswith(BRANCH)
    # The hand-prepared path is still there for a pre-release and a critical patch.
    assert "startsWith(github.event.pull_request.head.ref, 'release/')" in release


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "kpubdata"\nversion = "0.9.0"\n', encoding="utf-8"
    )
    (tmp_path / "uv.lock").write_text(
        '[[package]]\nname = "kpubdata"\nversion = "0.9.0"\nsource = { editable = "." }\n',
        encoding="utf-8",
    )
    (tmp_path / MANIFEST.name).write_text('{\n  ".": "0.9.0"\n}\n', encoding="utf-8")
    return tmp_path


def test_a_hand_prepared_release_moves_the_manifest_too(repo: Path) -> None:
    written = _load_set_version().set_version(repo, "0.9.1a0")

    assert written[MANIFEST.name] == 1
    assert json.loads((repo / MANIFEST.name).read_text(encoding="utf-8")) == {".": "0.9.1a0"}


def test_a_manifest_without_the_root_package_writes_nothing(repo: Path) -> None:
    script = _load_set_version()
    (repo / MANIFEST.name).write_text('{\n  "packages/core": "0.9.0"\n}\n', encoding="utf-8")

    with pytest.raises(script.VersionWriteError):
        script.set_version(repo, "0.9.1")

    assert 'version = "0.9.0"' in (repo / "pyproject.toml").read_text(encoding="utf-8")
