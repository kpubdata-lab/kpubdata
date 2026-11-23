"""The English-comment gate must not pass by looking at nothing."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "scripts" / "check_english_comments.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("check_english_comments", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_english_comments"] = module
    spec.loader.exec_module(module)
    return module


cec = _load_script()


def test_a_path_that_does_not_exist_is_an_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    missing = tmp_path / "no-such-dir"

    assert cec.main([str(missing)]) == 2
    assert "does not exist" in capsys.readouterr().err


def test_a_missing_path_among_real_ones_is_still_an_error(tmp_path: Path) -> None:
    good = tmp_path / "ok.py"
    good.write_text("# fine\n", encoding="utf-8")

    assert cec.main([str(good), str(tmp_path / "typo")]) == 2


def test_zero_checked_files_is_an_error(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (tmp_path / "notes.txt").write_text("hello\n", encoding="utf-8")

    assert cec.main([str(tmp_path)]) == 2
    assert "no Python files" in capsys.readouterr().err


def test_english_files_pass(tmp_path: Path) -> None:
    (tmp_path / "ok.py").write_text("# fine\n", encoding="utf-8")

    assert cec.main([str(tmp_path)]) == 0


def test_a_korean_comment_still_fails(tmp_path: Path) -> None:
    korean = "# 한글 주석\n"
    (tmp_path / "bad.py").write_text(korean, encoding="utf-8")

    assert cec.main([str(tmp_path)]) == 1


# Escapes, not literals: an editor may re-compose a decomposed literal into NFC.
@pytest.mark.parametrize(
    "comment",
    [
        "# ㅁㅁ ㅎㅎ",  # compatibility jamo only
        "# 한글",  # NFD-decomposed syllables
        "# 가",  # conjoining jamo only
        "# ꥠ",  # Hangul Jamo Extended-A
        "# ힰ",  # Hangul Jamo Extended-B
    ],
)
def test_jamo_and_decomposed_hangul_comments_fail(tmp_path: Path, comment: str) -> None:
    (tmp_path / "bad.py").write_text(comment + "\n", encoding="utf-8")

    assert cec.main([str(tmp_path)]) == 1


def test_a_decomposed_hangul_docstring_fails(tmp_path: Path) -> None:
    (tmp_path / "bad.py").write_text('"""한."""\n', encoding="utf-8")

    assert cec.main([str(tmp_path)]) == 1


def test_hangul_in_a_string_literal_is_still_allowed(tmp_path: Path) -> None:
    (tmp_path / "ok.py").write_text('x = "ㅁㅁ"\n', encoding="utf-8")

    assert cec.main([str(tmp_path)]) == 0
