#!/usr/bin/env python3
"""Licence inventory of what this repository depends on and bundles (#847).

``uv.lock`` says WHICH packages are used but not under what licence, and the MIT
``LICENSE`` of this repository says nothing about any of them. This script keeps two
things next to each other:

* ``docs/compliance/license_inventory.json`` -- one record per locked package (name,
  version, scope, licence as the package declares it, source URL) and one per group of
  bundled assets. It is written from the installed package metadata.
* ``THIRD_PARTY_NOTICES.md`` -- the same facts as a readable notice, written from the
  JSON alone.

It does not judge a licence. A package whose declared licence is empty, or is not one
of the plainly permissive identifiers below, is listed as ``needs review`` and left to
the maintainer and legal review; a match here is a string comparison, not a legal
conclusion.

Usage::

    uv sync --frozen --all-extras
    uv run python scripts/license_inventory.py            # rewrite both files
    uv run python scripts/license_inventory.py --check    # fail on drift (CI)

``--check`` needs no installed packages: it compares the lock file and ``git ls-files``
with the recorded JSON, and the JSON with the notice. So a dependency added to the lock
without a recorded licence fails the gate.
"""

from __future__ import annotations

import argparse
import importlib
import json
import re
import subprocess
import sys
from collections.abc import Iterable
from importlib import metadata
from pathlib import Path
from typing import Any

# tomllib is 3.11+; on 3.10 the dev lock carries tomli.
tomllib = importlib.import_module("tomllib" if sys.version_info >= (3, 11) else "tomli")

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "uv.lock"
INVENTORY = ROOT / "docs" / "compliance" / "license_inventory.json"
NOTICES = ROOT / "THIRD_PARTY_NOTICES.md"

#: Declared licences matched as plain permissive identifiers. Everything else, and every
#: empty declaration, is ``needs review``. This is a string match, not legal advice.
_PERMISSIVE = ("MIT", "BSD", "APACHE", "ISC", "PSF", "PYTHON SOFTWARE FOUNDATION", "0BSD")

#: Tracked file types that are assets and not code or data tables.
_ASSET_SUFFIXES = (
    ".png",
    ".gif",
    ".jpg",
    ".jpeg",
    ".svg",
    ".ico",
    ".ttf",
    ".otf",
    ".woff",
    ".woff2",
)

#: Bundled assets that are not Python packages. ``paths`` are ``git ls-files`` globs.
#: ``origin`` and ``terms`` say who made it and under what; none of it is relicensed by
#: the MIT ``LICENSE`` unless ``terms`` says it was made here.
ASSETS: list[dict[str, Any]] = [
    {
        "id": "terminal-captures",
        "paths": ["docs/assets/terminal/*"],
        "kind": "image (GIF)",
        "in_wheel": False,
        "origin": "recorded from this project's own CLI and examples (docs/terminal-captures.md)",
        "terms": "made in this repository; MIT",
        "status": "recorded",
    },
    {
        "id": "dataset-metadata-and-status",
        "paths": ["src/kpubdata/dataset_metadata.json", "src/kpubdata/dataset_status.json"],
        "kind": "data file",
        "in_wheel": True,
        "origin": "written in this repository (verification levels and dates)",
        "terms": "made in this repository; MIT",
        "status": "recorded",
    },
    {
        "id": "dataset-specs",
        "paths": ["src/kpubdata/specs/*"],
        "kind": "data file (YAML specs)",
        "in_wheel": True,
        "origin": "written in this repository from each provider's public usage guide",
        "terms": (
            "structure written here; names, parameter descriptions and per-dataset terms "
            "declared in the spec's license field follow the provider (docs/policy/terms-matrix.md)"
        ),
        "status": "needs review",
    },
    {
        "id": "provider-catalogues",
        "paths": ["src/kpubdata/providers/*/catalogue.json"],
        "kind": "data file (dataset catalogues)",
        "in_wheel": True,
        "origin": "dataset names and identifiers taken from each provider's public listing",
        "terms": "facts about third-party datasets; provider terms are not recorded per entry",
        "status": "needs review",
    },
    {
        "id": "recorded-fixtures",
        "paths": ["tests/fixtures/*"],
        "kind": "recorded API responses",
        "in_wheel": False,
        "origin": "recorded from live provider APIs by the recording workflow",
        "terms": (
            "third-party data under each provider's own terms (for example KOGL, the Korean "
            "Open Government License marks, set per service on data.go.kr); NOT relicensed "
            "as MIT, see docs/policy/terms-matrix.md"
        ),
        "status": "needs review",
    },
]


def locked_packages() -> dict[str, dict[str, Any]]:
    """Return ``{name==version: lock entry}`` for every package in ``uv.lock`` but this one."""
    data = tomllib.loads(LOCK.read_text(encoding="utf-8"))
    out: dict[str, dict[str, Any]] = {}
    for pkg in data["package"]:
        if pkg["name"] == "kpubdata":
            continue
        out[f"{pkg['name']}=={pkg['version']}"] = pkg
    return out


