"""Tests for beta migration maintainer tooling."""

import io
import json
import subprocess
from pathlib import Path

import pytest
import quickscale_core.schema as schema_module

from quickscale_devtools.beta_migration import (
    BetaMigrationInput,
    _insert_missing_path_dependencies,
    _locate_toml_section_bounds,
    _replace_toml_section,
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


def _install_in_place_success_stub(
    monkeypatch: pytest.MonkeyPatch,
    *,
    recipient: Path,
    package: str,
) -> list[tuple[tuple[str, ...], Path]]:
    calls: list[tuple[tuple[str, ...], Path]] = []
    original_run = subprocess.run

    def fake_run(command, cwd=None, **kwargs):
        command_tuple = tuple(command)
        call_cwd = Path(cwd) if cwd is not None else Path.cwd()

        if (
            len(command_tuple) >= 3
            and command_tuple[0] == "git"
            and command_tuple[1] == "-C"
        ):
            return original_run(command, cwd=cwd, **kwargs)

        if command_tuple == ("quickscale", "apply"):
            pyproject_path = recipient / "pyproject.toml"
            pyproject_text = pyproject_path.read_text()
            new_dependency_lines = (
                'quickscale-module-forms = {path = "./modules/forms", develop = true}\n'
                'quickscale-module-social = {path = "./modules/social", develop = true}\n\n'
            )
            if (
                'quickscale-module-forms = {path = "./modules/forms", develop = true}'
                not in pyproject_text
            ):
                pyproject_path.write_text(
                    pyproject_text.replace(
                        "[tool.poetry.group.dev.dependencies]\n",
                        new_dependency_lines + "[tool.poetry.group.dev.dependencies]\n",
                    )
                )

            (recipient / ".quickscale").mkdir(exist_ok=True)
            (recipient / ".quickscale" / "state.yml").write_text("applied: true\n")
            (recipient / "modules" / "forms").mkdir(parents=True, exist_ok=True)
            (recipient / "modules" / "social").mkdir(parents=True, exist_ok=True)
            (recipient / "modules" / "forms" / "README.md").write_text("forms module\n")
            (recipient / "modules" / "social" / "README.md").write_text(
                "social module\n"
            )
            settings_modules_path = recipient / package / "settings" / "modules.py"
            settings_modules_path.write_text(
                settings_modules_path.read_text() + "FORMS = True\nSOCIAL = True\n"
            )
            return subprocess.CompletedProcess(
                command_tuple,
                0,
                stdout="stdout:quickscale apply",
                stderr="stderr:quickscale apply",
            )

        if command_tuple in [
            argv for argv, _display, _cwd_suffix in EXPECTED_VERIFICATION_SEQUENCE
        ]:
            calls.append((command_tuple, call_cwd))
            joined = " ".join(command_tuple)
            return subprocess.CompletedProcess(
                command_tuple,
                0,
                stdout=f"stdout:{joined}",
                stderr=f"stderr:{joined}",
            )

        return original_run(command, cwd=cwd, **kwargs)

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


def test_parse_cli_args_supports_in_place_continuation_flag(tmp_path: Path) -> None:
    """In-place parsing should expose the explicit continuation opt-in."""
    donor = tmp_path / "donor"
    recipient = tmp_path / "recipient"

    parsed = parse_cli_args(
        [
            "in-place",
            "--donor",
            str(donor),
            "--recipient",
            str(recipient),
            "--continue-after-checkpoint",
        ]
    )

    assert parsed.mode == "in-place"
    assert parsed.continue_after_checkpoint is True
    assert parsed.dry_run is False


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


def test_run_in_place_without_continuation_keeps_checkpoint_default(
    tmp_path: Path,
) -> None:
    """The in-place run path should stay checkpoint-only unless continuation is explicit."""
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

    original_quickscale = (recipient / "quickscale.yml").read_text()
    report = run_beta_migration(
        BetaMigrationInput(
            mode="in-place",
            donor=donor,
            recipient=recipient,
            dry_run=False,
        )
    )

    assert report.status == "checkpoint"
    assert report.phase == "in-place-checkpoint"
    assert report.changed_files == []
    assert report.verification_results == []
    assert (recipient / "quickscale.yml").read_text() == original_quickscale
    assert any(
        action.action == "run-in-place-continuation-later"
        for action in report.pending_manual_actions
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


def test_run_in_place_with_continuation_executes_apply_and_verification(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Explicit in-place continuation should merge, apply, adopt missing surfaces, and verify."""
    donor = _write_project(
        tmp_path / "donor",
        slug="fresh-donor",
        package="fresh_donor",
        marker="donor",
        modules=("auth", "forms", "social"),
        path_dependencies=(
            "quickscale-module-auth",
            "quickscale-module-forms",
            "quickscale-module-social",
        ),
    )
    recipient = _write_project(
        tmp_path / "recipient",
        slug="beta-site",
        package="beta_site",
        marker="recipient",
        modules=("auth",),
        path_dependencies=("quickscale-module-auth",),
    )

    donor_pyproject = donor / "pyproject.toml"
    donor_pyproject.write_text(
        donor_pyproject.read_text().replace(
            'Django = ">=6.0.3,<7.0.0"\n',
            'Django = ">=6.1.0,<7.0.0"\ndjango-markdownx = "^4.0.7"\n',
        )
    )

    donor_package_json_path = donor / "frontend" / "package.json"
    donor_package_json = json.loads(donor_package_json_path.read_text())
    donor_package_json["scripts"] = {"build": "vite build", "test": "vitest run"}
    donor_package_json["dependencies"] = {"react": "^19.0.0"}
    donor_package_json_path.write_text(json.dumps(donor_package_json, indent=2) + "\n")

    (donor / "frontend" / "src" / "pages" / "FormsPage.tsx").write_text(
        "export default 'donor-forms';\n"
    )
    (recipient / "frontend" / "src" / "pages" / "FormsPage.tsx").write_text(
        "export default 'recipient-forms';\n"
    )
    (donor / "frontend" / "src" / "pages" / "SocialLinkTreePublicPage.tsx").write_text(
        "export default 'donor-link-tree';\n"
    )
    (donor / "frontend" / "src" / "pages" / "SocialEmbedsPublicPage.tsx").write_text(
        "export default 'donor-embeds';\n"
    )
    (donor / "frontend" / "src" / "components" / "social").mkdir(
        parents=True, exist_ok=True
    )
    (recipient / "frontend" / "src" / "components" / "social").mkdir(
        parents=True, exist_ok=True
    )
    (
        donor / "frontend" / "src" / "components" / "social" / "PublicSocialShell.tsx"
    ).write_text("export default 'donor-social-shell';\n")
    (
        recipient / "frontend" / "src" / "components" / "social" / "ExistingBadge.tsx"
    ).write_text("export default 'recipient-existing-social';\n")
    (donor / "frontend" / "src" / "hooks" / "usePublicSocialSurface.ts").write_text(
        "export const marker = 'donor-public-social-hook'\n"
    )

    # Create donor start.sh with donor's package reference for SA66
    # identity-substitution regression coverage
    (donor / "start.sh").write_text(
        "#!/usr/bin/env bash\nexec gunicorn fresh_donor.wsgi:application\n"
    )

    _init_clean_git_repo(recipient)

    calls = _install_in_place_success_stub(
        monkeypatch,
        recipient=recipient,
        package="beta_site",
    )
    report = run_beta_migration(
        BetaMigrationInput(
            mode="in-place",
            donor=donor,
            recipient=recipient,
            dry_run=False,
            continue_after_checkpoint=True,
        )
    )

    assert report.status == "ready"
    assert report.phase == "in-place-executed"
    _assert_verification_report(report, recipient, calls)

    quickscale_text = (recipient / "quickscale.yml").read_text()
    assert "forms:" in quickscale_text
    assert "social:" in quickscale_text

    dockerfile_text = (recipient / "Dockerfile").read_text()
    assert "donor-docker-marker" in dockerfile_text
    assert "beta_site.settings.production" in dockerfile_text
    assert "fresh_donor.settings.production" not in dockerfile_text

    compose_text = (recipient / "docker-compose.yml").read_text()
    assert "donor-compose-marker" in compose_text
    assert "beta-site_backend" in compose_text
    assert (
        "DATABASE_URL=postgresql://postgres:postgres@db:5432/beta_site" in compose_text
    )

    hook_text = (recipient / "frontend" / "src" / "hooks" / "useModules.ts").read_text()
    assert "projectName: 'beta-site'" in hook_text
    assert "donor-hook-marker" in hook_text

    # SA66 regression — start.sh must be identity-substituted during in-place
    # migration when donor and recipient have different package names.
    # Without substitution the copied start.sh would retain the donor's
    # gunicorn package reference.
    start_sh_text = (recipient / "start.sh").read_text()
    assert "beta_site" in start_sh_text, (
        "start.sh must contain recipient package beta_site after identity substitution"
    )
    assert "fresh_donor" not in start_sh_text, (
        "start.sh must not contain donor package fresh_donor after identity substitution"
    )
    # Verify the WSGI and Gunicorn module references use the recipient package
    assert "beta_site.wsgi" in start_sh_text
    assert "fresh_donor.wsgi" not in start_sh_text

    assert (
        "donor-pre-commit-marker" in (recipient / ".pre-commit-config.yaml").read_text()
    )
    assert (
        "donor-vite-marker" in (recipient / "frontend" / "vite.config.ts").read_text()
    )
    assert (
        "donor-eslint-marker"
        in (recipient / "frontend" / "eslint.config.js").read_text()
    )
    assert (
        "donor-postcss-marker"
        in (recipient / "frontend" / "postcss.config.js").read_text()
    )
    assert (
        "donor-prettier-marker"
        in (recipient / "frontend" / "prettier.config.js").read_text()
    )

    pyproject_text = (recipient / "pyproject.toml").read_text()
    assert 'Django = ">=6.1.0,<7.0.0"' in pyproject_text
    assert 'django-markdownx = "^4.0.7"' in pyproject_text
    assert (
        'quickscale-module-auth = {path = "./modules/auth", develop = true}'
        in pyproject_text
    )
    assert (
        'quickscale-module-forms = {path = "./modules/forms", develop = true}'
        in pyproject_text
    )
    assert (
        'quickscale-module-social = {path = "./modules/social", develop = true}'
        in pyproject_text
    )
    assert 'DJANGO_SETTINGS_MODULE = "beta_site.settings.local"' in pyproject_text

    package_json = json.loads((recipient / "frontend" / "package.json").read_text())
    assert package_json["name"] == "beta-site"
    assert package_json["scripts"] == {
        "build": "vite build",
        "test": "vitest run",
    }
    assert package_json["dependencies"] == {"react": "^19.0.0"}

    assert (
        "recipient-forms"
        in (recipient / "frontend" / "src" / "pages" / "FormsPage.tsx").read_text()
    )
    assert (
        "donor-link-tree"
        in (
            recipient / "frontend" / "src" / "pages" / "SocialLinkTreePublicPage.tsx"
        ).read_text()
    )
    assert (
        "donor-embeds"
        in (
            recipient / "frontend" / "src" / "pages" / "SocialEmbedsPublicPage.tsx"
        ).read_text()
    )
    assert (
        "recipient-existing-social"
        in (
            recipient
            / "frontend"
            / "src"
            / "components"
            / "social"
            / "ExistingBadge.tsx"
        ).read_text()
    )
    assert (
        "donor-social-shell"
        in (
            recipient
            / "frontend"
            / "src"
            / "components"
            / "social"
            / "PublicSocialShell.tsx"
        ).read_text()
    )
    assert (
        "donor-public-social-hook"
        in (
            recipient / "frontend" / "src" / "hooks" / "usePublicSocialSurface.ts"
        ).read_text()
    )

    assert (recipient / ".quickscale" / "state.yml").exists()
    assert any(path.endswith(".quickscale/state.yml") for path in report.changed_files)
    assert any(
        path.endswith("frontend/src/pages/SocialLinkTreePublicPage.tsx")
        for path in report.changed_files
    )
    assert any(
        action.action == "review-user-owned-react-routing"
        for action in report.pending_manual_actions
    )
    assert any(
        action.action == "run-local-smoke-checks"
        for action in report.pending_manual_actions
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


def test_replace_toml_section_refuses_child_array_of_tables(
    tmp_path: Path,
) -> None:
    """Replacing a section with nested [[child]] blocks must fail explicitly.

    The guard-fail strategy prevents silent data loss: the replacement body
    cannot represent the child array-of-tables, so the call must refuse
    rather than silently dropping the nested block.
    """
    target = tmp_path / "pyproject.toml"
    target.write_text(_PYPROJECT_WITH_ARRAY_OF_TABLES)

    with pytest.raises(ValueError, match="nested child block"):
        _replace_toml_section(
            target,
            "tool.poetry.dependencies",
            ['python = "^3.14"', 'Django = ">=6.0.3,<7.0.0"'],
        )
    # The file must not have been modified.
    assert target.read_text() == _PYPROJECT_WITH_ARRAY_OF_TABLES


def test_replace_toml_section_refuses_nested_child_table(
    tmp_path: Path,
) -> None:
    """Replacing a section with nested [parent.child] blocks must fail explicitly.

    The guard-fail strategy prevents silent data loss: the replacement body
    cannot represent the child table, so the call must refuse rather than
    silently dropping the nested block.
    """
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

    with pytest.raises(ValueError, match="nested child block"):
        _replace_toml_section(
            target,
            "tool.poetry.dependencies",
            ['python = "^3.14"', 'Django = ">=6.0.3,<7.0.0"'],
        )
    # The file must not have been modified.
    assert target.read_text() == document


def test_replace_toml_section_returns_false_when_unchanged(tmp_path: Path) -> None:
    """Replacing a section with the same body should not signal a change."""
    document = (
        "[tool.poetry]\n"
        'name = "demo"\n'
        "\n"
        "[tool.poetry.dependencies]\n"
        'python = "^3.14"\n'
        "\n"
        "[tool.poetry.group.dev.dependencies]\n"
        'pytest = "^9.0.0"\n'
    )
    target = tmp_path / "pyproject.toml"
    target.write_text(document)

    # First call: the body differs from the new content.
    changed = _replace_toml_section(
        target,
        "tool.poetry.dependencies",
        ['python = "^3.14"', 'Django = ">=6.0.3,<7.0.0"'],
    )
    assert changed is True
    rewritten = target.read_text()

    # Second call with the same new content on the already-rewritten file:
    # the body already matches, so no change is reported.
    changed_again = _replace_toml_section(
        target,
        "tool.poetry.dependencies",
        ['python = "^3.14"', 'Django = ">=6.0.3,<7.0.0"'],
    )
    assert changed_again is False
    assert target.read_text() == rewritten


def test_replace_toml_section_raises_when_section_missing(tmp_path: Path) -> None:
    """A missing target section should raise a clear error."""
    target = tmp_path / "pyproject.toml"
    target.write_text("[tool.poetry]\nname = 'demo'\n")
    with pytest.raises(ValueError, match="Unable to locate"):
        _replace_toml_section(target, "tool.poetry.dependencies", ['python = "^3.14"'])


def test_replace_toml_section_preserves_sibling_array_of_tables(
    tmp_path: Path,
) -> None:
    """A sibling [[tool.poetry.source]] must survive a section replacement.

    This is a realistic regression case: pyproject.toml files with
    ``[[tool.poetry.source]]`` entries should be replaceable for the
    ``tool.poetry.dependencies`` section without losing the source block.
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
    target = tmp_path / "pyproject.toml"
    target.write_text(document)

    changed = _replace_toml_section(
        target,
        "tool.poetry.dependencies",
        ['python = "^3.14"', 'Django = ">=6.0.3,<7.0.0"'],
    )

    assert changed is True
    updated = target.read_text()
    # The new body is present.
    assert 'python = "^3.14"' in updated
    assert 'Django = ">=6.0.3,<7.0.0"' in updated
    # The sibling [[tool.poetry.source]] block is preserved intact.
    assert "[[tool.poetry.source]]" in updated
    assert 'name = "private"' in updated
    assert 'url = "https://example.com/simple"' in updated
    # The subsequent section is preserved.
    assert "[tool.poetry.group.dev.dependencies]" in updated


def test_insert_missing_path_dependencies_inserts_after_array_of_tables(
    tmp_path: Path,
) -> None:
    """The new dependency is appended to the body, after any [[...]] content.

    The boundary detection treats [[...]] headers as part of the body, so
    insertion lands at the end of the body, which is after the [[...]] block.
    The [[...]] declaration itself is still present because insertion only
    adds lines; it does not replace existing content.
    """
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
    # The new dependency is appended AFTER the [[...]] block contents.
    extra_idx = updated.index("[[tool.poetry.dependencies.quickscale-module-extra]]")
    new_dep_idx = updated.index("quickscale-module-blog")
    assert new_dep_idx > extra_idx
    # Sibling sections remain after the rewritten body.
    assert "[tool.poetry.group.dev.dependencies]" in updated
    assert "[tool.pytest.ini_options]" in updated


def test_insert_missing_path_dependencies_inserts_after_nested_tables(
    tmp_path: Path,
) -> None:
    """The new dependency is appended after any nested-table content.

    The boundary detection treats ``[parent.child]`` (a strict child of the
    current section) as part of the body, so insertion lands at the end of
    the body, which is after the nested table's contents.
    """
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
    # The new entry is present and was inserted after the nested-table content.
    new_dep_idx = updated.index("quickscale-module-blog")
    nested_idx = updated.index('default = {url = "https://pypi.org/simple"}')
    assert new_dep_idx > nested_idx
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


# ---------------------------------------------------------------------------
# Higher-fidelity integration test: TOML rewrite + managed apply handoff
# ---------------------------------------------------------------------------


_REALISTIC_RECIPIENT_PYPROJECT = (
    "[tool.poetry]\n"
    'name = "beta-site"\n'
    'version = "0.1.0"\n'
    'packages = [{include = "beta_site"}]\n'
    "\n"
    "[tool.poetry.dependencies]\n"
    'python = "^3.14"\n'
    'Django = ">=6.0.3,<7.0.0"\n'
    'django-filter = "^24.0"\n'
    'quickscale-module-auth = {path = "./modules/auth", develop = true}\n'
    "\n"
    "[[tool.poetry.source]]\n"
    'name = "private"\n'
    'url = "https://example.com/simple"\n'
    'priority = "primary"\n'
    "\n"
    "[[tool.poetry.source]]\n"
    'name = "backup"\n'
    'url = "https://backup.example.com/simple"\n'
    'priority = "supplemental"\n'
    "\n"
    "[tool.poetry.group.dev.dependencies]\n"
    'pytest = "^9.0.0"\n'
    'ruff = "^0.8.0"\n'
    "\n"
    "[tool.pytest.ini_options]\n"
    'DJANGO_SETTINGS_MODULE = "beta_site.settings.local"\n'
    'python_files = ["tests.py", "test_*.py"]\n'
    "\n"
    "[tool.ruff]\n"
    "line-length = 100\n"
)


def test_run_in_place_with_continuation_preserves_sibling_sources_and_applies(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """In-place continuation with a realistic pyproject.toml should preserve sibling
    ``[[tool.poetry.source]]`` blocks and later sections through the TOML rewrite,
    and should still execute the managed apply handoff.

    This test uses the existing monkeypatched subprocess harness rather than a
    full end-to-end ``quickscale apply``, but it exercises the real
    ``run_beta_migration`` in-place path end-to-end including the tightened
    ``_locate_toml_section_bounds`` and ``_replace_toml_section`` helpers
    together with the apply handoff seam.
    """
    donor = _write_project(
        tmp_path / "donor",
        slug="fresh-donor",
        package="fresh_donor",
        marker="donor",
        modules=("auth", "forms", "social"),
        path_dependencies=(
            "quickscale-module-auth",
            "quickscale-module-forms",
            "quickscale-module-social",
        ),
    )
    recipient = _write_project(
        tmp_path / "recipient",
        slug="beta-site",
        package="beta_site",
        marker="recipient",
        modules=("auth",),
        path_dependencies=("quickscale-module-auth",),
    )

    # Give the donor a different non-path dependency set so the merge step
    # triggers a real _replace_toml_section rewrite on the recipient.
    donor_pyproject = donor / "pyproject.toml"
    donor_pyproject.write_text(
        donor_pyproject.read_text().replace(
            'Django = ">=6.0.3,<7.0.0"\n',
            'Django = ">=6.1.0,<7.0.0"\ndjango-markdownx = "^4.0.7"\n',
        )
    )

    # Replace the recipient pyproject.toml with a realistic layout that
    # includes sibling [[tool.poetry.source]] blocks and later tool sections.
    (recipient / "pyproject.toml").write_text(_REALISTIC_RECIPIENT_PYPROJECT)

    _init_clean_git_repo(recipient)

    calls = _install_in_place_success_stub(
        monkeypatch,
        recipient=recipient,
        package="beta_site",
    )
    report = run_beta_migration(
        BetaMigrationInput(
            mode="in-place",
            donor=donor,
            recipient=recipient,
            dry_run=False,
            continue_after_checkpoint=True,
        )
    )

    # --- Report-level assertions ---
    assert report.status == "ready"
    assert report.phase == "in-place-executed"
    _assert_verification_report(report, recipient, calls)

    # --- Managed apply handoff ---
    # The stub intercepts "quickscale apply" and creates .quickscale/state.yml,
    # so its presence proves the apply handoff executed.
    assert (recipient / ".quickscale" / "state.yml").exists()
    assert any(step.step == "run-quickscale-apply" for step in report.completed_steps)

    # --- TOML rewrite survival assertions ---
    pyproject_text = (recipient / "pyproject.toml").read_text()

    # The merged non-path dependencies from the donor are present.
    assert 'Django = ">=6.1.0,<7.0.0"' in pyproject_text
    assert 'django-markdownx = "^4.0.7"' in pyproject_text

    # The recipient's path dependency survived the merge.
    assert (
        'quickscale-module-auth = {path = "./modules/auth", develop = true}'
        in pyproject_text
    )

    # Both sibling [[tool.poetry.source]] blocks survived the rewrite intact.
    assert "[[tool.poetry.source]]" in pyproject_text
    assert 'name = "private"' in pyproject_text
    assert 'url = "https://example.com/simple"' in pyproject_text
    assert 'priority = "primary"' in pyproject_text
    assert 'name = "backup"' in pyproject_text
    assert 'url = "https://backup.example.com/simple"' in pyproject_text
    assert 'priority = "supplemental"' in pyproject_text

    # The later [tool.poetry.group.dev.dependencies] section survived.
    assert "[tool.poetry.group.dev.dependencies]" in pyproject_text
    assert 'pytest = "^9.0.0"' in pyproject_text
    assert 'ruff = "^0.8.0"' in pyproject_text

    # The [tool.pytest.ini_options] section survived with its content.
    assert "[tool.pytest.ini_options]" in pyproject_text
    assert 'DJANGO_SETTINGS_MODULE = "beta_site.settings.local"' in pyproject_text
    assert 'python_files = ["tests.py", "test_*.py"]' in pyproject_text

    # The [tool.ruff] section survived.
    assert "[tool.ruff]" in pyproject_text
    assert "line-length = 100" in pyproject_text

    # The rewritten TOML must still parse as valid TOML.
    import tomllib

    parsed = tomllib.loads(pyproject_text)
    sources = parsed["tool"]["poetry"]["source"]
    assert len(sources) == 2
    assert sources[0]["name"] == "private"
    assert sources[1]["name"] == "backup"
    assert parsed["tool"]["pytest"]["ini_options"]["DJANGO_SETTINGS_MODULE"] == (
        "beta_site.settings.local"
    )
    assert parsed["tool"]["ruff"]["line-length"] == 100


# ---------------------------------------------------------------------------
# Regression tests: recipient-only non-path dependency visibility and
# subprocess timeout hardening (Phase 3 roadmap items)
# ---------------------------------------------------------------------------


def test_in_place_merge_drops_and_surfaces_recipient_only_non_path_dependencies(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Recipient-only non-path dependencies must be dropped deliberately and surfaced in the report.

    The donor-authoritative merge contract replaces the recipient non-path
    dependency set with the donor's.  Recipient-only non-path dependencies
    are intentionally dropped; the step detail must name them so the
    maintainer can review the drop in the report rather than discovering it
    silently after the fact.
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

    # Give the recipient a non-path dependency that the donor does not have.
    recipient_pyproject = recipient / "pyproject.toml"
    recipient_pyproject.write_text(
        recipient_pyproject.read_text().replace(
            'Django = ">=6.0.3,<7.0.0"\n',
            'Django = ">=6.0.3,<7.0.0"\ndjango-recaptcha = "^4.0.0"\n',
        )
    )

    _init_clean_git_repo(recipient)
    _install_in_place_success_stub(
        monkeypatch,
        recipient=recipient,
        package="beta_site",
    )
    report = run_beta_migration(
        BetaMigrationInput(
            mode="in-place",
            donor=donor,
            recipient=recipient,
            dry_run=False,
            continue_after_checkpoint=True,
        )
    )

    assert report.status == "ready"

    # The dropped dependency must NOT appear in the final pyproject.toml.
    pyproject_text = (recipient / "pyproject.toml").read_text()
    assert "django-recaptcha" not in pyproject_text

    # The step detail must explicitly name the dropped dependency.
    merge_detail = _find_step_detail(report, "merge-pyproject-and-frontend-package")
    assert "django-recaptcha" in merge_detail
    assert "Recipient-only non-path dependencies dropped" in merge_detail


def test_quickscale_apply_timeout_blocks_with_actionable_diagnostic(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A hung quickscale apply must fail the migration with a bounded timeout diagnostic.

    The subprocess timeout prevents indefinite blocking; the error message
    must name the timeout, the working directory, and the remediation knob.
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
    _init_clean_git_repo(recipient)

    original_run = subprocess.run

    def fake_run_with_apply_timeout(command, cwd=None, **kwargs):
        command_tuple = tuple(command)
        if (
            len(command_tuple) >= 3
            and command_tuple[0] == "git"
            and command_tuple[1] == "-C"
        ):
            return original_run(command, cwd=cwd, **kwargs)
        if command_tuple == ("quickscale", "apply"):
            raise subprocess.TimeoutExpired(command, kwargs.get("timeout"))
        return original_run(command, cwd=cwd, **kwargs)

    monkeypatch.setattr(subprocess, "run", fake_run_with_apply_timeout)

    report = run_beta_migration(
        BetaMigrationInput(
            mode="in-place",
            donor=donor,
            recipient=recipient,
            dry_run=False,
            continue_after_checkpoint=True,
        )
    )

    assert report.status == "blocked"
    assert report.phase == "in-place-partial"
    assert any(
        "timeout" in blocker.lower() and "quickscale apply" in blocker.lower()
        for blocker in report.blockers
    )
    assert any(
        "QUICKSCALE_APPLY_TIMEOUT_SECONDS" in blocker for blocker in report.blockers
    )


def test_verification_command_timeout_blocks_with_actionable_diagnostic(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A hung verification command must fail the migration with a bounded timeout diagnostic.

    The verification result must record the timeout as a failure with a
    descriptive stderr, and the report must be blocked with a message that
    names the timed-out command and the remediation knob.
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
    _init_clean_git_repo(recipient)

    original_run = subprocess.run

    def fake_run_with_verification_timeout(command, cwd=None, **kwargs):
        command_tuple = tuple(command)
        if (
            len(command_tuple) >= 3
            and command_tuple[0] == "git"
            and command_tuple[1] == "-C"
        ):
            return original_run(command, cwd=cwd, **kwargs)
        if command_tuple == ("quickscale", "apply"):
            return subprocess.CompletedProcess(
                command_tuple,
                0,
                stdout="stdout:quickscale apply",
                stderr="stderr:quickscale apply",
            )
        if command_tuple == ("poetry", "lock"):
            raise subprocess.TimeoutExpired(command, kwargs.get("timeout"))
        return original_run(command, cwd=cwd, **kwargs)

    monkeypatch.setattr(subprocess, "run", fake_run_with_verification_timeout)

    report = run_beta_migration(
        BetaMigrationInput(
            mode="in-place",
            donor=donor,
            recipient=recipient,
            dry_run=False,
            continue_after_checkpoint=True,
        )
    )

    assert report.status == "blocked"
    assert report.phase == "in-place-partial"

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


# ---------------------------------------------------------------------------
# SA62 regression: module-dependency-sync validated writer rejects invalid TOML
# ---------------------------------------------------------------------------


def test_module_dependency_sync_write_validated_toml_accepts_valid_content(
    tmp_path: Path,
) -> None:
    """The module-dependency-sync validated writer should accept valid TOML."""
    from quickscale_cli.utils.module_dependency_sync import (
        _write_validated_toml,
    )

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
    from quickscale_cli.utils.module_dependency_sync import (
        DependencySyncError,
        _write_validated_toml,
    )

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
    from quickscale_cli.utils.module_dependency_sync import (
        _patch_module_path_dependencies,
    )

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
    from quickscale_cli.utils.module_dependency_sync import (
        DependencySyncError,
        _patch_module_path_dependencies,
    )

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
