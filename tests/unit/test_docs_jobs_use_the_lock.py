"""The docs jobs build with the locked docs extra, not a floating pip install (#874).

An unpinned ``pip install mkdocs-material`` let a release outside the declared
range turn ``mkdocs build --strict`` red on an unrelated day. Both docs jobs now
resolve the docs extra from ``uv.lock`` through uv, with the shared uv cache.
"""

from __future__ import annotations

from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]


def _text(name: str) -> str:
    return (_ROOT / ".github/workflows" / name).read_text(encoding="utf-8")


def test_neither_docs_job_pip_installs_mkdocs() -> None:
    for name in ("docs.yml", "ci.yml"):
        assert "pip install mkdocs-material" not in _text(name), name


def test_both_docs_jobs_resolve_the_docs_extra_from_the_lock() -> None:
    for name in ("docs.yml", "ci.yml"):
        text = _text(name)
        assert "uv sync --extra docs" in text, name
        assert "uv run mkdocs build --strict" in text, name
        assert "enable-cache: true" in text, name
