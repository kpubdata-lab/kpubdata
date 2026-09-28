#!/usr/bin/env python3
"""Write a version into every file that declares it (#718).

A release changes the version in more than one place. `pyproject.toml` declares it and
`uv.lock` repeats it under the project's own package entry; `package.json` declares it
and `package-lock.json` repeats it twice. Writing only the first leaves the repository
in a state its own gates refuse:

    error: The lockfile at `uv.lock` needs to be updated, but `--check` was provided.

That is how kpubdata-builder#744 failed — nine checks, from a one-line version change.

Only the project's own version is touched. Running `uv lock` or `npm install` instead
would also be free to raise transitive dependencies, which is a dependency change
smuggled into a release pull request, where nobody is looking for one.

**A substitution that changes nothing is an error here.** The failure this guards
against is silent: a regular expression that stops matching writes the file back
unchanged, the workflow reports success, and the release carries the old version. So
every file that exists must have been changed, and the count is printed.

**Every file is checked before any file is written.** The first draft wrote them one
by one and stopped on the first mismatch, leaving `pyproject.toml` at the new version
and `uv.lock` at the old one — a repository in exactly the half-updated state this
script exists to prevent.

Usage:
    python3 scripts/set_version.py 0.4.0
    python3 scripts/set_version.py 0.4.0 --root ../kpubdata-studio
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


class VersionWriteError(Exception):
    """A file that declares the version could not be updated."""


def _pyproject(text: str, version: str) -> tuple[str, int]:
    """The `[project] version` field, which is the first `version = ` at column 0."""
    return re.subn(r'^version = "[^"]+"', f'version = "{version}"', text, count=1, flags=re.M)


def _uv_lock(text: str, version: str, name: str) -> tuple[str, int]:
    """The project's own entry in `uv.lock`, found by its `source = { editable = "." }`.

    Matching on the name alone would also rewrite a dependency that happens to share
    it; the editable source is what makes an entry *this* project.
    """
    pattern = re.compile(
        r'(name = "' + re.escape(name) + r'"\nversion = ")[^"]+("\nsource = \{ editable = "\." \})'
    )
    return pattern.subn(r"\g<1>" + version + r"\g<2>", text, count=1)


def _package_json(text: str, version: str) -> tuple[str, int]:
    """The manifest's own `"version"`, which precedes any dependency block."""
    return re.subn(r'("version"\s*:\s*")[^"]+(")', r"\g<1>" + version + r"\g<2>", text, count=1)


def _package_lock(text: str, version: str) -> tuple[str, int]:
    """`package-lock.json` repeats the version at the top and again under `""`.

    npm writes both, and `npm ci` compares them against `package.json`. Updating one
    is worse than updating neither, because the mismatch surfaces at install time.
    """
    text, first = re.subn(
        r'("version"\s*:\s*")[^"]+(")', r"\g<1>" + version + r"\g<2>", text, count=1
    )
    text, second = re.subn(
        r'("": \{\n      "name": "[^"]+",\n      "version": ")[^"]+(")',
        r"\g<1>" + version + r"\g<2>",
        text,
        count=1,
    )
    return text, first + second


def project_name(root: Path) -> str:
    """The distribution name, read from the file that declares it.

    Not the directory name: a checkout can sit anywhere, and a CI runner's path is not
    the package's identity. Taking it from the directory made this script fail against
    a copy of a repository, which is precisely how a release gets tested.
    """
    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        match = re.search(r'^name = "([^"]+)"', pyproject.read_text(encoding="utf-8"), re.M)
        if match:
            return match.group(1)
    manifest = root / "package.json"
    if manifest.exists():
        match = re.search(r'"name"\s*:\s*"([^"]+)"', manifest.read_text(encoding="utf-8"))
        if match:
            return match.group(1)
    raise VersionWriteError(f"cannot tell what project {root} is: no name is declared")


def set_version(root: Path, version: str) -> dict[str, int]:
    """Write ``version`` into every declaring file present under ``root``.

    Returns:
        A map of the relative path to the number of substitutions made.

    Raises:
        VersionWriteError: A file exists but nothing in it matched, or no declaring
            file was found at all. Nothing is written in either case.
    """
    name = project_name(root)
    handlers = {
        "pyproject.toml": lambda t: _pyproject(t, version),
        "uv.lock": lambda t: _uv_lock(t, version, name),
        "package.json": lambda t: _package_json(t, version),
        "package-lock.json": lambda t: _package_lock(t, version),
    }

    # Work out every change first. A partial write is the failure mode this guards
    # against, so it must not be able to produce one on its way to reporting it.
    planned: list[tuple[Path, str, str, int]] = []
    for relative, handler in handlers.items():
        path = root / relative
        if not path.exists():
            continue
        new, count = handler(path.read_text(encoding="utf-8"))
        if count == 0:
            raise VersionWriteError(
                f"{relative} exists but declares no version this script recognises. "
                "Writing it back unchanged would publish the old version under the new "
                "tag. Nothing was written."
            )
        planned.append((path, relative, new, count))
    if not planned:
        raise VersionWriteError(f"no file under {root} declares a version")

    written: dict[str, int] = {}
    for path, relative, new, count in planned:
        path.write_text(new, encoding="utf-8")
        written[relative] = count
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write the version into every declaring file.")
    parser.add_argument("version")
    parser.add_argument("--root", type=Path, default=REPO_ROOT, help="Repository root.")
    args = parser.parse_args(argv)

    try:
        written = set_version(args.root, args.version)
    except VersionWriteError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    for relative, count in written.items():
        print(f"{relative}: {count} substitution(s) -> {args.version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
