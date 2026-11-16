"""Exercise declared installed extras and patched dependencies without provider calls."""

from __future__ import annotations

import importlib
import importlib.metadata
import io
import json
import os
import platform
import socket
import ssl
import sys
from contextlib import redirect_stdout
from unittest.mock import patch


def run_smoke() -> dict[str, object]:
    """Fail when an expected extra is missing or a bounded integration no longer works."""
    import certifi
    from opentelemetry.trace import get_current_span
    from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
    from PIL import Image

    ssl.create_default_context(cafile=certifi.where())
    with Image.new("RGB", (2, 2), (11, 22, 33)) as image:
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
    buffer.seek(0)
    with Image.open(buffer) as decoded:
        decoded.load()
        if decoded.size != (2, 2) or decoded.getpixel((0, 0)) != (11, 22, 33):
            raise RuntimeError("Pillow PNG round trip changed")
    context = TraceContextTextMapPropagator().extract(
        {"traceparent": "00-00000000000000000000000000000001-0000000000000002-01"}
    )
    span = get_current_span(context).get_span_context()
    if span.trace_id != 1 or span.span_id != 2 or not span.is_remote:
        raise RuntimeError("OpenTelemetry trace context changed")
    modules = ("pandas", "pykrx", "pydantic", "mcp", "xmltodict", "mkdocs", "pymdownx")
    for module in modules:
        importlib.import_module(module)
    from kpubdata import Client

    datasets = Client(env_keys=False).datasets.list()
    if not datasets:
        raise RuntimeError("SDK catalogue is unexpectedly empty")
    return {
        "python": platform.python_version(),
        "patched_versions": {
            name: importlib.metadata.version(name)
            for name in ("certifi", "Pillow", "opentelemetry-api")
        },
        "tls_context": "passed",
        "png_round_trip": "passed",
        "trace_context": "passed",
        "imported_integrations": list(modules),
        "catalogue": "passed",
        "provider_calls": False,
    }


def main() -> int:
    try:
        # pykrx can log in during import when these environment values exist.
        # Keep this installation check independent of operator credentials.
        with (
            patch.dict(os.environ, {"KRX_ID": "", "KRX_PW": ""}),
            patch.object(
                socket.socket,
                "connect",
                side_effect=RuntimeError("Network disabled in extras smoke"),
            ),
            patch.object(
                socket,
                "create_connection",
                side_effect=RuntimeError("Network disabled in extras smoke"),
            ),
            redirect_stdout(sys.stderr),
        ):
            result = run_smoke()
    except (ImportError, OSError, RuntimeError, ValueError) as exc:
        print(f"Installed extras smoke failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
