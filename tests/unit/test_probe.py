"""도달성 프로브 (#499).

데이터셋 추가에서 사람만 할 수 있는 단계는 data.go.kr 활용신청 하나인데, 어느
데이터셋이 그걸 기다리는지가 문서 비고란 텍스트에만 있었다. 에이전트는 spec 작업을
시작한 뒤에야 403 으로 알게 됐다 — 되돌릴 작업을 먼저 하는 셈이다.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from kpubdata._probe import (
    ProbeResult,
    classify,
    merge_with_existing,
    render_apply_report,
    service_id_of,
    summarize,
    write_report,
)
from kpubdata.core.spec import find_spec
from kpubdata.exceptions import (
    AuthError,
    DatasetNotFoundError,
    InvalidRequestError,
    ParseError,
    RateLimitError,
    ServiceUnavailableError,
    TransportError,
    TransportTimeoutError,
)

_NOW = datetime.now(tz=timezone.utc).isoformat(timespec="seconds")


def _result(dataset_id: str, service_id: str, status: str) -> ProbeResult:
    return ProbeResult(dataset_id=dataset_id, service_id=service_id, status=status, probed_at=_NOW)


class TestClassification:
    @pytest.mark.parametrize(
        ("error", "expected"),
        [
            (None, "available"),
            (AuthError("not activated"), "application_required"),
            (TransportError("forbidden", status_code=403), "application_required"),
            (InvalidRequestError("missing param"), "params_invalid"),
            (DatasetNotFoundError("gone"), "retired"),
            (ServiceUnavailableError("down"), "temporarily_unavailable"),
            (TransportError("boom", status_code=500), "temporarily_unavailable"),
            (ParseError("bad body"), "insufficient_metadata"),
        ],
    )
    def test_each_failure_lands_in_its_bucket(
        self, error: BaseException | None, expected: str
    ) -> None:
        assert classify(error)[0] == expected

    def test_a_rate_limit_counts_as_reachable(self) -> None:
        """한도 초과는 "도달은 된다" 는 뜻이다 — 활용신청 대상이 아니다.

        ``RateLimitError`` 가 ``TransportError`` 의 하위라, 판정 순서를 뒤집으면
        조용히 ``gone`` 으로 분류된다. 실제로 그렇게 짰다가 고쳤다.
        """
        assert classify(RateLimitError("quota exceeded"))[0] == "rate_limited"


class TestServiceIdGrouping:
    """활용신청은 데이터셋이 아니라 **서비스** 단위로 한다."""

    def test_datasets_sharing_a_service_share_an_id(self) -> None:
        ids = {
            service_id_of(spec)
            for dataset_id in ("datago.air_quality", "datago.air_station")
            if (spec := find_spec(dataset_id)) is not None
        }

        assert ids == {"ArpltnInforInqireSvc"}

    def test_a_different_service_gets_a_different_id(self) -> None:
        spec = find_spec("datago.apt_trade")
        assert spec is not None

        assert service_id_of(spec) != "ArpltnInforInqireSvc"


class TestApplyReport:
    def test_it_groups_by_service_not_dataset(self) -> None:
        """이게 보고서의 요점이다 — 데이터셋별로 나열하면 3번 신청해야 하는 것처럼 보인다."""
        results = [
            _result("datago.air_quality", "ArpltnInforInqireSvc", "application_required"),
            _result("datago.air_station", "ArpltnInforInqireSvc", "application_required"),
            _result("datago.airkorea_forecast", "ArpltnInforInqireSvc", "application_required"),
        ]

        report = render_apply_report(results)

        assert "서비스 1건을 신청하면 데이터셋 3종이 풀립니다" in report
        assert report.count("## ") == 1

    def test_only_pending_datasets_appear(self) -> None:
        results = [
            _result("datago.ok", "OkSvc", "available"),
            _result("datago.broken", "GoneSvc", "retired"),
            _result("datago.pending", "PendingSvc", "application_required"),
        ]

        report = render_apply_report(results)

        assert "PendingSvc" in report
        assert "OkSvc" not in report
        assert "GoneSvc" not in report

    def test_nothing_pending_says_so(self) -> None:
        report = render_apply_report([_result("datago.ok", "OkSvc", "available")])

        assert "없습니다" in report


class TestReportFile:
    def test_it_writes_the_documented_shape(self, tmp_path: Path) -> None:
        out = tmp_path / "key-scope.json"

        write_report([_result("datago.x", "XSvc", "application_required")], out)

        payload = json.loads(out.read_text(encoding="utf-8"))
        assert set(payload) == {"probed_at", "results"}
        assert payload["results"][0] == {
            "dataset_id": "datago.x",
            "service_id": "XSvc",
            "status": "application_required",
            "probed_at": _NOW,
            "detail": "",
        }

    def test_results_are_sorted_so_the_file_is_diffable(self, tmp_path: Path) -> None:
        out = tmp_path / "key-scope.json"

        write_report(
            [_result("datago.b", "S", "available"), _result("datago.a", "S", "available")], out
        )

        ids = [r["dataset_id"] for r in json.loads(out.read_text(encoding="utf-8"))["results"]]
        assert ids == sorted(ids)


def test_summarize_counts_each_bucket() -> None:
    results = [
        _result("a", "S", "available"),
        _result("b", "S", "application_required"),
        _result("c", "S", "application_required"),
    ]

    assert summarize(results) == {"available": 1, "application_required": 2}


class TestProviderResultCodeDecides:
    """The code carries more than the exception type does.

    A 403 can mean "you never applied" (30) or "your IP is not registered" (32),
    and those need different advice: one is an application, the other is a
    network location. Classifying both as application_required would send a user
    to fill in a form that changes nothing.
    """

    @pytest.mark.parametrize(
        ("code", "expected"),
        [
            ("01", "temporarily_unavailable"),
            ("02", "temporarily_unavailable"),
            ("10", "params_invalid"),
            ("12", "retired"),
            ("20", "application_required"),
            ("22", "rate_limited"),
            ("30", "application_required"),
            ("31", "application_required"),
            ("32", "auth_unknown"),
        ],
    )
    def test_the_documented_codes_map(self, code: str, expected: str) -> None:
        error = AuthError("provider said so", provider_code=code)
        assert classify(error)[0] == expected

    def test_the_code_wins_over_the_exception_type(self) -> None:
        """AuthError would be application_required on type alone; code 32 is not."""
        assert classify(AuthError("unregistered ip", provider_code="32"))[0] == "auth_unknown"

    def test_an_unknown_code_falls_back_to_the_exception_type(self) -> None:
        assert classify(AuthError("?", provider_code="99"))[0] == "application_required"

    def test_a_blank_code_falls_back_to_the_exception_type(self) -> None:
        assert classify(AuthError("?", provider_code=""))[0] == "application_required"


class TestSubclassOrdering:
    """RateLimitError and TransportTimeoutError both subclass TransportError.

    Checking the base first buried them, and a quota overrun classified as
    retirement -- telling a user to abandon something they only had to wait for.
    """

    def test_rate_limit_is_not_retired(self) -> None:
        assert classify(RateLimitError("quota"))[0] == "rate_limited"

    def test_timeout_is_a_network_error_not_an_outage(self) -> None:
        assert classify(TransportTimeoutError("timed out"))[0] == "network_error"

    def test_a_transport_error_with_no_status_is_a_network_error(self) -> None:
        """No HTTP exchange completed: DNS, TLS, connection refused."""
        assert classify(TransportError("dns failure"))[0] == "network_error"

    @pytest.mark.parametrize(
        ("status", "expected"),
        [
            (400, "params_invalid"),
            (403, "application_required"),
            (429, "rate_limited"),
            (500, "temporarily_unavailable"),
            (503, "temporarily_unavailable"),
        ],
    )
    def test_status_codes_without_a_provider_code(self, status: int, expected: str) -> None:
        assert classify(TransportError("http", status_code=status))[0] == expected


class TestRetirementIsSeparateFromAnOutage:
    def test_a_missing_service_is_retired(self) -> None:
        assert classify(DatasetNotFoundError("no such service"))[0] == "retired"

    def test_a_5xx_is_not_retired(self) -> None:
        assert classify(ServiceUnavailableError("down"))[0] == "temporarily_unavailable"

    def test_an_undecodable_body_is_not_retired(self) -> None:
        """The endpoint answered. Calling that retired would be wrong."""
        assert classify(ParseError("not xml"))[0] == "insufficient_metadata"


class TestTheReportIsMerged:
    def test_probing_one_dataset_keeps_the_others(self, tmp_path: Path) -> None:
        """--dataset used to overwrite the report with a single row, discarding
        every other verdict. Rebuilding it means calling every provider again."""
        report = tmp_path / "key-scope.json"
        write_report(
            [
                _result("datago.a", "SvcA", "available"),
                _result("datago.b", "SvcB", "application_required"),
            ],
            report,
        )
        merged = merge_with_existing([_result("datago.b", "SvcB", "available")], report)
        by_id = {r.dataset_id: r.status for r in merged}
        assert by_id == {"datago.a": "available", "datago.b": "available"}

    def test_a_corrupt_report_does_not_lose_the_new_results(self, tmp_path: Path) -> None:
        report = tmp_path / "broken.json"
        report.write_text("{ truncated", encoding="utf-8")
        merged = merge_with_existing([_result("datago.a", "SvcA", "available")], report)
        assert [r.dataset_id for r in merged] == ["datago.a"]

    def test_a_missing_report_is_not_an_error(self, tmp_path: Path) -> None:
        merged = merge_with_existing(
            [_result("datago.a", "SvcA", "available")], tmp_path / "absent.json"
        )
        assert len(merged) == 1


class TestTheWriteIsAtomic:
    def test_no_temporary_file_is_left_behind(self, tmp_path: Path) -> None:
        report = tmp_path / "key-scope.json"
        write_report([_result("datago.a", "SvcA", "available")], report)
        assert [p.name for p in tmp_path.iterdir()] == ["key-scope.json"]

    def test_the_report_is_valid_json_after_writing(self, tmp_path: Path) -> None:
        report = tmp_path / "key-scope.json"
        write_report([_result("datago.a", "SvcA", "available")], report)
        payload = json.loads(report.read_text(encoding="utf-8"))
        assert payload["results"][0]["dataset_id"] == "datago.a"
