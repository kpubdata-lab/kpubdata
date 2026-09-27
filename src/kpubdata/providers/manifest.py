"""Built-in provider manifest — single source of truth for provider discovery.

Each entry maps a provider name to its module path and adapter class name.
``Client`` uses lazy import of these modules on first access, so unused
providers incur no import cost.

To add a new built-in provider, append an entry here. No other files need
modification for default registration.
"""

from __future__ import annotations

#: (provider_name, module_path, adapter_class_name)
BUILTIN_PROVIDERS: tuple[tuple[str, str, str], ...] = (
    ("datago", "kpubdata.providers.datago", "DataGoAdapter"),
    ("bok", "kpubdata.providers.bok", "BokAdapter"),
    ("law", "kpubdata.providers.law", "LawAdapter"),
    ("seoul", "kpubdata.providers.seoul", "SeoulAdapter"),
    ("kosis", "kpubdata.providers.kosis", "KosisAdapter"),
    ("lofin", "kpubdata.providers.lofin", "LofinAdapter"),
    ("localdata", "kpubdata.providers.localdata.adapter", "LocaldataAdapter"),
    ("semas", "kpubdata.providers.semas.adapter", "SemasAdapter"),
    ("krx", "kpubdata.providers.krx", "KrxAdapter"),
    ("sgis", "kpubdata.providers.sgis", "SgisAdapter"),
    ("neis", "kpubdata.providers.neis", "NeisAdapter"),
    ("fds", "kpubdata.providers.fds", "FdsAdapter"),
    ("korean", "kpubdata.providers.korean", "KoreanAdapter"),
    ("kipris", "kpubdata.providers.kipris", "KiprisAdapter"),
)
