"""Step bodies for backups gitignore hardening and the shared env-example sync.

Steps 5-8 handle post-embed file maintenance that keeps the generated
project's supporting files aligned with module configuration:

- Step 5: Backups gitignore hardening
- Step 6: Notifications env-example sync
- Step 7: Analytics env-example sync
- Step 8: Billing env-example sync

The three env-example steps all invoke :func:`sync_env_example_blocks`, the
single owner of the generated ``.env.example`` credential contract:

* one :class:`EnvExampleModuleSpec` per credential-bearing module declares the
  ordered ``*_env_var`` options that module's manifest already declares, the
  conventional fallback name for a blank declaration, and the module-specific
  prose the managed block carries;
* :func:`render_env_example_block` renders that declaration into the managed
  block under the existing marker convention;
* :func:`sync_env_example_blocks` splices, replaces, or removes every enabled
  module's block in one pass and writes the file at most once.

The sync is idempotent and covers the full declared set, so the three legacy
stations (6, 7, 8) each invoke it and any apply resume point among them lands
a complete contract.  The stations keep their names, labels, and messages
because they are recovery sentinels recorded in the apply recovery ledger.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from functools import partial
from pathlib import Path
from typing import Any

from quickscale_core.apply.steps.types import StepContext, StepOutcome
from quickscale_core.contracts.module_options import (
    ANALYTICS_POSTHOG_DEFAULT_HOST,
    BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR_OPTION,
    BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR_OPTION,
    BILLING_ENV_VAR_OPTION_NAMES,
    DEFAULT_NOTIFICATIONS_RESEND_API_KEY_ENV_VAR,
    DEFAULT_NOTIFICATIONS_WEBHOOK_SECRET_ENV_VAR,
    DEFAULT_STORAGE_ACCESS_KEY_ID_ENV_VAR,
    DEFAULT_STORAGE_SECRET_ACCESS_KEY_ENV_VAR,
    NOTIFICATIONS_RESEND_API_KEY_ENV_VAR_OPTION,
    NOTIFICATIONS_WEBHOOK_SECRET_ENV_VAR_OPTION,
    STORAGE_ACCESS_KEY_ID_ENV_VAR_OPTION,
    STORAGE_SECRET_ACCESS_KEY_ENV_VAR_OPTION,
)
from quickscale_core.contracts.resolvers import (
    load_module_manifest_with_fallback,
    resolve_manifest_module_options,
    resolve_notifications_module_options,
    resolve_storage_module_options,
)

#: Generated file that carries the managed module credential contract.
ENV_EXAMPLE_FILENAME = ".env.example"


# ---------------------------------------------------------------------------
# Declaration-driven managed blocks
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EnvExampleModuleSpec:
    """One module's declared ``.env.example`` credential contract.

    Attributes:
        module: Module name as it appears in ``quickscale.yml``.
        title: Human-readable marker title (``# QuickScale <title> (managed)``).
        env_var_options: Ordered option names that declare environment
            variables; each renders as a ``NAME=`` placeholder using the
            resolved option value.
        env_var_defaults: Conventional environment-variable name used when a
            resolved option value is blank; a module whose manifest declares
            the option omits this and falls back to the manifest default.
        resolve_options: Resolver that merges the declared manifest defaults
            with the configured option overrides.
        prose: Hook returning the module-specific guidance lines that precede
            the placeholders.
        tail_lines: Optional fixed lines emitted after the placeholders.
        remove_when_absent: When ``True`` an existing managed block is removed
            if the module is not active.  When ``False`` a historical block is
            left untouched so existing projects keep their current bytes.
        respects_enabled_flag: When ``True`` a configured-but-disabled module
            counts as inactive.
    """

    module: str
    title: str
    env_var_options: tuple[str, ...]
    resolve_options: Callable[[Mapping[str, Any] | None], Mapping[str, Any]]
    prose: Callable[[Mapping[str, Any]], list[str]]
    env_var_defaults: Mapping[str, str] = field(default_factory=dict)
    tail_lines: tuple[str, ...] = ()
    remove_when_absent: bool = False
    respects_enabled_flag: bool = False


@dataclass(frozen=True)
class EnvExampleSyncResult:
    """Outcome of one managed-block sync pass over ``.env.example``."""

    success: bool
    changed: bool = False
    detail: str | None = None


def _declared_option_default(module_name: str, option_name: str) -> str:
    """Return a module manifest's declared default for one option."""
    defaults = load_module_manifest_with_fallback(module_name).get_defaults()
    return str(defaults.get(option_name, "") or "").strip()


def _placeholder_name(
    spec: EnvExampleModuleSpec,
    resolved: Mapping[str, Any],
    option_name: str,
) -> str:
    """Return the environment-variable name a declared option resolves to."""
    value = str(resolved.get(option_name) or "").strip()
    if value:
        return value
    fallback = spec.env_var_defaults.get(option_name)
    if fallback is None:
        fallback = _declared_option_default(spec.module, option_name)
    return fallback


def _notifications_prose(resolved: Mapping[str, Any]) -> list[str]:
    sender_email = str(resolved.get("sender_email", "noreply@example.com")).strip()
    resend_domain = str(resolved.get("resend_domain", "")).strip()
    lines = [
        "# Leave these blank until your verified Resend domain is ready for live delivery.",
        f"# Sender address from quickscale.yml: {sender_email}",
    ]
    if resend_domain:
        lines.append(f"# Verified Resend domain from quickscale.yml: {resend_domain}")
    return lines


def _analytics_prose(resolved: Mapping[str, Any]) -> list[str]:
    host = str(resolved.get("posthog_host") or ANALYTICS_POSTHOG_DEFAULT_HOST).strip()
    host_env_var = str(resolved.get("posthog_host_env_var") or "").strip()
    if not host_env_var:
        host_env_var = _declared_option_default("analytics", "posthog_host_env_var")
    return [
        "# Runtime PostHog variables for the backend analytics module.",
        "# VITE_* variables are for fresh showcase_react generations or manual frontend adoption.",
        f"# Leave {host_env_var} blank to fall back to {host}.",
    ]


def _billing_prose(resolved: Mapping[str, Any]) -> list[str]:
    billing_currency = str(resolved.get("billing_currency") or "").strip()
    if not billing_currency:
        billing_currency = _declared_option_default("billing", "billing_currency")
    return [
        "# Runtime Stripe variables for the backend billing module.",
        f"# Billing currency from quickscale.yml: {billing_currency}",
    ]


def _storage_prose(resolved: Mapping[str, Any]) -> list[str]:
    del resolved
    return [
        "# Runtime credential variables for S3-compatible backends",
        "# (modules.storage.backend: s3 or r2). The local backend does not read them.",
    ]


def _backups_prose(resolved: Mapping[str, Any]) -> list[str]:
    del resolved
    return [
        "# Runtime credential variables for private-remote backup targets",
        "# (modules.backups.target_mode: private_remote). The local target mode does not read them.",
    ]


ENV_EXAMPLE_MODULE_SPECS: tuple[EnvExampleModuleSpec, ...] = (
    EnvExampleModuleSpec(
        module="notifications",
        title="Notifications",
        env_var_options=(
            NOTIFICATIONS_RESEND_API_KEY_ENV_VAR_OPTION,
            NOTIFICATIONS_WEBHOOK_SECRET_ENV_VAR_OPTION,
        ),
        env_var_defaults={
            NOTIFICATIONS_RESEND_API_KEY_ENV_VAR_OPTION: (
                DEFAULT_NOTIFICATIONS_RESEND_API_KEY_ENV_VAR
            ),
            NOTIFICATIONS_WEBHOOK_SECRET_ENV_VAR_OPTION: (
                DEFAULT_NOTIFICATIONS_WEBHOOK_SECRET_ENV_VAR
            ),
        },
        resolve_options=resolve_notifications_module_options,
        prose=_notifications_prose,
    ),
    EnvExampleModuleSpec(
        module="analytics",
        title="Analytics",
        env_var_options=(
            "posthog_api_key_env_var",
            "posthog_host_env_var",
        ),
        resolve_options=partial(resolve_manifest_module_options, "analytics"),
        prose=_analytics_prose,
        tail_lines=("VITE_POSTHOG_KEY=", "VITE_POSTHOG_HOST="),
        remove_when_absent=True,
        respects_enabled_flag=True,
    ),
    EnvExampleModuleSpec(
        module="billing",
        title="Billing",
        env_var_options=BILLING_ENV_VAR_OPTION_NAMES,
        resolve_options=partial(resolve_manifest_module_options, "billing"),
        prose=_billing_prose,
    ),
    EnvExampleModuleSpec(
        module="storage",
        title="Storage",
        env_var_options=(
            STORAGE_ACCESS_KEY_ID_ENV_VAR_OPTION,
            STORAGE_SECRET_ACCESS_KEY_ENV_VAR_OPTION,
        ),
        env_var_defaults={
            STORAGE_ACCESS_KEY_ID_ENV_VAR_OPTION: (
                DEFAULT_STORAGE_ACCESS_KEY_ID_ENV_VAR
            ),
            STORAGE_SECRET_ACCESS_KEY_ENV_VAR_OPTION: (
                DEFAULT_STORAGE_SECRET_ACCESS_KEY_ENV_VAR
            ),
        },
        resolve_options=resolve_storage_module_options,
        prose=_storage_prose,
        remove_when_absent=True,
    ),
    EnvExampleModuleSpec(
        module="backups",
        title="Backups",
        env_var_options=(
            BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR_OPTION,
            BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR_OPTION,
        ),
        resolve_options=partial(resolve_manifest_module_options, "backups"),
        prose=_backups_prose,
        remove_when_absent=True,
    ),
)

_SPECS_BY_MODULE: dict[str, EnvExampleModuleSpec] = {
    spec.module: spec for spec in ENV_EXAMPLE_MODULE_SPECS
}


def _render_block(spec: EnvExampleModuleSpec, resolved: Mapping[str, Any]) -> str:
    lines = [f"# QuickScale {spec.title} (managed)"]
    lines.extend(spec.prose(resolved))
    lines.extend(
        f"{_placeholder_name(spec, resolved, option_name)}="
        for option_name in spec.env_var_options
    )
    lines.extend(spec.tail_lines)
    lines.append(f"# End QuickScale {spec.title}")
    return "\n".join(lines)


def render_env_example_block(
    module_name: str,
    options: Mapping[str, Any] | None = None,
) -> str:
    """Render one module's managed ``.env.example`` block.

    Args:
        module_name: Module whose declared block should be rendered.
        options: Configured module options; resolved against the declared
            manifest defaults.

    Returns:
        The block text, including its own start and end markers.

    Raises:
        KeyError: If the module declares no managed block.
    """
    spec = _SPECS_BY_MODULE[module_name]
    return _render_block(spec, spec.resolve_options(options))


def _splice_managed_block(
    content: str,
    spec: EnvExampleModuleSpec,
    rendered_block: str | None,
) -> str:
    """Replace, append, or remove one managed block without rewriting the rest.

    Reproduces the historical splice algorithm exactly: an existing marker
    pair is replaced in place (or removed together with its surrounding blank
    line), and a missing marker pair appends the block at the end of the file
    separated by one blank line.  A file carrying only one of the two markers
    still takes the append path, matching the historical behavior.
    """
    start_marker = f"# QuickScale {spec.title} (managed)"
    end_marker = f"# End QuickScale {spec.title}"

    if start_marker in content and end_marker in content:
        before, remainder = content.split(start_marker, maxsplit=1)
        _, after = remainder.split(end_marker, maxsplit=1)
        if rendered_block is None:
            updated = before.rstrip("\n")
            if after.strip():
                if updated:
                    updated += "\n"
                updated += after.lstrip("\n")
            elif updated:
                updated += "\n"
            return updated
        return before + rendered_block + after

    if rendered_block is None:
        return content

    suffix = "" if content.endswith("\n") else "\n"
    return content + suffix + "\n" + rendered_block + "\n"


def _is_active(spec: EnvExampleModuleSpec, resolved: Mapping[str, Any]) -> bool:
    if not spec.respects_enabled_flag:
        return True
    return bool(resolved.get("enabled", True))


def sync_env_example_blocks(
    output_path: Path | str,
    qs_config: Any,
) -> EnvExampleSyncResult:
    """Sync every enabled module's managed block into ``.env.example``.

    Renders the declared contract for every configured credential-bearing
    module in one pass, then writes the file at most once.  The operation is
    idempotent: a second run over an already-synced file leaves its bytes
    unchanged.

    Args:
        output_path: Project root that contains ``.env.example``.
        qs_config: Configuration object exposing a ``modules`` mapping of
            module name to module config with an ``options`` mapping.

    Returns:
        :class:`EnvExampleSyncResult`; ``success`` is ``False`` only when the
        file exists but cannot be read or written.
    """
    env_example_path = Path(output_path) / ENV_EXAMPLE_FILENAME
    if not env_example_path.exists():
        return EnvExampleSyncResult(success=True)

    modules = getattr(qs_config, "modules", None)
    if not isinstance(modules, Mapping):
        return EnvExampleSyncResult(success=True)

    try:
        content = env_example_path.read_text()
    except OSError as error:
        return EnvExampleSyncResult(success=False, detail=f"read failed: {error}")

    updated_content = content
    for spec in ENV_EXAMPLE_MODULE_SPECS:
        module_config = modules.get(spec.module)
        if module_config is None:
            if spec.remove_when_absent:
                updated_content = _splice_managed_block(updated_content, spec, None)
            continue

        options = getattr(module_config, "options", None)
        resolved = spec.resolve_options(options)
        if not _is_active(spec, resolved):
            if spec.remove_when_absent:
                updated_content = _splice_managed_block(updated_content, spec, None)
            continue

        rendered_block = _render_block(spec, resolved)
        updated_content = _splice_managed_block(updated_content, spec, rendered_block)

    if updated_content == content:
        return EnvExampleSyncResult(success=True)

    try:
        env_example_path.write_text(updated_content)
    except OSError as error:
        return EnvExampleSyncResult(success=False, detail=f"write failed: {error}")

    return EnvExampleSyncResult(success=True, changed=True)


# ---------------------------------------------------------------------------
# Step 5: backups gitignore hardening
# ---------------------------------------------------------------------------


def step_backups_gitignore(
    ctx: StepContext,
    *,
    ensure_backups_ignore_fn: Callable[..., bool],
) -> StepOutcome:
    """Step 5: Ensure custom backups directories are safely gitignored.

    Delegates to *ensure_backups_ignore_fn* which returns ``True`` on
    success.  On failure the step returns an unsuccessful outcome with
    the appropriate ``failed_step_label``.

    Args:
        ctx: Core-safe step context.
        ensure_backups_ignore_fn: Callable that reads ``qs_config`` and
            updates ``.gitignore`` with the backups ignore rule.  Returns
            ``True`` on success.

    Returns:
        :class:`StepOutcome` with ``failed_step_label`` set to
        ``"backups gitignore hardening"`` on failure.
    """
    if not ensure_backups_ignore_fn(ctx.output_path, ctx.qs_config):
        return StepOutcome(
            success=False,
            message="Unable to update .gitignore with configured backups directory",
            failed_step_label="backups gitignore hardening",
        )

    return StepOutcome(success=True, message="Backups gitignore rules applied")


# ---------------------------------------------------------------------------
# Step 6: notifications env-example sync
# ---------------------------------------------------------------------------


def step_notifications_env_sync(
    ctx: StepContext,
    *,
    sync_notifications_fn: Callable[..., bool],
) -> StepOutcome:
    """Step 6: Keep ``.env.example`` aligned with notifications env-var names.

    Args:
        ctx: Core-safe step context.
        sync_notifications_fn: Callable returning ``True`` on success.

    Returns:
        :class:`StepOutcome` with ``failed_step_label`` set to
        ``"notifications env example sync"`` on failure.
    """
    if not sync_notifications_fn(ctx.output_path, ctx.qs_config):
        return StepOutcome(
            success=False,
            message="Unable to update .env.example with notifications env vars",
            failed_step_label="notifications env example sync",
        )

    return StepOutcome(
        success=True, message="Notifications env vars synced to .env.example"
    )


# ---------------------------------------------------------------------------
# Step 7: analytics env-example sync
# ---------------------------------------------------------------------------


def step_analytics_env_sync(
    ctx: StepContext,
    *,
    sync_analytics_fn: Callable[..., bool],
) -> StepOutcome:
    """Step 7: Keep ``.env.example`` aligned with analytics env-var names.

    Args:
        ctx: Core-safe step context.
        sync_analytics_fn: Callable returning ``True`` on success.

    Returns:
        :class:`StepOutcome` with ``failed_step_label`` set to
        ``"analytics env example sync"`` on failure.
    """
    if not sync_analytics_fn(ctx.output_path, ctx.qs_config):
        return StepOutcome(
            success=False,
            message="Unable to update .env.example with analytics env vars",
            failed_step_label="analytics env example sync",
        )

    return StepOutcome(
        success=True, message="Analytics env vars synced to .env.example"
    )


# ---------------------------------------------------------------------------
# Step 8: billing env-example sync
# ---------------------------------------------------------------------------


def step_billing_env_sync(
    ctx: StepContext,
    *,
    sync_billing_fn: Callable[..., bool],
) -> StepOutcome:
    """Step 8: Keep ``.env.example`` aligned with billing env-var names.

    Args:
        ctx: Core-safe step context.
        sync_billing_fn: Callable returning ``True`` on success.

    Returns:
        :class:`StepOutcome` with ``failed_step_label`` set to
        ``"billing env example sync"`` on failure.
    """
    if not sync_billing_fn(ctx.output_path, ctx.qs_config):
        return StepOutcome(
            success=False,
            message="Unable to update .env.example with billing env vars",
            failed_step_label="billing env example sync",
        )

    return StepOutcome(success=True, message="Billing env vars synced to .env.example")


__all__ = [
    "ENV_EXAMPLE_MODULE_SPECS",
    "EnvExampleModuleSpec",
    "EnvExampleSyncResult",
    "render_env_example_block",
    "step_analytics_env_sync",
    "step_backups_gitignore",
    "step_billing_env_sync",
    "step_notifications_env_sync",
    "sync_env_example_blocks",
]
