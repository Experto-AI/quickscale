"""Manifest-to-ModuleWiringSpec assembler.

Turns a :class:`~quickscale_core.manifest.resolver.ResolverResult` (the
output of the manifest-driven resolver) into a
:class:`~quickscale_core.module_wiring.ModuleWiringSpec` that the wiring
renderer can write to disk.

Post-resolution hook seam
--------------------------
Adapter code that needs to override or augment individual spec fields (for
gnarly cases the generic resolver cannot express) should supply a callable
matching :data:`PostResolutionHook`:

    def my_hook(spec: ModuleWiringSpec, resolved: ResolvedOptions) -> ModuleWiringSpec:
        ...

Pass the hook to :func:`assemble_wiring_spec` via the ``post_hook``
keyword argument.  The hook receives the spec assembled from the resolver
result and the module's declared, canonical resolved option values as a
frozen, typed
:class:`~quickscale_core.manifest.resolved_options.ResolvedOptions`
object, and must return a ``ModuleWiringSpec`` instance (either the
original or a new one).  Only the manifest's declared options are exposed:
a supplied key the manifest does not declare never reaches the hook.

The precedent for this pattern is
the per-module post-resolution hooks in ``quickscale_core.contracts.resolvers``,
which applies analytics-specific domain logic after the generic resolver
pipeline.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from quickscale_core.manifest.loader import ManifestError
from quickscale_core.manifest.resolved_options import ResolvedOptions
from quickscale_core.manifest.resolver import ResolverResult
from quickscale_core.manifest.schema import MANAGED_FILE_ROOT_PREFIX
from quickscale_core.module_wiring import ModuleWiringSpec


# ---------------------------------------------------------------------------
# Type alias for the post-resolution hook
# ---------------------------------------------------------------------------

PostResolutionHook = Callable[
    [ModuleWiringSpec, ResolvedOptions],
    ModuleWiringSpec,
]
"""Callable type for per-adapter post-resolution hooks.

Args:
    spec: The :class:`~quickscale_core.module_wiring.ModuleWiringSpec`
        assembled from the resolver result.
    resolved: The module's declared, canonical resolved option values as a
        frozen, typed
        :class:`~quickscale_core.manifest.resolved_options.ResolvedOptions`
        object (a private copy — a hook reads attributes and cannot
        mutate; a supplied key the manifest does not declare is absent).

Returns:
    A :class:`~quickscale_core.module_wiring.ModuleWiringSpec`.  May be
    the same object received or a new instance with augmented fields.
"""


# ---------------------------------------------------------------------------
# Assembler
# ---------------------------------------------------------------------------


def _build_managed_files_mapping(
    result: ResolverResult,
) -> dict[str, str]:
    """Convert managed-file declarations into a ``ModuleWiringSpec`` mapping.

    Each declaration's ``output_path`` becomes the key and its ``renderer``
    identifier becomes the value.  This is a structural placeholder —
    content generation is deferred to a later phase.

    Declarations whose ``output_path`` does not start with
    ``quickscale_managed/`` are silently skipped as a defense-in-depth
    measure (the loader already rejects such paths at parse time).

    Args:
        result: The resolver result carrying managed-file declarations.

    Returns:
        A dict mapping output paths to renderer identifiers.
    """
    managed: dict[str, str] = {}
    for declaration in result.managed_files:
        if not declaration.output_path.startswith(MANAGED_FILE_ROOT_PREFIX):
            continue
        managed[declaration.output_path] = declaration.renderer
    return managed


def _declared_resolved_options(result: ResolverResult) -> dict[str, Any]:
    """Return *result*'s resolved values restricted to its declared options.

    The resolver merges every supplied override into ``resolved``, so a key
    the manifest does not declare would otherwise reach a hook as a raw,
    unvalidated attribute.  The manifest's defaults cover every option it
    declares, so their keys are exactly the hook's canonical option surface.

    Args:
        result: The resolver result whose declared options are exposed.

    Returns:
        The declared subset of ``result.resolved``, values untouched.
    """
    declared = result.defaults.keys()
    return {name: value for name, value in result.resolved.items() if name in declared}


def assemble_wiring_spec(
    result: ResolverResult,
    *,
    post_hook: PostResolutionHook | None = None,
) -> ModuleWiringSpec:
    """Assemble a :class:`~quickscale_core.module_wiring.ModuleWiringSpec`
    from a manifest resolver result.

    Copies the resolver-projected wiring fields (apps, middleware,
    url_includes, pre_home_url_includes) and derived settings directly into
    a frozen ``ModuleWiringSpec``.  The ``managed_files`` field is populated
    from the resolver result's manifest-declared managed-file declarations:
    each declaration's ``output_path`` maps to its ``renderer`` identifier.
    Content generation for managed files is deferred to a later phase.

    If a *post_hook* is provided it is called with the assembled spec and the
    module's declared, canonical resolved option values as a frozen, typed
    :class:`ResolvedOptions` object, allowing adapter code to override or
    augment specific fields for cases the generic resolver cannot express.
    An undeclared supplied key is not part of the hook's option surface.

    Args:
        result: The :class:`~quickscale_core.manifest.resolver.ResolverResult`
            produced by :func:`~quickscale_core.manifest.resolver.resolve_module_config`.
        post_hook: Optional adapter-supplied callable for post-resolution
            augmentation.  See :data:`PostResolutionHook`.

    Returns:
        A frozen :class:`~quickscale_core.module_wiring.ModuleWiringSpec`
        ready for use with
        :func:`~quickscale_core.module_wiring.write_managed_wiring`.

    Raises:
        ManifestError: When ``result.validation_issues`` is non-empty.  The
            error message lists each issue on a separate line prefixed with
            ``"  • "`` so the caller (typically
            :func:`~quickscale_core.manifest.entry_point.build_manifest_wiring_spec`)
            can surface them to the operator.
    """
    if result.validation_issues:
        issues_str = "\n".join(f"  • {issue}" for issue in result.validation_issues)
        raise ManifestError(
            f"Module '{result.module_name}' has validation issues "
            f"that must be resolved before assembly:\n{issues_str}"
        )

    spec = ModuleWiringSpec(
        apps=result.apps,
        middleware=result.middleware,
        settings=dict(result.derived_settings),
        pre_home_url_includes=result.pre_home_url_includes,
        url_includes=result.url_includes,
        spa_routes=result.spa_routes,
        managed_files=_build_managed_files_mapping(result),
    )

    if post_hook is not None:
        spec = post_hook(spec, ResolvedOptions(_declared_resolved_options(result)))

    return spec


__all__ = [
    "PostResolutionHook",
    "ResolvedOptions",
    "assemble_wiring_spec",
]
