"""Field renames read from the original record, so their order does not matter.

``_stage_fields`` renamed in place one field at a time. With ``b <- a`` then
``c <- b`` the second rename read the first one's output and then dropped it, and
``addr <- addr2`` overwrote a raw ``addr`` that another field still needed.
"""

from __future__ import annotations

from dataclasses import replace

from kpubdata.core.executor import SpecExecutor
from kpubdata.core.spec import FieldSpec, SpecDefinition, find_spec


def _probe(*fields: FieldSpec) -> SpecDefinition:
    spec = find_spec("datago.apt_trade")
    assert spec is not None
    return replace(spec, fields=fields)


def test_chained_renames_read_the_original_values() -> None:
    spec = _probe(
        FieldSpec(name="b", type="string", source_name="a"),
        FieldSpec(name="c", type="string", source_name="b"),
    )
    assert SpecExecutor._stage_fields(spec, [{"a": "A", "b": "B"}]) == [{"b": "A", "c": "B"}]


def test_rename_order_does_not_change_the_result() -> None:
    spec = _probe(
        FieldSpec(name="c", type="string", source_name="b"),
        FieldSpec(name="b", type="string", source_name="a"),
    )
    assert SpecExecutor._stage_fields(spec, [{"a": "A", "b": "B"}]) == [{"c": "B", "b": "A"}]


def test_rename_onto_a_raw_key_used_by_another_field() -> None:
    spec = _probe(
        FieldSpec(name="addr", type="string", source_name="addr2"),
        FieldSpec(name="old_addr", type="string", source_name="addr"),
    )
    staged = SpecExecutor._stage_fields(spec, [{"addr": "raw", "addr2": "new"}])
    assert staged == [{"addr": "new", "old_addr": "raw"}]


def test_transform_is_applied_once_to_the_source_value() -> None:
    spec = _probe(
        FieldSpec(name="d", type="string", transform="date_yyyymmdd"),
        FieldSpec(name="d_raw", type="string", source_name="d"),
    )
    staged = SpecExecutor._stage_fields(spec, [{"d": "20240105"}])
    assert staged == [{"d": "2024-01-05", "d_raw": "20240105"}]


def test_undeclared_keys_are_kept_and_renamed_sources_dropped() -> None:
    spec = _probe(FieldSpec(name="name", type="string", source_name="nm"))
    staged = SpecExecutor._stage_fields(spec, [{"nm": "x", "extra": 1}])
    assert staged == [{"extra": 1, "name": "x"}]
    assert list(staged[0]) == ["extra", "name"]


def test_input_records_are_not_mutated() -> None:
    spec = _probe(FieldSpec(name="b", type="string", source_name="a"))
    item: dict[str, object] = {"a": "A"}
    SpecExecutor._stage_fields(spec, [item])
    assert item == {"a": "A"}
