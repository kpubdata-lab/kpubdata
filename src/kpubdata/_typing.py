"""The single place that reaches for ``typing_extensions`` until the stdlib has it.

Four modules imported ``typing_extensions`` unconditionally while the dependency
marker said ``python_version < '3.11'``. A fresh install on 3.11 or newer
therefore had the import statements but not the package, and ``import kpubdata``
itself died with an ImportError. CI never showed it because CI always installs
the dev extra, which pulls ``typing_extensions`` in.

One marker cannot cover both names, because they landed in the stdlib in
different releases -- ``dataclass_transform`` in 3.11, ``override`` in 3.12. The
split lives here, and the marker is set to the wider of the two (below 3.12).
"""

from __future__ import annotations

import sys

if sys.version_info >= (3, 12):
    from typing import override
else:  # pragma: no cover - only taken on 3.11 and older
    from typing_extensions import override

if sys.version_info >= (3, 11):
    from typing import dataclass_transform
else:  # pragma: no cover - only taken on 3.10
    from typing_extensions import dataclass_transform

__all__ = ["dataclass_transform", "override"]
