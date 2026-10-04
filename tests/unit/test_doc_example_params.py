"""Documented examples pass parameter names the dataset's spec declares (#790).

``API_SPEC.md`` showed ``dataset.list(lawd_code="11680", deal_ym="202503")`` for
``datago.apt_trade``, whose spec declares ``LAWD_CD`` and ``DEAL_YMD``. A filter keyword
is sent to the provider verbatim, so the example could not have worked. This reads the
Python examples of the public documents and checks every filter keyword of a call on a
spec-backed dataset against that spec.

A dataset with no spec (a catalogue entry) declares no parameter names to check against,
so its examples are not covered.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from kpubdata import find_spec

_ROOT = Path(__file__).resolve().parents[2]
_DOCUMENTS = ("API_SPEC.md", "README.md", "README.en.md", "docs/quickstart.md")
_BLOCK = re.compile(r"```python\n(.*?)```", re.DOTALL)
_CALLS = frozenset({"list", "list_all", "call_raw"})
#: Keywords the library reads itself rather than sending as a filter.
_CANONICAL = frozenset(
    {"page", "page_size", "cursor", "start_date", "end_date", "fields", "sort", "operation"}
)


def _dataset_id(node: ast.expr) -> str | None:
    """The id in ``<anything>.dataset("<id>")``."""
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "dataset"
        and node.args
        and isinstance(node.args[0], ast.Constant)
        and isinstance(node.args[0].value, str)
    ):
        return node.args[0].value
    return None


def example_calls(text: str) -> list[tuple[str, str, tuple[str, ...]]]:
    """``(dataset id, method, filter keywords)`` of each example call that names its dataset.

    A variable bound to a dataset keeps its binding across code blocks, as a reader
    follows it down the page.
    """
    bound: dict[str, str] = {}
    calls: list[tuple[str, str, tuple[str, ...]]] = []
    for block in _BLOCK.findall(text):
        try:
            tree = ast.parse(block)
        except SyntaxError:
            continue  # a shell transcript or a fragment, not runnable Python
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and (found := _dataset_id(node.value)):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        bound[target.id] = found
        for node in ast.walk(tree):
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in _CALLS
            ):
                continue
            receiver = node.func.value
            dataset_id = _dataset_id(receiver) or (
                bound.get(receiver.id) if isinstance(receiver, ast.Name) else None
            )
            if dataset_id is None:
                continue
            keywords = tuple(k.arg for k in node.keywords if k.arg and k.arg not in _CANONICAL)
            calls.append((dataset_id, node.func.attr, keywords))
    return calls


def undeclared(text: str) -> list[str]:
    """Each filter keyword an example passes that its dataset's spec does not declare."""
    problems: list[str] = []
    for dataset_id, method, keywords in example_calls(text):
        spec = find_spec(dataset_id)
        if spec is None:
            continue
        declared = {param.exposed_name for param in spec.params}
        problems.extend(
            f"{dataset_id}.{method}({keyword}=…): the spec declares {sorted(declared)}"
            for keyword in keywords
            if keyword not in declared
        )
    return problems


@pytest.mark.parametrize("document", _DOCUMENTS)
def test_examples_use_the_parameter_names_the_spec_declares(document: str) -> None:
    path = _ROOT / document
    if not path.is_file():
        pytest.skip(f"{document} is not in this repository")

    assert undeclared(path.read_text(encoding="utf-8")) == []


def test_api_spec_has_examples_the_check_reads() -> None:
    """Guards the guard: a parser that finds nothing would pass every document."""
    calls = example_calls((_ROOT / "API_SPEC.md").read_text(encoding="utf-8"))

    assert ("datago.apt_trade", "list", ("LAWD_CD", "DEAL_YMD")) in calls
    assert ("datago.apt_trade", "call_raw", ("LAWD_CD", "DEAL_YMD")) in calls


def test_the_names_the_example_used_to_pass_are_refused() -> None:
    text = (
        "```python\n"
        'dataset = client.dataset("datago.apt_trade")\n'
        'result = dataset.list(lawd_code="11680", deal_ym="202503", page_size=10)\n'
        "```\n"
    )

    problems = undeclared(text)

    assert [problem.split(":")[0] for problem in problems] == [
        "datago.apt_trade.list(lawd_code=…)",
        "datago.apt_trade.list(deal_ym=…)",
    ]
