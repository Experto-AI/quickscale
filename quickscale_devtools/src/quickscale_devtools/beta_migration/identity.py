"""Fresh-first identity substitution and reconciliation planning."""

from .constants import (
    FRESH_FIRST_IDENTITY_PACKAGE_FILES,
    FRESH_FIRST_IDENTITY_ROOT_FILES,
)
from .model import (
    BetaMigrationReport,
    IdentityReconciliationPlan,
    IdentityReplacement,
    IdentityValueKind,
    ProjectSnapshot,
    _append_blocker,
    _append_check,
)
import re
from pathlib import Path
from quickscale_core.project_state import ProjectStateManager
from quickscale_core.schema.config_schema import generate_yaml, validate_config
from quickscale_core.schema.state_schema import QuickScaleState, StateError
from quickscale_core.utils.project_identity import ProjectIdentity


def _identity_replacements(
    source: ProjectIdentity,
    target: ProjectIdentity,
    *,
    value_kinds: tuple[IdentityValueKind, ...] = ("package", "slug"),
) -> tuple[IdentityReplacement, ...]:
    """Return raw and derived identity substitutions with token semantics."""
    package_replacements: tuple[IdentityReplacement, ...] = (
        (f"{source.package}_app_password", f"{target.package}_app_password", "package"),
        (f"{source.package}_app", f"{target.package}_app", "package"),
        (f"{source.package}-frontend", f"{target.package}-frontend", "package"),
        (source.package, target.package, "package"),
    )
    slug_replacements: tuple[IdentityReplacement, ...] = (
        (f"{source.slug}_frontend", f"{target.slug}_frontend", "slug"),
        (f"{source.slug}_backend", f"{target.slug}_backend", "slug"),
        (f"{source.slug}_db", f"{target.slug}_db", "slug"),
        (f":-{source.slug}", f":-{target.slug}", "slug"),
        (source.slug, target.slug, "slug"),
    )
    return tuple(
        replacement
        for replacement in (
            *package_replacements,
            *slug_replacements,
        )
        if replacement[0] != replacement[1] and replacement[2] in value_kinds
    )


def _replace_identity_text(
    text: str, replacements: tuple[IdentityReplacement, ...]
) -> str:
    """Apply non-cascading, token-aware identity substitutions to text."""
    updated = text
    sentinels: list[tuple[str, str]] = []
    replacement_targets: dict[str, str] = {}
    for old_value, new_value, _value_kind in replacements:
        prior_target = replacement_targets.setdefault(old_value, new_value)
        if prior_target != new_value:
            raise ValueError(
                f"Identity value {old_value!r} is ambiguous between {prior_target!r} "
                f"and {new_value!r}; select slug or package semantics explicitly."
            )
    ordered_replacements = sorted(
        replacements,
        key=lambda replacement: (
            -len(replacement[0]),
            0 if replacement[2] == "package" else 1,
        ),
    )
    for index, (old_value, new_value, value_kind) in enumerate(ordered_replacements):
        sentinel = f"\ue000{index}\ue001"
        if sentinel in updated:
            raise ValueError(
                "Identity substitution sentinel unexpectedly exists in input text."
            )
        token_characters = "A-Za-z0-9_" if value_kind == "package" else "A-Za-z0-9_-"
        left_boundary = (
            rf"(?<![{token_characters}])"
            if re.fullmatch(rf"[{token_characters}]", old_value[0])
            else ""
        )
        right_boundary = (
            rf"(?![{token_characters}])"
            if re.fullmatch(rf"[{token_characters}]", old_value[-1])
            else ""
        )
        pattern = re.compile(rf"{left_boundary}{re.escape(old_value)}{right_boundary}")
        updated = pattern.sub(sentinel, updated)
        sentinels.append((sentinel, new_value))

    for sentinel, new_value in sentinels:
        updated = updated.replace(sentinel, new_value)
    return updated


