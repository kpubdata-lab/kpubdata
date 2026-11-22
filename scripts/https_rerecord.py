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
    (KMA forecasts answer only for recent releases, so a recorded date ages out), in
    the spec and in the dataset's example script, whose parameters must match it. For a
    baseline entry it also rewrites the spec's ``base_url`` from
    ``http://apis.data.go.kr/`` to ``https://apis.data.go.kr/`` (any other host is
    refused) and removes the dataset's line from the insecure-http baseline; a spec
    already on https keeps its URL and the baseline is left alone. Either way it removes
    the dataset's fixtures' lines from ``scripts/legacy_evidence_baseline.txt``: a
    re-recorded meta carries ``spec_sha256``, and ``verify_spec.py`` fails a legacy
    entry that does.

``check``
    Runs after the recording and the generators, against the dispatch commit. Every
    changed path must be one this re-record produces; the spec may differ from the
    dispatch commit only in that scheme (baseline entries), in ``last_verified`` and in
    example ``base_date`` values, and the example script only in those dates; the
    insecure-http baseline may lose exactly this dataset's line for a baseline entry
    and must not change otherwise, and the legacy baseline may lose only lines of this
    dataset's fixtures.

Spec patch (#889, #931, #933). A spec's descriptive text — its ``title``,
``description``, ``source``, ``fields`` and ``license`` blocks — is part of the spec
digest, so correcting it voids the fixtures as surely as a ``base_url`` switch does,
and the change and its recording must land together. Dispatched with ``spec_commit``
(a full commit id) next to ``https_dataset``, the re-record takes the dataset's spec
file from that commit instead of the dispatch commit. Only a spec already on https may
be patched, and every other top-level block — ``endpoint``, ``auth``, ``params``,
``response``, ``pagination``, ``examples``, ``status`` and anything else — must match
the dispatch commit's exactly, so a patch cannot change what is requested or where the
key is sent. The one exception is ``response.items_path``, where the records sit in the
answer: it is read only after the response arrives, so a patch may correct its value to
another dotted path, but not add or remove it. ``switch`` refuses a patch that touches
anything else, and ``check`` holds the recorded spec to the patched one instead of to
the dispatch commit's. A patch that confirms the licence terms (adds ``attribution``)
also takes the dataset's line out of ``scripts/unconfirmed_terms_baseline.txt``, the
one other file it may change.

The script uses the standard library only: the gate job runs it on a bare runner.

Usage::

    python scripts/https_rerecord.py decide --permission write --dataset datago.apt_trade
    python scripts/https_rerecord.py switch datago.apt_trade
    python scripts/https_rerecord.py check datago.apt_trade --base "$GITHUB_SHA"
    python scripts/https_rerecord.py switch datago.bus_arrival --spec-commit <sha>
    python scripts/https_rerecord.py confirm datago.bus_arrival --base "$GITHUB_SHA"
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import unicodedata
from collections.abc import Callable, Sequence
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

REPO_ROOT = Path(__file__).resolve().parent.parent

INSECURE_BASELINE = "scripts/insecure_http_baseline.txt"
LEGACY_BASELINE = "scripts/legacy_evidence_baseline.txt"
#: Specs that say ``redistribution: allowed`` without confirming the terms. A spec
#: patch that confirms them (adds ``attribution``) takes the dataset's line out.
TERMS_BASELINE = "scripts/unconfirmed_terms_baseline.txt"

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
#: The hosts an already-https spec may be re-recorded against: the run sends the
#: data.go.kr key, so only data.go.kr's own gateways qualify.
_HTTPS_BASE_URL = re.compile(
    r'^\s*base_url:\s*"?https://(?:apis\.data\.go\.kr|api\.odcloud\.kr)/', re.MULTILINE
)
_HTTP_BASE_URL = re.compile(r'^(\s*base_url:\s*"?)http://apis\.data\.go\.kr/', re.MULTILINE)
_LAST_VERIFIED = re.compile(r"^last_verified:.*\n?", re.MULTILINE)
_BASE_DATE = re.compile(r"^(\s*base_date:\s*)(['\"]?)(\d{8})\2\s*$", re.MULTILINE)
_BASE_TIME = re.compile(r"^\s*base_time:\s*['\"]?(\d{4})['\"]?\s*$", re.MULTILINE)
#: ``base_date="…", base_time="…"`` in an example script: the script's parameters must
#: match the spec's ``examples[]`` exactly, or replay finds no fixture.
_SCRIPT_DATE = re.compile(
    r'(base_date\s*=\s*["\'])(\d{8})(["\']\s*,\s*base_time\s*=\s*["\'](\d{4})["\'])'
)
_KST = ZoneInfo("Asia/Seoul")
_COMMIT_ID = re.compile(r"[0-9a-f]{40}")
#: Characters a patched spec may not hold. YAML reads NEL, LS and PS as line breaks
#: where Python's ``re`` does not, and CR, tab and BOM invite the same kind of
#: disagreement between what a reviewer sees and what the loader reads (#889).
_UNSAFE_CHARACTERS = re.compile("[\t\r\x85\u2028\u2029\ufeff]")
#: The hosts the recording may send the data.go.kr key to.
_KEY_HOSTS = frozenset({"apis.data.go.kr", "api.odcloud.kr"})
_EIGHT_DIGITS = re.compile(r"\d{8}")
#: Unicode format and separator categories: zero-width and bidirectional controls,
#: line and paragraph separators. They change what a reviewer of the patch sees.
_HIDDEN = frozenset({"Cf", "Zl", "Zp"})
#: The top-level blocks a spec patch may change: they describe what is recorded and
#: never shape the request. Everything else must stay as the dispatch commit has it.
DESCRIPTIVE_BLOCKS = frozenset({"title", "description", "source", "fields", "license"})
#: The one key inside ``response`` a patch may change: where the records sit in the
#: answer. It is read only after the response arrives and never shapes the request.
PARSING_KEY = "items_path"
#: What a patched ``response.items_path`` must look like: dotted identifier segments.
_DOTTED_PATH = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*")
#: A corrected items path long enough to hide something from the PR's reviewer is refused.
_DOTTED_PATH_MAX = 200


def _is_dotted_path(value: object) -> bool:
    """Whether ``value`` is a short dotted identifier path such as ``response.body.items``."""
    return (
        isinstance(value, str)
        and len(value) <= _DOTTED_PATH_MAX
        and _DOTTED_PATH.fullmatch(value) is not None
    )


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


def is_commit_id(value: str) -> bool:
    """Whether ``value`` is a full, lower-case hexadecimal commit id."""
    return _COMMIT_ID.fullmatch(value) is not None


def _loaded(text: str) -> dict[str, object]:
    """``text`` parsed exactly as the spec loader parses it: a duplicate key's last value wins."""
    import yaml

    data = yaml.load(text, Loader=getattr(yaml, "CSafeLoader", yaml.SafeLoader))
    if not isinstance(data, dict):
        raise ValueError("the spec root is not a mapping")
    return data


def _strict_load(text: str) -> dict[str, object]:
    """``text`` parsed as the spec loader parses it, refusing duplicate mapping keys.

    PyYAML keeps the last of two equal keys without a word, which would let a second
    ``endpoint`` hidden in a descriptive block replace the real one. PyYAML is imported
    here, not at the top: ``decide`` runs on a bare runner with the standard library.
    """
    import yaml

    class _Strict(yaml.SafeLoader):
        """The pure-Python safe loader: it reads line breaks as libyaml's does."""

    def mapping(loader: yaml.SafeLoader, node: yaml.MappingNode, deep: bool = False) -> object:
        seen: set[str] = set()
        for key_node, _ in node.value:
            key = repr(loader.construct_object(key_node, deep=True))
            if key in seen:
                raise yaml.constructor.ConstructorError(
                    None, None, f"duplicate key {key}", key_node.start_mark
                )
            seen.add(key)
        return yaml.SafeLoader.construct_mapping(loader, node, deep=deep)

    _Strict.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, mapping)
    data = yaml.load(text, Loader=_Strict)
    if not isinstance(data, dict):
        raise ValueError("the spec root is not a mapping")
    return data


