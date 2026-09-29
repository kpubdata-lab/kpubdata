#!/usr/bin/env python3
"""KPubData must not depend on KPubData Builder or KPubData Studio (#668).

ADR 0007 fixes the dependency direction as Studio -> Builder -> KPubData. Rules 1
and 2 say the reverse edges do not exist: this package never imports
`kpubdata_builder` or `kpubdata_studio`, and never declares either distribution
as a dependency. A rule without a gate is a wish, so this is the gate.

Two things are checked:

- every `.py` file under `src/` is parsed, and any `import`, `from ... import`,
  `importlib.import_module("...")` or `__import__("...")` that names a forbidden
  package fails;
- every quoted string in `pyproject.toml` whose requirement name normalises to
  `kpubdata-builder` or `kpubdata-studio` fails, as does a bare TOML key with that
  name (as `[tool.uv.sources]` would use). The file is scanned as text rather than
  parsed, because `tomllib` does not exist on Python 3.10 and one code path on
  every supported version is easier to trust than two.

Usage:
    python scripts/check_independence.py [--root PATH]
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
import warnings
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

FORBIDDEN_MODULES = ("kpubdata_builder", "kpubdata_studio")
FORBIDDEN_DISTRIBUTIONS = ("kpubdata-builder", "kpubdata-studio")

_QUOTED = re.compile(r"""["']([^"'\n]*)["']""")
_BARE_KEY = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)\s*=", re.MULTILINE)
_REQUIREMENT_NAME = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")
_IMPORT_FUNCTIONS = {"import_module", "__import__"}


def _normalise(name: str) -> str:
    """PEP 503 normalisation: runs of `-`, `_` and `.` compare equal."""
    return re.sub(r"[-_.]+", "-", name).lower()


def _is_forbidden_module(dotted: str) -> bool:
    top = dotted.split(".", 1)[0]
    return top in FORBIDDEN_MODULES


def import_violations(path: Path, root: Path) -> list[str]:
    """Imports of a forbidden package in one source file."""
    # Parsing only reads imports; a SyntaxWarning about a docstring escape is not
    # this gate's business and would bury its output.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", SyntaxWarning)
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    where = path.relative_to(root)
    found: list[str] = []
    for node in ast.walk(tree):
        names: list[str] = []
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names = [node.module]
        elif isinstance(node, ast.Call):
            func = node.func
            called = (
                func.attr
                if isinstance(func, ast.Attribute)
                else func.id
                if isinstance(func, ast.Name)
                else None
            )
            if called in _IMPORT_FUNCTIONS and node.args:
                first = node.args[0]
                if isinstance(first, ast.Constant) and isinstance(first.value, str):
                    names = [first.value]
        found.extend(
            f"{where}:{node.lineno}: imports {name}" for name in names if _is_forbidden_module(name)
        )
    return found


def dependency_violations(pyproject: Path, root: Path) -> list[str]:
    """Declarations of a forbidden distribution in pyproject.toml."""
    text = pyproject.read_text(encoding="utf-8")
    where = pyproject.relative_to(root)
    forbidden = {_normalise(name) for name in FORBIDDEN_DISTRIBUTIONS}
    found: list[str] = []
    for pattern, kind in ((_QUOTED, "requirement"), (_BARE_KEY, "key")):
        for match in pattern.finditer(text):
            value = match.group(1)
            name_match = _REQUIREMENT_NAME.match(value)
            if name_match and _normalise(name_match.group(1)) in forbidden:
                line = text.count("\n", 0, match.start()) + 1
                found.append(f"{where}:{line}: {kind} {value.strip()!r}")
    return found


def main(argv: list[str] | None = None) -> int:
    """Run both checks. Returns 0 when KPubData stands alone, 1 otherwise."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=REPO_ROOT)
    root: Path = parser.parse_args(argv).root.resolve()

    src = root / "src"
    pyproject = root / "pyproject.toml"
    problems: list[str] = []
    if not src.is_dir():
        problems.append(f"{src} does not exist, so nothing was checked")
    if not pyproject.is_file():
        problems.append(f"{pyproject} does not exist, so nothing was checked")
    if problems:
        for line in problems:
            print(f"  {line}", file=sys.stderr)
        return 1

    sources = sorted(src.rglob("*.py"))
    for path in sources:
        problems.extend(import_violations(path, root))
    problems.extend(dependency_violations(pyproject, root))

    if problems:
        print("KPubData depends on KPubData Builder or KPubData Studio.\n", file=sys.stderr)
        for line in problems:
            print(f"  {line}", file=sys.stderr)
        print(
            "\nADR 0007 Rules 1-2: dependencies flow Studio -> Builder -> KPubData only."
            "\nIf Builder needs something from here, add it to KPubData's public API.",
            file=sys.stderr,
        )
        return 1

    print(
        f"KPubData stands alone: {len(sources)} source files and pyproject.toml "
        f"name neither {' nor '.join(FORBIDDEN_DISTRIBUTIONS)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
