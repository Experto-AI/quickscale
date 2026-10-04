"""Tests for beta migration maintainer tooling."""

import hashlib
import io
import json
import os
import subprocess
from pathlib import Path

import pytest
import quickscale_core.schema as schema_module
from quickscale_core.advisory_lock import AdvisoryLock
from quickscale_core.schema.state_schema import (
    ManagedFileRecord,
    ProjectState,
    QuickScaleState,
    StateManager,
)

from quickscale_devtools.beta_migration import (
    BetaMigrationInput,
    _insert_missing_path_dependencies,
    _locate_toml_section_bounds,
    _write_validated_toml,
    parse_cli_args,
    plan_beta_migration,
    run_beta_migration,
    run_beta_migration_cli,
)

EXPECTED_VERIFICATION_SEQUENCE = [
    (("poetry", "lock"), "poetry lock", "."),
    (("poetry", "install"), "poetry install", "."),
    (("pnpm", "install"), "pnpm install", "frontend"),
    (("pnpm", "build"), "pnpm build", "frontend"),
    (("quickscale", "manage", "migrate"), "quickscale manage migrate", "."),
    (("pytest",), "pytest", "."),
    (("pnpm", "test"), "pnpm test", "frontend"),
]


def _write_project(
    root: Path,
    *,
    slug: str,
    package: str,
    marker: str,
    modules: tuple[str, ...] = (),
    path_dependencies: tuple[str, ...] = (),
    include_docker_files: bool = True,
    include_use_modules_hook: bool = True,
    include_frontend_infra_files: bool = True,
) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    modules_block = ""
    if modules:
        module_lines = "\n".join(f"  {module}: {{}}" for module in modules)
        modules_block = f"modules:\n{module_lines}\n"

    quickscale_content = (
        'version: "1"\n'
        "project:\n"
        f"  slug: {slug}\n"
        f"  package: {package}\n"
        "  theme: showcase_react\n"
        f"{modules_block}"
        "docker:\n"
        "  start: false\n"
        "  build: false\n"
    )
    (root / "quickscale.yml").write_text(quickscale_content)

    dependency_lines = [
        'python = "^3.14"',
        'python-decouple = "^3.8"',
        'Django = ">=6.0.3,<7.0.0"',
    ]
    dependency_lines.extend(
        f'{name} = {{path = "./modules/{name.removeprefix("quickscale-module-")}", develop = true}}'
        for name in path_dependencies
    )
    pyproject_content = (
        "[tool.poetry]\n"
        f'name = "{slug}"\n'
        'version = "0.1.0"\n'
        f'packages = [{{include = "{package}"}}]\n\n'
        "[tool.poetry.dependencies]\n" + "\n".join(dependency_lines) + "\n\n"
        "[tool.poetry.group.dev.dependencies]\n"
        'pytest = "^9.0.0"\n\n'
        "[tool.pytest.ini_options]\n"
        f'DJANGO_SETTINGS_MODULE = "{package}.settings.local"\n'
    )
    (root / "pyproject.toml").write_text(pyproject_content)

    for dependency_name in path_dependencies:
        module_name = dependency_name.removeprefix("quickscale-module-")
        module_dir = root / "modules" / module_name
        module_dir.mkdir(parents=True, exist_ok=True)
        (module_dir / "README.md").write_text(f"{module_name} module\n")

    package_dir = root / package
    settings_dir = package_dir / "settings"
    settings_dir.mkdir(parents=True, exist_ok=True)
    (package_dir / "__init__.py").write_text(f"# {marker}-package-marker\n")
    (package_dir / "urls.py").write_text(f"# {marker}-urls-marker\n")
    (package_dir / "views.py").write_text(f"# {marker}-views-marker\n")
    (package_dir / "context_processors.py").write_text(
        f"# {marker}-context-processors-marker\n"
    )
    (package_dir / "middleware.py").write_text(f"# {marker}-middleware-marker\n")
    (package_dir / "sitemaps.py").write_text(f"# {marker}-sitemaps-marker\n")
    (package_dir / "urls_modules.py").write_text(f"# {marker}-urls-modules-marker\n")
    (package_dir / "asgi.py").write_text(
        f'"""ASGI config for {slug} project."""\n'
        "import os\n"
        f'os.environ.setdefault("DJANGO_SETTINGS_MODULE", "{package}.settings.production")\n'
        f"# {marker}-asgi-marker\n"
    )
    (package_dir / "wsgi.py").write_text(
        f'"""WSGI config for {slug} project."""\n'
        "import os\n"
        f'os.environ.setdefault("DJANGO_SETTINGS_MODULE", "{package}.settings.production")\n'
        f"# {marker}-wsgi-marker\n"
    )
    (settings_dir / "__init__.py").write_text(f"# {marker}-settings-init-marker\n")
    (settings_dir / "modules.py").write_text(
        f"# {marker}-modules-marker\nMODULE_INSTALLED_APPS = []\nMODULE_MIDDLEWARE = []\nMODULE_SETTINGS = {{}}\n"
    )
    (settings_dir / "base.py").write_text(
        f'"""Django base settings for {slug} project. {marker}-base-marker"""\n'
        f'ROOT_URLCONF = "{package}.urls"\n'
        f'CONTEXT_PROCESSOR = "{package}.context_processors.project_settings"\n'
        f'WSGI_APPLICATION = "{package}.wsgi.application"\n'
        f'DATABASE_NAME = "{package}"\n'
        f'LOGGER = "{package}"\n'
        f'RUNTIME_DB_ROLE = "{package}_app"\n'
    )
    (settings_dir / "local.py").write_text(
        f'"""Local development settings for {slug}. {marker}-local-marker"""\n'
        f'LOGGER = "{package}"\n'
    )
    (settings_dir / "production.py").write_text(
        f'"""{marker}-production-marker {slug}"""\n'
        "import dj_database_url\n"
        "import os\n"
        "from decouple import config\n"
        "from quickscale_core.runtime.settings import resolve_runtime_database_url\n"
        '\n_runtime_db_url = config("RUNTIME_DATABASE_URL", default=None)\n'
        'database_url = config("DATABASE_URL", default=None)\n'
        '_privileged_command = os.environ.get("QUICKSCALE_PRIVILEGED_COMMAND", "")\n'
        '_non_db_command = os.environ.get("QUICKSCALE_NON_DB_COMMAND", "")\n'
        "_db_url = resolve_runtime_database_url(\n"
        "    runtime_database_url=_runtime_db_url,\n"
        "    database_url=database_url,\n"
        "    privileged_command=_privileged_command,\n"
        "    non_db_command=_non_db_command,\n"
        '    allow_bypass_rls=os.environ.get("QUICKSCALE_ALLOW_BYPASSRLS") == "1",\n'
        ")\n"
        'DATABASES = {"default": dj_database_url.parse(_db_url)}\n'
        f'DEFAULT_FROM_EMAIL = "noreply@{slug}.com"\n'
        f'LOGGER = "{package}"\n'
    )

    (root / "manage.py").write_text(
        "import os\n"
        f'os.environ.setdefault("DJANGO_SETTINGS_MODULE", "{package}.settings.local")\n'
        f"# {marker}-manage-marker {slug}\n"
    )
    (root / "railway.json").write_text(
        json.dumps({"marker": f"{marker}-railway-marker"}, indent=2) + "\n"
    )
    (root / "start.sh").write_text(
        "#!/usr/bin/env bash\n"
        'QUICKSCALE_PRIVILEGED_COMMAND=migrate RUNTIME_DATABASE_URL="" python manage.py migrate --noinput\n'
        'QUICKSCALE_PRIVILEGED_COMMAND=createcachetable RUNTIME_DATABASE_URL="" python manage.py createcachetable\n'
        f"exec gunicorn {package}.wsgi:application\n"
    )

    frontend_src = root / "frontend" / "src"
    (frontend_src / "pages").mkdir(parents=True, exist_ok=True)
    (frontend_src / "components" / "layout").mkdir(parents=True, exist_ok=True)
    (frontend_src / "components" / "ui").mkdir(parents=True, exist_ok=True)
    (frontend_src / "App.tsx").write_text(
        f"export default function App() {{ return '{marker}-app'; }}\n"
    )
    (frontend_src / "pages" / "Dashboard.tsx").write_text(
        f"export default '{marker}-dashboard';\n"
    )
    (frontend_src / "components" / "layout" / "Nav.tsx").write_text(
        f"export default '{marker}-layout';\n"
    )
    (frontend_src / "components" / "ui" / "Button.tsx").write_text(
        f"export default '{marker}-ui';\n"
    )
    (root / "frontend" / "package.json").write_text(
        json.dumps({"name": slug, "private": True}, indent=2) + "\n"
    )

    # The project-owned design layer every current-release showcase_react
    # project carries (SA214 slice d). Markers keep donor and recipient
    # versions distinguishable so copy assertions see the port.
    design_root = root / "frontend" / "design"
    (design_root / "fonts").mkdir(parents=True, exist_ok=True)
    (design_root / "brand").mkdir(parents=True, exist_ok=True)
    (design_root / "tokens.css").write_text(
        f"/* {marker}-design-tokens {slug} */\n:root {{ --primary: 240 5.9% 10%; }}\n"
    )
    (design_root / "tailwind.preset.js").write_text(
        f"// {marker}-design-preset {slug}\nexport default {{}};\n"
    )
    (design_root / "fonts" / "README.md").write_text(f"# {marker}-design-fonts\n")
    (design_root / "brand" / "README.md").write_text(f"# {marker}-design-brand\n")

    if include_frontend_infra_files:
        (root / ".pre-commit-config.yaml").write_text(f"# {marker}-pre-commit-marker\n")
        (root / "frontend" / "vite.config.ts").write_text(
            f"// {marker}-vite-marker {slug}\n"
        )
        (root / "frontend" / "tsconfig.json").write_text(
            json.dumps({"marker": f"{marker}-tsconfig-marker", "slug": slug}, indent=2)
            + "\n"
        )
        (root / "frontend" / "tsconfig.app.json").write_text(
            json.dumps(
                {"marker": f"{marker}-tsconfig-app-marker", "slug": slug}, indent=2
            )
            + "\n"
        )
        (root / "frontend" / "tsconfig.node.json").write_text(
            json.dumps(
                {"marker": f"{marker}-tsconfig-node-marker", "slug": slug}, indent=2
            )
            + "\n"
        )
        (root / "frontend" / "eslint.config.js").write_text(
            f"// {marker}-eslint-marker {slug}\n"
        )
        (root / "frontend" / "postcss.config.js").write_text(
            f"// {marker}-postcss-marker {slug}\n"
        )
        (root / "frontend" / "prettier.config.js").write_text(
            f"// {marker}-prettier-marker {slug}\n"
        )

    if include_use_modules_hook:
        (frontend_src / "hooks").mkdir(parents=True, exist_ok=True)
        (frontend_src / "hooks" / "useModules.ts").write_text(
            f"export const projectConfig = {{ projectName: '{slug}' }}; // {marker}-hook-marker\n"
        )
        # validateQuickScaleSeam.ts is the runtime seam that useModules.ts imports.
        # Generate it alongside the useModules hook so the fixture mirrors a
        # real scaffold layout.
        seam_dir = frontend_src / "lib"
        seam_dir.mkdir(parents=True, exist_ok=True)
        (seam_dir / "validateQuickScaleSeam.ts").write_text(
            f"export function validateQuickScaleConfig(config: any) {{ return config; }} // {marker}-seam-marker\n"
        )

    if include_docker_files:
        (root / "Dockerfile").write_text(
            "FROM python:3.14-slim-bookworm\n"
            f"ENV DJANGO_SETTINGS_MODULE={package}.settings.production\n"
            "RUN QUICKSCALE_NON_DB_COMMAND=collectstatic python manage.py collectstatic --noinput\n"
            "HEALTHCHECK --interval=30s \\\n"
            '    CMD python -c "print(1)"\n'
            'CMD ["./start.sh"]\n'
            f"# {marker}-docker-marker {slug}\n"
        )
        (root / "docker-compose.yml").write_text(
            "services:\n"
            f"  backend:\n    image: quickscale-backend:{slug}\n"
            f"    container_name: {slug}_backend\n"
            f"    labels:\n      com.quickscale.scope: {slug}\n"
            "    environment:\n"
            f"      - DJANGO_SETTINGS_MODULE={package}.settings.local\n"
            f"      - DATABASE_URL=postgresql://postgres:postgres@db:5432/{package}\n"
            f"      - RUNTIME_DATABASE_URL=postgresql://{package}_app:{package}_app_password@db:5432/{package}\n"
            "    command: python manage.py runserver 0.0.0.0:8000\n"
            f"# {marker}-compose-marker\n"
        )

    managed_paths = (
        f"{package}/settings/modules.py",
        f"{package}/urls_modules.py",
    )
    managed_files = {
        relative_path: ManagedFileRecord(
            path=relative_path,
            hash=hashlib.sha256((root / relative_path).read_bytes()).hexdigest(),
        )
        for relative_path in managed_paths
    }
    state_manager = StateManager(root)
    state_manager.save(
        QuickScaleState(
            version="1",
            project=ProjectState(
                slug=slug,
                package=package,
                theme="showcase_react",
            ),
            managed_files=managed_files,
        )
    )
    state_manager.flush_empty_consolidated_sections()

    return root


