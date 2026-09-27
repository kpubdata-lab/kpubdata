"""KPubData Python module.

Holds the implementation at ``src/kpubdata/cli.py``. The main classes and
functions each serve one of three roles: public API, transport layer, or
provider adapter.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import logging
import sys
import traceback
from collections.abc import Iterable, Mapping, Sequence
from enum import Enum
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import cast

from kpubdata import __version__
from kpubdata.client import Client
from kpubdata.core.capability import Operation, QuerySupport
from kpubdata.core.models import DatasetRef, RecordBatch
from kpubdata.exceptions import (
    AuthError,
    DatasetNotFoundError,
    InvalidRequestError,
    ProviderResponseError,
    TransportError,
)

logger = logging.getLogger("kpubdata.cli")

_MAX_TABLE_COLUMNS = 20
_MAX_CELL_WIDTH = 40


def main(argv: Sequence[str] | None = None) -> int:
    """Parse arguments, dispatch the command, and map errors to exit codes."""
    parser = _build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    parsed_values = vars(args)
    debug_enabled = _configure_logging(cast(str, parsed_values.get("log_level", "warning")))

    try:
        return _run_command(args)
    except (DatasetNotFoundError, InvalidRequestError) as exc:
        _print_error(exc)
        if debug_enabled:
            traceback.print_exc(file=sys.stderr)
        return 2
    except AuthError as exc:
        _print_error(exc)
        if debug_enabled:
            traceback.print_exc(file=sys.stderr)
        return 3
    except (TransportError, ProviderResponseError) as exc:
        _print_error(exc)
        if debug_enabled:
            traceback.print_exc(file=sys.stderr)
        return 4
    except Exception as exc:
        _print_error(exc)
        if debug_enabled:
            traceback.print_exc(file=sys.stderr)
        return 1


def _build_parser() -> argparse.ArgumentParser:
    """Build and return the argparse parser."""
    parser = argparse.ArgumentParser(prog="kpubdata")
    _ = parser.add_argument("--cache", action="store_true", help="Enable response cache")
    _ = parser.add_argument(
        "--log-level",
        choices=("warning", "info", "debug"),
        default="warning",
        help="Set the kpubdata logger level",
    )
    _ = parser.add_argument(
        "--provider-key",
        action="append",
        default=[],
        metavar="PROVIDER=KEY",
        help="Override a provider API key",
    )
    _ = parser.add_argument("--version", action="store_true", help="Print kpubdata version")

    subparsers = parser.add_subparsers(dest="command")

    datasets_parser = subparsers.add_parser("datasets", help="Dataset discovery commands")
    datasets_subparsers = datasets_parser.add_subparsers(dest="datasets_command")

    datasets_list = datasets_subparsers.add_parser("list", help="List datasets")
    _ = datasets_list.add_argument("--provider", help="Filter by provider")
    _ = datasets_list.add_argument("--search", help="Filter by text search")
    _ = datasets_list.add_argument(
        "--format",
        choices=("json", "table"),
        default="table",
        help="Output format",
    )

    datasets_show = datasets_subparsers.add_parser("show", help="Show dataset metadata")
    _ = datasets_show.add_argument("dataset_id")
    _ = datasets_show.add_argument(
        "--format",
        choices=("json", "table"),
        default="table",
        help="Output format",
    )

    fetch_parser = subparsers.add_parser("fetch", help="Fetch normalized data")
    _ = fetch_parser.add_argument("dataset_id")
    _ = fetch_parser.add_argument("-p", "--param", action="append", default=[], metavar="KEY=VALUE")
    _ = fetch_parser.add_argument("--page", type=int)
    _ = fetch_parser.add_argument("--page-size", type=int)
    _ = fetch_parser.add_argument("--all", action="store_true", help="Fetch all pages")
    _ = fetch_parser.add_argument(
        "--format",
        choices=("json", "csv", "table"),
        default="table",
        help="Output format",
    )
    _ = fetch_parser.add_argument("--output", help="Write output to a file")

    raw_parser = subparsers.add_parser("raw", help="Call a raw provider operation")
    _ = raw_parser.add_argument("dataset_id")
    _ = raw_parser.add_argument("operation")
    _ = raw_parser.add_argument("-p", "--param", action="append", default=[], metavar="KEY=VALUE")
    _ = raw_parser.add_argument("--output", help="Write output to a file")

    probe_parser = subparsers.add_parser(
        "probe", help="Classify dataset reachability and list datasets awaiting 활용신청"
    )
    _ = probe_parser.add_argument("--provider", help="Probe only this provider")
    _ = probe_parser.add_argument("--dataset", help="Probe only this dataset id")
    _ = probe_parser.add_argument(
        "--report-apply", action="store_true", help="Print the 활용신청 checklist"
    )
    _ = probe_parser.add_argument(
        "--output", help="Write the report here instead of the default location"
    )

    scaffold_parser = subparsers.add_parser(
        "scaffold", help="Generate skeleton files for a new provider adapter"
    )
    scaffold_sub = scaffold_parser.add_subparsers(dest="scaffold_command")
    scaffold_provider = scaffold_sub.add_parser(
        "provider", help="Scaffold a new provider adapter package"
    )
    _ = scaffold_provider.add_argument("name", help="Provider name (lowercase python identifier)")
    _ = scaffold_provider.add_argument(
        "--dataset-key",
        default="sample",
        help="Seed catalogue dataset_key (default: sample)",
    )
    _ = scaffold_provider.add_argument(
        "--repo-root",
        default=".",
        help="Repository root containing src/ and tests/ (default: cwd)",
    )
    _ = scaffold_provider.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing scaffold files",
    )

    return parser


def _configure_logging(level_name: str) -> bool:
    """Configure logging from the level name; return whether debug is enabled."""
    level_map = {
        "warning": logging.WARNING,
        "info": logging.INFO,
        "debug": logging.DEBUG,
    }
    level = level_map[level_name]
    logging.basicConfig(level=level)
    root_logger = logging.getLogger("kpubdata")
    root_logger.setLevel(level)
    logger.debug("CLI logging configured", extra={"log_level": level_name.lower()})
    return level == logging.DEBUG


def _run_command(args: argparse.Namespace) -> int:
    """Dispatch the parsed command to its handler."""
    values = vars(args)
    version_flag = cast(bool, values.get("version", False))
    command = cast(str | None, values.get("command"))
    provider_key_values = cast(list[str], values.get("provider_key", []))
    cache_enabled = cast(bool, values.get("cache", False))

    if version_flag:
        print(_get_version())
        return 0

    if command is None:
        _build_parser().print_help()
        return 0

    # scaffold needs no client or provider key, so it branches off early.
    if command == "scaffold":
        return _handle_scaffold_command(args)

    # probe builds its own fast-fail transport (15s timeout, zero retries) —
    # the shared client would let cache and retries interfere with the
    # question "is this key reachable right now".
    if command == "probe":
        return _handle_probe_command(args)

    provider_keys = _parse_assignments(provider_key_values, flag_name="--provider-key")
    client = _create_client(cache_enabled=cache_enabled, provider_keys=provider_keys)
    try:
        if command == "datasets":
            return _handle_datasets_command(client, args)
        if command == "fetch":
            return _handle_fetch_command(client, args)
        if command == "raw":
            return _handle_raw_command(client, args)
        raise InvalidRequestError(f"Unknown command: {command}")
    finally:
        client.close()


def _handle_probe_command(args: argparse.Namespace) -> int:
    """``kpubdata probe`` — reachability classification and the activation checklist (#499)."""
    from pathlib import Path

    from kpubdata._probe import (
        DEFAULT_REPORT_PATH,
        merge_with_existing,
        probe_all,
        render_apply_report,
        summarize,
        write_report,
    )

    results = probe_all(
        provider=getattr(args, "provider", None),
        dataset_id=getattr(args, "dataset", None),
    )
    if not results:
        print("프로브 대상이 없습니다.", file=sys.stderr)
        return 1

    output = getattr(args, "output", None)
    report_path = Path(output) if output else DEFAULT_REPORT_PATH
    filtered = bool(getattr(args, "provider", None) or getattr(args, "dataset", None))
    # A partial probe merges: erasing the other verdicts would mean calling every
    # provider again to get them back (#514).
    #
    # A full probe replaces. It *is* the whole picture, so merging would keep rows
    # for specs that have since been removed or renamed, and the report would go
    # on naming a dataset that no longer exists.
    rows = merge_with_existing(results, report_path) if filtered else results
    write_report(rows, report_path)
    counts = summarize(results)
    print(
        "프로브 "
        + str(len(results))
        + "종: "
        + ", ".join(f"{name}={count}" for name, count in sorted(counts.items()))
    )
    if getattr(args, "report_apply", False):
        print()
        print(render_apply_report(results))
    return 0


def _create_client(*, cache_enabled: bool, provider_keys: dict[str, str]) -> Client:
    """Create a Client, optionally with the response cache enabled."""
    if cache_enabled:
        return Client.from_env(provider_keys=provider_keys, cache=True)
    return Client.from_env(provider_keys=provider_keys)


def _handle_datasets_command(client: Client, args: argparse.Namespace) -> int:
    """Handle the ``datasets`` command."""
    values = vars(args)
    datasets_command = cast(str | None, values.get("datasets_command"))

    if datasets_command == "list":
        provider = cast(str | None, values.get("provider"))
        search_text = cast(str | None, values.get("search"))
        output_format = cast(str, values.get("format", "table"))
        datasets = client.datasets.list(provider=provider)
        if search_text:
            needle = search_text.casefold()
            datasets = [
                dataset
                for dataset in datasets
                if needle in dataset.id.casefold()
                or needle in dataset.name.casefold()
                or needle in dataset.provider.casefold()
            ]
        datasets = sorted(datasets, key=lambda dataset: dataset.id)
        if output_format == "json":
            print(
                json.dumps(
                    [_dataset_summary(dataset) for dataset in datasets],
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 0
        dataset_rows: list[dict[str, object]] = [
            {
                "id": dataset.id,
                "name": dataset.name,
                "provider": dataset.provider,
                "operations": ", ".join(_operation_names(dataset.operations)),
            }
            for dataset in datasets
        ]
        print(_render_table(dataset_rows, headers=["id", "name", "provider", "operations"]))
        return 0

    if datasets_command == "show":
        dataset_id = cast(str, values.get("dataset_id"))
        output_format = cast(str, values.get("format", "table"))
        _, dataset = client.datasets.resolve(dataset_id)
        metadata = _dataset_details(dataset)
        if output_format == "json":
            print(json.dumps(metadata, ensure_ascii=False, indent=2))
            return 0
        raw_metadata_keys = cast(list[str], metadata["raw_metadata_keys"])
        capabilities = metadata["capabilities"]
        detail_rows: list[dict[str, object]] = [
            {"field": "id", "value": metadata["id"]},
            {"field": "name", "value": metadata["name"]},
            {"field": "provider", "value": metadata["provider"]},
            {"field": "operations", "value": ", ".join(_operation_names(dataset.operations))},
            {
                "field": "capabilities",
                "value": json.dumps(capabilities, ensure_ascii=False),
            },
            {
                "field": "raw_metadata_keys",
                "value": ", ".join(raw_metadata_keys),
            },
        ]
        print(_render_table(detail_rows, headers=["field", "value"]))
        return 0

    raise InvalidRequestError("Missing datasets subcommand")


def _handle_fetch_command(client: Client, args: argparse.Namespace) -> int:
    """Handle the ``fetch`` command."""
    values = vars(args)
    params = _parse_assignments(cast(list[str], values.get("param", [])), flag_name="-p/--param")
    list_kwargs: dict[str, object] = dict(params)
    page = cast(int | None, values.get("page"))
    page_size = cast(int | None, values.get("page_size"))
    output_format = cast(str, values.get("format", "table"))
    output_path = cast(str | None, values.get("output"))
    dataset_id = cast(str, values.get("dataset_id"))
    fetch_all = cast(bool, values.get("all", False))

    if page is not None:
        list_kwargs["page"] = page
    if page_size is not None:
        list_kwargs["page_size"] = page_size

    dataset = client.dataset(dataset_id)
    if fetch_all:
        items: list[dict[str, object]] = []
        # Extract max_pages from user-provided params to avoid mypy error
        # User can pass -p max_pages=10, but we need to pass it explicitly
        raw_max_pages = list_kwargs.pop("max_pages", None)

        if raw_max_pages is not None:
            # CLI parser returns strings, so we need to convert "10" to 10
            max_pages_value: int | None = None
            if isinstance(raw_max_pages, str):
                try:
                    max_pages_value = int(raw_max_pages)
                except ValueError as err:
                    raise InvalidRequestError(
                        f"max_pages must be a positive integer or None, got string: {raw_max_pages}"
                    ) from err
            elif isinstance(raw_max_pages, bool):
                raise InvalidRequestError(
                    f"max_pages must be a positive integer or None, got bool: {raw_max_pages}"
                )
            elif isinstance(raw_max_pages, int):
                max_pages_value = raw_max_pages
            else:
                raise InvalidRequestError(
                    f"max_pages must be a positive integer or None, "
                    f"got {type(raw_max_pages).__name__}: {raw_max_pages}"
                )

            if max_pages_value <= 0:
                raise InvalidRequestError(
                    f"max_pages must be a positive integer or None, got {max_pages_value}"
                )
            # Only pass max_pages when explicitly provided by user
            for batch in dataset.list_all(max_pages=max_pages_value, **list_kwargs):
                items.extend(batch.items)
        else:
            # No max_pages specified, use default
            for batch in dataset.list_all(max_pages=None, **list_kwargs):
                items.extend(batch.items)
        rendered = _render_records(items, output_format=output_format)
    else:
        batch = dataset.list(**list_kwargs)
        rendered = _render_records(batch.items, output_format=output_format)
    _write_output(rendered, output_path)
    return 0


def _handle_raw_command(client: Client, args: argparse.Namespace) -> int:
    """Handle the ``raw`` command."""
    values = vars(args)
    params = _parse_assignments(cast(list[str], values.get("param", [])), flag_name="-p/--param")
    dataset_id = cast(str, values.get("dataset_id"))
    operation = cast(str, values.get("operation"))
    output_path = cast(str | None, values.get("output"))
    dataset = client.dataset(dataset_id)
    payload = dataset.call_raw(operation, **params)
    _write_output(json.dumps(_to_jsonable(payload), ensure_ascii=False, indent=2), output_path)
    return 0


def _handle_scaffold_command(args: argparse.Namespace) -> int:
    """Handle ``kpubdata scaffold provider <name>`` — generate a new provider skeleton."""
    from kpubdata.scaffold import scaffold_provider

    values = vars(args)
    sub = cast(str | None, values.get("scaffold_command"))
    if sub != "provider":
        print(
            "error: 'kpubdata scaffold' requires a subcommand (e.g. 'provider')",
            file=sys.stderr,
        )
        return 2

    name = cast(str, values.get("name"))
    dataset_key = cast(str, values.get("dataset_key") or "sample")
    repo_root = Path(cast(str, values.get("repo_root") or "."))
    force = cast(bool, values.get("force", False))

    try:
        result = scaffold_provider(
            name, repo_root=repo_root, dataset_key=dataset_key, overwrite=force
        )
    except (ValueError, FileExistsError) as exc:
        print(f"error: scaffold failed: {exc}", file=sys.stderr)
        return 1

    print(f"Scaffolded provider '{name}' at {result.provider_dir}")
    for path in result.created:
        print(f"  + {path.relative_to(repo_root) if repo_root != Path('.') else path}")
    print("Next steps:")
    print(f"  - fill in adapter logic in {result.adapter_path}")
    print(f"  - replace placeholder catalogue entry in {result.catalogue_path}")
    print(f"  - run: pytest {result.contract_test_path}")
    return 0


def _dataset_summary(dataset: DatasetRef) -> dict[str, object]:
    """Build a JSON-serializable dataset summary."""
    return {
        "id": dataset.id,
        "name": dataset.name,
        "provider": dataset.provider,
        "operations": _operation_names(dataset.operations),
    }


def _dataset_details(dataset: DatasetRef) -> dict[str, object]:
    """Build a JSON-serializable dataset detail mapping."""
    return {
        "id": dataset.id,
        "name": dataset.name,
        "provider": dataset.provider,
        "operations": _operation_names(dataset.operations),
        "capabilities": _query_support_payload(dataset.query_support),
        "raw_metadata_keys": sorted(dataset.raw_metadata.keys()),
    }


def _query_support_payload(query_support: QuerySupport | None) -> dict[str, object] | None:
    """Build a JSON payload describing query support."""
    if query_support is None:
        return None
    return {
        "pagination": query_support.pagination.value,
        "filterable_fields": sorted(query_support.filterable_fields),
        "sortable_fields": sorted(query_support.sortable_fields),
        "time_range": query_support.time_range,
        "max_page_size": query_support.max_page_size,
    }


def _render_records(items: list[dict[str, object]], *, output_format: str) -> str:
    """Render record items in the requested output format."""
    if output_format == "json":
        return json.dumps(_to_jsonable(items), ensure_ascii=False, indent=2)
    if output_format == "csv":
        return _render_csv(items)
    return _render_table(items, headers=_table_headers(items))


def _render_csv(items: list[dict[str, object]]) -> str:
    """Render items as CSV."""
    output = io.StringIO()
    headers = _csv_headers(items)
    writer = csv.DictWriter(output, fieldnames=headers, extrasaction="ignore")
    if headers:
        writer.writeheader()
        for item in items:
            writer.writerow({key: _stringify_value(item.get(key, "")) for key in headers})
    return output.getvalue()


def _render_table(rows: Sequence[Mapping[str, object]], *, headers: Sequence[str]) -> str:
    """Render rows as an aligned text table."""
    if not headers:
        return "(no columns)"
    if not rows:
        return "(no rows)"

    normalized_rows: list[dict[str, str]] = [
        {header: _truncate(_stringify_value(row.get(header, ""))) for header in headers}
        for row in rows
    ]
    widths = {
        header: max(len(header), *(len(row[header]) for row in normalized_rows))
        for header in headers
    }
    header_line = "  ".join(header.ljust(widths[header]) for header in headers)
    separator_line = "  ".join("-" * widths[header] for header in headers)
    body_lines = [
        "  ".join(row[header].ljust(widths[header]) for header in headers)
        for row in normalized_rows
    ]
    return "\n".join([header_line, separator_line, *body_lines])


def _table_headers(items: list[dict[str, object]]) -> list[str]:
    """Return the header keys for a table, capped at the column limit."""
    if not items:
        return []
    return list(items[0].keys())[:_MAX_TABLE_COLUMNS]


def _csv_headers(items: list[dict[str, object]]) -> list[str]:
    """Return the union of item keys, in first-seen order."""
    headers: list[str] = []
    for item in items:
        for key in item:
            if key not in headers:
                headers.append(key)
    return headers


def _parse_assignments(values: Sequence[str], *, flag_name: str) -> dict[str, str]:
    """Parse KEY=VALUE strings into a dict."""
    assignments: dict[str, str] = {}
    for value in values:
        key, parsed_value = _split_assignment(value, flag_name=flag_name)
        assignments[key] = parsed_value
    return assignments


def _split_assignment(value: str, *, flag_name: str) -> tuple[str, str]:
    """Split one KEY=VALUE string; raise InvalidRequestError when malformed."""
    if "=" not in value:
        raise InvalidRequestError(f"{flag_name} expects KEY=VALUE: {value}")
    key, parsed_value = value.split("=", 1)
    normalized_key = key.strip()
    if not normalized_key:
        raise InvalidRequestError(f"{flag_name} expects a non-empty key: {value}")
    return normalized_key, parsed_value


def _write_output(content: str, output_path: str | None) -> None:
    """Write content to stdout or to a file."""
    if output_path is None:
        _ = sys.stdout.write(content)
        if not content.endswith("\n"):
            _ = sys.stdout.write("\n")
        return
    _ = Path(output_path).write_text(content, encoding="utf-8")


def _operation_names(operations: Iterable[Operation]) -> list[str]:
    """Return the sorted operation value names."""
    return sorted(operation.value for operation in operations)


def _to_jsonable(value: object) -> object:
    """Convert a value into a JSON-serializable form."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Enum):
        return cast(object, value.value)
    if isinstance(value, Mapping):
        mapping_value = cast(Mapping[object, object], value)
        return {str(key): _to_jsonable(item) for key, item in mapping_value.items()}
    if isinstance(value, (list, tuple)):
        sequence_value = cast(Sequence[object], value)
        return [_to_jsonable(item) for item in sequence_value]
    if isinstance(value, RecordBatch):
        return {
            "items": _to_jsonable(value.items),
            "dataset": value.dataset.id,
            "total_count": value.total_count,
            "next_page": value.next_page,
            "next_cursor": value.next_cursor,
            "meta": _to_jsonable(value.meta),
            "raw": _to_jsonable(value.raw),
        }
    if isinstance(value, DatasetRef):
        return _dataset_details(value)
    return repr(value)


def _stringify_value(value: object) -> str:
    """Render a value as a display string."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    return json.dumps(_to_jsonable(value), ensure_ascii=False)


def _truncate(value: str) -> str:
    """Truncate a cell to the table width limit."""
    if len(value) <= _MAX_CELL_WIDTH:
        return value
    return f"{value[: _MAX_CELL_WIDTH - 1]}…"


def _print_error(exc: BaseException) -> None:
    """Print an error line to stderr."""
    print(f"error: {type(exc).__name__}: {exc}", file=sys.stderr)


def _get_version() -> str:
    """Return the installed package version."""
    try:
        return version("kpubdata")
    except PackageNotFoundError:
        return __version__


if __name__ == "__main__":
    exit_code = main()
    raise SystemExit(exit_code)