def scopes() -> dict[str, str]:
    """Classify each locked package: ``runtime``, ``extra:<name>`` or ``dev``."""
    data = tomllib.loads(LOCK.read_text(encoding="utf-8"))
    by_name: dict[str, list[dict[str, Any]]] = {}
    root: dict[str, Any] = {}
    for pkg in data["package"]:
        if pkg["name"] == "kpubdata":
            root = pkg
        else:
            by_name.setdefault(pkg["name"], []).append(pkg)

    def closure(seeds: Iterable[str]) -> set[str]:
        seen: set[str] = set()
        todo = list(seeds)
        while todo:
            name = todo.pop()
            if name in seen or name not in by_name:
                continue
            seen.add(name)
            for pkg in by_name[name]:
                todo.extend(d["name"] for d in pkg.get("dependencies", []))
        return seen

    result: dict[str, str] = {}
    for name in closure(d["name"] for d in root.get("dependencies", [])):
        result[name] = "runtime"
    for extra, deps in sorted(root.get("optional-dependencies", {}).items()):
        if extra == "dev":
            continue
        for name in sorted(closure(d["name"] for d in deps)):
            result.setdefault(name, f"extra:{extra}")
    for name in by_name:
        result.setdefault(name, "dev")
    return result


def declared_license(dist: metadata.Distribution) -> str:
    """The licence a package declares, from its own metadata; ``""`` when it declares none."""
    md = dist.metadata
    expression = (md.get("License-Expression") or "").strip()
    if expression:
        return expression
    text = " ".join((md.get("License") or "").split())
    if text and len(text) <= 80:
        return text
    classifiers = [
        c.rsplit("::", 1)[-1].strip()
        for c in md.get_all("Classifier") or []
        if c.startswith("License ::")
    ]
    if classifiers:
        return "; ".join(classifiers)
    return ""


def status_of(license_text: str) -> str:
    """``recorded`` for a plainly permissive identifier, ``needs review`` otherwise."""
    upper = license_text.upper()
    if not upper:
        return "needs review"
    if re.search(r"\b(AND|OR|WITH)\b", upper) and not all(
        any(p in part for p in _PERMISSIVE) for part in re.split(r"\s+(?:AND|OR)\s+", upper)
    ):
        return "needs review"
    if any(word in upper for word in ("GPL", "MPL", "EUPL", "CDDL", "EPL", "UNKNOWN")):
        return "needs review"
    return "recorded" if any(p in upper for p in _PERMISSIVE) else "needs review"


def source_url(dist: metadata.Distribution | None, name: str) -> str:
    if dist is not None:
        urls = dist.metadata.get_all("Project-URL") or []
        for url in urls:
            label, _, value = url.partition(",")
            if label.strip().lower() in {"homepage", "home", "source", "repository"}:
                return value.strip()
        home = dist.metadata.get("Home-page")
        if home:
            return str(home)
    return f"https://pypi.org/project/{name}/"


