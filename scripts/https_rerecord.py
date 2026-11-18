#!/usr/bin/env python3
"""Move one plain-http spec to https, or re-record one on https, and guard the result.

#893 is the switch; #907 is the re-record of a spec already on https whose fixtures
name a recording run that did not succeed.

Twenty-two bundled specs still call ``http://apis.data.go.kr`` and send the service key
in the clear. Switching a ``base_url`` moves the spec digest, so the dataset's fixtures
must be recorded again, and only a successful run of the recording workflow counts as a
recording (``scripts/check_fixture_authorship.py``). The agent path of that workflow
needs an LLM and a model key for what is a mechanical change, so ``build-dataset.yml``
has a second, deterministic mode that runs the three subcommands of this script around
``make record``:

``decide``
    Runs in the hosted ``gate`` job, which holds no secret. A run passes only when the
    account that started it can push to the repository, no issue number was given with
    it, and the dataset id is well formed and either listed in
    ``scripts/insecure_http_baseline.txt`` (switch and re-record) or names a spec whose
    ``base_url`` is already ``https://`` (re-record only). Prints ``key=value`` lines for
    ``$GITHUB_OUTPUT`` and exits 0 either way, like ``dataset_request_gate.py``.

``switch``
    Moves every example ``base_date`` to the latest release its ``base_time`` has had
    (KMA forecasts answer only for recent releases, so a recorded date ages out), then
    rewrites the spec's ``base_url`` from ``http://apis.data.go.kr/`` to
    ``https://apis.data.go.kr/`` (any other host is refused), removes the dataset's line
    from the insecure-http baseline, and removes its fixtures' lines from
    ``scripts/legacy_evidence_baseline.txt``: a re-recorded meta carries
    ``spec_sha256``, and ``verify_spec.py`` fails a legacy entry that does.

``check``
    Runs after the recording and the generators, against the dispatch commit. Every
    changed path must be one this re-record produces; the spec may differ from the
    dispatch commit only in that scheme, in ``last_verified`` and in example
    ``base_date`` values; the insecure-http
    baseline may lose exactly this dataset's line, and the legacy baseline only lines
    of this dataset's fixtures.

The script uses the standard library only: the gate job runs it on a bare runner.

Usage::

    python scripts/https_rerecord.py decide --permission write --dataset datago.apt_trade
    python scripts/https_rerecord.py switch datago.apt_trade
    python scripts/https_rerecord.py check datago.apt_trade --base "$GITHUB_SHA"
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections.abc import Callable, Sequence
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

REPO_ROOT = Path(__file__).resolve().parent.parent

INSECURE_BASELINE = "scripts/insecure_http_baseline.txt"
LEGACY_BASELINE = "scripts/legacy_evidence_baseline.txt"

#: Written by the generators the workflow runs after ``make record``.
GENERATED = (
    "SUPPORTED_DATA.md",
    "src/kpubdata/dataset_metadata.json",
    "src/kpubdata/dataset_status.json",
    "docs/dataset-examples.md",
    "docs/status.md",
    "docs/status/latest.json",
)

_WRITE_PERMISSIONS = frozenset({"admin", "write"})
_DATASET_ID = re.compile(r"[a-z][a-z0-9_]{0,31}\.[a-z][a-z0-9_]{0,63}")
_HTTPS_BASE_URL = re.compile(r'^\s*base_url:\s*"?https://', re.MULTILINE)
_HTTP_BASE_URL = re.compile(r'^(\s*base_url:\s*"?)http://apis\.data\.go\.kr/', re.MULTILINE)
_LAST_VERIFIED = re.compile(r"^last_verified:.*\n?", re.MULTILINE)
_BASE_DATE = re.compile(r"^(\s*base_date:\s*)(['\"]?)(\d{8})\2\s*$", re.MULTILINE)
_BASE_TIME = re.compile(r"^\s*base_time:\s*['\"]?(\d{4})['\"]?\s*$", re.MULTILINE)
_KST = ZoneInfo("Asia/Seoul")
#: How long after its base_time a KMA release is safely published.
_RELEASE_MARGIN = timedelta(hours=1)


def baseline_entries(text: str) -> list[str]:
    """Entries of a baseline file: comments and blank lines dropped."""
    entries: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            entries.append(stripped)
    return entries


def split_dataset(dataset: str) -> tuple[str, str]:
    """``provider.key`` → ``(provider, key)``; anything else is refused."""
    if _DATASET_ID.fullmatch(dataset) is None:
        raise ValueError(f"not a dataset id: {dataset!r}")
    provider, _, key = dataset.partition(".")
    return provider, key


def spec_path(dataset: str) -> str:
    provider, key = split_dataset(dataset)
    return f"src/kpubdata/specs/{provider}/{key}.yaml"


def fixture_prefix(dataset: str) -> str:
    """The dataset's fixture directory relative to ``tests/fixtures``, with a slash."""
    provider, key = split_dataset(dataset)
    return f"{provider}/{key}/"


