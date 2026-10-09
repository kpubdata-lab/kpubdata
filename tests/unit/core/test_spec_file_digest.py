"""The spec digest pins what the recorder executed (#522).

Evidence binding hashes the spec file's pipeline-relevant content; these
tests pin the one normalization that makes that possible at all — the
recorder rewrites ``last_verified`` after recording, and that rewrite must
not void the record it just made.
"""

from __future__ import annotations

from pathlib import Path

import pytest

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


_FIELD_SPEC = """id: datago.x
title: 데이터셋 이름
fields:
- name: dealAmount
  type: integer
  description: 거래금액
"""


def test_a_fields_title_and_unit_do_not_move_the_digest(tmp_path: Path) -> None:
    # They label what was recorded; they change neither the request nor the casting
    # (#877), so filling them in must not void recorded evidence.
    plain = tmp_path / "plain.yaml"
    labelled = tmp_path / "labelled.yaml"
    plain.write_text(_FIELD_SPEC, encoding="utf-8")
    labelled.write_text(
        _FIELD_SPEC.replace(
            "  type: integer\n", "  type: integer\n  title: 거래금액\n  unit: 만원\n"
        ),
        encoding="utf-8",
    )

    assert spec_file_digest(labelled) == spec_file_digest(plain)


@pytest.mark.parametrize(
    ("before", "after"),
    [
        ("title: 데이터셋 이름\n", "title: 다른 이름\n"),  # the spec's own title
        ("  type: integer\n", "  type: integer\n  semantic_kind: measure\n"),
        ("  type: integer\n", "  type: string\n"),
        ("  description: 거래금액\n", "  description: 금액\n"),
    ],
)
def test_anything_else_still_moves_the_digest(tmp_path: Path, before: str, after: str) -> None:
    original = tmp_path / "a.yaml"
    changed = tmp_path / "b.yaml"
    original.write_text(_FIELD_SPEC, encoding="utf-8")
    changed.write_text(_FIELD_SPEC.replace(before, after), encoding="utf-8")

    assert spec_file_digest(changed) != spec_file_digest(original)


def test_no_bundled_spec_on_record_changed_its_digest() -> None:
    # Every fixture's recorded digest still matches: the verify step (2-c) is the
    # real check; this names the rule here too.
    import json

    root = Path(__file__).resolve().parents[3]
    fixtures = root / "tests" / "fixtures"
    for meta_path in fixtures.rglob("*.meta.json"):
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        recorded = meta.get("spec_sha256")
        if not recorded:
            continue
        provider, dataset = str(meta["dataset_id"]).split(".", 1)
        spec_path = root / "src" / "kpubdata" / "specs" / provider / f"{dataset}.yaml"
        if spec_path.exists():
            assert spec_file_digest(spec_path) == recorded, meta_path.name