def build_packages(previous: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Records for every locked package, from installed metadata where available."""
    scope = scopes()
    out: dict[str, dict[str, Any]] = {}
    for key, pkg in sorted(locked_packages().items()):
        name, version = pkg["name"], pkg.get("version", "")
        try:
            dist: metadata.Distribution | None = metadata.distribution(name)
        except metadata.PackageNotFoundError:
            dist = None
        old = previous.get(key)
        if dist is not None and dist.version == version:
            lic, url, basis = declared_license(dist), source_url(dist, name), "installed"
        elif old:
            lic, url, basis = old["license"], old["source"], old["basis"]  # kept as recorded
        elif dist is not None:
            # Another version of the same package is installed; its declaration is
            # shown, but it is not this version's.
            lic, url, basis = declared_license(dist), source_url(dist, name), "other-version"
        else:
            lic, url, basis = "", source_url(None, name), "none"
        out[key] = {
            "version": version,
            "scope": scope[name],
            "license": lic,
            "source": url,
            "basis": basis,
            "status": status_of(lic),
        }
    return out


def tracked_files() -> list[str]:
    done = subprocess.run(["git", "ls-files"], cwd=ROOT, check=True, capture_output=True, text=True)
    return done.stdout.splitlines()


def glob_match(path: str, pattern: str) -> bool:
    regex = re.escape(pattern).replace(r"\*", "[^/]*") if "**" not in pattern else pattern
    return re.fullmatch(regex, path) is not None or (
        pattern.endswith("/*") and path.startswith(pattern[:-1])
    )


def uncovered_assets(files: list[str]) -> list[str]:
    """Tracked asset-type files that no ``ASSETS`` entry covers."""
    patterns = [p for a in ASSETS for p in a["paths"]]
    return [
        f
        for f in files
        if f.lower().endswith(_ASSET_SUFFIXES) and not any(glob_match(f, p) for p in patterns)
    ]


def empty_assets(files: list[str]) -> list[str]:
    """``ASSETS`` ids whose paths match no tracked file (a stale entry)."""
    return [a["id"] for a in ASSETS if not any(glob_match(f, p) for f in files for p in a["paths"])]


def render(inventory: dict[str, Any]) -> str:
    pkgs: dict[str, dict[str, Any]] = inventory["packages"]
    review = [n for n, r in pkgs.items() if r["status"] != "recorded"]
    lines = [
        "# Third-party notices",
        "",
        "<!-- Generated by scripts/license_inventory.py"
        " from docs/compliance/license_inventory.json. Do not edit. -->",
        "",
        "The MIT `LICENSE` of this repository covers the code written here. It does not cover",
        "the packages below, the third-party data in the fixtures, or anything a provider",
        "owns. Each keeps the terms it was published under.",
        "",
        "This list is generated, not a legal conclusion. A licence is `recorded` when its",
        "declared text matches a plainly permissive identifier; anything else is `needs",
        "review` and is left to the maintainer. Until that review is done, nothing here says",
        "every dependency is clear.",
        "",
        "## Needs review",
        "",
    ]
    if review:
        lines += [
            f"- `{n.split('==')[0]}` {pkgs[n]['version']}: declared "
            f"`{pkgs[n]['license'] or '(none)'}`"
            for n in review
        ]
    else:
        lines.append("- (no package)")
    lines += [
        "",
        "## Packages (from `uv.lock`)",
        "",
        "Declared licence is read from the package metadata of the installed version. A",
        "locked version that is not installed on the generating machine (marker-gated)",
        "keeps its earlier record, or shows another version's declaration (`basis` in the",
        "JSON says which).",
        "",
        "Scope: `runtime` is installed with `pip install kpubdata`; `extra:<name>` with that",
        "optional extra; `dev` only for development and documentation.",
        "",
        "| Package | Version | Scope | Declared licence | Status | Source |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for name, r in pkgs.items():
        lic = (r["license"] or "(none)").replace("|", "/")
        lines.append(
            f"| {name.split('==')[0]} | {r['version']} | {r['scope']} | {lic} | "
            f"{r['status']} | {r['source']} |"
        )
    lines += [
        "",
        "## Bundled assets",
        "",
        "| Asset | Kind | In wheel | Origin | Terms | Status |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for a in inventory["assets"]:
        wheel = "yes" if a["in_wheel"] else "no"
        lines.append(
            f"| {a['id']} (`{'`, `'.join(a['paths'])}`) | {a['kind']} | {wheel} | "
            f"{a['origin']} | {a['terms']} | {a['status']} |"
        )
    lines += [
        "",
        "The wheel packs `src/kpubdata` only. The source distribution has no exclusion rule,",
        "so it also carries the fixtures and docs above; their terms apply there too.",
        "Fonts and icons: none are tracked in this repository (checked by the same script).",
        "",
    ]
    return "\n".join(lines)


def check(inventory: dict[str, Any] | None, files: list[str]) -> list[str]:
    problems: list[str] = []
    if inventory is None:
        return [f"{INVENTORY.relative_to(ROOT)} is missing; run scripts/license_inventory.py"]
    recorded: dict[str, Any] = inventory.get("packages", {})
    locked = locked_packages()
    for name, pkg in sorted(locked.items()):
        rec = recorded.get(name)
        if rec is None:
            problems.append(f"{name} is locked but has no recorded licence")
        elif rec.get("version") != pkg.get("version"):
            problems.append(
                f"{name}: locked {pkg.get('version')} but recorded {rec.get('version')}"
            )
        elif "license" not in rec or rec.get("status") not in {"recorded", "needs review"}:
            problems.append(f"{name}: record has no licence or status")
        elif not rec["license"] and rec["status"] == "recorded":
            problems.append(f"{name}: empty licence cannot be 'recorded'")
    for name in sorted(set(recorded) - set(locked)):
        problems.append(f"{name} is recorded but no longer locked")
    problems += [f"asset {f} is not covered by an ASSETS entry" for f in uncovered_assets(files)]
    problems += [f"ASSETS entry {i} matches no tracked file" for i in empty_assets(files)]
    if inventory.get("assets") != ASSETS:
        problems.append("recorded assets differ from ASSETS in this script")
    if not NOTICES.exists() or NOTICES.read_text(encoding="utf-8") != render(inventory):
        problems.append("THIRD_PARTY_NOTICES.md is out of date")
    return problems


def load() -> dict[str, Any] | None:
    if not INVENTORY.exists():
        return None
    data: dict[str, Any] = json.loads(INVENTORY.read_text(encoding="utf-8"))
    return data


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--check", action="store_true", help="fail on drift instead of writing")
    args = parser.parse_args(argv)
    if args.check:
        problems = check(load(), tracked_files())
        for p in problems:
            print(f"license inventory: {p}", file=sys.stderr)
        if problems:
            print("Run: uv run python scripts/license_inventory.py", file=sys.stderr)
            return 1
        print("license inventory: up to date")
        return 0
    previous = (load() or {}).get("packages", {})
    inventory = {"packages": build_packages(previous), "assets": ASSETS}
    INVENTORY.parent.mkdir(parents=True, exist_ok=True)
    INVENTORY.write_text(
        json.dumps(inventory, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    NOTICES.write_text(render(inventory), encoding="utf-8")
    review = sum(1 for r in inventory["packages"].values() if r["status"] != "recorded")
    print(f"wrote {len(inventory['packages'])} packages, {review} need review")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
