"""Reachability probe (#499).

In dataset addition, the only human-only step is applying at data.go.kr.
Which datasets await that was buried in documentation notes. An agent didn't
learn until hitting 403 while working on the spec—too late. This detects
which datasets need applications upfront.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from kpubdata._probe import (
    PROBE_STATUSES,
    ProbeResult,
    classify,
    merge_with_existing,
    render_apply_report,
    service_id_of,
    summarize,
    write_report,
)
from kpubdata.core.spec import find_spec
from kpubdata.core.status import DriftClassification
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
        """Rate limit means reachable—not a target for application.

        RateLimitError subclasses TransportError; reversed order would silently
        classify it as retired. That's what happened before being fixed.
        """
        assert classify(RateLimitError("quota exceeded"))[0] == "rate_limited"


class TestServiceIdGrouping:
    """Application is by service, not dataset."""

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
        """Report groups by service, not dataset—avoids appearing to need 3 apps."""
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
        assert set(payload) == {"probed_at", "runner", "results"}
        assert payload["runner"] == "local"
        assert payload["results"][0] == {
            "dataset_id": "datago.x",
            "service_id": "XSvc",
            "status": "application_required",
            "probed_at": _NOW,
            "detail": "",
            "http_status": None,
            "result_code": None,
            "latency_ms": None,
            "schema_hash": None,
            "classification": None,
        }

    def test_results_are_sorted_so_the_file_is_diffable(self, tmp_path: Path) -> None:
        out = tmp_path / "key-scope.json"

        write_report(
            [_result("datago.b", "S", "available"), _result("datago.a", "S", "available")], out
        )

        ids = [r["dataset_id"] for r in json.loads(out.read_text(encoding="utf-8"))["results"]]
        assert ids == sorted(ids)


class TestEvidenceFields:
    """The drift step reads the evidence fields off the report (#625, LIVE_PROBE.md).

    Each field is None where it could not be observed — inventing a value would
    invent a signal nobody measured."""

    def test_schema_hash_fingerprints_field_names_not_values(self) -> None:
        from kpubdata._probe import _schema_hash

        assert _schema_hash([{"b": 1, "a": 2}]) == _schema_hash([{"a": 9}, {"b": 0, "a": 1}])

    def test_schema_hash_moves_when_a_field_appears(self) -> None:
        from kpubdata._probe import _schema_hash

        assert _schema_hash([{"a": 1}]) != _schema_hash([{"a": 1, "b": 2}])

    def test_schema_hash_is_none_for_an_empty_page(self) -> None:
        from kpubdata._probe import _schema_hash

        assert _schema_hash([]) is None

    def test_classification_follows_the_documented_mapping(self) -> None:
        from kpubdata._probe import _classification_of

        assert _classification_of("available") == DriftClassification.HEALTHY
        assert _classification_of("retired") == DriftClassification.RETIRED
        # params_invalid says the probe config is wrong, and an unknown name is
        # not a signal anybody measured.
        assert _classification_of("params_invalid") is None
        assert _classification_of("not-a-status") is None

    def test_the_runner_is_recorded_in_the_header(self, tmp_path: Path) -> None:
        out = tmp_path / "probe-result.json"

        write_report([_result("datago.x", "XSvc", "available")], out, runner="github-actions")

        assert json.loads(out.read_text(encoding="utf-8"))["runner"] == "github-actions"

    def test_a_row_from_the_evidence_schema_survives_a_merge(self, tmp_path: Path) -> None:
        report = tmp_path / "probe-result.json"
        enriched = ProbeResult(
            dataset_id="datago.x",
            service_id="XSvc",
            status="available",
            probed_at=_NOW,
            http_status=200,
            latency_ms=342,
            schema_hash="a3f5c8d0e1b2",
            classification=DriftClassification.HEALTHY,
        )
        write_report([enriched], report)

        assert merge_with_existing([], report) == [enriched]

    def test_a_row_with_bogus_evidence_reads_as_none(self, tmp_path: Path) -> None:
        report = tmp_path / "probe-result.json"
        report.write_text(
            json.dumps(
                {
                    "probed_at": _NOW,
                    "results": [
                        {
                            "dataset_id": "datago.x",
                            "service_id": "XSvc",
                            "status": "available",
                            "probed_at": _NOW,
                            "classification": "NOT-A-SIGNAL",
                            "http_status": True,
                            "schema_hash": "",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

        merged = merge_with_existing([], report)

        assert merged[0].classification is None
        assert merged[0].http_status is None
        assert merged[0].schema_hash is None

    def test_a_successful_call_carries_its_evidence(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from typing import cast

        from kpubdata._probe import _call_and_classify, _schema_hash, new_probe_transport
        from kpubdata.config import KPubDataConfig
        from kpubdata.core import executor as executor_module
        from kpubdata.core.models import DatasetRef, RecordBatch

        spec = find_spec("datago.apt_trade")
        assert spec is not None

        class StubExecutor:
            def __init__(self, *, config: object, transport: object) -> None:
                pass

            def query(self, spec: object, ref: object, query: object) -> RecordBatch:
                return RecordBatch(
                    items=[{"dealAmount": "1,000", "aptNm": "래미안"}],
                    dataset=cast(DatasetRef, ref),
                )

        monkeypatch.setattr(executor_module, "SpecExecutor", StubExecutor)

        result = _call_and_classify(
            spec,
            KPubDataConfig(provider_keys={"datago": "probe-key"}),
            new_probe_transport(),
        )

        assert result.status == "available"
        assert result.http_status == 200
        assert result.result_code is None  # success does not parse the envelope code
        assert result.latency_ms is not None and result.latency_ms >= 0
        assert result.schema_hash == _schema_hash([{"dealAmount": "1,000", "aptNm": "래미안"}])
        assert result.classification is DriftClassification.HEALTHY

    def test_an_error_call_carries_its_codes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from kpubdata._probe import _call_and_classify, new_probe_transport
        from kpubdata.config import KPubDataConfig
        from kpubdata.core import executor as executor_module

        spec = find_spec("datago.apt_trade")
        assert spec is not None

        class StubExecutor:
            def __init__(self, *, config: object, transport: object) -> None:
                pass

            def query(self, spec: object, ref: object, query: object) -> object:
                raise AuthError("denied", status_code=403, provider_code="30")

        monkeypatch.setattr(executor_module, "SpecExecutor", StubExecutor)

        result = _call_and_classify(
            spec,
            KPubDataConfig(provider_keys={"datago": "probe-key"}),
            new_probe_transport(),
        )

        assert result.status == "application_required"
        assert result.http_status == 403
        assert result.result_code == "30"
        assert result.schema_hash is None
        assert result.classification is DriftClassification.APPLICATION_REQUIRED


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


class TestTheCodexFindings:
    """Regression cover for the review findings on #536."""

    def test_401_is_a_credential_problem_not_an_outage(self) -> None:
        """Falling through to temporarily_unavailable tells the caller to retry,
        when what is needed is a different key."""
        assert classify(TransportError("unauthorized", status_code=401))[0] == "auth_unknown"

    def test_401_as_the_transport_now_raises_it_is_still_auth_unknown(self) -> None:
        """HTTP 401 leaves the transport as AuthError (#786); the verdict must not
        become application_required, which is what an AuthError otherwise means."""
        assert classify(AuthError("unauthorized", status_code=401))[0] == "auth_unknown"
        assert classify(AuthError("not registered"))[0] == "application_required"

    def test_a_legacy_status_row_is_dropped(self, tmp_path: Path) -> None:
        """A report from the previous implementation holds statuses like "ok".
        Keeping them produces a report whose values are not in the vocabulary,
        and guessing a translation would invent a verdict nobody measured."""
        report = tmp_path / "legacy.json"
        report.write_text(
            json.dumps(
                {
                    "results": [
                        {"dataset_id": "datago.old", "status": "ok"},
                        {"dataset_id": "datago.new", "status": "available"},
                    ]
                }
            ),
            encoding="utf-8",
        )
        merged = merge_with_existing([], report)
        assert [r.dataset_id for r in merged] == ["datago.new"]

    def test_every_retained_status_is_in_the_vocabulary(self, tmp_path: Path) -> None:
        report = tmp_path / "mixed.json"
        report.write_text(
            json.dumps(
                {
                    "results": [
                        {"dataset_id": "a", "status": s}
                        for s in ("ok", "gone", "auth-403", "params-400", "available")
                    ]
                }
            ),
            encoding="utf-8",
        )
        for result in merge_with_existing([], report):
            assert result.status in PROBE_STATUSES

    @pytest.mark.parametrize("body", ['{"results": null}', '{"results": 3}', '{"results": {}}'])
    def test_a_non_list_results_container_does_not_lose_the_new_rows(
        self, tmp_path: Path, body: str
    ) -> None:
        report = tmp_path / "malformed.json"
        report.write_text(body, encoding="utf-8")
        merged = merge_with_existing([_result("datago.a", "SvcA", "available")], report)
        assert [r.dataset_id for r in merged] == ["datago.a"]
