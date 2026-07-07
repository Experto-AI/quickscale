"""
QuickScale runtime API facade — combined re-export surface.

This is the public import path for generated-project code and module-owned
adapters.  It re-exports all symbols from two sub-modules:

* ``runtime.dr`` — DR adapter functions, primitives, and lazy backup-dependent
  symbols (orchestration, recovery, verification).
* ``runtime.manifest`` — manifest resolver, assembler, social-manifest path
  constants, renderers, and wiring types.

Module-owned adapters (e.g. ``quickscale_modules_social.adapter``) should
import from ``quickscale_core.runtime.manifest`` directly to avoid pulling
in the DR surface at import time and triggering circular imports.

Backward-compatible: all existing imports from ``quickscale_core.runtime``
continue to work through this combined facade.
"""

from __future__ import annotations

import typing

# Import sub-modules as module objects — no eager ``from ... import *``
# for lazy-loaded DR symbols (orchestration, recovery, verification).
from quickscale_core.runtime import dr as _dr  # noqa: F401
from quickscale_core.runtime import manifest as _manifest  # noqa: F401

# Build combined __all__ from both sub-modules (union).
__all__ = list(_dr.__all__) + [
    sym for sym in _manifest.__all__ if sym not in _dr.__all__
]


def __getattr__(name: str) -> typing.Any:
    """Resolve attribute from ``dr`` or ``manifest`` sub-module."""
    if hasattr(_dr, name):
        return getattr(_dr, name)
    if hasattr(_manifest, name):
        return getattr(_manifest, name)
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)


def __dir__() -> list[str]:
    """Include lazy symbols in module dir()."""
    return sorted(__all__)
