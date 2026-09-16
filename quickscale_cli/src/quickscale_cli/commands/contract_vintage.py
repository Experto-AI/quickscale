"""Shared project-contract vintage checks for CLI command boundaries."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import cast

import click

from quickscale_core.contracts.resolvers import load_module_manifest_with_fallback
from quickscale_core.manifest import (
    ContractVintage,
    ModuleManifest,
    parse_version_tuple,
)
from quickscale_core.schema.state_schema import QuickScaleState


ACKNOWLEDGE_CONTRACT_VINTAGE_OPTION = "--acknowledge-contract-vintage"


def check_contract_vintage(
    project_contract: str | None,
    manifests: Mapping[str, ModuleManifest] | None,
    *,
    requirements: Mapping[str, ContractVintage] | None = None,
) -> dict[str, object]:
    """Compare declared requirements with a project's recorded contract."""
    declared: dict[str, ContractVintage] = {}
    for module_name, manifest in (manifests or {}).items():
        if manifest.contract_vintage is not None:
            declared[module_name] = manifest.contract_vintage
    declared.update(requirements or {})

    project_tuple = parse_version_tuple(project_contract) if project_contract else (0,)
    consumers_behind: list[dict[str, object]] = []
    for consumer, vintage in declared.items():
        if project_tuple < parse_version_tuple(vintage.minimum):
            consumers_behind.append(
                {
                    "module": consumer,
                    "minimum": vintage.minimum,
                    "manual_adoption_steps": list(vintage.manual_adoption_steps),
                }
            )

    return {
        "project_contract": project_contract,
        "modules_behind": consumers_behind,
        "module_count": len(declared),
        "modules_behind_count": len(consumers_behind),
    }


def load_shipped_contract_manifests(
    module_names: Iterable[str],
) -> dict[str, ModuleManifest]:
    """Load current shipped manifests rather than a project's older copies."""
    manifests: dict[str, ModuleManifest] = {}
    for module_name in sorted(set(module_names)):
        try:
            manifests[module_name] = load_module_manifest_with_fallback(module_name)
        except Exception as error:
            raise click.ClickException(
                f"Unable to check the contract vintage for module {module_name!r}: "
                f"{error}"
            ) from error
    return manifests


def enforce_contract_vintage(
    state: QuickScaleState | None,
    manifests: Mapping[str, ModuleManifest] | None,
    *,
    operation: str,
    acknowledged: bool,
    requirements: Mapping[str, ContractVintage] | None = None,
) -> None:
    """Refuse an operation when upgradable code outruns generated files."""
    if state is None:
        return

    diagnostics = check_contract_vintage(
        state.project.project_contract,
        manifests,
        requirements=requirements,
    )
    consumers_behind = cast(list[dict[str, object]], diagnostics["modules_behind"])
    if not consumers_behind:
        return

    if acknowledged:
        click.secho(
            f"⚠️  Contract-vintage gap explicitly acknowledged for {operation}.",
            fg="yellow",
            err=True,
        )
        return

    project_contract = state.project.project_contract or "unknown (legacy project)"
    click.secho(
        f"\n❌ Cannot run {operation}: project contract {project_contract} is behind.",
        fg="red",
        err=True,
        bold=True,
    )
    for entry in consumers_behind:
        click.echo(
            f"  • {entry['module']} requires project_contract >= {entry['minimum']}",
            err=True,
        )
        adoption_steps = cast(list[str], entry["manual_adoption_steps"])
        for step in adoption_steps:
            click.echo(f"    - {step}", err=True)
    click.echo(
        "\nComplete every adoption step before retrying. If those files are already "
        f"updated, re-run with {ACKNOWLEDGE_CONTRACT_VINTAGE_OPTION} to acknowledge "
        "the compatibility boundary for this invocation.",
        err=True,
    )
    raise click.Abort()


def enforce_shipped_contract_vintage(
    state: QuickScaleState | None,
    module_names: Iterable[str],
    *,
    operation: str,
    acknowledged: bool,
) -> None:
    """Enforce current shipped module requirements for an existing project."""
    if state is None:
        return
    enforce_contract_vintage(
        state,
        load_shipped_contract_manifests(module_names),
        operation=operation,
        acknowledged=acknowledged,
    )