# --- decide ---------------------------------------------------------------------------


def is_https(spec_text: str) -> bool:
    """Whether the spec's ``base_url`` already says ``https://``."""
    return _HTTPS_BASE_URL.search(spec_text) is not None


def decide(
    *,
    permission: str,
    dataset: str,
    issue_number: str,
    baseline: str,
    spec: str | None = None,
) -> list[str]:
    """``key=value`` lines for ``$GITHUB_OUTPUT``. No value holds a newline."""

    def lines(allowed: bool, reason: str, chosen: str = "") -> list[str]:
        return [
            f"allowed={'true' if allowed else 'false'}",
            f"reason={' '.join(reason.split())}",
            f"dataset={chosen}",
        ]

    if permission not in _WRITE_PERMISSIONS:
        return lines(
            False,
            f"the account that started this run has '{permission or 'no'}' permission;"
            " a maintainer with write access must dispatch the re-record",
        )
    if issue_number:
        return lines(False, "give either an issue number or an https dataset, not both")
    try:
        split_dataset(dataset)
    except ValueError:
        return lines(False, "the https dataset is not a well-formed dataset id")
    if dataset in baseline_entries(baseline):
        return lines(True, f"{dataset} https switch and re-record", dataset)
    if spec is not None and is_https(spec):
        return lines(True, f"{dataset} re-record (already on https)", dataset)
    return lines(
        False,
        f"{dataset} is neither in {INSECURE_BASELINE} nor a spec already on https",
    )


# --- switch ---------------------------------------------------------------------------


def switch_spec(text: str) -> str:
    """The spec text with its one ``http://apis.data.go.kr/`` base_url moved to https."""
    new, count = _HTTP_BASE_URL.subn(r"\1https://apis.data.go.kr/", text)
    if count != 1:
        raise ValueError(f"expected exactly one base_url on http://apis.data.go.kr/, found {count}")
    return new


def latest_release_date(base_time: str, now: datetime) -> str:
    """The most recent KST date whose ``base_time`` release is already published."""
    local = now.astimezone(_KST)
    release = local.replace(
        hour=int(base_time[:2]), minute=int(base_time[2:]), second=0, microsecond=0
    )
    if local < release + _RELEASE_MARGIN:
        release -= timedelta(days=1)
    return release.strftime("%Y%m%d")


def refresh_example_dates(text: str, now: datetime) -> str:
    """Move each ``base_date`` to the latest release of the ``base_time`` after it.

    A spec without ``base_date`` comes back unchanged. A ``base_date`` with no
    ``base_time`` before the next ``base_date`` is refused: the date alone does not say
    which release is meant.
    """
    out: list[str] = []
    last = 0
    dates = list(_BASE_DATE.finditer(text))
    for index, match in enumerate(dates):
        end = dates[index + 1].start() if index + 1 < len(dates) else len(text)
        window = text[match.end() : end]
        time_match = _BASE_TIME.search(window)
        if time_match is None:
            raise ValueError("an example has base_date without a base_time after it")
        new_date = latest_release_date(time_match.group(1), now)
        out.append(text[last : match.start(3)])
        out.append(new_date)
        last = match.end(3)
    out.append(text[last:])
    return "".join(out)


