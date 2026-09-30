"""The spec digest pins what the recorder executed (#522).

Evidence binding hashes the spec file's pipeline-relevant content; these
tests pin the one normalization that makes that possible at all — the
recorder rewrites ``last_verified`` after recording, and that rewrite must
not void the record it just made.
"""

from __future__ import annotations

from pathlib import Path

from kpubdata.core.spec import spec_file_digest

_SPEC = """\
provider: datago
status: active
last_verified: "2026-01-01"
endpoint:
  operation: getData
"""


def test_the_digest_is_stable_for_the_same_content(tmp_path: Path) -> None:
    one = tmp_path / "a.yaml"
    other = tmp_path / "b.yaml"
    one.write_text(_SPEC, encoding="utf-8")
    other.write_text(_SPEC, encoding="utf-8")

    assert spec_file_digest(one) == spec_file_digest(other)


def test_a_last_verified_rewrite_keeps_the_digest(tmp_path: Path) -> None:
    path = tmp_path / "spec.yaml"
    path.write_text(_SPEC, encoding="utf-8")

    before = spec_file_digest(path)
    path.write_text(_SPEC.replace("2026-01-01", "2026-12-31"), encoding="utf-8")

    assert spec_file_digest(path) == before


def test_dropping_last_verified_altogether_keeps_the_digest(tmp_path: Path) -> None:
    path = tmp_path / "spec.yaml"
    path.write_text(_SPEC, encoding="utf-8")

    before = spec_file_digest(path)
    stripped = "\n".join(
        line for line in _SPEC.splitlines() if not line.startswith("last_verified:")
    )
    path.write_text(stripped + "\n", encoding="utf-8")

    assert spec_file_digest(path) == before


def test_any_other_change_moves_the_digest(tmp_path: Path) -> None:
    path = tmp_path / "spec.yaml"
    path.write_text(_SPEC, encoding="utf-8")

    before = spec_file_digest(path)
    path.write_text(_SPEC + "  extra: value\n", encoding="utf-8")

    assert spec_file_digest(path) != before


def test_a_missing_file_reads_as_none(tmp_path: Path) -> None:
    assert spec_file_digest(tmp_path / "absent.yaml") is None