def _request_view(data: dict[str, object]) -> dict[str, object]:
    """The parsed spec without what a patch or a re-record may change."""
    view = {
        key: value
        for key, value in data.items()
        if key not in DESCRIPTIVE_BLOCKS and key != "last_verified"
    }
    examples = view.get("examples")
    if isinstance(examples, list):
        normalised: list[object] = []
        for example in examples:
            if isinstance(example, dict) and isinstance(example.get("params"), dict):
                example = {**example, "params": undate(example["params"])}
            normalised.append(example)
        view["examples"] = normalised
    response = view.get("response")
    if isinstance(response, dict):
        view["response"] = {key: value for key, value in response.items() if key != PARSING_KEY}
    return view


def _items_path_problems(before: dict[str, object], after: dict[str, object]) -> list[str]:
    """Problems with how a patch changes ``response.items_path``; empty when it may.

    :func:`_request_view` leaves the key out of the comparison, so it is held here: a
    patch may correct its value, never add or remove it, and the new value must be a
    plain dotted path.
    """
    old, new = before.get("response"), after.get("response")
    old_has = isinstance(old, dict) and PARSING_KEY in old
    new_has = isinstance(new, dict) and PARSING_KEY in new
    if old_has != new_has:
        return [f"the spec patch adds or removes response.{PARSING_KEY}"]
    if not (isinstance(old, dict) and isinstance(new, dict) and new_has):
        return []
    value = new[PARSING_KEY]
    if value == old[PARSING_KEY]:
        return []
    if not _is_dotted_path(value):
        return [f"the patched response.{PARSING_KEY} is not a dotted identifier path: {value!r}"]
    return []