def _without_volatile(text: str) -> str:
    """Spec text with the lines a re-record may change blanked out."""
    text = _LAST_VERIFIED.sub("", text)
    return _BASE_DATE.sub(lambda m: f"{m.group(1)}{m.group(2)}<date>{m.group(2)}", text)


def drop_baseline_lines(text: str, drop: Callable[[str], bool]) -> str:
    """The baseline text without the entry lines ``drop`` selects; comments stay."""
    kept = [
        line
        for line in text.splitlines(keepends=True)
        if line.strip().startswith("#") or not line.strip() or not drop(line.strip())
    ]
    return "".join(kept)


def switch(dataset: str, root: Path, now: datetime | None = None) -> list[str]:
    """Apply the switch in ``root``. Returns problems; an empty list means it applied."""
    spec = root / spec_path(dataset)
    insecure = root / INSECURE_BASELINE
    legacy = root / LEGACY_BASELINE
    if not spec.is_file():
        return [f"{spec_path(dataset)} does not exist"]
    insecure_text = insecure.read_text(encoding="utf-8")
    listed = dataset in baseline_entries(insecure_text)
    text = spec.read_text(encoding="utf-8")
    if not listed and not is_https(text):
        return [f"{dataset} is neither in {INSECURE_BASELINE} nor a spec already on https"]
    try:
        new_spec = switch_spec(text) if listed else text
        new_spec = refresh_example_dates(new_spec, now or datetime.now(tz=_KST))
    except ValueError as exc:
        return [f"{spec_path(dataset)}: {exc}"]
    spec.write_text(new_spec, encoding="utf-8")
    if listed:
        insecure.write_text(
            drop_baseline_lines(insecure_text, lambda entry: entry == dataset),
            encoding="utf-8",
        )
    if legacy.is_file():
        prefix = fixture_prefix(dataset)
        legacy.write_text(
            drop_baseline_lines(
                legacy.read_text(encoding="utf-8"), lambda entry: entry.startswith(prefix)
            ),
            encoding="utf-8",
        )
    return []


# --- check ----------------------------------------------------------------------------


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, capture_output=True, text=True, check=True
    ).stdout


def _git_paths(root: Path, *args: str) -> set[str]:
    output = subprocess.run(["git", *args], cwd=root, capture_output=True, check=True).stdout
    return {path for path in output.decode("utf-8", "surrogateescape").split("\0") if path}


def _base_text(root: Path, base: str, path: str) -> str:
    return _git(root, "show", f"{base}:{path}")