_IDENTITY_LINE_RULES: dict[
    str, tuple[tuple[re.Pattern[str], tuple[IdentityValueKind, ...]], ...]
] = {
    ".env": ((re.compile(r"^\s*DATABASE_URL="), ("package",)),),
    ".env.example": (
        (
            re.compile(r"^\s*#?\s*(?:DATABASE_URL|RUNTIME_DATABASE_URL)="),
            ("package",),
        ),
    ),
    ".github/workflows/ci.yml": (
        (re.compile(r"--cov=|DJANGO_SETTINGS_MODULE"), ("package",)),
    ),
    "manage.py": ((re.compile(r"DJANGO_SETTINGS_MODULE"), ("package",)),),
    "docker-compose.yml": (
        (
            re.compile(
                r"POSTGRES_DB:|psql\s.+\s-d\s|DJANGO_SETTINGS_MODULE="
                r"|DATABASE_URL="
            ),
            ("package",),
        ),
        (
            re.compile(
                r"container_name:|com\.quickscale\.scope:"
                r"|image:.*quickscale-backend:"
            ),
            ("slug",),
        ),
    ),
    "README.md": (
        (
            re.compile(
                r"--cov=|poetry run mypy\s|DATABASE_URL=postgresql://"
                r"|Main Django project package|DJANGO_SETTINGS_MODULE="
            ),
            ("package",),
        ),
        (
            re.compile(
                r"^#\s+[A-Za-z0-9_-]+\s*$|^docker build -t\s"
                r"|^[A-Za-z0-9_-]+/\s*$"
            ),
            ("slug",),
        ),
    ),
    "OPERATIONS.md": (
        (
            re.compile(
                r"\|\s*`[A-Za-z_][A-Za-z0-9_]*_app`\s*\|"
                r"|creates the `|CREATE ROLE\s|GRANT .+ TO\s"
                r"|RUNTIME_DATABASE_URL=postgresql://|^\\c\s"
                r"|rolname\s*=|Expected:\s"
            ),
            ("package",),
        ),
        (
            re.compile(r"^# Operations Guide for\s| uses two PostgreSQL roles"),
            ("slug",),
        ),
    ),
    "db/init.sql": (
        (
            re.compile(
                r"rolname\s*=|CREATE ROLE\s|PASSWORD\s|GRANT .+ TO\s"
                r"|ALTER DATABASE\s"
            ),
            ("package",),
        ),
        (re.compile(r"^-- PostgreSQL initialization script for\s"), ("slug",)),
    ),
    "scripts/lint.sh": ((re.compile(r"poetry run mypy\s"), ("package",)),),
    "tests/conftest.py": (
        (re.compile(r"Pytest configuration and fixtures for\s"), ("slug",)),
    ),
    "tests/test_example.py": (
        (re.compile(r"Example tests demonstrating pytest patterns for\s"), ("slug",)),
    ),
    "frontend/package.json": ((re.compile(r'^\s*"name"\s*:'), ("package",)),),
    "frontend/e2e/home.spec.ts": (
        (re.compile(r"toHaveTitle\(|Welcome to your\s"), ("slug",)),
    ),
    "frontend/src/hooks/useModules.ts": (
        (re.compile(r"\bprojectName\s*:"), ("slug",)),
    ),
    "templates/404.html": ((re.compile(r"\btitle\b", re.IGNORECASE), ("slug",)),),
    "templates/500.html": ((re.compile(r"\btitle\b", re.IGNORECASE), ("slug",)),),
    "templates/base.html": (
        (
            re.compile(r"<title>|qs-topbar-brand|&copy;", re.IGNORECASE),
            ("slug",),
        ),
    ),
    "templates/index.html": (
        (
            re.compile(r"<title>|<meta\s+name=[\"']description|projectName\s*:"),
            ("slug",),
        ),
    ),
    "templates/social/link_tree.html": (
        (re.compile(r"\{%\s*block title|projectName\s*:"), ("slug",)),
    ),
    "templates/social/embeds.html": (
        (re.compile(r"\{%\s*block title|projectName\s*:"), ("slug",)),
    ),
    "__init__.py": (
        (re.compile(r"^\s*[A-Za-z0-9_-]+\s+- Django Project\s*$"), ("slug",)),
    ),
    "asgi.py": (
        (re.compile(r"ASGI config for\s", re.IGNORECASE), ("slug",)),
        (re.compile(r"DJANGO_SETTINGS_MODULE"), ("package",)),
    ),
    "wsgi.py": (
        (re.compile(r"WSGI config for\s", re.IGNORECASE), ("slug",)),
        (re.compile(r"DJANGO_SETTINGS_MODULE"), ("package",)),
    ),
    "settings/__init__.py": ((re.compile(r"Django settings for\s"), ("slug",)),),
    "settings/base.py": (
        (re.compile(r"Django base settings for\s"), ("slug",)),
        (
            re.compile(
                r"\.settings\.base\.|ROOT_URLCONF\s*=|\.context_processors\."
                r"|WSGI_APPLICATION\s*=|POSTGRES_DB|RUNTIME_DB_ROLE"
                r"|DATABASE_NAME\s*=|LOGGER\s*="
                r'|^\s*["\'][A-Za-z_][A-Za-z0-9_]*["\']\s*:\s*\{\s*$'
            ),
            ("package",),
        ),
    ),
    "settings/local.py": (
        (re.compile(r"Local development settings for\s"), ("slug",)),
        (
            re.compile(r'LOGGER\s*=|^\s*["\'][A-Za-z_][A-Za-z0-9_]*["\']\s*:\s*\{\s*$'),
            ("package",),
        ),
    ),
}


