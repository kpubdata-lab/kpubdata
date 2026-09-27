"""Execution path and verify path must use same implementation.

``SpecExecutor._check_error``/``_extract_items`` is module function
``check_payload_error``/``extract_items`` were implemented **separately**. Module side is used by
``make verify`` and ``make record`` and method side is used by actual queries. As two diverged
four things were added to module side only — ``err_field`` style, ``{operation}``
substitution, KorService-like top-level ``resultCode`` fallback, ``resultMsg``/``errMsg`` fallback,
and ``extract_items`` side had ``neis_double_list`` and ``$`` root.

So "verify pass" does not guarantee verify of execution path. current repository has
specs in(23 datago/localdata specs)do not use that feature so nothing breaks immediately but
however when specs using that feature arrive verify passes but execution fails.
"""

from __future__ import annotations

import dataclasses
import pathlib

import pytest

from kpubdata.core.executor import SpecExecutor, check_payload_error, extract_items
from kpubdata.core.spec import SpecDefinition, load_spec_file
from kpubdata.exceptions import ProviderResponseError, RateLimitError

_SPEC_DIR = pathlib.Path(__file__).resolve().parents[3] / "src" / "kpubdata" / "specs" / "datago"


@pytest.fixture()
def spec() -> SpecDefinition:
    return load_spec_file(sorted(_SPEC_DIR.glob("*.yaml"))[0])


@pytest.fixture()
def executor() -> SpecExecutor:
    return SpecExecutor.__new__(SpecExecutor)


def _with_error_style(spec: SpecDefinition, style: str) -> SpecDefinition:
    error = dataclasses.replace(spec.response.error, style=style)
    return dataclasses.replace(spec, response=dataclasses.replace(spec.response, error=error))


class TestTheRuntimePathHasTheSameCapabilities:
    def test_root_items_path(self, spec: SpecDefinition, executor: SpecExecutor) -> None:
        """``$`` points to root (kosis top-level array). previously was empty list."""
        rooted = dataclasses.replace(
            spec, response=dataclasses.replace(spec.response, items_path="$")
        )

        assert executor._extract_items(rooted, {"x": 1}) == [{"x": 1}]

    def test_err_field_style_accepts_a_success(
        self, spec: SpecDefinition, executor: SpecExecutor
    ) -> None:
        """kosis-like has no code system — previously success response was actually failure."""
        executor._check_error(_with_error_style(spec, "err_field"), {"result": [{"a": 1}]})

    def test_err_field_style_rejects_a_failure(
        self, spec: SpecDefinition, executor: SpecExecutor
    ) -> None:
        with pytest.raises(ProviderResponseError, match="quota exceeded"):
            executor._check_error(_with_error_style(spec, "err_field"), {"err": "quota exceeded"})

    def test_the_top_level_result_code_fallback(
        self, spec: SpecDefinition, executor: SpecExecutor
    ) -> None:
        """KorService-like returns errors flat at top level outside envelope."""
        with pytest.raises(RateLimitError):
            executor._check_error(spec, {"resultCode": "22", "resultMsg": "LIMITED"})


class TestBothPathsAgree:
    """whether both paths return same answer for same input — pin to prevent divergence."""

    @pytest.mark.parametrize(
        "payload",
        [
            {"response": {"header": {"resultCode": "00"}, "body": {"items": {"item": []}}}},
            {"resultCode": "22", "resultMsg": "LIMITED"},
            {"err": "boom"},
            {"unexpected": True},
        ],
    )
    def test_check_error_agrees(
        self, spec: SpecDefinition, executor: SpecExecutor, payload: dict[str, object]
    ) -> None:
        def _outcome(call: object) -> str:
            try:
                call()  # type: ignore[operator]
            except Exception as exc:
                return type(exc).__name__
            return "ok"

        assert _outcome(lambda: executor._check_error(spec, payload)) == _outcome(
            lambda: check_payload_error(spec, payload)
        )

    @pytest.mark.parametrize(
        "payload",
        [
            {"response": {"body": {"items": {"item": [{"a": 1}]}}}},
            {"response": {"body": {"items": {}}}},
            {},
        ],
    )
    def test_extract_items_agrees(
        self, spec: SpecDefinition, executor: SpecExecutor, payload: dict[str, object]
    ) -> None:
        assert executor._extract_items(spec, payload) == extract_items(spec, payload)
