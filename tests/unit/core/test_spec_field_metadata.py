"""Every bundled spec field has a display name, and its unit and meaning where known (#877).

Studio showed raw provider field names and bare numbers: no spec set ``title`` or
``unit``, so ``dealAmount`` read ``101300`` with no unit. These hold the bundled specs to
what #877 filled in.
"""

from __future__ import annotations

from kpubdata import discover_specs


def test_every_field_has_a_korean_title() -> None:
    untitled = [
        f"{spec.id}.{field.name}"
        for spec in discover_specs()
        for field in spec.fields
        if not (field.title and any("가" <= ch <= "힣" for ch in field.title))
    ]

    assert untitled == []


def test_money_and_measurements_carry_their_unit() -> None:
    units = {
        (spec.id, field.name): field.unit for spec in discover_specs() for field in spec.fields
    }

    assert units[("datago.apt_trade", "dealAmount")] == "만원"
    assert units[("datago.apt_rent", "deposit")] == "만원"
    assert units[("datago.apt_trade", "excluUseAr")] == "㎡"
    assert units[("datago.air_quality", "pm10Value")] == "㎍/㎥"
    assert units[("datago.metro_fare", "gnrlCardFare")] == "원"
    assert units[("datago.ocean_buoy", "wtem")] == "°C"


def test_meanings_are_declared_and_agree_with_storage() -> None:
    kinds = {
        (spec.id, field.name): field.semantic_kind
        for spec in discover_specs()
        for field in spec.fields
    }

    assert kinds[("datago.apt_trade", "dealAmount")] == "measure"
    assert kinds[("datago.apt_rent", "contractTerm")] == "period"
    assert kinds[("datago.air_quality", "dataTime")] == "date"
    assert kinds[("datago.hospital_info", "ykiho")] == "code"
    # The loader refuses a meaning its storage type cannot hold (ADR 0006), so a code
    # kept as an integer is left without one rather than mislabelled.
    assert kinds[("datago.tour_kor_area", "areacode")] is None
    declared = sum(1 for kind in kinds.values() if kind is not None)
    assert declared >= 220
