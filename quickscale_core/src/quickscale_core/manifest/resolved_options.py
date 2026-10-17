"""Frozen, typed resolved-options object handed to adapter hooks.

The manifest boundary validates, coerces, and defaults every option before any
post-resolution hook runs; a hook consumes the resulting canonical values.
:class:`ResolvedOptions` is the object that carries them: one read-only
attribute per resolved option, and deliberately no mapping interface.

Container idioms a hook might use to re-read an option — ``resolved["key"]``,
``resolved.get("key", fallback)``, iteration over the container — fail with
``TypeError`` or ``AttributeError`` by construction, so a hook cannot re-read
an option through a raw container or manufacture a fallback for a value the
boundary already defaulted.  That is what makes the hook boundary structural
instead of policed by an adapter-code detector (arch audit
``rules-held-by-parity-not-derivation``, option 2).

The object is a shallow, frozen wrapper: the values are the canonical resolved
values exactly as the manifest boundary produced them, and the object holds a
private copy, so a hook cannot reach the resolver result through it.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Any, cast


class ResolvedOptions:
    """Frozen attribute surface over one module's resolved option values.

    Each option the module's manifest declares is exposed as an attribute
    holding its canonical resolved value (the manifest's own default when the
    caller supplied none).  Attributes are read-only: assignment and deletion
    raise ``AttributeError``, and a name that is not a resolved option raises
    ``AttributeError`` naming it.  There is no ``__getitem__``, ``get``,
    iteration, or length, so a raw container read fails by construction.
    """

    __slots__ = ("_values",)

    def __init__(self, values: Mapping[str, Any]) -> None:
        """Wrap *values* (already canonical) as a frozen, private copy."""
        object.__setattr__(self, "_values", MappingProxyType(dict(values)))

    def __getattr__(self, name: str) -> Any:
        """Return the resolved option *name*, or refuse a non-option read."""
        try:
            values = object.__getattribute__(self, "_values")
        except AttributeError:
            raise AttributeError(name) from None
        try:
            return values[name]
        except KeyError:
            raise AttributeError(
                f"{type(self).__name__!r} exposes resolved options as attributes "
                f"only; it carries no resolved option {name!r}"
            ) from None

    def __setattr__(self, name: str, value: Any) -> None:
        """Refuse every write: the resolved options are frozen."""
        raise AttributeError(f"{type(self).__name__!r} is frozen; cannot set {name!r}")

    def __delattr__(self, name: str) -> None:
        """Refuse every delete: the resolved options are frozen."""
        raise AttributeError(
            f"{type(self).__name__!r} is frozen; cannot delete {name!r}"
        )

    def __repr__(self) -> str:
        """Return an attribute-form representation of the resolved values."""
        values = object.__getattribute__(self, "_values")
        entries = ", ".join(f"{key}={value!r}" for key, value in values.items())
        return f"{type(self).__name__}({entries})"


def _resolved_values(resolved: ResolvedOptions) -> Mapping[str, Any]:
    """Return the frozen values of *resolved* for core-side evaluation.

    The option-validation engine evaluates a manifest's declared rules against
    an already-resolved option set (Module Conventions rule 12).  The accessor
    is a module-private function rather than a method, so adapter hooks — which
    hold only the :class:`ResolvedOptions` object — still cannot re-read an
    option through a mapping surface (SA281's boundary by construction).
    """
    return cast("Mapping[str, Any]", object.__getattribute__(resolved, "_values"))


__all__ = ["ResolvedOptions"]
