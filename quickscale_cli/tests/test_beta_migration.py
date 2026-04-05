"""Tests for beta migration maintainer tooling."""

import io
import json
import subprocess
from pathlib import Path

import pytest
import quickscale_cli.schema as schema_module

from quickscale_cli.beta_migration import (
    BetaMigrationInput,
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
        "import os\n"
        f'os.environ.setdefault("DJANGO_SETTINGS_MODULE", "{package}.settings.production")\n'
        f"# {marker}-asgi-marker {slug}\n"
    )
    (package_dir / "wsgi.py").write_text(
        "import os\n"
        f'os.environ.setdefault("DJANGO_SETTINGS_MODULE", "{package}.settings.production")\n'
        f"# {marker}-wsgi-marker {slug}\n"
    )
    (settings_dir / "__init__.py").write_text(f"# {marker}-settings-init-marker\n")
    (settings_dir / "modules.py").write_text(
        f"# {marker}-modules-marker\nMODULE_INSTALLED_APPS = []\nMODULE_MIDDLEWARE = []\nMODULE_SETTINGS = {{}}\n"
    )
    (settings_dir / "base.py").write_text(
        f'"""{marker}-base-marker {slug}"""\n'
        f'ROOT_URLCONF = "{package}.urls"\n'
        f'CONTEXT_PROCESSOR = "{package}.context_processors.project_settings"\n'
        f'WSGI_APPLICATION = "{package}.wsgi.application"\n'
        f'DATABASE_NAME = "{package}"\n'
        f'LOGGER = "{package}"\n'
    )
    (settings_dir / "local.py").write_text(
        f'"""{marker}-local-marker {slug}"""\nLOGGER = "{package}"\n'
    )
    (settings_dir / "production.py").write_text(
        f'"""{marker}-production-marker {slug}"""\n'
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

    if include_use_modules_hook:
        (frontend_src / "hooks").mkdir(parents=True, exist_ok=True)
        (frontend_src / "hooks" / "useModules.ts").write_text(
            f"export const projectConfig = {{ projectName: '{slug}' }}; // {marker}-hook-marker\n"
        )

    if include_docker_files:
        (root / "Dockerfile").write_text(
            "FROM python:3.14-slim-bookworm\n"
            f"ENV DJANGO_SETTINGS_MODULE={package}.settings.production\n"
            f"# {marker}-docker-marker {slug}\n"
        )
        (root / "docker-compose.yml").write_text(
            "services:\n"
            f"  backend:\n    container_name: {slug}_backend\n"
            "    environment:\n"
            f"      - DJANGO_SETTINGS_MODULE={package}.settings.local\n"
            f"      - DATABASE_URL=postgresql://postgres:postgres@db:5432/{package}\n"
            f"# {marker}-compose-marker\n"
        )

    return root


def _init_clean_git_repo(path: Path) -> None:
    subprocess.run(
        ["git", "init"], cwd=path, check=True, capture_output=True, text=True
    )
    subprocess.run(
        ["git", "config", "user.email", "quickscale-tests@example.com"],
        cwd=path,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "QuickScale Tests"],
        cwd=path,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "add", "."], cwd=path, check=True, capture_output=True, text=True
    )
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=path,
        check=True,
        capture_output=True,
        text=True,
    )


def _install_verification_success_stub(
    monkeypatch: pytest.MonkeyPatch,
) -> list[tuple[tuple[str, ...], Path]]:
    calls: list[tuple[tuple[str, ...], Path]] = []

    def fake_run(command, cwd=None, **kwargs):
        command_tuple = tuple(command)
        call_cwd = Path(cwd) if cwd is not None else Path.cwd()
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


def test_parse_cli_args_supports_modes_and_optional_flags(tmp_path: Path) -> None:
    """Argument parsing should preserve both modes and optional report flags."""
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
    assert report.changed_files == []
    assert any(
        action.step == "sync-missing-path-dependencies"
        for action in report.planned_actions
    )
    assert any(
        step.step == "perform-fresh-first-file-copy-sequence"
        for step in report.skipped_steps
    )


def test_in_place_clean_git_worktree_yields_checkpoint_report(tmp_path: Path) -> None:
    """In-place planning should require a clean git worktree and then stop at the checkpoint."""
    donor = _write_project(
        tmp_path / "donor",
        slug="fresh-donor",
        package="fresh_donor",
        marker="donor",
        modules=("auth", "social"),
    )
    recipient = _write_project(
        tmp_path / "recipient",
        slug="beta-site",
        package="beta_site",
        marker="recipient",
        modules=("auth",),
    )
    _init_clean_git_repo(recipient)

    report = plan_beta_migration(
        BetaMigrationInput(
            mode="in-place",
            donor=donor,
            recipient=recipient,
            dry_run=False,
        )
    )

    assert report.status == "checkpoint"
    assert report.module_diff is not None
    assert report.module_diff.donor_only == ["social"]
    assert any(
        check.name == "recipient-clean-git-worktree" and check.status == "passed"
        for check in report.preflight_checks
    )
    assert any(
        action.step == "pre-apply-review-checkpoint"
        for action in report.planned_actions
    )


def test_in_place_dirty_git_worktree_blocks(tmp_path: Path) -> None:
    """Dirty in-place recipients should fail the clean-git preflight check."""
    donor = _write_project(
        tmp_path / "donor",
        slug="fresh-donor",
        package="fresh_donor",
        marker="donor",
        modules=("auth",),
    )
    recipient = _write_project(
        tmp_path / "recipient",
        slug="beta-site",
        package="beta_site",
        marker="recipient",
        modules=("auth",),
    )
    _init_clean_git_repo(recipient)
    (recipient / "quickscale.yml").write_text(
        (recipient / "quickscale.yml").read_text() + "# dirty\n"
    )

    report = plan_beta_migration(
        BetaMigrationInput(
            mode="in-place",
            donor=donor,
            recipient=recipient,
            dry_run=False,
        )
    )

    assert report.status == "blocked"
    assert any("not clean" in blocker for blocker in report.blockers)
    assert any(
        check.name == "recipient-clean-git-worktree" and check.status == "failed"
        for check in report.preflight_checks
    )


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
    (donor_package_dir / "settings" / "production.py").write_text(
        '"""donor-production-marker experto-ai-web"""\n'
        'DEFAULT_FROM_EMAIL = "noreply@experto-ai-web.com"\n'
        'LOGGER = "experto_ai_web"\n'
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
    assert report.phase == "fresh-first-executed"
    assert report.identity_reconciliation_required is True
    _assert_verification_report(report, recipient, calls)

    new_package_dir = recipient / "experto_ai_web"
    assert new_package_dir.is_dir()
    assert not recipient_package_dir.exists()
    assert report.recipient is not None
    assert report.recipient.identity.slug == "experto-ai-web"
    assert report.recipient.identity.package == "experto_ai_web"

    quickscale_text = (recipient / "quickscale.yml").read_text()
    assert "slug: experto-ai-web" in quickscale_text
    assert "package: experto_ai_web" in quickscale_text

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
    (donor_package_dir / "settings" / "production.py").write_text(
        '"""donor-production-marker bap-web"""\n'
        'DEFAULT_FROM_EMAIL = "noreply@bap-web.com"\n'
        'LOGGER = "bap_web"\n'
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
    parsed_stdout_json = json.loads(json_payload)
    assert parsed_stdout_json["mode"] == "fresh-first"
    assert report_path.exists()
    parsed_file_json = json.loads(report_path.read_text())
    assert parsed_file_json["written_report_path"] == str(report_path.resolve())