def _replace_identity_fields_for_path(
    text: str,
    *,
    relative_path: str,
    source: ProjectIdentity,
    target: ProjectIdentity,
) -> str:
    """Rewrite only generated fields that structurally carry project identity."""
    rules = _IDENTITY_LINE_RULES.get(relative_path, ())
    lines = text.splitlines(keepends=True)
    for index, line in enumerate(lines):
        value_kinds = tuple(
            kind
            for pattern, pattern_kinds in rules
            if pattern.search(line)
            for kind in pattern_kinds
        )
        if not value_kinds:
            continue
        lines[index] = _replace_identity_text(
            line,
            _identity_replacements(
                source,
                target,
                value_kinds=tuple(dict.fromkeys(value_kinds)),
            ),
        )
    return "".join(lines)


def _replace_identity_text_for_path(
    text: str,
    *,
    relative_path: str,
    source: ProjectIdentity,
    target: ProjectIdentity,
) -> str:
    """Apply path-specific slug/package semantics to one generated-project file."""
    if relative_path in {"start.sh", "Dockerfile"}:
        suffix = (
            r"\.wsgi\b" if relative_path == "start.sh" else r"\.settings\.production\b"
        )
        return re.sub(
            rf"(?<![A-Za-z0-9_]){re.escape(source.package)}(?={suffix})",
            target.package,
            text,
        )
    if relative_path == "pyproject.toml":
        lines = text.splitlines(keepends=True)
        in_poetry_section = False
        for index, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("[") and stripped.endswith("]"):
                in_poetry_section = stripped == "[tool.poetry]"
            value_kinds: tuple[IdentityValueKind, ...] = ()
            if in_poetry_section and re.match(r"^\s*name\s*=", line):
                value_kinds = ("slug",)
            elif (
                re.match(r"^\s*packages\s*=", line)
                or "DJANGO_SETTINGS_MODULE" in line
                or "--cov=" in line
                or re.match(r"^\s*django_settings_module\s*=", line)
            ):
                value_kinds = ("package",)
            if not value_kinds:
                continue
            lines[index] = _replace_identity_text(
                line,
                _identity_replacements(
                    source,
                    target,
                    value_kinds=value_kinds,
                ),
            )
        return "".join(lines)

    return _replace_identity_fields_for_path(
        text,
        relative_path=relative_path,
        source=source,
        target=target,
    )


