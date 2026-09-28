"""The README parity gate has to actually fail (#546).

ADR 0003 refused a separate `README.en.md` because a translation in its own file stops
being maintained. The decision changed, so the reason needs a counterweight — and a
counterweight nobody has watched work is not one.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "check_readme_parity.py"


def _load(repo_root: Path) -> Any:
    """Load the checker pointed at a temporary repository."""
    spec = importlib.util.spec_from_file_location("_readme_parity", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.REPO_ROOT = repo_root
    module.KOREAN = repo_root / "README.md"
    module.ENGLISH = repo_root / "README.en.md"
    return module


def _write(repo: Path, ko_sections: list[str], en_sections: list[str], pad: int = 0) -> None:
    """Write two READMEs with the given section headings."""
    for path, sections in (("README.md", ko_sections), ("README.en.md", en_sections)):
        body = "# Title\n\n" + "\n".join(f"## {s}\n\n내용\n" for s in sections)
        (repo / path).write_text(body + "\n" * pad, encoding="utf-8")


def test_matching_sections_pass(tmp_path: Path) -> None:
    """The case the gate must not break."""
    _write(tmp_path, ["설치", "문서"], ["설치", "문서"])
    assert _load(tmp_path).main() == 0


def test_a_section_added_to_one_file_fails(tmp_path: Path) -> None:
    """The drift that actually happens: a section added on one side only."""
    _write(tmp_path, ["설치", "문서", "새 절"], ["설치", "문서"])
    module = _load(tmp_path)

    assert module.main() == 1


def test_a_section_added_to_the_english_file_fails(tmp_path: Path) -> None:
    """Drift in the other direction counts too."""
    _write(tmp_path, ["설치"], ["설치", "Extra"])
    assert _load(tmp_path).main() == 1


def test_reordered_sections_fail(tmp_path: Path) -> None:
    """Same sections in a different order still describes the project twice."""
    _write(tmp_path, ["설치", "문서"], ["문서", "설치"])
    assert _load(tmp_path).main() == 1


def test_an_overlong_readme_fails(tmp_path: Path) -> None:
    """The 150-line budget is enforced so that it survives being decided."""
    _write(tmp_path, ["설치"], ["설치"], pad=200)
    assert _load(tmp_path).main() == 1


def test_a_missing_english_readme_fails(tmp_path: Path) -> None:
    """Absence is a failure, not a pass — that is how the file stops existing."""
    (tmp_path / "README.md").write_text("# Title\n\n## 설치\n", encoding="utf-8")
    assert _load(tmp_path).main() == 1


def test_the_real_readmes_agree() -> None:
    """The check passes against this repository as it stands."""
    module = _load(Path(__file__).resolve().parents[2])
    assert module.main() == 0


def test_the_status_page_is_current() -> None:
    """docs/status.md is generated, and a generator nobody checks drifts (#498).

    It claimed 22 spec and 149 catalogue datasets while the README said 23 and 150 —
    two generated documents disagreeing about the same repository, because only one of
    them was checked in CI.
    """
    import subprocess
    import sys

    repo_root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [sys.executable, "scripts/gen_status_page.py", "--check"],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, (
        f"docs/status.md is stale: {result.stdout.strip()}\n"
        "Run `python scripts/gen_status_page.py` and commit the result."
    )