def _install_verification_success_stub(
    monkeypatch: pytest.MonkeyPatch,
    env_calls: list[tuple[tuple[str, ...], dict[str, str] | None]] | None = None,
) -> list[tuple[tuple[str, ...], Path]]:
    calls: list[tuple[tuple[str, ...], Path]] = []

    def fake_run(command, cwd=None, **kwargs):
        command_tuple = tuple(command)
        call_cwd = Path(cwd) if cwd is not None else Path.cwd()
        if env_calls is not None:
            env_calls.append((command_tuple, kwargs.get("env")))
        calls.append((command_tuple, call_cwd))
        joined = " ".join(command_tuple)
        return subprocess.CompletedProcess(
            command_tuple,
            0,
            stdout=f"stdout:{joined}",
            stderr=f"stderr:{joined}",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    return calls


def _assert_verification_report(
    report,
    recipient: Path,
    calls: list[tuple[tuple[str, ...], Path]],
) -> None:
    expected_calls = [
        (
            argv,
            recipient if cwd_suffix == "." else recipient / cwd_suffix,
        )
        for argv, _display, cwd_suffix in EXPECTED_VERIFICATION_SEQUENCE
    ]
    assert calls == expected_calls
    assert [result.command for result in report.verification_results] == [
        display for _argv, display, _cwd_suffix in EXPECTED_VERIFICATION_SEQUENCE
    ]
    assert [Path(result.cwd) for result in report.verification_results] == [
        cwd for _argv, cwd in expected_calls
    ]
    assert [result.stdout for result in report.verification_results] == [
        f"stdout:{' '.join(argv)}"
        for argv, _display, _cwd_suffix in EXPECTED_VERIFICATION_SEQUENCE
    ]
    assert [result.stderr for result in report.verification_results] == [
        f"stderr:{' '.join(argv)}"
        for argv, _display, _cwd_suffix in EXPECTED_VERIFICATION_SEQUENCE
    ]
    assert all(result.status == "passed" for result in report.verification_results)


def _find_step_detail(report, step_name: str) -> str:
    for step in report.completed_steps:
        if step.step == step_name:
            return step.detail
    raise AssertionError(f"Missing completed step: {step_name}")


def test_schema_module_lazy_reexports_work_for_state_symbols() -> None:
    """Lazy schema re-exports should resolve state-layer helpers on demand."""
    assert schema_module.QuickScaleState.__name__ == "QuickScaleState"
    assert schema_module.StateManager.__name__ == "StateManager"


def test_schema_module_raises_for_unknown_lazy_export() -> None:
    """Unknown schema attributes should raise a standard AttributeError."""
    with pytest.raises(AttributeError, match="does_not_exist"):
        getattr(schema_module, "does_not_exist")


def test_parse_cli_args_supports_mode_and_optional_flags(tmp_path: Path) -> None:
    """Argument parsing should preserve the supported mode and optional report flags."""
    donor = tmp_path / "donor"
    recipient = tmp_path / "recipient"
    report_path = tmp_path / "report.json"

    parsed = parse_cli_args(
        [
            "fresh-first",
            "--donor",
            str(donor),
            "--recipient",
            str(recipient),
            "--dry-run",
            "--report-path",
            str(report_path),
        ]
    )

    assert parsed.mode == "fresh-first"
    assert parsed.dry_run is True
    assert parsed.report_path == report_path


def test_plan_blocks_relative_paths() -> None:
    """Relative donor or recipient paths should fail preflight validation."""
    report = plan_beta_migration(
        BetaMigrationInput(
            mode="fresh-first",
            donor=Path("relative-donor"),
            recipient=Path("/tmp/absolute-recipient"),
            dry_run=True,
        )
    )

    assert report.status == "blocked"
    assert any("absolute path" in blocker for blocker in report.blockers)


def test_missing_required_file_blocks_preflight(tmp_path: Path) -> None:
    """Required files should be enforced before planning continues."""
    donor = _write_project(
        tmp_path / "donor",
        slug="donor-app",
        package="donor_app",
        marker="donor",
        modules=("auth",),
    )
    recipient = _write_project(
        tmp_path / "recipient",
        slug="recipient-app",
        package="recipient_app",
        marker="recipient",
        modules=("auth",),
    )
    (recipient / "frontend" / "package.json").unlink()

    report = plan_beta_migration(
        BetaMigrationInput(
            mode="fresh-first",
            donor=donor,
            recipient=recipient,
            dry_run=True,
        )
    )

    assert report.status == "blocked"
    assert any("frontend/package.json" in blocker for blocker in report.blockers)


def test_symlink_aliased_project_roots_block_preflight(tmp_path: Path) -> None:
    """Filesystem aliases must not let donor and recipient identify the same tree."""
    donor = _write_project(
        tmp_path / "donor",
        slug="donor-app",
        package="donor_app",
        marker="donor",
    )
    recipient = tmp_path / "recipient-alias"
    recipient.symlink_to(donor, target_is_directory=True)

    report = plan_beta_migration(
        BetaMigrationInput(
            mode="fresh-first",
            donor=donor,
            recipient=recipient,
            dry_run=True,
        )
    )

    assert report.status == "blocked"
    assert report.changed_files == []
    assert any("non-overlapping directories" in blocker for blocker in report.blockers)


def test_fresh_first_plan_loads_identity_and_diffs(tmp_path: Path) -> None:
    """Fresh-first planning should compute identity and module/path diffs."""
    donor = _write_project(
        tmp_path / "donor",
        slug="experto-ai-web",
        package="experto_ai_web",
        marker="donor",
        modules=("auth", "blog"),
        path_dependencies=("quickscale-module-auth", "quickscale-module-blog"),
    )
    recipient = _write_project(
        tmp_path / "recipient",
        slug="fresh-temp",
        package="fresh_temp",
        marker="recipient",
        modules=("auth",),
        path_dependencies=("quickscale-module-auth",),
    )
    (recipient / "modules" / "blog").mkdir(parents=True)

    report = plan_beta_migration(
        BetaMigrationInput(
            mode="fresh-first",
            donor=donor,
            recipient=recipient,
            dry_run=True,
        )
    )

    assert report.status == "ready"
    assert report.identity_reconciliation_required is True
    assert report.module_diff is not None
    assert report.module_diff.donor_only == ["blog"]
    assert report.path_dependency_diff is not None
    assert report.path_dependency_diff.donor_only == ["quickscale-module-blog"]
    assert report.runtime_provenance is not None
    assert report.runtime_provenance.settings_production == "donor"
    assert report.runtime_provenance.start_sh == "recipient"
    assert report.runtime_provenance.dockerfile == "recipient"
    assert report.changed_files == []
    assert any(
        action.step == "sync-missing-path-dependencies"
        for action in report.planned_actions
    )
    assert any(
        step.step == "perform-fresh-first-file-copy-sequence"
        for step in report.skipped_steps
    )


def test_fresh_first_missing_path_dependency_target_blocks_preflight(
    tmp_path: Path,
) -> None:
    """A dependency declaration cannot be transferred without its recipient module."""
    donor = _write_project(
        tmp_path / "donor",
        slug="donor-app",
        package="donor_app",
        marker="donor",
        modules=("auth", "blog"),
        path_dependencies=("quickscale-module-auth", "quickscale-module-blog"),
    )
    recipient = _write_project(
        tmp_path / "recipient",
        slug="recipient-app",
        package="recipient_app",
        marker="recipient",
        modules=("auth",),
        path_dependencies=("quickscale-module-auth",),
    )

    report = plan_beta_migration(
        BetaMigrationInput(
            mode="fresh-first",
            donor=donor,
            recipient=recipient,
            dry_run=True,
        )
    )

    assert report.status == "blocked"
    assert report.changed_files == []
    assert any(
        "quickscale-module-blog" in blocker and "missing recipient directory" in blocker
        for blocker in report.blockers
    )


def test_runtime_package_skew_blocks_before_mutation(
    tmp_path: Path,
) -> None:
    """Effective launchers must resolve to the package that will own production settings."""
    donor = _write_project(
        tmp_path / "donor",
        slug="fresh-donor",
        package="fresh_donor",
        marker="donor",
    )
    recipient = _write_project(
        tmp_path / "recipient",
        slug="beta-site",
        package="beta_site",
        marker="recipient",
    )
    launcher_root = recipient
    launcher_package = "beta_site"
    start_script = launcher_root / "start.sh"
    start_script.write_text(
        start_script.read_text().replace(
            f"{launcher_package}.wsgi", "unrelated_package.wsgi"
        )
    )

    report = run_beta_migration(
        BetaMigrationInput(
            mode="fresh-first",
            donor=donor,
            recipient=recipient,
            dry_run=True,
        )
    )

    assert report.status == "blocked"
    assert report.changed_files == []
    assert report.verification_results == []
    assert any("unrelated_package" in blocker for blocker in report.blockers)
    assert any(
        check.name == "runtime-launcher-settings-compatibility"
        and check.status == "failed"
        for check in report.preflight_checks
    )


def test_dynamic_gunicorn_package_is_not_masked_by_static_import_probe(
    tmp_path: Path,
) -> None:
    """Every execution package target must resolve statically and independently."""
    donor = _write_project(
        tmp_path / "donor",
        slug="fresh-donor",
        package="fresh_donor",
        marker="donor",
    )
    recipient = _write_project(
        tmp_path / "recipient",
        slug="beta-site",
        package="beta_site",
        marker="recipient",
    )
    launcher_root = recipient
    launcher_package = "beta_site"
    start_script = launcher_root / "start.sh"
    start_script.write_text(
        start_script.read_text().replace(
            f"exec gunicorn {launcher_package}.wsgi:application",
            (
                f'python -c "from {launcher_package}.wsgi import application"\n'
                'exec gunicorn "${WRONG_PACKAGE}.wsgi:application"'
            ),
        )
    )

    report = run_beta_migration(
        BetaMigrationInput(
            mode="fresh-first",
            donor=donor,
            recipient=recipient,
            dry_run=True,
        )
    )

    assert report.status == "blocked"
    assert report.changed_files == []
    assert report.verification_results == []
    assert any(
        "gunicorn" in blocker and "unresolved" in blocker for blocker in report.blockers
    )


@pytest.mark.parametrize(
    "launcher_lines",
    [
        (
            'runtime_command="${1:-migrate}"\n'
            'QUICKSCALE_PRIVILEGED_COMMAND="$runtime_command" '
            'python manage.py "$runtime_command"\n'
        ),
        ('QUICKSCALE_PRIVILEGED_COMMAND="migrate"x python manage.py migratex\n'),
        ("QUICKSCALE_PRIVILEGED_COMMAND=\\\nmigrate python manage.py migrate\n"),
        (
            "selector=QUICKSCALE_PRIVILEGED\n"
            'env "${selector}_COMMAND=unsupported_migration" '
            'RUNTIME_DATABASE_URL="" python manage.py unsupported_migration\n'
        ),
        (
            'env_name="QUICKSCALE_PRIVILEGED_"COMMAND\n'
            'env "$env_name=unsupported_migration" RUNTIME_DATABASE_URL="" '
            "python manage.py unsupported_migration\n"
        ),
        (
            'env_name="QUICKSCALE_PRIVILEGED_"COMMAND\n'
            'python manage.py check && env "$env_name=unsupported_migration" '
            'RUNTIME_DATABASE_URL="" python manage.py unsupported_migration\n'
        ),
        (
            'env_name="QUICKSCALE_PRIVILEGED_"COMMAND\n'
            '/usr/bin/env "$env_name=unsupported_migration" '
            'RUNTIME_DATABASE_URL="" python manage.py unsupported_migration\n'
        ),
        (
            'env "$(printf QUICK)SCALE_PRIVILEGED_COMMAND=custom" '
            "python manage.py custom\n"
        ),
        (
            'selector_name="$(printf QUICKSCALE_PRIVILEGED)_$(printf COMMAND)"\n'
            'export "$selector_name=unsupported_migration"\n'
            "python manage.py unsupported_migration\n"
        ),
        (
            "export QUICKSCALE_{PRIVILEGED_,}COMMAND=unsupported_migration\n"
            "python manage.py unsupported_migration\n"
        ),
        (
            'selector_name="$(printf QUICKSCALE_PRIVILEGED)_$(printf COMMAND)"\n'
            'declare -x "$selector_name=migrate"\n'
            "declare -x RUNTIME_DATABASE_URL=\n"
            "python manage.py unsupported_migration\n"
        ),
        (
            'selector_name="$(printf QUICKSCALE_PRIVILEGED)_$(printf COMMAND)"\n'
            'IGNORED=1 export "$selector_name=unsupported_migration"\n'
            "python manage.py unsupported_migration\n"
        ),
        (
            "persist=export\n"
            'selector_name="$(printf QUICKSCALE_PRIVILEGED)_$(printf COMMAND)"\n'
            '$persist "$selector_name=unsupported_migration"\n'
            "python manage.py unsupported_migration\n"
        ),
        (
            "persist=export\n"
            'selector_name="$(printf QUICKSCALE_PRIVILEGED)_$(printf COMMAND)"\n'
            'true && $persist "$selector_name=unsupported_migration"\n'
            "python manage.py unsupported_migration\n"
        ),
        (
            "persist=export\n"
            'selector_name="$(printf QUICKSCALE_PRIVILEGED)_$(printf COMMAND)"\n'
            'false || command $persist "$selector_name=unsupported_migration"\n'
            "python manage.py unsupported_migration\n"
        ),
        (
            "persist=export\n"
            'selector_name="$(printf QUICKSCALE_PRIVILEGED)_$(printf COMMAND)"\n'
            'true; IGNORED=1 $persist "$selector_name=unsupported_migration"\n'
            "python manage.py unsupported_migration\n"
        ),
        (
            "persist=export\n"
            'selector_name="$(printf QUICKSCALE_PRIVILEGED)_$(printf COMMAND)"\n'
            'printf ok | $persist "$selector_name=unsupported_migration"\n'
            "python manage.py unsupported_migration\n"
        ),
        (
            "persist=export\n"
            'selector_name="$(printf QUICKSCALE_PRIVILEGED)_$(printf COMMAND)"\n'
            '( $persist "$selector_name=unsupported_migration" )\n'
            "python manage.py unsupported_migration\n"
        ),
        (
            'selector_name="$(printf QUICKSCALE_PRIVILEGED)_$(printf COMMAND)"\n'
            'sh -c "export ${selector_name}=unsupported_migration '
            'RUNTIME_DATABASE_URL=; python manage.py unsupported_migration"\n'
        ),
        ("bash scripts/privileged.sh\n"),
        (
            "persist=export\n"
            "selector_name=QUICKSCALE_PRIVILEGED_COMMAND\n"
            'case x in x) $persist "$selector_name=unsupported_migration" '
            "RUNTIME_DATABASE_URL=;; esac\n"
            "python manage.py unsupported_migration\n"
        ),
        (
            "persist=export\n"
            'selector_name="$(printf QUICKSCALE_PRIVILEGED)_$(printf COMMAND)"\n'
            'if true; then $persist "$selector_name=unsupported_migration"; fi\n'
            "python manage.py unsupported_migration\n"
        ),
        (
            "shopt -s expand_aliases\n"
            "alias persist=export\n"
            'selector_name="$(printf QUICKSCALE_PRIVILEGED)_$(printf COMMAND)"\n'
            'persist "$selector_name=unsupported_migration"\n'
            "python manage.py unsupported_migration\n"
        ),
        ("QUICKSCALE_${MODE}_COMMAND=${CMD} python manage.py ${CMD}\n"),
        (
            'QUICKSCALE_PRIVILEGED_COMMAND=migrate RUNTIME_DATABASE_URL="" '
            'python manage.py "$CMD"\n'
        ),
        ("QUICKSCALE_PRIVILEGED_COMMAND=migrate python manage.py migrate\n"),
        (
            "QUICKSCALE_PRIVILEGED_COMMAND=migrate "
            'QUICKSCALE_NON_DB_COMMAND=collectstatic RUNTIME_DATABASE_URL="" '
            "python manage.py migrate\n"
        ),
    ],
)
def test_nonstatic_runtime_command_assignment_blocks_before_mutation(
    tmp_path: Path,
    launcher_lines: str,
) -> None:
    """Dynamic or concatenated launcher assignments must not bypass the allowlist."""
    donor = _write_project(
        tmp_path / "donor",
        slug="fresh-donor",
        package="fresh_donor",
        marker="donor",
    )
    recipient = _write_project(
        tmp_path / "recipient",
        slug="beta-site",
        package="beta_site",
        marker="recipient",
    )
    launcher_root = recipient
    launcher_package = "beta_site"
    start_script = launcher_root / "start.sh"
    gunicorn_line = f"exec gunicorn {launcher_package}.wsgi:application\n"
    start_script.write_text(
        start_script.read_text().replace(
            gunicorn_line,
            launcher_lines + gunicorn_line,
        )
    )

    report = run_beta_migration(
        BetaMigrationInput(
            mode="fresh-first",
            donor=donor,
            recipient=recipient,
            dry_run=True,
        )
    )

    assert report.status == "blocked"
    assert report.changed_files == []
    assert report.verification_results == []
    assert any(
        "QUICKSCALE_PRIVILEGED_COMMAND" in blocker and "static literal" in blocker
        for blocker in report.blockers
    )


@pytest.mark.parametrize(
    ("launcher_line", "expected_blocker"),
    [
        (
            'export QUICKSCALE_PRIVILEGED_COMMAND=migrate RUNTIME_DATABASE_URL="" '
            "python manage.py migrate\n",
            "one-shot command environment prefixes",
        ),
        (
            "QUICKSCALE_PRIVILEGED_COMMAND=migrate python manage.py migrate "
            'RUNTIME_DATABASE_URL="" --noinput\n',
            "before python manage.py",
        ),
        (
            'env "QUICKSCALE_$(printf PRIVILEGED)_COMMAND=migrate" '
            'RUNTIME_DATABASE_URL="" python manage.py migrate\n',
            "static literal",
        ),
        (
            'RUNTIME_DATABASE_URL="" QUICKSCALE_ALLOW_BYPASSRLS=1 '
            "python manage.py migrate\n",
            "only supported as a one-shot prefix",
        ),
    ],
)
def test_runtime_selector_must_be_one_shot_static_command_prefix(
    tmp_path: Path,
    launcher_line: str,
    expected_blocker: str,
) -> None:
    """Persistent, misordered, or dynamically named selector forms must block."""
    donor = _write_project(
        tmp_path / "donor",
        slug="fresh-donor",
        package="fresh_donor",
        marker="donor",
    )
    recipient = _write_project(
        tmp_path / "recipient",
        slug="beta-site",
        package="beta_site",
        marker="recipient",
    )
    launcher_root = recipient
    with (launcher_root / "start.sh").open("a") as start_script:
        start_script.write(launcher_line)

    report = run_beta_migration(
        BetaMigrationInput(
            mode="fresh-first",
            donor=donor,
            recipient=recipient,
            dry_run=True,
        )
    )

    assert report.status == "blocked"
    assert report.changed_files == []
    assert report.verification_results == []
    assert any(expected_blocker in blocker for blocker in report.blockers)


def test_static_unrelated_env_name_with_expanded_value_is_allowed(
    tmp_path: Path,
) -> None:
    """Value expansion on an unrelated static environment name is compatible."""
    donor = _write_project(
        tmp_path / "donor",
        slug="fresh-donor",
        package="fresh_donor",
        marker="donor",
    )
    recipient = _write_project(
        tmp_path / "recipient",
        slug="beta-site",
        package="beta_site",
        marker="recipient",
    )
    launcher_root = recipient
    with (launcher_root / "start.sh").open("a") as start_script:
        start_script.write(
            "count=0\n"
            "(( count += 1 )) || true\n"
            'if [[ "$#" -eq 1 && "$1" == "maintenance_check" ]]; then :; fi\n'
            'env DJANGO_SETTINGS_MODULE="$SETTINGS_MODULE" python manage.py check\n'
        )

    report = plan_beta_migration(
        BetaMigrationInput(
            mode="fresh-first",
            donor=donor,
            recipient=recipient,
            dry_run=True,
        )
    )

    assert report.status == "ready", report.blockers
    assert report.changed_files == []


@pytest.mark.parametrize(
    ("env_line", "expected_blocker"),
    [
        (
            "ENV QUICKSCALE_NON_DB_COMMAND unsupported_migration",
            "persistent Docker ENV",
        ),
        (
            "ENV QUICKSCALE_NON_DB_COMMAND=unsupported_migration",
            "persistent Docker ENV",
        ),
        (
            "ENV QUICKSCALE_NON_DB_COMMAND=collectstatic # persisted value text",
            "persistent Docker ENV",
        ),
    ],
)
def test_docker_env_runtime_command_forms_block_before_mutation(
    tmp_path: Path,
    env_line: str,
    expected_blocker: str,
) -> None:
    """Modern, legacy, and unresolved Docker ENV forms must fail closed."""
    donor = _write_project(
        tmp_path / "donor",
        slug="fresh-donor",
        package="fresh_donor",
        marker="donor",
    )
    recipient = _write_project(
        tmp_path / "recipient",
        slug="beta-site",
        package="beta_site",
        marker="recipient",
    )
    launcher_root = recipient
    dockerfile = launcher_root / "Dockerfile"
    dockerfile.write_text(dockerfile.read_text() + f"\n{env_line}\n")

    report = run_beta_migration(
        BetaMigrationInput(
            mode="fresh-first",
            donor=donor,
            recipient=recipient,
            dry_run=True,
        )
    )

    assert report.status == "blocked"
    assert report.changed_files == []
    assert report.verification_results == []
    assert any(expected_blocker in blocker for blocker in report.blockers)


def test_unrelated_custom_production_settings_are_allowed(
    tmp_path: Path,
) -> None:
    """Donor-owned integrations must not be rejected by the facade check."""
    donor = _write_project(
        tmp_path / "donor",
        slug="fresh-donor",
        package="fresh_donor",
        marker="donor",
    )
    recipient = _write_project(
        tmp_path / "recipient",
        slug="beta-site",
        package="beta_site",
        marker="recipient",
    )
    settings_root = donor
    package = "fresh_donor"
    settings_path = settings_root / package / "settings" / "production.py"
    settings_path.write_text(
        settings_path.read_text()
        + "\nimport sentry_sdk\n"
        + "from sentry_sdk.integrations.django import DjangoIntegration\n"
        + 'SENTRY_DSN = "https://public@example.invalid/1"\n'
        + "def build_request_context(request):\n"
        + '    _KNOWN_PRIVILEGED_COMMANDS = {"local-only"}\n'
        + "    return dict(locals())\n"
        + 'os.environ.setdefault("SENTRY_ENVIRONMENT", "production")\n'
        + "if SENTRY_DSN:\n"
        + "    sentry_sdk.init(dsn=SENTRY_DSN, integrations=[DjangoIntegration()])\n"
    )

    report = plan_beta_migration(
        BetaMigrationInput(
            mode="fresh-first",
            donor=donor,
            recipient=recipient,
            dry_run=True,
        )
    )

    assert report.status == "ready"
    assert report.changed_files == []


_INLINE_CONTRACT_PRODUCTION_SETTINGS = (
    '"""Inline command-mode contract (pre-SA206 donor copy)."""\n'
    "import dj_database_url\n"
    "import os\n"
    "from decouple import config\n"
    '\n_runtime_db_url = config("RUNTIME_DATABASE_URL", default=None)\n'
    'database_url = config("DATABASE_URL", default=None)\n'
    '_privileged_command = os.environ.get("QUICKSCALE_PRIVILEGED_COMMAND", "")\n'
    '_non_db_command = os.environ.get("QUICKSCALE_NON_DB_COMMAND", "")\n'
    '_KNOWN_PRIVILEGED_COMMANDS = frozenset({"migrate", "createcachetable"})\n'
    '_KNOWN_NON_DB_COMMANDS = frozenset({"collectstatic", "compilemessages"})\n'
    "if _privileged_command:\n"
    "    if _privileged_command not in _KNOWN_PRIVILEGED_COMMANDS:\n"
    '        raise ValueError("unknown privileged command")\n'
    "    _db_url = database_url\n"
    "elif _non_db_command:\n"
    "    _db_url = database_url or "
    '"postgresql://dummy:dummy@localhost:5432/dummy"\n'
    "elif _runtime_db_url:\n"
    "    _db_url = _runtime_db_url\n"
    "else:\n"
    '    raise ValueError("RUNTIME_DATABASE_URL is required")\n'
    'DATABASES = {"default": dj_database_url.parse(_db_url)}\n'
)


def test_inline_command_contract_blocks_before_mutation(
    tmp_path: Path,
) -> None:
    """Donor settings that keep the retired inline contract must be refused."""
    donor = _write_project(
        tmp_path / "donor",
        slug="fresh-donor",
        package="fresh_donor",
        marker="donor",
    )
    recipient = _write_project(
        tmp_path / "recipient",
        slug="beta-site",
        package="beta_site",
        marker="recipient",
    )
    settings_path = donor / "fresh_donor" / "settings" / "production.py"
    settings_path.write_text(_INLINE_CONTRACT_PRODUCTION_SETTINGS)

    report = run_beta_migration(
        BetaMigrationInput(
            mode="fresh-first",
            donor=donor,
            recipient=recipient,
            dry_run=True,
        )
    )

    assert report.status == "blocked"
    assert report.changed_files == []
    assert report.verification_results == []
    assert any(
        "does not select its database through the QuickScale runtime settings facade"
        in blocker
        for blocker in report.blockers
    )
    assert any(
        check.name == "runtime-launcher-settings-compatibility"
        and check.status == "failed"
        for check in report.preflight_checks
    )


_FACADE_CALL_IN_DEAD_FUNCTION_SETTINGS = (
    '"""Facade call inside an unused function."""\n'
    "import dj_database_url\n"
    "from decouple import config\n"
    "from quickscale_core.runtime.settings import resolve_runtime_database_url\n"
    "\n"
    "def unused_helper():\n"
    "    return resolve_runtime_database_url(\n"
    '        runtime_database_url=None, database_url=None, privileged_command=""\n'
    "    )\n"
    "\n"
    'database_url = config("DATABASE_URL", default=None)\n'
    'DATABASES = {"default": dj_database_url.parse(database_url)}\n'
)

_FACADE_SELECTION_NOT_CONSUMED_SETTINGS = (
    '"""Facade selection assigned but not used for DATABASES."""\n'
    "import dj_database_url\n"
    "from decouple import config\n"
    "from quickscale_core.runtime.settings import resolve_runtime_database_url\n"
    "\n"
    'database_url = config("DATABASE_URL", default=None)\n'
    "_db_url = resolve_runtime_database_url(\n"
    '    runtime_database_url=None, database_url=database_url, privileged_command=""\n'
    ")\n"
    'DATABASES = {"default": dj_database_url.parse(database_url)}\n'
)


_FACADE_SELECTION_OUTRANKED_SETTINGS = (
    '"""Facade selection mentioned but another URL wins for the default."""\n'
    "import dj_database_url\n"
    "from decouple import config\n"
    "from quickscale_core.runtime.settings import resolve_runtime_database_url\n"
    "\n"
    'database_url = config("DATABASE_URL", default=None)\n'
    "_db_url = resolve_runtime_database_url(\n"
    '    runtime_database_url=None, database_url=database_url, privileged_command=""\n'
    ")\n"
    'DATABASES = {"default": database_url or _db_url}\n'
)


@pytest.mark.parametrize(
    "settings_text",
    [
        _FACADE_CALL_IN_DEAD_FUNCTION_SETTINGS,
        _FACADE_SELECTION_NOT_CONSUMED_SETTINGS,
        _FACADE_SELECTION_OUTRANKED_SETTINGS,
    ],
    ids=["call-in-dead-function", "selection-not-consumed", "selection-outranked"],
)
def test_facade_call_must_select_databases(tmp_path: Path, settings_text: str) -> None:
    """A syntactic facade call that does not govern DATABASES must be refused."""
    donor = _write_project(
        tmp_path / "donor",
        slug="fresh-donor",
        package="fresh_donor",
        marker="donor",
    )
    recipient = _write_project(
        tmp_path / "recipient",
        slug="beta-site",
        package="beta_site",
        marker="recipient",
    )
    settings_path = donor / "fresh_donor" / "settings" / "production.py"
    settings_path.write_text(settings_text)

    report = run_beta_migration(
        BetaMigrationInput(
            mode="fresh-first",
            donor=donor,
            recipient=recipient,
            dry_run=True,
        )
    )

    assert report.status == "blocked"
    assert report.changed_files == []
    assert any(
        "does not select its database through the QuickScale runtime settings facade"
        in blocker
        for blocker in report.blockers
    )


def test_module_attribute_facade_call_is_accepted(tmp_path: Path) -> None:
    """The facade check accepts the module-attribute call form."""
    donor = _write_project(
        tmp_path / "donor",
        slug="fresh-donor",
        package="fresh_donor",
        marker="donor",
    )
    recipient = _write_project(
        tmp_path / "recipient",
        slug="beta-site",
        package="beta_site",
        marker="recipient",
    )
    settings_path = donor / "fresh_donor" / "settings" / "production.py"
    settings_path.write_text(
        settings_path.read_text()
        .replace(
            "from quickscale_core.runtime.settings import "
            "resolve_runtime_database_url\n",
            "import quickscale_core.runtime.settings as runtime_settings\n",
        )
        .replace(
            "_db_url = resolve_runtime_database_url(",
            "_db_url = runtime_settings.resolve_runtime_database_url(",
        )
    )

    report = run_beta_migration(
        BetaMigrationInput(
            mode="fresh-first",
            donor=donor,
            recipient=recipient,
            dry_run=True,
        )
    )

    assert report.status == "ready"


def test_dockerfile_package_skew_blocks_before_mutation(
    tmp_path: Path,
) -> None:
    """Dockerfile production settings references must target the effective package."""
    donor = _write_project(
        tmp_path / "donor",
        slug="fresh-donor",
        package="fresh_donor",
        marker="donor",
    )
    recipient = _write_project(
        tmp_path / "recipient",
        slug="beta-site",
        package="beta_site",
        marker="recipient",
    )
    launcher_root = recipient
    launcher_package = "beta_site"
    dockerfile = launcher_root / "Dockerfile"
    dockerfile.write_text(
        dockerfile.read_text().replace(
            f"{launcher_package}.settings.production",
            "unrelated_package.settings.production",
        )
    )

    report = run_beta_migration(
        BetaMigrationInput(
            mode="fresh-first",
            donor=donor,
            recipient=recipient,
            dry_run=True,
        )
    )

    assert report.status == "blocked"
    assert report.changed_files == []
    assert report.verification_results == []
    assert any("unrelated_package" in blocker for blocker in report.blockers)


def test_dockerfile_requires_effective_final_stage_production_settings(
    tmp_path: Path,
) -> None:
    """A package token outside final-stage ENV must not satisfy runtime settings."""
    donor = _write_project(
        tmp_path / "donor",
        slug="fresh-donor",
        package="fresh_donor",
        marker="donor",
    )
    recipient = _write_project(
        tmp_path / "recipient",
        slug="beta-site",
        package="beta_site",
        marker="recipient",
    )
    launcher_root = recipient
    launcher_package = "beta_site"
    dockerfile = launcher_root / "Dockerfile"
    dockerfile.write_text(
        dockerfile.read_text().replace(
            f"ENV DJANGO_SETTINGS_MODULE={launcher_package}.settings.production",
            f'LABEL note="{launcher_package}.settings.production"',
        )
    )

    report = plan_beta_migration(
        BetaMigrationInput(
            mode="fresh-first",
            donor=donor,
            recipient=recipient,
            dry_run=True,
        )
    )

    assert report.status == "blocked"
    assert report.changed_files == []
    assert any("final stage must define ENV" in blocker for blocker in report.blockers)


def test_required_collectstatic_must_be_in_effective_final_stage(
    tmp_path: Path,
) -> None:
    """An unused Docker stage cannot satisfy final-image collection requirements."""
    donor = _write_project(
        tmp_path / "donor",
        slug="fresh-donor",
        package="fresh_donor",
        marker="donor",
    )
    recipient = _write_project(
        tmp_path / "recipient",
        slug="beta-site",
        package="beta_site",
        marker="recipient",
    )
    launcher_root = recipient
    dockerfile = launcher_root / "Dockerfile"
    collectstatic_line = (
        "RUN QUICKSCALE_NON_DB_COMMAND=collectstatic "
        "python manage.py collectstatic --noinput\n"
    )
    docker_text = dockerfile.read_text()
    assert collectstatic_line in docker_text
    dockerfile.write_text(
        "FROM python:3.14-slim-bookworm AS unused\n"
        + collectstatic_line
        + docker_text.replace(collectstatic_line, "")
    )

    report = run_beta_migration(
        BetaMigrationInput(
            mode="fresh-first",
            donor=donor,
            recipient=recipient,
            dry_run=True,
        )
    )

    assert report.status == "blocked"
    assert report.changed_files == []
    assert any(
        "required QUICKSCALE_NON_DB_COMMAND=collectstatic" in blocker
        for blocker in report.blockers
    )


def test_dockerfile_runtime_entrypoint_skew_blocks_before_mutation(
    tmp_path: Path,
) -> None:
    """Effective Dockerfiles must retain one canonical start.sh runtime command."""
    donor = _write_project(
        tmp_path / "donor",
        slug="fresh-donor",
        package="fresh_donor",
        marker="donor",
    )
    recipient = _write_project(
        tmp_path / "recipient",
        slug="beta-site",
        package="beta_site",
        marker="recipient",
    )
    launcher_root = recipient
    with (launcher_root / "Dockerfile").open("a") as dockerfile:
        dockerfile.write('CMD ["gunicorn", "unrelated_package.wsgi:application"]\n')

    report = run_beta_migration(
        BetaMigrationInput(
            mode="fresh-first",
            donor=donor,
            recipient=recipient,
            dry_run=True,
        )
    )

    assert report.status == "blocked"
    assert report.changed_files == []
    assert report.verification_results == []
    assert any("canonical Docker runtime" in blocker for blocker in report.blockers)


def test_required_migrate_invocation_cannot_disappear(
    tmp_path: Path,
) -> None:
    """The effective launcher must keep every required generated command mode."""
    donor = _write_project(
        tmp_path / "donor",
        slug="fresh-donor",
        package="fresh_donor",
        marker="donor",
    )
    recipient = _write_project(
        tmp_path / "recipient",
        slug="beta-site",
        package="beta_site",
        marker="recipient",
    )
    launcher_root = recipient
    start_script = launcher_root / "start.sh"
    start_script.write_text(
        start_script.read_text().replace(
            'QUICKSCALE_PRIVILEGED_COMMAND=migrate RUNTIME_DATABASE_URL="" '
            "python manage.py migrate --noinput\n",
            "",
        )
    )

    report = run_beta_migration(
        BetaMigrationInput(
            mode="fresh-first",
            donor=donor,
            recipient=recipient,
            dry_run=True,
        )
    )

    assert report.status == "blocked"
    assert report.changed_files == []
    assert any(
        "required QUICKSCALE_PRIVILEGED_COMMAND=migrate" in blocker
        for blocker in report.blockers
    )


def test_required_command_after_final_exec_is_not_counted_as_reachable(
    tmp_path: Path,
) -> None:
    """A valid command in the shell's dead suffix cannot satisfy compatibility."""
    donor = _write_project(
        tmp_path / "donor",
        slug="fresh-donor",
        package="fresh_donor",
        marker="donor",
    )
    recipient = _write_project(
        tmp_path / "recipient",
        slug="beta-site",
        package="beta_site",
        marker="recipient",
    )
    launcher_root = recipient
    start_script = launcher_root / "start.sh"
    migrate_line = (
        'QUICKSCALE_PRIVILEGED_COMMAND=migrate RUNTIME_DATABASE_URL="" '
        "python manage.py migrate --noinput\n"
    )
    start_text = start_script.read_text()
    assert migrate_line in start_text
    start_script.write_text(start_text.replace(migrate_line, "") + migrate_line)

    report = run_beta_migration(
        BetaMigrationInput(
            mode="fresh-first",
            donor=donor,
            recipient=recipient,
            dry_run=True,
        )
    )

    assert report.status == "blocked"
    assert report.changed_files == []
    assert any(
        "QUICKSCALE_PRIVILEGED_COMMAND=migrate" in blocker
        and "unconditionally executable" in blocker
        for blocker in report.blockers
    )


def test_required_migrate_invocation_must_be_unconditional(
    tmp_path: Path,
) -> None:
    """A conditional branch cannot satisfy the required startup migration."""
    donor = _write_project(
        tmp_path / "donor",
        slug="fresh-donor",
        package="fresh_donor",
        marker="donor",
    )
    recipient = _write_project(
        tmp_path / "recipient",
        slug="beta-site",
        package="beta_site",
        marker="recipient",
    )
    launcher_root = recipient
    start_script = launcher_root / "start.sh"
    migrate_line = (
        'QUICKSCALE_PRIVILEGED_COMMAND=migrate RUNTIME_DATABASE_URL="" '
        "python manage.py migrate --noinput\n"
    )
    start_text = start_script.read_text()
    assert migrate_line in start_text
    start_script.write_text(
        start_text.replace(
            migrate_line,
            f"if [[ 1 == 0 ]]; then\n  {migrate_line}fi\n",
        )
    )

    report = run_beta_migration(
        BetaMigrationInput(
            mode="fresh-first",
            donor=donor,
            recipient=recipient,
            dry_run=True,
        )
    )

    assert report.status == "blocked"
    assert report.changed_files == []
    assert any(
        "must be unconditionally executable" in blocker for blocker in report.blockers
    )


def test_compound_exit_before_required_migrate_blocks(
    tmp_path: Path,
) -> None:
    """Compound top-level exits must not hide an unreachable migration."""
    donor = _write_project(
        tmp_path / "donor",
        slug="fresh-donor",
        package="fresh_donor",
        marker="donor",
    )
    recipient = _write_project(
        tmp_path / "recipient",
        slug="beta-site",
        package="beta_site",
        marker="recipient",
    )
    launcher_root = recipient
    start_script = launcher_root / "start.sh"
    migrate_line = (
        'QUICKSCALE_PRIVILEGED_COMMAND=migrate RUNTIME_DATABASE_URL="" '
        "python manage.py migrate --noinput\n"
    )
    start_text = start_script.read_text()
    assert migrate_line in start_text
    start_script.write_text(
        start_text.replace(migrate_line, "true && exit\n" + migrate_line)
    )

    report = run_beta_migration(
        BetaMigrationInput(
            mode="fresh-first",
            donor=donor,
            recipient=recipient,
            dry_run=True,
        )
    )

    assert report.status == "blocked"
    assert report.changed_files == []
    assert any("compound top-level exit/exec" in blocker for blocker in report.blockers)


def test_errexit_failure_before_required_migrate_blocks(
    tmp_path: Path,
) -> None:
    """A guaranteed failure under active errexit cannot precede migration."""
    donor = _write_project(
        tmp_path / "donor",
        slug="fresh-donor",
        package="fresh_donor",
        marker="donor",
    )
    recipient = _write_project(
        tmp_path / "recipient",
        slug="beta-site",
        package="beta_site",
        marker="recipient",
    )
    launcher_root = recipient
    start_script = launcher_root / "start.sh"
    migrate_line = (
        'QUICKSCALE_PRIVILEGED_COMMAND=migrate RUNTIME_DATABASE_URL="" '
        "python manage.py migrate --noinput\n"
    )
    start_text = start_script.read_text()
    assert migrate_line in start_text
    start_script.write_text(
        start_text.replace(migrate_line, "set -e\nfalse\n" + migrate_line)
    )

    report = run_beta_migration(
        BetaMigrationInput(
            mode="fresh-first",
            donor=donor,
            recipient=recipient,
            dry_run=True,
        )
    )

    assert report.status == "blocked"
    assert report.changed_files == []
    assert any(
        "top-level false under active set -e" in blocker for blocker in report.blockers
    )


def test_required_startup_command_cannot_move_to_docker_build(
    tmp_path: Path,
) -> None:
    """A privileged Docker RUN cannot replace the required startup migration."""
    donor = _write_project(
        tmp_path / "donor",
        slug="fresh-donor",
        package="fresh_donor",
        marker="donor",
    )
    recipient = _write_project(
        tmp_path / "recipient",
        slug="beta-site",
        package="beta_site",
        marker="recipient",
    )
    launcher_root = recipient
    start_script = launcher_root / "start.sh"
    migrate_line = (
        'QUICKSCALE_PRIVILEGED_COMMAND=migrate RUNTIME_DATABASE_URL="" '
        "python manage.py migrate --noinput\n"
    )
    start_text = start_script.read_text()
    assert migrate_line in start_text
    start_script.write_text(start_text.replace(migrate_line, ""))
    dockerfile = launcher_root / "Dockerfile"
    dockerfile.write_text(
        dockerfile.read_text().replace(
            'CMD ["./start.sh"]\n',
            "RUN QUICKSCALE_PRIVILEGED_COMMAND=migrate "
            'RUNTIME_DATABASE_URL="" python manage.py migrate --noinput\n'
            'CMD ["./start.sh"]\n',
        )
    )

    report = plan_beta_migration(
        BetaMigrationInput(
            mode="fresh-first",
            donor=donor,
            recipient=recipient,
            dry_run=True,
        )
    )

    assert report.status == "blocked"
    assert report.changed_files == []
    assert any(
        "only supported in start.sh" in blocker
        or "missing from the effective start.sh" in blocker
        for blocker in report.blockers
    )


def test_dead_launcher_package_references_do_not_create_runtime_skew(
    tmp_path: Path,
) -> None:
    """Package references after final exec are validated text, not runtime targets."""
    donor = _write_project(
        tmp_path / "donor",
        slug="fresh-donor",
        package="fresh_donor",
        marker="donor",
    )
    recipient = _write_project(
        tmp_path / "recipient",
        slug="beta-site",
        package="beta_site",
        marker="recipient",
    )
    launcher_root = recipient
    with (launcher_root / "start.sh").open("a") as start_script:
        start_script.write("echo unrelated_package.wsgi:application\n")

    report = plan_beta_migration(
        BetaMigrationInput(
            mode="fresh-first",
            donor=donor,
            recipient=recipient,
            dry_run=True,
        )
    )

    assert report.status == "ready"
    assert report.changed_files == []


def test_required_manage_command_without_selector_blocks_before_mutation(
    tmp_path: Path,
) -> None:
    """A required management command cannot run without its one-shot selector."""
    donor = _write_project(
        tmp_path / "donor",
        slug="fresh-donor",
        package="fresh_donor",
        marker="donor",
    )
    recipient = _write_project(
        tmp_path / "recipient",
        slug="beta-site",
        package="beta_site",
        marker="recipient",
    )
    launcher_root = recipient
    start_script = launcher_root / "start.sh"
    start_script.write_text(
        start_script.read_text().replace(
            'QUICKSCALE_PRIVILEGED_COMMAND=migrate RUNTIME_DATABASE_URL="" '
            "python manage.py migrate --noinput",
            "python manage.py migrate --noinput",
        )
    )

    report = run_beta_migration(
        BetaMigrationInput(
            mode="fresh-first",
            donor=donor,
            recipient=recipient,
            dry_run=True,
        )
    )

    assert report.status == "blocked"
    assert report.changed_files == []
    assert any("required one-shot" in blocker for blocker in report.blockers)


def test_later_unguarded_manage_command_on_same_line_blocks_before_mutation(
    tmp_path: Path,
) -> None:
    """Every management-command invocation on a launcher line must be classified."""
    donor = _write_project(
        tmp_path / "donor",
        slug="fresh-donor",
        package="fresh_donor",
        marker="donor",
    )
    recipient = _write_project(
        tmp_path / "recipient",
        slug="beta-site",
        package="beta_site",
        marker="recipient",
    )
    launcher_root = recipient
    with (launcher_root / "start.sh").open("a") as start_script:
        start_script.write("python manage.py check && python manage.py migrate\n")

    report = run_beta_migration(
        BetaMigrationInput(
            mode="fresh-first",
            donor=donor,
            recipient=recipient,
            dry_run=True,
        )
    )

    assert report.status == "blocked"
    assert report.changed_files == []
    assert any("python manage.py migrate" in blocker for blocker in report.blockers)


@pytest.mark.parametrize(
    "launcher_lines",
    [
        (
            'python -c "import subprocess; '
            "subprocess.run(['python', 'manage.py', 'migrate'])\"\n"
        ),
        (
            "python - <<'PY'\n"
            "import subprocess\n"
            'subprocess.run(["python", "manage.py", "migrate"])\n'
            "PY\n"
        ),
        (
            'python manage.py shell -c "import os; '
            "os.system('python manage.py migrate')\"\n"
        ),
        "python ./scripts/runtime_wrapper.py\n",
        "python manage.py shell < /tmp/runtime_payload.py\n",
    ],
)
def test_indirect_python_launcher_execution_blocks_before_mutation(
    tmp_path: Path,
    launcher_lines: str,
) -> None:
    """Executable Python payloads must not hide an unmarked manage.py process."""
    donor = _write_project(
        tmp_path / "donor",
        slug="fresh-donor",
        package="fresh_donor",
        marker="donor",
    )
    recipient = _write_project(
        tmp_path / "recipient",
        slug="beta-site",
        package="beta_site",
        marker="recipient",
    )
    launcher_root = recipient
    launcher_package = "beta_site"
    start_script = launcher_root / "start.sh"
    gunicorn_line = f"exec gunicorn {launcher_package}.wsgi:application\n"
    start_script.write_text(
        start_script.read_text().replace(
            gunicorn_line,
            launcher_lines + gunicorn_line,
        )
    )

    report = run_beta_migration(
        BetaMigrationInput(
            mode="fresh-first",
            donor=donor,
            recipient=recipient,
            dry_run=True,
        )
    )

    assert report.status == "blocked"
    assert report.changed_files == []
    assert report.verification_results == []
    assert any(
        "static" in blocker.lower() or "payload" in blocker.lower()
        for blocker in report.blockers
    )


@pytest.mark.parametrize(
    "docker_run",
    [
        (
            "RUN python -c \"import subprocess; subprocess.run(['python', "
            "'manage' + '.py', 'migrate'])\"\n"
        ),
        (
            'RUN python -c "import os; raise SystemExit('
            "os.system('python manage' + '.py migrate'))\"\n"
        ),
        ("RUN echo `python -c 'import os; os.system(\"python manage.py migrate\")'`\n"),
    ],
)
def test_indirect_docker_python_execution_blocks_before_mutation(
    tmp_path: Path,
    docker_run: str,
) -> None:
    """Docker build instructions must not hide an unmarked manage.py process."""
    donor = _write_project(
        tmp_path / "donor",
        slug="fresh-donor",
        package="fresh_donor",
        marker="donor",
    )
    recipient = _write_project(
        tmp_path / "recipient",
        slug="beta-site",
        package="beta_site",
        marker="recipient",
    )
    launcher_root = recipient
    dockerfile = launcher_root / "Dockerfile"
    dockerfile.write_text(
        dockerfile.read_text().replace(
            'CMD ["./start.sh"]\n', docker_run + 'CMD ["./start.sh"]\n'
        )
    )

    report = run_beta_migration(
        BetaMigrationInput(
            mode="fresh-first",
            donor=donor,
            recipient=recipient,
            dry_run=True,
        )
    )

    assert report.status == "blocked"
    assert report.changed_files == []
    assert report.verification_results == []
    assert any("static" in blocker.lower() for blocker in report.blockers)


def test_python_package_identity_preserves_launcher_executables(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A valid package named python must not rewrite the Python executable."""
    donor = _write_project(
        tmp_path / "donor",
        slug="target-site",
        package="target_site",
        marker="donor",
    )
    recipient = _write_project(
        tmp_path / "recipient",
        slug="python",
        package="python",
        marker="recipient",
    )
    _install_verification_success_stub(monkeypatch)
    report = run_beta_migration(
        BetaMigrationInput(
            mode="fresh-first",
            donor=donor,
            recipient=recipient,
            dry_run=False,
        )
    )

    assert report.status == "ready", report.blockers
    start_text = (recipient / "start.sh").read_text()
    assert "python manage.py migrate" in start_text
    assert "python manage.py createcachetable" in start_text
    assert "target_site.wsgi:application" in start_text
    pyproject_text = (recipient / "pyproject.toml").read_text()
    assert 'python = "^3.14"' in pyproject_text
    assert 'python-decouple = "^3.8"' in pyproject_text
    compose_text = (recipient / "docker-compose.yml").read_text()
    assert "command: python manage.py runserver" in compose_text
    assert "command: target-site manage.py runserver" not in compose_text


def test_overlapping_identity_substitution_is_non_cascading(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A source slug inside its package must not rewrite replacement output."""
    donor = _write_project(
        tmp_path / "donor",
        slug="beta-site",
        package="beta_site_v2",
        marker="donor",
    )
    recipient = _write_project(
        tmp_path / "recipient",
        slug="beta",
        package="beta_site",
        marker="recipient",
    )
    _install_verification_success_stub(monkeypatch)
    report = run_beta_migration(
        BetaMigrationInput(
            mode="fresh-first",
            donor=donor,
            recipient=recipient,
            dry_run=False,
        )
    )

    assert report.status == "ready"
    start_script = (recipient / "start.sh").read_text()
    dockerfile = (recipient / "Dockerfile").read_text()
    assert "beta_site_v2.wsgi" in start_script
    assert "beta_site_v2.settings.production" in dockerfile
    assert "beta-site_site_v2" not in start_script + dockerfile


def test_equal_source_slug_and_package_use_path_specific_identity_semantics(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A one-word source identity must map slug and package contexts separately."""
    donor = _write_project(
        tmp_path / "donor",
        slug="beta-site",
        package="beta_site_v2",
        marker="donor",
    )
    recipient = _write_project(
        tmp_path / "recipient",
        slug="test80",
        package="test80",
        marker="recipient",
    )
    _install_verification_success_stub(monkeypatch)
    report = run_beta_migration(
        BetaMigrationInput(
            mode="fresh-first",
            donor=donor,
            recipient=recipient,
            dry_run=False,
        )
    )

    assert report.status == "ready"
    project_text = (recipient / "quickscale.yml").read_text()
    assert "slug: beta-site" in project_text
    assert "package: beta_site_v2" in project_text
    start_script = (recipient / "start.sh").read_text()
    dockerfile = (recipient / "Dockerfile").read_text()
    compose = (recipient / "docker-compose.yml").read_text()
    hook = (recipient / "frontend" / "src" / "hooks" / "useModules.ts").read_text()
    assert "beta_site_v2.wsgi" in start_script
    assert "beta_site_v2.settings.production" in dockerfile
    assert "beta-site_backend" in compose
    assert "quickscale-backend:beta-site" in compose
    assert "com.quickscale.scope: beta-site" in compose
    assert "5432/beta_site_v2" in compose
    assert "beta_site_v2_app:beta_site_v2_app_password" in compose
    assert "projectName: 'beta-site'" in hook
    pyproject = (recipient / "pyproject.toml").read_text()
    assert 'name = "beta-site"' in pyproject
    assert 'packages = [{include = "beta_site_v2"}]' in pyproject
    assert 'DJANGO_SETTINGS_MODULE = "beta_site_v2.settings.local"' in pyproject
    package_root = recipient / "beta_site_v2"
    assert "ASGI config for beta-site project" in (package_root / "asgi.py").read_text()
    assert "beta_site_v2.settings.production" in (package_root / "asgi.py").read_text()
    base_text = (package_root / "settings" / "base.py").read_text()
    assert "Django base settings for beta-site project" in base_text
    assert 'RUNTIME_DB_ROLE = "beta_site_v2_app"' in base_text
    local_text = (package_root / "settings" / "local.py").read_text()
    assert "Local development settings for beta-site" in local_text
    assert 'LOGGER = "beta_site_v2"' in local_text


def test_fresh_first_identity_fields_disambiguate_package_derived_slug_overlap(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Structural fields distinguish a slug that equals a package-derived value."""
    donor = _write_project(
        tmp_path / "donor",
        slug="target-site",
        package="target_pkg",
        marker="donor",
    )
    recipient = _write_project(
        tmp_path / "recipient",
        slug="acme-frontend",
        package="acme",
        marker="recipient",
    )
    calls = _install_verification_success_stub(monkeypatch)
    report = run_beta_migration(
        BetaMigrationInput(
            mode="fresh-first",
            donor=donor,
            recipient=recipient,
            dry_run=False,
        )
    )

    assert report.status == "ready", report.blockers
    assert calls
    assert not (recipient / "acme").exists()
    assert (recipient / "target_pkg").is_dir()
    assert 'name = "target-site"' in (recipient / "pyproject.toml").read_text()
    assert (
        '"name": "target_pkg-frontend"'
        in (recipient / "frontend" / "package.json").read_text()
    )
    compose_text = (recipient / "docker-compose.yml").read_text()
    assert "quickscale-backend:target-site" in compose_text
    assert "target_pkg_app:target_pkg_app_password" in compose_text


def test_malformed_authoritative_state_blocks_identity_before_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A malformed authoritative state file must block before identity writes."""
    donor = _write_project(
        tmp_path / "donor",
        slug="target-site",
        package="target_pkg",
        marker="donor",
    )
    recipient = _write_project(
        tmp_path / "recipient",
        slug="fresh-temp",
        package="fresh_temp",
        marker="recipient",
    )
    state_path = recipient / ".quickscale" / "state.yml"
    state_path.write_text("project: [not-a-mapping\n")
    calls = _install_verification_success_stub(monkeypatch)
    config_before = (recipient / "quickscale.yml").read_bytes()
    state_before = state_path.read_bytes()

    report = run_beta_migration(
        BetaMigrationInput(
            mode="fresh-first",
            donor=donor,
            recipient=recipient,
            dry_run=False,
        )
    )

    assert report.status == "blocked"
    assert report.changed_files == []
    assert calls == []
    assert (recipient / "quickscale.yml").read_bytes() == config_before
    assert state_path.read_bytes() == state_before
    assert (recipient / "fresh_temp").is_dir()
    assert not (recipient / "target_pkg").exists()
    assert any("state" in blocker.lower() for blocker in report.blockers)


def test_mismatched_authoritative_state_blocks_identity_before_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Well-formed state for another identity must block before identity writes."""
    donor = _write_project(
        tmp_path / "donor",
        slug="target-site",
        package="target_pkg",
        marker="donor",
    )
    recipient = _write_project(
        tmp_path / "recipient",
        slug="fresh-temp",
        package="fresh_temp",
        marker="recipient",
    )
    state_manager = StateManager(recipient)
    state = state_manager.load()
    assert state is not None
    state.project.slug = "stale-site"
    state.project.package = "stale_site"
    state_manager.save(state)
    calls = _install_verification_success_stub(monkeypatch)
    config_before = (recipient / "quickscale.yml").read_bytes()
    state_before = state_manager.state_file.read_bytes()

    report = run_beta_migration(
        BetaMigrationInput(
            mode="fresh-first",
            donor=donor,
            recipient=recipient,
            dry_run=False,
        )
    )

    assert report.status == "blocked"
    assert report.changed_files == []
    assert calls == []
    assert (recipient / "quickscale.yml").read_bytes() == config_before
    assert state_manager.state_file.read_bytes() == state_before
    assert (recipient / "fresh_temp").is_dir()
    assert not (recipient / "target_pkg").exists()
    assert any(
        "does not match the recipient identity" in blocker
        for blocker in report.blockers
    )


def test_matching_project_identity_still_validates_authoritative_state(
    tmp_path: Path,
) -> None:
    """Stale state must block even when donor and recipient identities already match."""
    donor = _write_project(
        tmp_path / "donor",
        slug="shared-site",
        package="shared_site",
        marker="donor",
    )
    recipient = _write_project(
        tmp_path / "recipient",
        slug="shared-site",
        package="shared_site",
        marker="recipient",
    )
    state_manager = StateManager(recipient)
    state = state_manager.load()
    assert state is not None
    state.project.slug = "stale-site"
    state.project.package = "stale_site"
    state_manager.save(state)

    report = plan_beta_migration(
        BetaMigrationInput(
            mode="fresh-first",
            donor=donor,
            recipient=recipient,
            dry_run=True,
        )
    )

    assert report.status == "blocked"
    assert report.changed_files == []
    assert any(
        "does not match the recipient identity" in blocker
        for blocker in report.blockers
    )


def test_identity_reconciliation_respects_authoritative_state_lock(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A held state lock must stop fresh-first reconciliation before mutation."""
    donor = _write_project(
        tmp_path / "donor",
        slug="target-site",
        package="target_pkg",
        marker="donor",
    )
    recipient = _write_project(
        tmp_path / "recipient",
        slug="fresh-temp",
        package="fresh_temp",
        marker="recipient",
    )
    calls = _install_verification_success_stub(monkeypatch)
    config_before = (recipient / "quickscale.yml").read_bytes()
    state_path = recipient / ".quickscale" / "state.yml"
    state_before = state_path.read_bytes()
    lock = AdvisoryLock(recipient, operation="test-contention")

    with lock:
        report = run_beta_migration(
            BetaMigrationInput(
                mode="fresh-first",
                donor=donor,
                recipient=recipient,
                dry_run=False,
            )
        )
        assert lock.lock_path.is_file()

    assert report.status == "blocked"
    assert report.phase == "fresh-first-partial"
    assert report.changed_files == []
    assert calls == []
    assert (recipient / "quickscale.yml").read_bytes() == config_before
    assert state_path.read_bytes() == state_before
    assert (recipient / "fresh_temp").is_dir()
    assert not (recipient / "target_pkg").exists()
    assert not lock.lock_path.exists()
    assert any("Advisory lock" in blocker for blocker in report.blockers)


def test_identity_reconciliation_records_package_rename_before_later_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A post-rename write failure must retain both sides of the rename in recovery data."""
    donor = _write_project(
        tmp_path / "donor",
        slug="target-site",
        package="target_pkg",
        marker="donor",
    )
    recipient = _write_project(
        tmp_path / "recipient",
        slug="fresh-temp",
        package="fresh_temp",
        marker="recipient",
    )
    source_package = recipient / "fresh_temp"
    target_package = recipient / "target_pkg"
    failing_path = target_package / "asgi.py"
    original_write_text = Path.write_text

    def fail_after_package_rename(
        path: Path, data: str, *args: object, **kwargs: object
    ) -> int:
        if path == failing_path:
            raise OSError("forced post-rename write failure")
        return original_write_text(path, data, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", fail_after_package_rename)

    report = run_beta_migration(
        BetaMigrationInput(
            mode="fresh-first",
            donor=donor,
            recipient=recipient,
            dry_run=False,
        )
    )

    assert report.status == "blocked"
    assert report.phase == "fresh-first-partial"
    assert not source_package.exists()
    assert target_package.is_dir()
    assert str(source_package) in report.changed_files
    assert str(target_package) in report.changed_files
    assert any(
        "forced post-rename write failure" in blocker for blocker in report.blockers
    )


def test_missing_effective_start_script_blocks_preflight(
    tmp_path: Path,
) -> None:
    """A missing effective start.sh must block instead of being silently skipped."""
    donor = _write_project(
        tmp_path / "donor",
        slug="fresh-donor",
        package="fresh_donor",
        marker="donor",
    )
    recipient = _write_project(
        tmp_path / "recipient",
        slug="beta-site",
        package="beta_site",
        marker="recipient",
    )
    missing_root = recipient
    (missing_root / "start.sh").unlink()

    report = plan_beta_migration(
        BetaMigrationInput(
            mode="fresh-first",
            donor=donor,
            recipient=recipient,
            dry_run=True,
        )
    )

    assert report.status == "blocked"
    assert report.changed_files == []
    assert any("start.sh" in blocker for blocker in report.blockers)


def test_run_fresh_first_different_slug_executes_verification_and_preserves_boundaries(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fresh-first execution should reconcile identity, copy donor content, and preserve recipient-managed files."""
    donor = _write_project(
        tmp_path / "donor",
        slug="experto-ai-web",
        package="experto_ai_web",
        marker="donor",
        modules=("auth", "blog", "social"),
        path_dependencies=(
            "quickscale-module-auth",
            "quickscale-module-blog",
            "quickscale-module-social",
        ),
    )
    recipient = _write_project(
        tmp_path / "recipient",
        slug="fresh-temp",
        package="fresh_temp",
        marker="recipient",
        modules=("auth", "blog"),
        path_dependencies=("quickscale-module-auth", "quickscale-module-blog"),
    )
    (recipient / "modules" / "social").mkdir(parents=True)

    donor_package_dir = donor / "experto_ai_web"
    recipient_package_dir = recipient / "fresh_temp"

    (donor / "frontend" / "src" / "App.tsx").write_text(
        "export default function App() { return 'donor-app'; }\n"
    )
    (recipient / "frontend" / "src" / "App.tsx").write_text(
        "export default function App() { return 'recipient-app'; }\n"
    )
    (donor / "frontend" / "src" / "pages" / "About.tsx").write_text(
        "export default 'donor-about';\n"
    )
    (donor / "frontend" / "src" / "pages" / "Dashboard.tsx").write_text(
        "export default 'donor-dashboard';\n"
    )
    (recipient / "frontend" / "src" / "pages" / "Dashboard.tsx").write_text(
        "export default 'recipient-dashboard';\n"
    )
    (donor / "frontend" / "src" / "components" / "layout" / "Nav.tsx").write_text(
        "export default 'donor-layout';\n"
    )
    (recipient / "frontend" / "src" / "components" / "layout" / "Nav.tsx").write_text(
        "export default 'recipient-layout';\n"
    )
    (donor / "frontend" / "src" / "components" / "ui" / "Button.tsx").write_text(
        "export default 'donor-ui';\n"
    )
    (recipient / "frontend" / "src" / "components" / "ui" / "Button.tsx").write_text(
        "export default 'recipient-ui';\n"
    )
    (donor / "frontend" / "src" / "assets").mkdir(parents=True, exist_ok=True)
    (recipient / "frontend" / "src" / "assets").mkdir(parents=True, exist_ok=True)
    (donor / "frontend" / "src" / "assets" / "logo.txt").write_text("donor-logo\n")
    (recipient / "frontend" / "src" / "assets" / "logo.txt").write_text(
        "recipient-logo\n"
    )

    (donor_package_dir / "urls.py").write_text("# donor-urls-marker\n")
    (donor_package_dir / "views.py").write_text("# donor-views-marker\n")
    (donor_package_dir / "context_processors.py").write_text(
        "# donor-context-processors-marker\n"
    )
    (donor_package_dir / "middleware.py").write_text("# donor-middleware-marker\n")
    (donor_package_dir / "sitemaps.py").write_text("# donor-sitemaps-marker\n")
    env_calls: list[tuple[tuple[str, ...], dict[str, str] | None]] = []
    ambient_venv = tmp_path / "ambient-venv"
    ambient_venv_bin = str(ambient_venv / "bin")
    monkeypatch.setenv("VIRTUAL_ENV", str(ambient_venv))
    monkeypatch.setenv("POETRY_ACTIVE", "1")
    monkeypatch.setenv("PATH", os.pathsep.join((ambient_venv_bin, "/usr/bin")))
    calls = _install_verification_success_stub(monkeypatch, env_calls)
    report = run_beta_migration(
        BetaMigrationInput(
            mode="fresh-first",
            donor=donor,
            recipient=recipient,
            dry_run=False,
        )
    )

    assert report.status == "ready"
    assert report.phase == "fresh-first-executed"
    assert report.identity_reconciliation_required is True
    _assert_verification_report(report, recipient, calls)

    poetry_envs = {
        command: env
        for command, env in env_calls
        if command in {("poetry", "lock"), ("poetry", "install")}
    }
    assert set(poetry_envs) == {("poetry", "lock"), ("poetry", "install")}
    for isolated_env in poetry_envs.values():
        assert isolated_env is not None
        assert "VIRTUAL_ENV" not in isolated_env
        assert "POETRY_ACTIVE" not in isolated_env
        assert ambient_venv_bin not in isolated_env["PATH"]
        assert isolated_env["POETRY_VIRTUALENVS_IN_PROJECT"] == "true"

    ambient_commands = {
        command
        for command, env in env_calls
        if command not in {("poetry", "lock"), ("poetry", "install")} and env is None
    }
    assert ambient_commands == {
        ("pnpm", "install"),
        ("pnpm", "build"),
        ("quickscale", "manage", "migrate"),
        ("pytest",),
        ("pnpm", "test"),
    }

    new_package_dir = recipient / "experto_ai_web"
    assert new_package_dir.is_dir()
    assert not recipient_package_dir.exists()
    assert report.recipient is not None
    assert report.recipient.identity.slug == "experto-ai-web"
    assert report.recipient.identity.package == "experto_ai_web"

    quickscale_text = (recipient / "quickscale.yml").read_text()
    assert "slug: experto-ai-web" in quickscale_text
    assert "package: experto_ai_web" in quickscale_text
    reconciled_state = StateManager(recipient).load()
    assert reconciled_state is not None
    assert reconciled_state.project.slug == "experto-ai-web"
    assert reconciled_state.project.package == "experto_ai_web"
    assert set(reconciled_state.managed_files) == {
        "experto_ai_web/settings/modules.py",
        "experto_ai_web/urls_modules.py",
    }

    pyproject_text = (recipient / "pyproject.toml").read_text()
    assert 'name = "experto-ai-web"' in pyproject_text
    assert 'packages = [{include = "experto_ai_web"}]' in pyproject_text
    assert 'DJANGO_SETTINGS_MODULE = "experto_ai_web.settings.local"' in pyproject_text
    assert (
        'quickscale-module-social = {path = "./modules/social", develop = true}'
        in pyproject_text
    )

    manage_text = (recipient / "manage.py").read_text()
    assert "experto_ai_web.settings.local" in manage_text
    assert "recipient-manage-marker" in manage_text
    assert "donor-manage-marker" not in manage_text

    dockerfile_text = (recipient / "Dockerfile").read_text()
    assert "recipient-docker-marker" in dockerfile_text
    assert "experto_ai_web.settings.production" in dockerfile_text
    assert "fresh_temp.settings.production" not in dockerfile_text
    assert "donor-docker-marker" not in dockerfile_text

    compose_text = (recipient / "docker-compose.yml").read_text()
    assert "recipient-compose-marker" in compose_text
    assert "experto-ai-web_backend" in compose_text
    assert (
        "DATABASE_URL=postgresql://postgres:postgres@db:5432/experto_ai_web"
        in compose_text
    )
    assert "donor-compose-marker" not in compose_text

    hook_text = (recipient / "frontend" / "src" / "hooks" / "useModules.ts").read_text()
    assert "projectName: 'experto-ai-web'" in hook_text
    assert "recipient-hook-marker" in hook_text

    start_sh_text = (recipient / "start.sh").read_text()
    assert "experto_ai_web.wsgi" in start_sh_text
    assert "fresh_temp.wsgi" not in start_sh_text

    base_text = (new_package_dir / "settings" / "base.py").read_text()
    assert "recipient-base-marker" in base_text
    assert "experto_ai_web.urls" in base_text
    assert "fresh_temp.urls" not in base_text
    assert "donor-base-marker" not in base_text

    local_text = (new_package_dir / "settings" / "local.py").read_text()
    assert "recipient-local-marker" in local_text
    assert 'LOGGER = "experto_ai_web"' in local_text
    assert 'LOGGER = "fresh_temp"' not in local_text
    assert "donor-local-marker" not in local_text

    assert (
        "recipient-modules-marker"
        in (new_package_dir / "settings" / "modules.py").read_text()
    )
    assert (
        "recipient-urls-modules-marker"
        in (new_package_dir / "urls_modules.py").read_text()
    )
    assert "recipient-railway-marker" in (recipient / "railway.json").read_text()

    assert "donor-app" in (recipient / "frontend" / "src" / "App.tsx").read_text()
    assert (
        "donor-about"
        in (recipient / "frontend" / "src" / "pages" / "About.tsx").read_text()
    )
    assert (
        "recipient-dashboard"
        in (recipient / "frontend" / "src" / "pages" / "Dashboard.tsx").read_text()
    )
    assert (
        "donor-layout"
        in (
            recipient / "frontend" / "src" / "components" / "layout" / "Nav.tsx"
        ).read_text()
    )
    assert (
        "recipient-ui"
        in (
            recipient / "frontend" / "src" / "components" / "ui" / "Button.tsx"
        ).read_text()
    )
    assert (
        "donor-logo"
        in (recipient / "frontend" / "src" / "assets" / "logo.txt").read_text()
    )

    assert "donor-urls-marker" in (new_package_dir / "urls.py").read_text()
    assert "donor-views-marker" in (new_package_dir / "views.py").read_text()
    assert (
        "donor-context-processors-marker"
        in (new_package_dir / "context_processors.py").read_text()
    )
    assert "donor-middleware-marker" in (new_package_dir / "middleware.py").read_text()
    assert "donor-sitemaps-marker" in (new_package_dir / "sitemaps.py").read_text()
    assert (
        "donor-production-marker"
        in (new_package_dir / "settings" / "production.py").read_text()
    )

    assert any(
        action.action == "run-local-smoke-checks"
        for action in report.pending_manual_actions
    )
    assert any(path.endswith("quickscale.yml") for path in report.changed_files)
    assert any(path.endswith(".quickscale/state.yml") for path in report.changed_files)
    assert any(path.endswith("frontend/src/App.tsx") for path in report.changed_files)


def test_run_fresh_first_same_slug_skips_identity_reconciliation_and_copies_only_allowed_surfaces(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fresh-first execution should skip identity reconciliation when slug/package already match."""
    donor = _write_project(
        tmp_path / "donor",
        slug="bap-web",
        package="bap_web",
        marker="donor",
        modules=("auth", "social"),
        path_dependencies=("quickscale-module-auth", "quickscale-module-social"),
    )
    recipient = _write_project(
        tmp_path / "recipient",
        slug="bap-web",
        package="bap_web",
        marker="recipient",
        modules=("auth",),
        path_dependencies=("quickscale-module-auth",),
    )
    (recipient / "modules" / "social").mkdir(parents=True)

    package_dir = recipient / "bap_web"
    donor_package_dir = donor / "bap_web"

    (donor / "frontend" / "src" / "App.tsx").write_text(
        "export default function App() { return 'donor-app'; }\n"
    )
    (donor / "frontend" / "src" / "pages" / "About.tsx").write_text(
        "export default 'donor-about';\n"
    )
    (recipient / "frontend" / "src" / "pages" / "Dashboard.tsx").write_text(
        "export default 'recipient-dashboard';\n"
    )
    (donor / "frontend" / "src" / "components" / "layout" / "Nav.tsx").write_text(
        "export default 'donor-layout';\n"
    )
    (recipient / "frontend" / "src" / "components" / "ui" / "Button.tsx").write_text(
        "export default 'recipient-ui';\n"
    )
    (donor / "frontend" / "src" / "assets").mkdir(parents=True, exist_ok=True)
    (donor / "frontend" / "src" / "assets" / "logo.txt").write_text("donor-logo\n")
    (recipient / "frontend" / "src" / "assets").mkdir(parents=True, exist_ok=True)
    (recipient / "frontend" / "src" / "assets" / "logo.txt").write_text(
        "recipient-logo\n"
    )

    (donor_package_dir / "urls.py").write_text("# donor-urls-marker\n")
    (donor_package_dir / "views.py").write_text("# donor-views-marker\n")
    (donor_package_dir / "context_processors.py").write_text(
        "# donor-context-processors-marker\n"
    )
    calls = _install_verification_success_stub(monkeypatch)
    report = run_beta_migration(
        BetaMigrationInput(
            mode="fresh-first",
            donor=donor,
            recipient=recipient,
            dry_run=False,
        )
    )

    assert report.status == "ready"
    assert report.identity_reconciliation_required is False
    _assert_verification_report(report, recipient, calls)

    assert package_dir.is_dir()
    assert report.recipient is not None
    assert report.recipient.package_dir == package_dir

    quickscale_text = (recipient / "quickscale.yml").read_text()
    assert "slug: bap-web" in quickscale_text
    assert "package: bap_web" in quickscale_text

    pyproject_text = (recipient / "pyproject.toml").read_text()
    assert 'name = "bap-web"' in pyproject_text
    assert 'packages = [{include = "bap_web"}]' in pyproject_text
    assert (
        'quickscale-module-social = {path = "./modules/social", develop = true}'
        in pyproject_text
    )

    manage_text = (recipient / "manage.py").read_text()
    assert "recipient-manage-marker" in manage_text
    assert "donor-manage-marker" not in manage_text

    base_text = (package_dir / "settings" / "base.py").read_text()
    assert "recipient-base-marker" in base_text
    assert "donor-base-marker" not in base_text

    local_text = (package_dir / "settings" / "local.py").read_text()
    assert "recipient-local-marker" in local_text
    assert "donor-local-marker" not in local_text

    assert (
        "recipient-modules-marker"
        in (package_dir / "settings" / "modules.py").read_text()
    )
    assert (
        "recipient-urls-modules-marker" in (package_dir / "urls_modules.py").read_text()
    )
    assert "recipient-railway-marker" in (recipient / "railway.json").read_text()

    assert "donor-app" in (recipient / "frontend" / "src" / "App.tsx").read_text()
    assert (
        "donor-about"
        in (recipient / "frontend" / "src" / "pages" / "About.tsx").read_text()
    )
    assert (
        "recipient-dashboard"
        in (recipient / "frontend" / "src" / "pages" / "Dashboard.tsx").read_text()
    )
    assert (
        "donor-layout"
        in (
            recipient / "frontend" / "src" / "components" / "layout" / "Nav.tsx"
        ).read_text()
    )
    assert (
        "recipient-ui"
        in (
            recipient / "frontend" / "src" / "components" / "ui" / "Button.tsx"
        ).read_text()
    )
    assert (
        "donor-logo"
        in (recipient / "frontend" / "src" / "assets" / "logo.txt").read_text()
    )

    assert "donor-urls-marker" in (package_dir / "urls.py").read_text()
    assert "donor-views-marker" in (package_dir / "views.py").read_text()
    assert (
        "donor-context-processors-marker"
        in (package_dir / "context_processors.py").read_text()
    )
    assert (
        "donor-production-marker"
        in (package_dir / "settings" / "production.py").read_text()
    )

    assert "no reconciliation was required" in _find_step_detail(
        report, "identity-reconciliation"
    )
    assert any(
        action.action == "run-local-smoke-checks"
        for action in report.pending_manual_actions
    )


def test_run_beta_migration_cli_writes_report_and_stdout_json(tmp_path: Path) -> None:
    """CLI execution should emit a readable summary, JSON, and an optional report file."""
    donor = _write_project(
        tmp_path / "donor",
        slug="donor-app",
        package="donor_app",
        marker="donor",
        modules=("auth", "blog"),
        path_dependencies=("quickscale-module-auth", "quickscale-module-blog"),
    )
    recipient = _write_project(
        tmp_path / "recipient",
        slug="recipient-app",
        package="recipient_app",
        marker="recipient",
        modules=("auth",),
        path_dependencies=("quickscale-module-auth",),
    )
    (recipient / "modules" / "blog").mkdir(parents=True)
    report_path = tmp_path / "artifacts" / "beta-report.json"
    stdout = io.StringIO()

    exit_code = run_beta_migration_cli(
        [
            "fresh-first",
            "--donor",
            str(donor),
            "--recipient",
            str(recipient),
            "--dry-run",
            "--report-path",
            str(report_path),
        ],
        stdout=stdout,
    )
    assert exit_code == 0
    output = stdout.getvalue()
    summary, json_payload = output.strip().split("\n\n", maxsplit=1)
    assert "Beta migration summary" in summary
    assert "Runtime provenance:" in summary
    parsed_stdout_json = json.loads(json_payload)
    assert parsed_stdout_json["report_version"] == "1"
    assert parsed_stdout_json["mode"] == "fresh-first"
    assert parsed_stdout_json["runtime_provenance"] == {
        "settings_production": "donor",
        "start_sh": "recipient",
        "dockerfile": "recipient",
    }
    assert report_path.exists()
    parsed_file_json = json.loads(report_path.read_text())
    assert parsed_file_json["written_report_path"] == str(report_path.resolve())


# ---------------------------------------------------------------------------
# Helper-focused tests for the TOML rewrite helpers
# ---------------------------------------------------------------------------


_PYPROJECT_WITH_ARRAY_OF_TABLES = (
    "[tool.poetry]\n"
    'name = "demo"\n'
    'version = "0.1.0"\n'
    "packages = [{include = 'demo'}]\n"
    "\n"
    "[tool.poetry.dependencies]\n"
    'python = "^3.14"\n'
    "\n"
    "[[tool.poetry.dependencies.quickscale-module-extra]]\n"
    'name = "extra-source"\n'
    'url = "https://example.com/simple"\n'
    "\n"
    "[tool.poetry.group.dev.dependencies]\n"
    'pytest = "^9.0.0"\n'
    "\n"
    "[tool.pytest.ini_options]\n"
    'DJANGO_SETTINGS_MODULE = "demo.settings.local"\n'
)


def test_write_validated_toml_accepts_valid_content(tmp_path: Path) -> None:
    """The validator should accept TOML that round-trips through tomllib.loads."""
    target = tmp_path / "pyproject.toml"
    _write_validated_toml(target, _PYPROJECT_WITH_ARRAY_OF_TABLES)
    assert target.read_text() == _PYPROJECT_WITH_ARRAY_OF_TABLES


def test_write_validated_toml_rejects_invalid_content(tmp_path: Path) -> None:
    """The validator should refuse to write TOML that does not parse."""
    target = tmp_path / "pyproject.toml"
    invalid = "[tool.poetry.dependencies]\npython = ^3.14\n"  # missing quotes
    with pytest.raises(ValueError, match="invalid TOML"):
        _write_validated_toml(target, invalid)
    assert not target.exists()


def test_locate_toml_section_bounds_ignores_child_array_of_tables() -> None:
    """The end boundary should keep child [[parent.child]] headers in the body."""
    lines = _PYPROJECT_WITH_ARRAY_OF_TABLES.splitlines()
    start, end = _locate_toml_section_bounds(lines, "tool.poetry.dependencies")
    assert lines[start].strip() == "[tool.poetry.dependencies]"
    body = lines[start + 1 : end]
    # The [[array-of-tables]] header that is a strict child of the section
    # is still part of the section body and must not be the boundary.
    assert any(line.strip().startswith("[[") for line in body)
    assert lines[end].strip() == "[tool.poetry.group.dev.dependencies]"


def test_locate_toml_section_bounds_treats_nested_tables_as_same_section() -> None:
    """A nested-table header (foo.bar.child) must not end the foo.bar section."""
    document = (
        "[tool.poetry]\n"
        'name = "demo"\n'
        "\n"
        "[tool.poetry.dependencies]\n"
        'python = "^3.14"\n'
        "\n"
        "[tool.poetry.dependencies.sources]\n"
        'default = {url = "https://pypi.org/simple"}\n'
        "\n"
        "[tool.poetry.group.dev.dependencies]\n"
        'pytest = "^9.0.0"\n'
    )
    lines = document.splitlines()
    start, end = _locate_toml_section_bounds(lines, "tool.poetry.dependencies")
    body = lines[start + 1 : end]
    assert any(line.strip() == "[tool.poetry.dependencies.sources]" for line in body)
    assert lines[end].strip() == "[tool.poetry.group.dev.dependencies]"


def test_locate_toml_section_bounds_raises_when_section_missing() -> None:
    """A missing section header should raise a clear ValueError."""
    with pytest.raises(ValueError, match="Unable to locate"):
        _locate_toml_section_bounds(
            ["[tool.poetry]", 'name = "demo"'], "tool.poetry.dependencies"
        )


def test_locate_toml_section_bounds_terminates_at_sibling_array_of_tables() -> None:
    """A sibling [[...]] header must terminate the active section bounds.

    Unlike child array-of-tables (``[[parent.child]]``), a sibling
    array-of-tables such as ``[[tool.poetry.source]]`` is not part of the
    ``tool.poetry.dependencies`` section and must end the body scan.
    """
    document = (
        "[tool.poetry]\n"
        'name = "demo"\n'
        "\n"
        "[tool.poetry.dependencies]\n"
        'python = "^3.14"\n'
        "\n"
        "[[tool.poetry.source]]\n"
        'name = "private"\n'
        'url = "https://example.com/simple"\n'
        "\n"
        "[tool.poetry.group.dev.dependencies]\n"
        'pytest = "^9.0.0"\n'
    )
    lines = document.splitlines()
    start, end = _locate_toml_section_bounds(lines, "tool.poetry.dependencies")
    assert lines[start].strip() == "[tool.poetry.dependencies]"
    # The sibling [[tool.poetry.source]] must NOT be inside the body.
    body = lines[start + 1 : end]
    assert not any("[[tool.poetry.source]]" in line for line in body)
    assert lines[end].strip() == "[[tool.poetry.source]]"


def test_locate_toml_section_bounds_keeps_child_array_of_tables_in_body() -> None:
    """A child [[parent.child]] header must remain inside the section body."""
    document = (
        "[tool.poetry]\n"
        'name = "demo"\n'
        "\n"
        "[tool.poetry.dependencies]\n"
        'python = "^3.14"\n'
        "\n"
        "[[tool.poetry.dependencies.extra-source]]\n"
        'name = "extra"\n'
        'url = "https://example.com/simple"\n'
        "\n"
        "[tool.poetry.group.dev.dependencies]\n"
        'pytest = "^9.0.0"\n'
    )
    lines = document.splitlines()
    start, end = _locate_toml_section_bounds(lines, "tool.poetry.dependencies")
    body = lines[start + 1 : end]
    assert any("[[tool.poetry.dependencies.extra-source]]" in line for line in body)
    assert lines[end].strip() == "[tool.poetry.group.dev.dependencies]"


def test_insert_missing_path_dependencies_inserts_before_array_of_tables(
    tmp_path: Path,
) -> None:
    """Parent-table keys must be inserted before a child array-of-tables header."""
    target = tmp_path / "pyproject.toml"
    target.write_text(_PYPROJECT_WITH_ARRAY_OF_TABLES)

    changed = _insert_missing_path_dependencies(
        target,
        {
            "quickscale-module-blog": {
                "path": "./modules/blog",
                "develop": True,
            }
        },
    )

    assert changed is True
    updated = target.read_text()
    # The new path dependency is present and formatted as an inline table.
    assert "quickscale-module-blog" in updated
    assert '{path = "./modules/blog", develop = true}' in updated
    # The [[...]] array-of-tables that lived under the same section is still
    # there because insertion only adds lines.
    assert "[[tool.poetry.dependencies.quickscale-module-extra]]" in updated
    # Parent keys after a child header would bind to the child table instead.
    extra_idx = updated.index("[[tool.poetry.dependencies.quickscale-module-extra]]")
    new_dep_idx = updated.index("quickscale-module-blog")
    assert new_dep_idx < extra_idx
    import tomllib

    parsed = tomllib.loads(updated)
    assert parsed["tool"]["poetry"]["dependencies"]["quickscale-module-blog"] == {
        "path": "./modules/blog",
        "develop": True,
    }
    # Sibling sections remain after the rewritten body.
    assert "[tool.poetry.group.dev.dependencies]" in updated
    assert "[tool.pytest.ini_options]" in updated


def test_insert_missing_path_dependencies_inserts_before_nested_tables(
    tmp_path: Path,
) -> None:
    """Parent-table keys must be inserted before a nested child table."""
    document = (
        "[tool.poetry]\n"
        'name = "demo"\n'
        "\n"
        "[tool.poetry.dependencies]\n"
        'python = "^3.14"\n'
        "\n"
        "[tool.poetry.dependencies.sources]\n"
        'default = {url = "https://pypi.org/simple"}\n'
        "\n"
        "[tool.pytest.ini_options]\n"
        'DJANGO_SETTINGS_MODULE = "demo.settings.local"\n'
    )
    target = tmp_path / "pyproject.toml"
    target.write_text(document)

    changed = _insert_missing_path_dependencies(
        target,
        {
            "quickscale-module-blog": {
                "path": "./modules/blog",
                "develop": True,
            }
        },
    )

    assert changed is True
    updated = target.read_text()
    # The nested table declaration is still present (insertion only adds).
    assert "[tool.poetry.dependencies.sources]" in updated
    assert 'default = {url = "https://pypi.org/simple"}' in updated
    # The new entry must remain a key of the parent dependency table.
    new_dep_idx = updated.index("quickscale-module-blog")
    nested_idx = updated.index("[tool.poetry.dependencies.sources]")
    assert new_dep_idx < nested_idx
    import tomllib

    parsed = tomllib.loads(updated)
    assert parsed["tool"]["poetry"]["dependencies"]["quickscale-module-blog"] == {
        "path": "./modules/blog",
        "develop": True,
    }
    # The section that lives after the rewritten body is still intact.
    assert "[tool.pytest.ini_options]" in updated


def test_insert_missing_path_dependencies_returns_false_for_empty(
    tmp_path: Path,
) -> None:
    """An empty dependency map is a no-op and should not touch the file."""
    target = tmp_path / "pyproject.toml"
    target.write_text(_PYPROJECT_WITH_ARRAY_OF_TABLES)
    before = target.read_text()

    changed = _insert_missing_path_dependencies(target, {})

    assert changed is False
    assert target.read_text() == before


def test_insert_missing_path_dependencies_raises_when_section_missing(
    tmp_path: Path,
) -> None:
    """Missing [tool.poetry.dependencies] should raise a clear error."""
    target = tmp_path / "pyproject.toml"
    target.write_text("[tool.poetry]\nname = 'demo'\n")
    with pytest.raises(ValueError, match="Unable to locate"):
        _insert_missing_path_dependencies(
            target,
            {"quickscale-module-blog": {"path": "./modules/blog", "develop": True}},
        )


# Regression tests: recipient-only non-path dependency visibility and
# subprocess timeout hardening (Phase 3 roadmap items)
# ---------------------------------------------------------------------------


def test_verification_command_timeout_blocks_with_actionable_diagnostic(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A hung verification command must fail the migration with a bounded timeout diagnostic.

    The fresh-first verification stack must record the timeout as a failure
    with a descriptive stderr, and the report must be blocked with a message
    that names the timed-out command and the remediation knob.
    """
    donor = _write_project(
        tmp_path / "donor",
        slug="fresh-donor",
        package="fresh_donor",
        marker="donor",
        modules=("auth",),
        path_dependencies=("quickscale-module-auth",),
    )
    recipient = _write_project(
        tmp_path / "recipient",
        slug="beta-site",
        package="beta_site",
        marker="recipient",
        modules=("auth",),
        path_dependencies=("quickscale-module-auth",),
    )

    original_run = subprocess.run

    def fake_run_with_verification_timeout(command, cwd=None, **kwargs):
        command_tuple = tuple(command)
        if command_tuple == ("poetry", "lock"):
            raise subprocess.TimeoutExpired(command, kwargs.get("timeout"))
        return original_run(command, cwd=cwd, **kwargs)

    monkeypatch.setattr(subprocess, "run", fake_run_with_verification_timeout)

    report = run_beta_migration(
        BetaMigrationInput(
            mode="fresh-first",
            donor=donor,
            recipient=recipient,
            dry_run=False,
        )
    )

    assert report.status == "blocked"
    assert report.phase == "fresh-first-partial"

    # The timed-out verification command must appear as a failed result.
    timed_out_results = [
        result
        for result in report.verification_results
        if result.command == "poetry lock"
    ]
    assert len(timed_out_results) == 1
    assert timed_out_results[0].status == "failed"
    assert "timed out" in timed_out_results[0].stderr.lower()

    # The blocker must name the command and the remediation knob.
    assert any(
        "poetry lock" in blocker and "timed out" in blocker.lower()
        for blocker in report.blockers
    )
    assert any(
        "VERIFICATION_COMMAND_TIMEOUT_SECONDS" in blocker for blocker in report.blockers
    )


def test_verification_command_nonzero_exit_blocks_and_stops_stack(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A nonzero verification exit should be recorded and stop later commands."""
    donor = _write_project(
        tmp_path / "donor",
        slug="fresh-donor",
        package="fresh_donor",
        marker="donor",
        modules=("auth",),
        path_dependencies=("quickscale-module-auth",),
    )
    recipient = _write_project(
        tmp_path / "recipient",
        slug="beta-site",
        package="beta_site",
        marker="recipient",
        modules=("auth",),
        path_dependencies=("quickscale-module-auth",),
    )
    calls: list[tuple[str, ...]] = []

    def fake_run(command, **kwargs):
        command_tuple = tuple(command)
        calls.append(command_tuple)
        return subprocess.CompletedProcess(
            command_tuple,
            7,
            stdout="nonzero stdout",
            stderr="nonzero stderr",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    report = run_beta_migration(
        BetaMigrationInput(
            mode="fresh-first",
            donor=donor,
            recipient=recipient,
            dry_run=False,
        )
    )

    assert report.status == "blocked"
    assert calls == [EXPECTED_VERIFICATION_SEQUENCE[0][0]]
    assert len(report.verification_results) == 1
    result = report.verification_results[0]
    assert result.command == "poetry lock"
    assert result.status == "failed"
    assert result.return_code == 7
    assert result.stdout == "nonzero stdout"
    assert result.stderr == "nonzero stderr"
    assert report.blockers == [
        "run-verification-stack failed: Verification command failed with exit code 7: poetry lock"
    ]


def test_verification_command_launch_oserror_blocks_and_stops_stack(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A verification launch OSError should be recorded and stop later commands."""
    donor = _write_project(
        tmp_path / "donor",
        slug="fresh-donor",
        package="fresh_donor",
        marker="donor",
        modules=("auth",),
        path_dependencies=("quickscale-module-auth",),
    )
    recipient = _write_project(
        tmp_path / "recipient",
        slug="beta-site",
        package="beta_site",
        marker="recipient",
        modules=("auth",),
        path_dependencies=("quickscale-module-auth",),
    )
    calls: list[tuple[str, ...]] = []

    def fake_run(command, **kwargs):
        command_tuple = tuple(command)
        calls.append(command_tuple)
        raise OSError("poetry executable missing")

    monkeypatch.setattr(subprocess, "run", fake_run)

    report = run_beta_migration(
        BetaMigrationInput(
            mode="fresh-first",
            donor=donor,
            recipient=recipient,
            dry_run=False,
        )
    )

    assert report.status == "blocked"
    assert calls == [EXPECTED_VERIFICATION_SEQUENCE[0][0]]
    assert len(report.verification_results) == 1
    result = report.verification_results[0]
    assert result.command == "poetry lock"
    assert result.status == "failed"
    assert result.return_code is None
    assert result.stdout == ""
    assert result.stderr == "poetry executable missing"
    assert report.blockers == [
        "run-verification-stack failed: Verification command failed to start: poetry lock: poetry executable missing"
    ]


# ---------------------------------------------------------------------------
# CR-SA94-REV-B-001: Theme preflight blocks on retired/malformed sources
# ---------------------------------------------------------------------------


def _write_project_with_theme(
    root: Path,
    *,
    slug: str,
    package: str,
    marker: str,
    theme: str,
    modules: tuple[str, ...] = (),
    path_dependencies: tuple[str, ...] = (),
    include_docker_files: bool = True,
    include_use_modules_hook: bool = True,
    include_frontend_infra_files: bool = True,
) -> Path:
    """Create a full project skeleton (like ``_write_project``) and set the given theme."""
    root = _write_project(
        root,
        slug=slug,
        package=package,
        marker=marker,
        modules=modules,
        path_dependencies=path_dependencies,
        include_docker_files=include_docker_files,
        include_use_modules_hook=include_use_modules_hook,
        include_frontend_infra_files=include_frontend_infra_files,
    )
    # Override quickscale.yml with the desired theme
    modules_block = ""
    if modules:
        module_lines = "\n".join(f"  {module}: {{}}" for module in modules)
        modules_block = f"modules:\n{module_lines}\n"
    quickscale_content = (
        'version: "1"\n'
        "project:\n"
        f"  slug: {slug}\n"
        f"  package: {package}\n"
        f"  theme: {theme}\n"
        f"{modules_block}"
        "docker:\n"
        "  start: false\n"
        "  build: false\n"
    )
    (root / "quickscale.yml").write_text(quickscale_content)
    return root


def _write_malformed_config_project(root: Path, *, slug: str, package: str) -> Path:
    """Create a full project skeleton and replace quickscale.yml with malformed YAML."""
    root = _write_project(
        root,
        slug=slug,
        package=package,
        marker="malformed",
    )
    (root / "quickscale.yml").write_text("{invalid: yaml: unquoted: yes")
    return root


def _assert_theme_preflight_blocks(
    report,
    *,
    donor_label: str = "donor",
    recipient_label: str = "recipient",
) -> None:
    """Assert that theme preflight blocked the migration with correct check records."""
    assert report.status == "blocked"
    # Must not have loaded any snapshots
    assert report.donor is None, (
        f"donor snapshot must be None when theme preflight blocks, got {report.donor}"
    )
    assert report.recipient is None, (
        f"recipient snapshot must be None when theme preflight blocks, got {report.recipient}"
    )
    # Must have preflight checks for the failing side(s)
    donor_failed = any(
        check.name == f"{donor_label}-theme-preflight" and check.status == "failed"
        for check in report.preflight_checks
    )
    recipient_failed = any(
        check.name == f"{recipient_label}-theme-preflight" and check.status == "failed"
        for check in report.preflight_checks
    )
    assert donor_failed or recipient_failed, (
        "Expected at least one theme preflight check to fail"
    )
    # No changed files
    assert report.changed_files == [], (
        f"No files should be changed: {report.changed_files}"
    )
    assert report.verification_results == [], (
        f"No verification should have run: {report.verification_results}"
    )


class TestRetiredThemeBlocksFreshFirst:
    """Retired ``showcase_html`` theme must block fresh-first preflight."""

    def test_donor_retired_blocks_plan(self, tmp_path: Path) -> None:
        """Retired theme on donor blocks fresh-first planning."""
        donor = _write_project_with_theme(
            tmp_path / "donor",
            slug="donor-app",
            package="donor_app",
            marker="donor",
            theme="showcase_html",
        )
        recipient = _write_project(
            tmp_path / "recipient",
            slug="recipient-app",
            package="recipient_app",
            marker="recipient",
        )
        report = plan_beta_migration(
            BetaMigrationInput(
                mode="fresh-first", donor=donor, recipient=recipient, dry_run=True
            )
        )
        _assert_theme_preflight_blocks(report, donor_label="donor")

    def test_recipient_retired_blocks_plan(self, tmp_path: Path) -> None:
        """Retired theme on recipient blocks fresh-first planning."""
        donor = _write_project(
            tmp_path / "donor", slug="donor-app", package="donor_app", marker="donor"
        )
        recipient = _write_project_with_theme(
            tmp_path / "recipient",
            slug="recipient-app",
            package="recipient_app",
            marker="recipient",
            theme="showcase_html",
        )
        report = plan_beta_migration(
            BetaMigrationInput(
                mode="fresh-first", donor=donor, recipient=recipient, dry_run=True
            )
        )
        _assert_theme_preflight_blocks(report, donor_label="recipient")

    def test_both_retired_both_reported(self, tmp_path: Path) -> None:
        """Both projects with retired theme should produce both failure checks."""
        donor = _write_project_with_theme(
            tmp_path / "donor",
            slug="donor-app",
            package="donor_app",
            marker="donor",
            theme="showcase_html",
        )
        recipient = _write_project_with_theme(
            tmp_path / "recipient",
            slug="recipient-app",
            package="recipient_app",
            marker="recipient",
            theme="showcase_html",
        )
        report = plan_beta_migration(
            BetaMigrationInput(
                mode="fresh-first", donor=donor, recipient=recipient, dry_run=True
            )
        )
        _assert_theme_preflight_blocks(report, donor_label="donor")
        # Both checks should be present
        donor_failed = any(
            check.name == "donor-theme-preflight" and check.status == "failed"
            for check in report.preflight_checks
        )
        recipient_failed = any(
            check.name == "recipient-theme-preflight" and check.status == "failed"
            for check in report.preflight_checks
        )
        assert donor_failed, "Donor theme preflight must also report failure"
        assert recipient_failed, "Recipient theme preflight must also report failure"

    def test_run_retired_donor_zero_side_effects(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Running migration with retired donor must block before any subprocess/mutation."""
        calls = _install_verification_success_stub(monkeypatch)
        donor = _write_project_with_theme(
            tmp_path / "donor",
            slug="donor-app",
            package="donor_app",
            marker="donor",
            theme="showcase_html",
        )
        recipient = _write_project(
            tmp_path / "recipient",
            slug="recipient-app",
            package="recipient_app",
            marker="recipient",
        )
        report = run_beta_migration(
            BetaMigrationInput(
                mode="fresh-first", donor=donor, recipient=recipient, dry_run=False
            )
        )
        _assert_theme_preflight_blocks(report, donor_label="donor")
        # Verify zero subprocess calls
        assert calls == [], f"No subprocess calls should have been made: {calls}"


class TestMalformedConfigBlocksFreshFirst:
    """Malformed quickscale.yml must block fresh-first preflight."""

    def test_donor_malformed_blocks_plan(self, tmp_path: Path) -> None:
        """Malformed donor config blocks fresh-first planning."""
        donor = _write_malformed_config_project(
            tmp_path / "donor", slug="donor-app", package="donor_app"
        )
        recipient = _write_project(
            tmp_path / "recipient",
            slug="recipient-app",
            package="recipient_app",
            marker="recipient",
        )
        report = plan_beta_migration(
            BetaMigrationInput(
                mode="fresh-first", donor=donor, recipient=recipient, dry_run=True
            )
        )
        _assert_theme_preflight_blocks(report, donor_label="donor")

    def test_recipient_malformed_blocks_plan(self, tmp_path: Path) -> None:
        """Malformed recipient config blocks fresh-first planning."""
        donor = _write_project(
            tmp_path / "donor", slug="donor-app", package="donor_app", marker="donor"
        )
        recipient = _write_malformed_config_project(
            tmp_path / "recipient", slug="recipient-app", package="recipient_app"
        )
        report = plan_beta_migration(
            BetaMigrationInput(
                mode="fresh-first", donor=donor, recipient=recipient, dry_run=True
            )
        )
        _assert_theme_preflight_blocks(report, donor_label="recipient")

    def test_run_malformed_donor_zero_side_effects(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Running migration with malformed donor must block before any subprocess/mutation."""
        calls = _install_verification_success_stub(monkeypatch)
        donor = _write_malformed_config_project(
            tmp_path / "donor", slug="donor-app", package="donor_app"
        )
        recipient = _write_project(
            tmp_path / "recipient",
            slug="recipient-app",
            package="recipient_app",
            marker="recipient",
        )
        report = run_beta_migration(
            BetaMigrationInput(
                mode="fresh-first", donor=donor, recipient=recipient, dry_run=False
            )
        )
        _assert_theme_preflight_blocks(report, donor_label="donor")
        assert calls == [], f"No subprocess calls should have been made: {calls}"


# SA62 regression: module-dependency-sync validated writer rejects invalid TOML
# ---------------------------------------------------------------------------


def test_module_dependency_sync_write_validated_toml_accepts_valid_content(
    tmp_path: Path,
) -> None:
    """The module-dependency-sync validated writer should accept valid TOML."""
    from quickscale_cli.utils._dependency_write import _write_validated_toml

    target = tmp_path / "pyproject.toml"
    valid_content = (
        "[tool.poetry.dependencies]\n"
        'python = "^3.14"\n'
        'quickscale-core = ">=0.86.0,<0.87.0"\n'
    )
    _write_validated_toml(target, valid_content)
    assert target.read_text() == valid_content


def test_module_dependency_sync_write_validated_toml_rejects_invalid_content(
    tmp_path: Path,
) -> None:
    """The module-dependency-sync validated writer must refuse to write TOML
    that does not parse, matching the sibling writers' existing test pattern.

    This is the regression guard for SA62: _patch_module_path_dependencies now
    routes through _write_validated_toml, so invalid splice output is rejected
    before touching disk — exactly like _append_dependency_entries and
    _update_dependency_entries.
    """
    from quickscale_cli.utils._dependency_io import DependencySyncError
    from quickscale_cli.utils._dependency_write import _write_validated_toml

    target = tmp_path / "pyproject.toml"
    # Unquoted version string is invalid TOML — same pattern as the existing
    # test_write_validated_toml_rejects_invalid_content sibling test.
    invalid = "[tool.poetry.dependencies]\npython = ^3.14\n"
    with pytest.raises(DependencySyncError, match="invalid TOML"):
        _write_validated_toml(target, invalid)
    assert not target.exists()


def test_patch_module_path_dependencies_replaces_path_with_version(
    tmp_path: Path,
) -> None:
    """SA62 regression: _patch_module_path_dependencies should replace non-existent
    path dependencies with version constraints from the module manifest when the
    splice produces valid TOML, exercising the validated-writer route."""
    from quickscale_cli.utils._dependency_write import _patch_module_path_dependencies

    project = tmp_path / "project"
    project.mkdir()
    module_dir = project / "modules" / "foo"
    module_dir.mkdir(parents=True)

    # Module pyproject.toml with a path dependency pointing to a non-existent
    # location — this triggers the patch check.
    (module_dir / "pyproject.toml").write_text(
        "[tool.poetry]\n"
        'name = "quickscale-module-foo"\n'
        'version = "0.1.0"\n'
        "\n"
        "[tool.poetry.dependencies]\n"
        'python = "^3.14"\n'
        'quickscale-core = {path = "../../nonexistent", develop = true}\n'
    )

    # Module manifest with a version constraint for the path dependency.
    (module_dir / "module.yml").write_text(
        'name: "quickscale-module-foo"\n'
        'version: "0.1.0"\n'
        "dependencies:\n"
        '  - "quickscale-core>=0.86.0,<0.87.0"\n'
    )

    _patch_module_path_dependencies(project, {"foo": None})

    updated = (module_dir / "pyproject.toml").read_text()
    # The path-style entry must be replaced with the version constraint.
    assert 'quickscale-core = ">=0.86.0,<0.87.0"' in updated
    # The original path syntax must be gone.
    assert '{path = "../../nonexistent", develop = true}' not in updated
    # The rewritten TOML must still parse as valid TOML.
    import tomllib

    tomllib.loads(updated)


def test_patch_module_path_dependencies_rejects_invalid_splice(
    tmp_path: Path,
) -> None:
    """SA62 regression: _patch_module_path_dependencies must refuse to write
    TOML when the line-level splice produces invalid content, protecting
    against silent data corruption before target-file mutation.

    The module.yml manifest carries a version spec with an embedded
    double-quote character that, after line-level splice, produces
    unparseable TOML.  _write_validated_toml catches the malformed
    document and raises DependencySyncError before anything touches disk.
    """
    from quickscale_cli.utils._dependency_io import DependencySyncError
    from quickscale_cli.utils._dependency_write import _patch_module_path_dependencies

    project = tmp_path / "project"
    project.mkdir()
    module_dir = project / "modules" / "foo"
    module_dir.mkdir(parents=True)

    module_pyproject = (
        "[tool.poetry]\n"
        'name = "quickscale-module-foo"\n'
        'version = "0.1.0"\n'
        "\n"
        "[tool.poetry.dependencies]\n"
        'python = "^3.14"\n'
        'quickscale-core = {path = "../../nonexistent", develop = true}\n'
    )
    pyproject_path = module_dir / "pyproject.toml"
    pyproject_path.write_text(module_pyproject)

    # Module manifest with a spec that contains a double-quote character.
    # After line-level splice: quickscale-core = "">=0.86.0,<0.87.0"
    # which is invalid TOML (empty string followed by garbage).
    (module_dir / "module.yml").write_text(
        'name: "quickscale-module-foo"\n'
        'version: "0.1.0"\n'
        "dependencies:\n"
        "  - 'quickscale-core\">=0.86.0,<0.87.0'\n"
    )

    with pytest.raises(DependencySyncError, match="invalid TOML"):
        _patch_module_path_dependencies(project, {"foo": None})

    # The file must not have been modified.
    assert pyproject_path.read_text() == module_pyproject


# ---------------------------------------------------------------------------
# SA191: the completed run writes the recipient handoff prompt
# ---------------------------------------------------------------------------

_HANDOFF_PROMPT_SNAPSHOT_PATH = Path(__file__).parent / "fixtures" / "handoff_prompt.md"


def _write_handoff_prompt_fixture(tmp_path: Path) -> tuple[Path, Path]:
    """Create the same-slug donor/recipient pair used by the handoff prompt tests."""
    donor = _write_project(
        tmp_path / "donor",
        slug="bap-web",
        package="bap_web",
        marker="donor",
        modules=("auth", "social"),
        path_dependencies=("quickscale-module-auth", "quickscale-module-social"),
    )
    recipient = _write_project(
        tmp_path / "recipient",
        slug="bap-web",
        package="bap_web",
        marker="recipient",
        modules=("auth",),
        path_dependencies=("quickscale-module-auth",),
    )
    (recipient / "modules" / "social").mkdir(parents=True)

    donor_package_dir = donor / "bap_web"
    (donor / "frontend" / "src" / "App.tsx").write_text(
        "export default function App() { return 'donor-app'; }\n"
    )
    (donor / "frontend" / "src" / "pages" / "About.tsx").write_text(
        "export default 'donor-about';\n"
    )
    (donor / "frontend" / "src" / "components" / "layout" / "Nav.tsx").write_text(
        "export default 'donor-layout';\n"
    )
    (donor / "frontend" / "src" / "assets").mkdir(parents=True, exist_ok=True)
    (donor / "frontend" / "src" / "assets" / "logo.txt").write_text("donor-logo\n")
    (recipient / "frontend" / "src" / "assets").mkdir(parents=True, exist_ok=True)
    (recipient / "frontend" / "src" / "assets" / "logo.txt").write_text(
        "recipient-logo\n"
    )
    (donor_package_dir / "urls.py").write_text("# donor-urls-marker\n")
    (donor_package_dir / "views.py").write_text("# donor-views-marker\n")
    (donor_package_dir / "context_processors.py").write_text(
        "# donor-context-processors-marker\n"
    )
    return donor, recipient


def test_run_fresh_first_writes_handoff_prompt_matching_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The completed run writes a snapshot-stable handoff prompt into the recipient."""
    donor, recipient = _write_handoff_prompt_fixture(tmp_path)
    _install_verification_success_stub(monkeypatch)

    report = run_beta_migration(
        BetaMigrationInput(
            mode="fresh-first",
            donor=donor,
            recipient=recipient,
            dry_run=False,
        )
    )

    assert report.status == "ready", report.blockers
    prompt_path = recipient / "MIGRATION_PROMPT.md"
    assert prompt_path.is_file()
    assert str(prompt_path) in report.changed_files
    assert any(step.step == "write-handoff-prompt" for step in report.completed_steps)

    actions = {action.action: action for action in report.pending_manual_actions}
    assert actions["run-local-smoke-checks"].paths == ["."]
    assert actions["set-module-env-vars"].paths == ["modules/auth"]
    assert all(action.rule for action in report.pending_manual_actions)

    rendered = prompt_path.read_text()
    assert str(recipient) not in rendered
    normalized = rendered.replace(str(donor), "<DONOR>")
    assert normalized == _HANDOFF_PROMPT_SNAPSHOT_PATH.read_text()


def test_handoff_prompt_requires_completed_execution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Dry-run and partial runs must not write the recipient handoff prompt."""
    donor = _write_project(
        tmp_path / "donor",
        slug="beta-site",
        package="beta_site",
        marker="donor",
    )
    recipient = _write_project(
        tmp_path / "recipient",
        slug="beta-site",
        package="beta_site",
        marker="recipient",
    )
    prompt_path = recipient / "MIGRATION_PROMPT.md"

    dry_run_report = run_beta_migration(
        BetaMigrationInput(
            mode="fresh-first",
            donor=donor,
            recipient=recipient,
            dry_run=True,
        )
    )
    assert dry_run_report.status == "ready", dry_run_report.blockers
    assert not prompt_path.exists()

    def failing_verification(command, **kwargs):
        return subprocess.CompletedProcess(
            tuple(command), 1, stdout="nonzero stdout", stderr="nonzero stderr"
        )

    monkeypatch.setattr(subprocess, "run", failing_verification)
    partial_report = run_beta_migration(
        BetaMigrationInput(
            mode="fresh-first",
            donor=donor,
            recipient=recipient,
            dry_run=False,
        )
    )

    assert partial_report.status == "blocked"
    assert partial_report.phase == "fresh-first-partial"
    assert not prompt_path.exists()
    assert any(
        step.step == "write-handoff-prompt" for step in partial_report.skipped_steps
    )


@pytest.mark.parametrize("link_kind", ["symlink", "hardlink"])
def test_handoff_prompt_write_does_not_reach_a_linked_target(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    link_kind: str,
) -> None:
    """An existing prompt link must be replaced, never written through."""
    donor = _write_project(
        tmp_path / "donor",
        slug="beta-site",
        package="beta_site",
        marker="donor",
    )
    recipient = _write_project(
        tmp_path / "recipient",
        slug="beta-site",
        package="beta_site",
        marker="recipient",
    )
    donor_target = donor / "frontend" / "notes.txt"
    donor_target.write_text("donor-owned\n")
    prompt_path = recipient / "MIGRATION_PROMPT.md"
    if link_kind == "symlink":
        prompt_path.symlink_to(donor_target)
    else:
        os.link(donor_target, prompt_path)

    _install_verification_success_stub(monkeypatch)
    report = run_beta_migration(
        BetaMigrationInput(
            mode="fresh-first",
            donor=donor,
            recipient=recipient,
            dry_run=False,
        )
    )

    assert report.status == "ready", report.blockers
    assert donor_target.read_text() == "donor-owned\n"
    assert not prompt_path.is_symlink()
    assert prompt_path.stat().st_nlink == 1
    assert "## Remaining work" in prompt_path.read_text()


def test_handoff_prompt_never_claims_readiness_when_report_write_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failed CLI report write must not leave the prompt claiming readiness."""
    donor = _write_project(
        tmp_path / "donor",
        slug="beta-site",
        package="beta_site",
        marker="donor",
    )
    recipient = _write_project(
        tmp_path / "recipient",
        slug="beta-site",
        package="beta_site",
        marker="recipient",
    )
    _install_verification_success_stub(monkeypatch)
    stdout = io.StringIO()

    exit_code = run_beta_migration_cli(
        [
            "fresh-first",
            "--donor",
            str(donor),
            "--recipient",
            str(recipient),
            # A directory cannot receive the JSON report, so the CLI fails closed
            # after the execution phase already wrote the recipient prompt.
            "--report-path",
            str(recipient),
        ],
        stdout=stdout,
    )

    assert exit_code == 1
    _summary, json_payload = stdout.getvalue().strip().split("\n\n", maxsplit=1)
    parsed = json.loads(json_payload)
    assert parsed["status"] == "blocked"
    assert any("Failed to write report" in blocker for blocker in parsed["blockers"])

    prompt_text = (recipient / "MIGRATION_PROMPT.md").read_text()
    assert "## Remaining work" in prompt_text
    assert "- Status: ready" not in prompt_text