def undate(params: dict[str, object]) -> dict[str, object]:
    """``params`` with a ``base_date`` the re-record refreshes blanked out.

    Only an eight-digit date next to a ``base_time`` is what ``refresh_example_dates``
    rewrites; any other value is sent as written, so it must match exactly.
    """
    value = params.get("base_date")
    if isinstance(value, str) and _EIGHT_DIGITS.fullmatch(value) and "base_time" in params:
        return {**params, "base_date": "<date>"}
    return params


def _key_host(data: dict[str, object]) -> str | None:
    """The host of the parsed ``endpoint.base_url`` when it is https, else None."""
    endpoint = data.get("endpoint")
    url = endpoint.get("base_url") if isinstance(endpoint, dict) else None
    if not isinstance(url, str):
        return None
    parts = urlsplit(url)
    return parts.hostname if parts.scheme == "https" else None


def check_spec_patch(base_spec: str, patched: str) -> list[str]:
    """Problems with taking ``patched`` in place of ``base_spec``; empty when it may be.

    The comparison is of what the YAML means, not of its lines: both texts are parsed
    as the spec loader parses them, duplicate keys refused, and every top-level key
    but the descriptive ones must come out equal. A line-based comparison was shown to
    be bypassable by line breaks only YAML recognises (review of #889).
    """
    if _UNSAFE_CHARACTERS.search(patched):
        return ["the spec patch holds a tab, CR, BOM or Unicode line break"]
    hidden = sorted({f"U+{ord(c):04X}" for c in patched if unicodedata.category(c) in _HIDDEN})
    if hidden:
        return [f"the spec patch holds invisible characters a reviewer cannot see: {hidden}"]
    try:
        # The dispatch commit's spec is main's and trusted: read it as the spec loader
        # does, last duplicate key winning, so a patch may remove a duplicate key that
        # is already there (#933). Only the patch has to parse strictly.
        before = _loaded(base_spec)
        after = _strict_load(patched)
    except Exception as exc:  # noqa: BLE001 — any parse failure refuses the patch
        return [f"the spec patch does not parse strictly: {' '.join(str(exc).split())}"]
    if _key_host(before) not in _KEY_HOSTS or _key_host(after) not in _KEY_HOSTS:
        return ["a spec patch applies only to a spec already on https at a data.go.kr host"]
    problems = _items_path_problems(before, after)
    old_view, new_view = _request_view(before), _request_view(after)
    if old_view == new_view:
        return problems
    changed = sorted(
        str(key) for key in set(old_view) | set(new_view) if old_view.get(key) != new_view.get(key)
    )
    allowed = ", ".join(sorted(DESCRIPTIVE_BLOCKS))
    return [
        f"the spec patch changes {', '.join(changed)};"
        f" only {allowed} and response.{PARSING_KEY} may change",
        *problems,
    ]


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
    spec_commit: str = "",
) -> list[str]:
    """``key=value`` lines for ``$GITHUB_OUTPUT``. No value holds a newline."""

    def lines(allowed: bool, reason: str, chosen: str = "") -> list[str]:
        return [
            f"allowed={'true' if allowed else 'false'}",
            f"reason={' '.join(reason.split())}",
            f"dataset={chosen}",
            f"spec_commit={spec_commit if allowed else ''}",
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
    if spec_commit and not is_commit_id(spec_commit):
        return lines(False, "the spec commit is not a full lower-case commit id")
    listed = dataset in baseline_entries(baseline)
    if spec_commit and listed:
        return lines(False, f"{dataset} must reach https before its spec can be patched")
    if listed:
        return lines(True, f"{dataset} https switch and re-record", dataset)
    if spec is not None and is_https(spec):
        if spec_commit:
            return lines(True, f"{dataset} re-record with the spec of {spec_commit}", dataset)
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


def refresh_script_dates(text: str, now: datetime) -> str:
    """Move each ``base_date=`` in an example script to its ``base_time``'s latest release."""
    return _SCRIPT_DATE.sub(
        lambda m: f"{m.group(1)}{latest_release_date(m.group(4), now)}{m.group(3)}", text
    )


def _script_without_dates(text: str) -> str:
    return _SCRIPT_DATE.sub(lambda m: f"{m.group(1)}<date>{m.group(3)}", text)


def example_path(dataset: str) -> str:
    provider, key = split_dataset(dataset)
    return f"examples/{provider}/{key}.py"


def _without_volatile(text: str) -> str:
    """Spec text with the lines a re-record may change blanked out."""
    text = _LAST_VERIFIED.sub("", text)
    return _BASE_DATE.sub(lambda m: f"{m.group(1)}{m.group(2)}<date>{m.group(2)}", text)


def _confirms_terms(spec_text: str) -> bool:
    """Whether the spec's licence carries the ``attribution`` that confirms its terms."""
    licence = _strict_load(spec_text).get("license")
    value = licence.get("attribution") if isinstance(licence, dict) else None
    # The same test verify_spec.py applies: blank text confirms nothing.
    return isinstance(value, str) and bool(value.strip())


def drop_baseline_lines(text: str, drop: Callable[[str], bool]) -> str:
    """The baseline text without the entry lines ``drop`` selects; comments stay."""
    kept = [
        line
        for line in text.splitlines(keepends=True)
        if line.strip().startswith("#") or not line.strip() or not drop(line.strip())
    ]
    return "".join(kept)


def switch(
    dataset: str, root: Path, now: datetime | None = None, spec_commit: str = ""
) -> list[str]:
    """Apply the switch in ``root``. Returns problems; an empty list means it applied.

    With ``spec_commit`` the spec is first replaced by that commit's version of it,
    which :func:`check_spec_patch` must accept.
    """
    spec = root / spec_path(dataset)
    insecure = root / INSECURE_BASELINE
    legacy = root / LEGACY_BASELINE
    terms = root / TERMS_BASELINE
    confirms_terms = False
    if not spec.is_file():
        return [f"{spec_path(dataset)} does not exist"]
    insecure_text = insecure.read_text(encoding="utf-8")
    listed = dataset in baseline_entries(insecure_text)
    text = spec.read_text(encoding="utf-8")
    if not listed and not is_https(text):
        return [f"{dataset} is neither in {INSECURE_BASELINE} nor a spec already on https"]
    if spec_commit:
        try:
            patched = _patched_spec(root, spec_commit, dataset)
        except (ValueError, subprocess.CalledProcessError) as exc:
            return [f"the spec patch cannot be read: {exc}"]
        problems = [] if not listed else [f"{dataset} must reach https before a spec patch"]
        problems += check_spec_patch(text, patched)
        if problems:
            return problems
        text = patched
        confirms_terms = _confirms_terms(patched)
    try:
        new_spec = switch_spec(text) if listed else text
        new_spec = refresh_example_dates(new_spec, now or datetime.now(tz=_KST))
    except ValueError as exc:
        return [f"{spec_path(dataset)}: {exc}"]
    spec.write_text(new_spec, encoding="utf-8")
    script = root / example_path(dataset)
    if script.is_file():
        script.write_text(
            refresh_script_dates(script.read_text(encoding="utf-8"), now or datetime.now(tz=_KST)),
            encoding="utf-8",
        )
    if listed:
        insecure.write_text(
            drop_baseline_lines(insecure_text, lambda entry: entry == dataset),
            encoding="utf-8",
        )
    if confirms_terms and terms.is_file():
        terms.write_text(
            drop_baseline_lines(terms.read_text(encoding="utf-8"), lambda entry: entry == dataset),
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
    # Decoded as UTF-8 by hand: text mode would follow the runner's locale and
    # translate CR, hiding it from the spec-patch check.
    output = subprocess.run(["git", *args], cwd=root, capture_output=True, check=True).stdout
    return output.decode("utf-8")


def _git_paths(root: Path, *args: str) -> set[str]:
    output = subprocess.run(["git", *args], cwd=root, capture_output=True, check=True).stdout
    return {path for path in output.decode("utf-8", "surrogateescape").split("\0") if path}


def _base_text(root: Path, base: str, path: str) -> str:
    return _git(root, "show", f"{base}:{path}")


def _base_text_or_empty(root: Path, base: str, path: str) -> str:
    """The file at ``base``, or empty when it did not exist there."""
    listed = _git(root, "ls-tree", "--name-only", base, "--", path).strip()
    return _base_text(root, base, path) if listed else ""


def _patched_spec(root: Path, spec_commit: str, dataset: str) -> str:
    """The dataset's spec file as ``spec_commit`` has it."""
    if not is_commit_id(spec_commit):
        raise ValueError("the spec commit is not a full lower-case commit id")
    return _git(root, "show", f"{spec_commit}:{spec_path(dataset)}")


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
    base_script: str = "",
    script: str = "",
    spec_patch: str | None = None,
    base_terms: str = "",
    terms: str = "",
) -> list[str]:
    """Problems with a re-record's changes; an empty list means it may be committed.

    ``spec_patch`` is the spec the run was dispatched to record with (``spec_commit``):
    when given, the recorded spec is held to it rather than to ``base_spec``.
    """
    problems: list[str] = []
    fixtures = f"tests/fixtures/{fixture_prefix(dataset)}"
    allowed = {
        spec_path(dataset),
        example_path(dataset),
        INSECURE_BASELINE,
        LEGACY_BASELINE,
        *GENERATED,
    }
    if spec_patch is not None:
        allowed.add(TERMS_BASELINE)
    for path in changed:
        if path not in allowed and not path.startswith(fixtures):
            problems.append(f"{path} is not something an https re-record of {dataset} changes")

    listed = dataset in baseline_entries(base_insecure)
    try:
        expected_spec = switch_spec(base_spec) if listed else base_spec
        if not listed and not is_https(base_spec):
            raise ValueError("it is not in the insecure-http baseline and not on https")
        if spec_patch is not None:
            if listed:
                raise ValueError("a spec patch applies only to a spec already on https")
            patch_problems = check_spec_patch(base_spec, spec_patch)
            if patch_problems:
                raise ValueError("; ".join(patch_problems))
            expected_spec = spec_patch
    except ValueError as exc:
        problems.append(f"the dispatch commit's spec cannot be re-recorded: {exc}")
    else:
        if _without_volatile(expected_spec) != _without_volatile(spec):
            what = "the patched spec" if spec_patch is not None else "the https scheme"
            problems.append(
                f"{spec_path(dataset)} changed beyond {what}, last_verified"
                " and example base_date values"
            )

    if _script_without_dates(base_script) != _script_without_dates(script):
        problems.append(f"{example_path(dataset)} changed beyond example base_date values")

    before = baseline_entries(base_insecure)
    after = baseline_entries(insecure)
    if listed and sorted(after) != sorted(e for e in before if e != dataset):
        problems.append(f"{INSECURE_BASELINE} must lose exactly the line {dataset}")
    if not listed and sorted(after) != sorted(before):
        problems.append(f"{INSECURE_BASELINE} must not change when re-recording {dataset}")

    terms_before = baseline_entries(base_terms)
    terms_after = baseline_entries(terms)
    confirmed = spec_patch is not None and _confirms_terms(spec_patch)
    expected_terms = [e for e in terms_before if e != dataset] if confirmed else terms_before
    if terms_after != expected_terms:
        problems.append(
            f"{TERMS_BASELINE} may lose only the line {dataset},"
            " and only when the spec patch confirms its terms"
        )

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


def check(dataset: str, root: Path, base: str, spec_commit: str = "") -> list[str]:
    """Run :func:`evaluate` on the working tree of ``root`` against ``base``."""
    spec_patch: str | None = None
    if spec_commit:
        try:
            spec_patch = _patched_spec(root, spec_commit, dataset)
        except (ValueError, subprocess.CalledProcessError) as exc:
            return [f"the spec patch cannot be read: {exc}"]
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
        base_script=_base_text_or_empty(root, base, example_path(dataset)),
        script=read(example_path(dataset)),
        spec_patch=spec_patch,
        base_terms=_base_text_or_empty(root, base, TERMS_BASELINE),
        terms=read(TERMS_BASELINE),
    )


