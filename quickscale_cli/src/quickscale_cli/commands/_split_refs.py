"""Split-ref parsing and embed-set coverage validation.

Implementation detail of :mod:`quickscale_cli.commands.apply_command`;
collaborators are resolved through the sibling modules that define
them (decisions.md, Split-Facade Seams).
"""

from __future__ import annotations

from collections.abc import Mapping

import click


# AF6 Phase 2 — core step bodies
from quickscale_cli.commands._types import ApplyContext

import quickscale_core.utils.git_errors as _git_errors
import quickscale_core.utils.git_naming as _git_naming
import quickscale_core.utils.git_tags as _git_tags


def _parse_split_ref_overrides(split_refs: tuple[str, ...]) -> dict[str, str]:
    """Parse repeatable ``MODULE=REF`` values without lossy normalization."""
    parsed: dict[str, str] = {}
    seen_modules: set[str] = set()
    for raw_value in split_refs:
        module_name, separator, split_ref = raw_value.partition("=")
        if not separator:
            raise click.BadParameter(
                f"invalid --split-ref value {raw_value!r}: expected MODULE=REF",
                param_hint="--split-ref",
            )
        try:
            _git_naming.validate_module_name(module_name)
            _git_tags.validate_tag_name(split_ref)
        except _git_errors.GitError as error:
            raise click.BadParameter(
                f"invalid --split-ref value {raw_value!r}: {error}",
                param_hint="--split-ref",
            ) from error
        if module_name in seen_modules:
            raise click.BadParameter(
                f"duplicate module {module_name!r} in --split-ref value {raw_value!r}",
                param_hint="--split-ref",
            )
        seen_modules.add(module_name)
        parsed[module_name] = split_ref
    return parsed


def _expand_split_refs_from_branches(ctx: ApplyContext) -> dict[str, str]:
    """
    Map every module being embedded to its canonical ``splits/<name>-module`` branch.

    This is the bulk form of ``--split-ref``.  Every override in the pre-seal
    verification flow is mechanically the module's own split branch, so deriving
    them removes a dozen hand-typed arguments -- and with them the chance of
    typing one wrong or omitting one, which the exact-coverage rule would reject
    only after the operator had already retyped the whole line.

    The result covers exactly the embed set by construction, so
    :func:`_validate_split_ref_override_coverage` cannot fail on it.  It is
    recomputed against the refreshed context after the advisory lock is taken,
    because the embed set itself can change there.
    """
    try:
        return {
            module_name: _git_naming.resolve_split_branch(module_name)
            for module_name in sorted(_module_names_to_embed(ctx))
        }
    except _git_errors.GitError as error:
        raise click.UsageError(f"--split-refs-from-branches: {error}") from error


def _module_names_to_embed(ctx: ApplyContext) -> set[str]:
    """Return the exact module target set for this apply pass."""
    if ctx.existing_state is None:
        return set(ctx.qs_config.modules.keys())
    return set(ctx.delta.modules_to_add)


def _validate_split_ref_override_coverage(
    ctx: ApplyContext,
    split_ref_overrides: Mapping[str, str] | None,
    *,
    no_modules: bool,
) -> None:
    """Require explicit overrides to cover exactly the modules being added."""
    overrides = split_ref_overrides or {}
    if not overrides:
        return
    if no_modules:
        raise click.UsageError("--split-ref cannot be combined with --no-modules")

    target_modules = _module_names_to_embed(ctx)
    if not target_modules:
        raise click.UsageError(
            "--split-ref cannot be used when this apply has no modules to embed"
        )

    unknown = sorted(set(overrides) - target_modules)
    missing = sorted(target_modules - set(overrides))
    if unknown or missing:
        details: list[str] = []
        if unknown:
            details.append("unknown modules: " + ", ".join(unknown))
        if missing:
            details.append("missing modules: " + ", ".join(missing))
        raise click.UsageError(
            "--split-ref mappings must cover exactly the modules being embedded ("
            + "; ".join(details)
            + ")"
        )