def evaluate(
    dataset: str,
    *,
    changed: Sequence[str],
    base_spec: str,
    spec: str,
    base_insecure: str,
    insecure: str,
    base_legacy: str,
    legacy: str,
) -> list[str]:
    """Problems with a re-record's changes; an empty list means it may be committed."""
    problems: list[str] = []
    fixtures = f"tests/fixtures/{fixture_prefix(dataset)}"
    allowed = {spec_path(dataset), INSECURE_BASELINE, LEGACY_BASELINE, *GENERATED}
    for path in changed:
        if path not in allowed and not path.startswith(fixtures):
            problems.append(f"{path} is not something an https re-record of {dataset} changes")

    listed = dataset in baseline_entries(base_insecure)
    try:
        expected_spec = switch_spec(base_spec) if listed else base_spec
        if not listed and not is_https(base_spec):
            raise ValueError("it is not in the insecure-http baseline and not on https")
    except ValueError as exc:
        problems.append(f"the dispatch commit's spec cannot be re-recorded: {exc}")
    else:
        if _without_volatile(expected_spec) != _without_volatile(spec):
            problems.append(
                f"{spec_path(dataset)} changed beyond the https scheme, last_verified"
                " and example base_date values"
            )

    before = baseline_entries(base_insecure)
    after = baseline_entries(insecure)
    if listed and sorted(after) != sorted(e for e in before if e != dataset):
        problems.append(f"{INSECURE_BASELINE} must lose exactly the line {dataset}")
    if not listed and sorted(after) != sorted(before):
        problems.append(f"{INSECURE_BASELINE} must not change when re-recording {dataset}")

    prefix = fixture_prefix(dataset)
    legacy_before = baseline_entries(base_legacy)
    legacy_after = baseline_entries(legacy)
    added = sorted(set(legacy_after) - set(legacy_before))
    removed = sorted(set(legacy_before) - set(legacy_after))
    if added:
        problems.append(f"{LEGACY_BASELINE} gained lines: {', '.join(added)}")
    if len(set(legacy_after)) != len(legacy_after):
        problems.append(f"{LEGACY_BASELINE} repeats a line")
    foreign = [entry for entry in removed if not entry.startswith(prefix)]
    if foreign:
        problems.append(f"{LEGACY_BASELINE} lost lines of other datasets: {', '.join(foreign)}")
    return problems


def check(dataset: str, root: Path, base: str) -> list[str]:
    """Run :func:`evaluate` on the working tree of ``root`` against ``base``."""
    tracked = _git_paths(root, "diff", "-z", "--name-only", "--no-renames", base, "--")
    untracked = _git_paths(root, "ls-files", "-z", "--others", "--exclude-standard")

    def read(path: str) -> str:
        file = root / path
        return file.read_text(encoding="utf-8") if file.is_file() else ""

    return evaluate(
        dataset,
        changed=sorted(tracked | untracked),
        base_spec=_base_text(root, base, spec_path(dataset)),
        spec=read(spec_path(dataset)),
        base_insecure=_base_text(root, base, INSECURE_BASELINE),
        insecure=read(INSECURE_BASELINE),
        base_legacy=_base_text(root, base, LEGACY_BASELINE),
        legacy=read(LEGACY_BASELINE),
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n", 1)[0])
    sub = parser.add_subparsers(dest="command", required=True)
    decide_cmd = sub.add_parser("decide")
    decide_cmd.add_argument("--permission", required=True)
    decide_cmd.add_argument("--dataset", required=True)
    decide_cmd.add_argument("--issue-number", default="")
    for name in ("switch", "check"):
        command = sub.add_parser(name)
        command.add_argument("dataset")
        command.add_argument("--root", type=Path, default=REPO_ROOT)
        if name == "check":
            command.add_argument("--base", required=True, help="the run's dispatch commit")
    args = parser.parse_args(argv)

    if args.command == "decide":
        baseline = (REPO_ROOT / INSECURE_BASELINE).read_text(encoding="utf-8")
        spec_text: str | None = None
        try:
            spec_file = REPO_ROOT / spec_path(args.dataset.strip())
            if spec_file.is_file():
                spec_text = spec_file.read_text(encoding="utf-8")
        except ValueError:
            spec_text = None
        print(
            "\n".join(
                decide(
                    permission=args.permission.strip(),
                    dataset=args.dataset.strip(),
                    issue_number=args.issue_number.strip(),
                    baseline=baseline,
                    spec=spec_text,
                )
            )
        )
        return 0

    try:
        split_dataset(args.dataset)
    except ValueError as exc:
        print(f"::error::{exc}", file=sys.stderr)
        return 2
    root = args.root.resolve()
    if args.command == "switch":
        problems = switch(args.dataset, root)
    else:
        problems = check(args.dataset, root, args.base)
    for problem in problems:
        print(f"::error::{problem}", file=sys.stderr)
    if problems:
        return 1
    print(f"https re-record {args.command}: {args.dataset} ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
