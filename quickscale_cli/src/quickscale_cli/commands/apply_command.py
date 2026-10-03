"""Apply command for executing project configuration.

The implementation lives in private sibling modules grouped by concern
(``_types``, ``_git_ops``, ``_steps``, ...); this module owns the public
command surface, re-exports public names for unchanged import paths, and
resolves collaborators through the sibling modules that define them
(decisions.md, Split-Facade Seams).
"""

from __future__ import annotations

import shlex as shlex
from pathlib import (
    Path as Path,
)
import click as click
from quickscale_core.contracts.module_options import (
    ANALYTICS_POSTHOG_DEFAULT_HOST as ANALYTICS_POSTHOG_DEFAULT_HOST,
    BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR_OPTION as BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR_OPTION,
    BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR_OPTION as BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR_OPTION,
    NOTIFICATIONS_RESEND_API_KEY_ENV_VAR_OPTION as NOTIFICATIONS_RESEND_API_KEY_ENV_VAR_OPTION,
    NOTIFICATIONS_WEBHOOK_SECRET_ENV_VAR_OPTION as NOTIFICATIONS_WEBHOOK_SECRET_ENV_VAR_OPTION,
    sanitize_module_options as sanitize_module_options,
    SOCIAL_EMBEDS_PATH as SOCIAL_EMBEDS_PATH,
    SOCIAL_INTEGRATION_BASE_PATH as SOCIAL_INTEGRATION_BASE_PATH,
    SOCIAL_INTEGRATION_EMBEDS_PATH as SOCIAL_INTEGRATION_EMBEDS_PATH,
    SOCIAL_LINK_TREE_PATH as SOCIAL_LINK_TREE_PATH,
)
from quickscale_core.contracts.resolvers import (
    load_module_manifest_with_fallback as load_module_manifest_with_fallback,
    resolve_manifest_module_options as resolve_manifest_module_options,
)
from quickscale_core.manifest.option_validation import (
    validate_module_options as validate_module_options,
)
from quickscale_core.contracts.module_catalog import (
    find_not_ready_modules as find_not_ready_modules,
    get_module_readiness_reason as get_module_readiness_reason,
)
from quickscale_core.manifest.required_modules import (
    resolve_required_modules as resolve_required_modules,
)
from quickscale_cli.commands.apply_support import (
    notifications_adapter_module as notifications_adapter_module,
)
from quickscale_cli.commands.contract_vintage import (
    declared_adoption_step_ids as declared_adoption_step_ids,
    enforce_shipped_contract_vintage as enforce_shipped_contract_vintage,
    record_contract_adoption as record_contract_adoption,
)
from quickscale_cli.commands.module_commands import (
    APPLY_MODULE_EXECUTION_MODE as APPLY_MODULE_EXECUTION_MODE,
    embed_module as embed_module,
    ModuleEmbedProvenance as ModuleEmbedProvenance,
)
from quickscale_cli.utils.module_dependency_sync import (
    DependencySyncError as DependencySyncError,
    sync_project_core_dependency as sync_project_core_dependency,
    sync_project_module_dependencies as sync_project_module_dependencies,
)
from quickscale_cli.utils.docker_utils import (
    compose_down as compose_down,
    find_stale_project_volumes as find_stale_project_volumes,
    remove_volumes as remove_volumes,
)
from quickscale_cli.utils.module_wiring_manager import (
    regenerate_managed_wiring as regenerate_managed_wiring,
)
from quickscale_cli.utils.railway_utils import (
    deploy_railway_service as deploy_railway_service,
    get_app_service_name as get_app_service_name,
)
from quickscale_core.schema.config_schema import (
    ConfigValidationError as ConfigValidationError,
    ModuleConfig as ModuleConfig,
    QuickScaleConfig as QuickScaleConfig,
    generate_yaml as generate_yaml,
    validate_config as validate_config,
)
from quickscale_core.schema.delta import (
    ConfigDelta as ConfigDelta,
    compute_delta as compute_delta,
    format_delta as format_delta,
)
from quickscale_core.schema.state_schema import (
    ManagedFileRecord as ManagedFileRecord,
    ModuleState as ModuleState,
    ProjectState as ProjectState,
    QuickScaleState as QuickScaleState,
    StateError as StateError,
    StateManager as StateManager,
)
from quickscale_core import __version__ as quickscale_version  # noqa: F401
from quickscale_core.config import (
    normalize_installed_version as normalize_installed_version,
)
from quickscale_core.apply import (
    APPLY_STEPS as APPLY_STEPS,
    ApplyExecutor as ApplyExecutor,
    ApplyStep as ApplyStep,
    LedgerError as LedgerError,
    LedgerManager as LedgerManager,
    RecoveryLedger as RecoveryLedger,
)
from quickscale_core.advisory_lock import (
    AdvisoryLock as AdvisoryLock,
    AdvisoryLockContentionError as AdvisoryLockContentionError,
)
from quickscale_core.project_state import (
    ConfigError as ConfigError,
    DEFAULT_MANAGED_WIRING_PATHS as DEFAULT_MANAGED_WIRING_PATHS,
    ProjectStateManager as ProjectStateManager,
    VersionDriftWarning as VersionDriftWarning,
    check_version_drift as check_version_drift,
    compute_file_hashes as compute_file_hashes,
)
from quickscale_core.utils.theme_validation import (
    ThemeValidationError as ThemeValidationError,
    validate_theme_preflight as validate_theme_preflight,
)
from quickscale_core.utils.git_utils import (
    GitError as GitError,
    is_working_directory_clean as is_working_directory_clean,
    resolve_remote_ref as resolve_remote_ref,
    resolve_split_branch as resolve_split_branch,
    validate_module_name as validate_module_name,
    validate_tag_name as validate_tag_name,
)
from quickscale_core.generator import ProjectGenerator as ProjectGenerator
from quickscale_core.manifest import ModuleManifest as ModuleManifest
from quickscale_core.manifest.loader import (
    ManifestError as ManifestError,
    get_manifest_for_module as get_manifest_for_module,
)
from quickscale_core.apply.steps import (
    GitIndexSnapshot as GitIndexSnapshot,
    step_apply_mutable_config as step_apply_mutable_config,
    step_backups_gitignore as step_backups_gitignore,
    step_capture_hashes as step_capture_hashes,
    step_display_next_steps as step_display_next_steps,
    step_embed_modules as step_embed_modules,
    step_finalize_state as step_finalize_state,
    step_notifications_env_sync as step_notifications_env_sync,
    step_analytics_env_sync as step_analytics_env_sync,
    step_billing_env_sync as step_billing_env_sync,
    step_post_embed_snapshot as step_post_embed_snapshot,
    step_post_generation_setup as step_post_generation_setup,
    step_railway_deploy as step_railway_deploy,
    step_regenerate_wiring as step_regenerate_wiring,
    step_run_migrations as step_run_migrations,
    step_start_docker as step_start_docker,
    step_sync_dependencies as step_sync_dependencies,
    sync_env_example_blocks as sync_env_example_blocks,
)
from quickscale_core.apply.steps.types import (
    StepContext as StepContext,
    StepOutcome as StepOutcome,
)
from quickscale_cli.commands._types import ApplyContext as ApplyContext
from quickscale_cli.commands._types import EmbedModulesResult as EmbedModulesResult
import quickscale_cli.commands.apply_support as _apply_support
import quickscale_cli.commands.contract_vintage as _contract_vintage
import quickscale_cli.commands._generation as _generation
import quickscale_cli.commands._split_refs as _split_refs
import quickscale_cli.commands._context as _context
import quickscale_cli.commands._steps as _steps