def confirm_request(dataset: str, root: Path, base: str) -> list[str]:
    """Load the switched spec with kpubdata's own loader and hold its request to ``base``.

    A second guard after :func:`check_spec_patch`, independent of it: it runs in the
    self-hosted job right before the one step that holds the provider key, and parses
    with :func:`kpubdata.core.spec.load_spec_file` — the loader ``make record`` uses —
    rather than this script's own. Every part of the spec that shapes the request must
    equal the dispatch commit's, example ``base_date`` values and ``response.items_path``
    aside, and the key may go
    only to a data.go.kr gateway over https.
    """
    import tempfile
    from dataclasses import replace

    from kpubdata.core.spec import ExampleSpec, SpecDefinition, load_spec_file

    def request(spec: SpecDefinition) -> tuple[object, ...]:
        def undated(example: ExampleSpec) -> ExampleSpec:
            params: dict[str, object] = {**example.params}
            normalised = undate(params)
            if normalised is params:
                return example
            return replace(example, params={**example.params, "base_date": "<date>"})

        examples = tuple(undated(example) for example in spec.examples)
        return (
            spec.id,
            spec.provider,
            spec.endpoint,
            spec.auth,
            # Where the records sit in the answer is read after it arrives (PARSING_KEY).
            replace(spec.response, items_path=None),
            spec.pagination,
            spec.status,
            spec.params,
            examples,
        )

    path = spec_path(dataset)
    try:
        current = load_spec_file(root / path)
        with tempfile.TemporaryDirectory() as tmp:
            dispatched_file = Path(tmp) / "spec.yaml"
            dispatched_file.write_text(_base_text(root, base, path), encoding="utf-8")
            dispatched = load_spec_file(dispatched_file)
    except Exception as exc:  # noqa: BLE001 — any load failure stops the recording
        return [f"{path} cannot be confirmed: {' '.join(str(exc).split())}"]
    problems: list[str] = []
    if request(current) != request(dispatched):
        problems.append(f"{path} sends a different request from the dispatch commit's spec")
    # The items path is left out of request(); hold it here to the same rule the patch
    # check applies, so this guard stays independent of that one.
    now, then = current.response.items_path, dispatched.response.items_path
    if (now is None) != (then is None) or (now != then and not _is_dotted_path(now)):
        problems.append(f"{path} changes response.{PARSING_KEY} beyond a dotted-path correction")
    parts = urlsplit(current.endpoint.base_url)
    if parts.scheme != "https" or parts.hostname not in _KEY_HOSTS:
        problems.append(f"{path} would send the key to {parts.scheme}://{parts.hostname}")
    return problems


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n", 1)[0])
    sub = parser.add_subparsers(dest="command", required=True)
    decide_cmd = sub.add_parser("decide")
    decide_cmd.add_argument("--permission", required=True)
    decide_cmd.add_argument("--dataset", required=True)
    decide_cmd.add_argument("--issue-number", default="")
    decide_cmd.add_argument("--spec-commit", default="")
    for name in ("switch", "check", "confirm"):
        command = sub.add_parser(name)
        command.add_argument("dataset")
        command.add_argument("--root", type=Path, default=REPO_ROOT)
        command.add_argument(
            "--spec-commit", default="", help="take the dataset's spec from this commit"
        )
        if name in ("check", "confirm"):
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
                    spec_commit=args.spec_commit.strip(),
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
        problems = switch(args.dataset, root, spec_commit=args.spec_commit)
    elif args.command == "confirm":
        problems = confirm_request(args.dataset, root, args.base)
    else:
        problems = check(args.dataset, root, args.base, args.spec_commit)
    for problem in problems:
        print(f"::error::{problem}", file=sys.stderr)
    if problems:
        return 1
    print(f"https re-record {args.command}: {args.dataset} ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