def _render_reconciled_state(
    recipient: ProjectSnapshot,
    target_identity: ProjectIdentity,
) -> QuickScaleState | None:
    """Load authoritative state and reconcile identity-bearing metadata in memory."""
    state = ProjectStateManager(recipient.path).load_state()
    if state is None:
        return None
    if (
        state.project.slug != recipient.identity.slug
        or state.project.package != recipient.identity.package
    ):
        raise ValueError(
            f"{recipient.path / '.quickscale' / 'state.yml'} identity "
            f"slug={state.project.slug}, package={state.project.package} does not match "
            f"the recipient identity slug={recipient.identity.slug}, "
            f"package={recipient.identity.package}."
        )

    source_prefix = f"{recipient.identity.package}/"
    target_prefix = f"{target_identity.package}/"
    reconciled_records = {}
    for stored_path, record in state.managed_files.items():
        if stored_path != record.path:
            raise ValueError(
                f"Managed-file state key {stored_path!r} does not match its record path "
                f"{record.path!r}."
            )
        reconciled_path = (
            target_prefix + stored_path.removeprefix(source_prefix)
            if stored_path.startswith(source_prefix)
            else stored_path
        )
        if reconciled_path in reconciled_records:
            raise ValueError(
                f"Identity reconciliation would collide managed-file state paths at "
                f"{reconciled_path!r}."
            )
        record.path = reconciled_path
        reconciled_records[reconciled_path] = record

    state.project.slug = target_identity.slug
    state.project.package = target_identity.package
    state.managed_files = reconciled_records
    return state


def _build_identity_reconciliation_plan(
    report: BetaMigrationReport,
) -> IdentityReconciliationPlan:
    """Render and validate every fresh-first identity change before any write."""
    if report.mode != "fresh-first" or report.donor is None or report.recipient is None:
        raise ValueError(
            "Fresh-first donor and recipient snapshots are required for identity reconciliation."
        )

    donor_identity = report.donor.identity
    recipient = report.recipient
    recipient_config = validate_config(recipient.config_path.read_text())
    recipient_config.project.slug = donor_identity.slug
    recipient_config.project.package = donor_identity.package
    config_content = generate_yaml(recipient_config)
    validated_config = validate_config(config_content)
    if (
        validated_config.project.slug != donor_identity.slug
        or validated_config.project.package != donor_identity.package
    ):
        raise ValueError(
            "Rendered recipient identity did not validate to the donor identity."
        )

    target_package_dir = recipient.path / donor_identity.package
    if recipient.package_dir != target_package_dir and target_package_dir.exists():
        raise ValueError(
            "Cannot reconcile recipient package directory because the target already "
            f"exists: {target_package_dir}"
        )

    file_updates: list[tuple[Path, str]] = []
    for relative_path in FRESH_FIRST_IDENTITY_ROOT_FILES:
        source_path = recipient.path / relative_path
        if not source_path.is_file():
            continue
        original = source_path.read_text()
        updated = _replace_identity_text_for_path(
            original,
            relative_path=relative_path,
            source=recipient.identity,
            target=donor_identity,
        )
        if updated != original:
            file_updates.append((source_path, updated))

    for relative_path in FRESH_FIRST_IDENTITY_PACKAGE_FILES:
        source_path = recipient.package_dir / relative_path
        if not source_path.is_file():
            continue
        original = source_path.read_text()
        updated = _replace_identity_text_for_path(
            original,
            relative_path=relative_path,
            source=recipient.identity,
            target=donor_identity,
        )
        if updated != original:
            file_updates.append((target_package_dir / relative_path, updated))

    return IdentityReconciliationPlan(
        config_content=config_content,
        source_package_dir=recipient.package_dir,
        target_package_dir=target_package_dir,
        file_updates=tuple(file_updates),
        state=_render_reconciled_state(recipient, donor_identity),
    )


def _validate_identity_reconciliation(report: BetaMigrationReport) -> None:
    """Fail before execution when any fresh-first identity transform is unresolved."""
    if report.blockers:
        return
    try:
        plan = _build_identity_reconciliation_plan(report)
    except (OSError, StateError, ValueError) as exc:
        detail = f"Fresh-first identity reconciliation preflight failed: {exc}"
        _append_check(
            report,
            name="fresh-first-identity-reconciliation",
            status="failed",
            detail=detail,
        )
        _append_blocker(report, detail)
        return

    state_detail = (
        "including authoritative .quickscale/state.yml"
        if plan.state is not None
        else "with no applied state file present"
    )
    _append_check(
        report,
        name="fresh-first-identity-reconciliation",
        status="passed",
        detail=(
            "Rendered and validated every fresh-first identity change before mutation, "
            f"{state_detail}."
        ),
    )