@click.command()
@click.argument(
    "config",
    required=False,
    type=click.Path(exists=True),
    default="quickscale.yml",
)
@click.option(
    "--force",
    "-f",
    is_flag=True,
    help="Overwrite existing project directory",
)
@click.option(
    "--no-docker",
    is_flag=True,
    help="Skip Docker operations even if configured",
)
@click.option(
    "--no-modules",
    is_flag=True,
    help="Skip module embedding",
)
@click.option(
    "--split-ref",
    "split_refs",
    metavar="MODULE=REF",
    multiple=True,
    help="Use an explicit split ref for each module being embedded (repeatable).",
)
@click.option(
    "--split-refs-from-branches",
    is_flag=True,
    help=(
        "Embed every module from its own splits/<module>-module branch. "
        "Bulk form of --split-ref for pre-seal release verification."
    ),
)
@click.option(
    "--verbose-docker",
    is_flag=True,
    help="Show Docker build output (useful for debugging build issues)",
)
@click.option(
    "--acknowledge-contract-vintage",
    is_flag=True,
    help="Proceed after manually adopting every required generated-file contract.",
)
@click.option(
    "--confirm-contract-adoption",
    is_flag=True,
    help=(
        "Record the generated-project contract adoption in .quickscale/state.yml "
        "and proceed."
    ),
)
def apply(
    config: str,
    force: bool,
    no_docker: bool,
    no_modules: bool,
    split_refs: tuple[str, ...],
    split_refs_from_branches: bool,
    verbose_docker: bool,
    acknowledge_contract_vintage: bool,
    confirm_contract_adoption: bool,
) -> None:
    """
    Execute project configuration from quickscale.yml.

    Generates a Django project based on the configuration file,
    embeds selected modules, and optionally starts Docker services.

    Apply is resumable from the first unsatisfied step when a
    recovery checkpoint exists (``.quickscale/apply-recovery.yml``).
    Steps 11-16 are gated behind a destructive/remote confirmation
    prompt: the operator must explicitly confirm before Docker startup,
    database migrations, Railway deploy, or state finalization proceed.

    \b
    Examples:
      quickscale apply                    # Use quickscale.yml in current dir
      quickscale apply myapp/quickscale.yml  # Use specific config file
      quickscale apply --force            # Overwrite existing project
      quickscale apply --no-docker        # Skip Docker operations
      quickscale apply --verbose-docker   # Show Docker build output

    \b
    Execution Order:
      1. Validate configuration
      2. Generate project (new projects only)
      3. Initialize git + initial commit (new projects only)
      4. Embed modules (fail-fast on required module failure)
      5. Snapshot post-embed state for recovery
      6. Regenerate managed module wiring
      7. Capture managed file hashes
      8. Harden backups gitignore + sync env-example files
      9. Sync embedded-module Poetry dependencies
      10. Refresh poetry.lock + install
      --- destructive/remote phase (operator confirmation required) ---
      11. Apply mutable config changes
      12. Start Docker (if configured)
      13. Run database migrations (Docker or local)
      14. Trigger Railway deploy (if Railway-linked)
      15. Finalize authoritative state
      16. Display next steps
    """
    if split_refs and split_refs_from_branches:
        raise click.UsageError(
            "--split-refs-from-branches cannot be combined with --split-ref"
        )
    split_ref_overrides = _split_refs._parse_split_ref_overrides(split_refs)
    config_path = Path(config)
    output_path = _context._resolve_apply_preflight(config_path)
    _context._enforce_apply_contract_vintage_preflight(
        config_path,
        output_path,
        acknowledged=acknowledge_contract_vintage,
        confirmed=confirm_contract_adoption,
    )

    # Prepare context
    ctx = _context._prepare_apply_context(config_path)
    ctx.confirm_contract_adoption = confirm_contract_adoption
    _contract_vintage.enforce_shipped_contract_vintage(
        ctx.existing_state,
        set(ctx.qs_config.modules)
        | set(ctx.existing_state.modules if ctx.existing_state else ()),
        operation="'quickscale apply'",
        acknowledged=acknowledge_contract_vintage or confirm_contract_adoption,
    )
    if split_refs_from_branches:
        split_ref_overrides = _split_refs._expand_split_refs_from_branches(ctx)
    _split_refs._validate_split_ref_override_coverage(
        ctx,
        split_ref_overrides,
        no_modules=no_modules,
    )

    # Display configuration summary
    _generation._display_config_summary(ctx.qs_config)

    # Probe whether provenance repair might be needed before the no-op gate.
    # The actual repair is deferred to the locked path inside
    # _execute_apply_steps (CR-F26-001).
    has_pending_provenance_repair = _context._provenance_repair_might_be_needed(ctx)

    # Adoption-only confirmation: a project whose configuration is unchanged
    # still needs a path to record the confirmed adoption (SA207).  The record
    # is written under the same advisory lock the mutating path uses.
    if (
        confirm_contract_adoption
        and ctx.existing_state is not None
        and not ctx.delta.has_changes
        and not ctx.has_pending_post_embed_recovery
        and not has_pending_provenance_repair
    ):
        adopted = _context._record_confirmed_adoption(ctx)
        if adopted is None:
            # A concurrent apply landed between the pre-lock read and the
            # lock.  The desired configuration in memory may be stale, so do
            # not act on it: ask the operator to re-run against the current
            # state instead of applying a stale desired snapshot.
            click.secho(
                "\n⚠️  The project configuration changed while waiting for "
                "the state lock. Re-run the same command "
                f"(quickscale apply {shlex.quote(str(config))} "
                "--confirm-contract-adoption) to "
                "apply the current configuration.",
                fg="yellow",
                err=True,
            )
            raise click.Abort()
        if not adopted:
            raise click.Abort()
        click.secho(
            "\n✅ Nothing else to do. Configuration matches applied state.",
            fg="green",
        )
        return

    # Handle delta and existing state
    _context._handle_delta_and_existing_state(
        ctx.delta,
        ctx.existing_state,
        has_pending_post_embed_recovery=ctx.has_pending_post_embed_recovery,
        has_pending_provenance_repair=has_pending_provenance_repair,
    )

    # Check output directory
    _generation._check_output_directory(ctx.output_path, ctx.existing_state, force)

    show_docker_output = _apply_support._confirm_apply(
        ctx,
        no_docker=no_docker,
        verbose_docker=verbose_docker,
    )

    # Execute apply steps
    _steps._execute_apply_steps(
        ctx,
        force,
        no_docker,
        no_modules,
        show_docker_output,
        split_ref_overrides,
        split_refs_from_branches=split_refs_from_branches,
    )
