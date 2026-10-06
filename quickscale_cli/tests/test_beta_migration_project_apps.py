"""Behavioral tests for project-owned app migration and frontend dependency merge.

The fresh-first workflow detects the donor's top-level Django apps, carries
them into the recipient without their migration history, registers and
URL-mounts them through user-owned files, regenerates their migrations through
the verification stack, and merges donor-only frontend dependencies while
reporting every version conflict.
"""

from __future__ import annotations

import ast
import hashlib
import json
import shutil
import subprocess
import sys
import types
from pathlib import Path

import pytest
from django.db.migrations.graph import MigrationGraph
from quickscale_core.generator import ProjectGenerator
from quickscale_core.schema.state_schema import (
    ManagedFileRecord,
    ProjectState,
    QuickScaleState,
    StateManager,
)
from quickscale_devtools.beta_migration import (
    BetaMigrationInput,
    BetaMigrationReport,
    _insert_dependency_entries,
    _iterate_stage_dir,
    run_beta_migration,
)


def _write_project_config(project: Path, slug: str) -> None:
    package = slug.replace("-", "_")
    (project / "quickscale.yml").write_text(
        'version: "1"\n'
        "project:\n"
        f"  slug: {slug}\n"
        f"  package: {package}\n"
        "  theme: showcase_react\n"
        "modules: {}\n"
        "docker: {}\n"
    )


def _generate_project(root: Path, slug: str) -> Path:
    """Generate a real QuickScale project with applied-state records."""
    project = root / slug
    ProjectGenerator(theme="showcase_react").generate(slug, project)
    _write_project_config(project, slug)
    package = slug.replace("-", "_")
    managed_paths = (
        f"{package}/settings/modules.py",
        f"{package}/urls_modules.py",
    )
    state_manager = StateManager(project)
    state_manager.save(
        QuickScaleState(
            version="1",
            project=ProjectState(
                slug=slug,
                package=package,
                theme="showcase_react",
            ),
            managed_files={
                relative_path: ManagedFileRecord(
                    path=relative_path,
                    hash=hashlib.sha256(
                        (project / relative_path).read_bytes()
                    ).hexdigest(),
                )
                for relative_path in managed_paths
            },
        )
    )
    state_manager.flush_empty_consolidated_sections()
    return project


@pytest.fixture(scope="module")
def generated_pair(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    """Generate one pristine donor/recipient pair reused by every test."""
    root = tmp_path_factory.mktemp("project-apps-generated")
    return (
        _generate_project(root / "donor-root", "beta-site"),
        _generate_project(root / "recipient-root", "beta-site"),
    )


@pytest.fixture()
def project_pair(
    tmp_path: Path, generated_pair: tuple[Path, Path]
) -> tuple[Path, Path]:
    """Copy the pristine pair so each test mutates its own tree."""
    donor_source, recipient_source = generated_pair
    donor = tmp_path / "donor" / "beta-site"
    recipient = tmp_path / "recipient" / "beta-site"
    shutil.copytree(donor_source, donor)
    shutil.copytree(recipient_source, recipient)
    return donor, recipient


def _install_subprocess_stub(
    monkeypatch: pytest.MonkeyPatch,
    *,
    on_command=None,
) -> list[tuple[tuple[str, ...], Path]]:
    """Stub subprocess.run and record every verification command.

    ``on_command`` (when given) observes each stubbed command, so a test can
    materialize the artifacts the real command would produce — for example the
    recipient's regenerated ``makemigrations`` output.
    """
    calls: list[tuple[tuple[str, ...], Path]] = []

    def fake_run(command, cwd=None, **kwargs):
        command_tuple = tuple(command)
        working_dir = Path(str(cwd)) if cwd is not None else Path.cwd()
        calls.append((command_tuple, working_dir))
        if command_tuple[:2] == ("docker", "inspect"):
            if command_tuple[3] == "{{.State.Health.Status}}":
                return subprocess.CompletedProcess(
                    command_tuple, 0, stdout="healthy", stderr=""
                )
            if "Config.Env" in command_tuple[3]:
                return subprocess.CompletedProcess(
                    command_tuple,
                    0,
                    stdout=json.dumps(
                        [
                            "POSTGRES_DB=app",
                            "POSTGRES_USER=postgres",
                            "POSTGRES_PASSWORD=postgres",
                        ]
                    ),
                    stderr="",
                )
            if "NetworkSettings.Ports" in command_tuple[3]:
                return subprocess.CompletedProcess(
                    command_tuple,
                    0,
                    stdout=json.dumps(
                        {"5432/tcp": [{"HostIp": "127.0.0.1", "HostPort": "55000"}]}
                    ),
                    stderr="",
                )
            return subprocess.CompletedProcess(
                command_tuple, 0, stdout="true", stderr=""
            )
        if on_command is not None:
            on_command(command_tuple, working_dir)
        return subprocess.CompletedProcess(
            command_tuple, 0, stdout="stub stdout", stderr=""
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    return calls


def _add_project_app(project: Path, name: str, *, label: str | None = None) -> None:
    """Write a plausible project-owned Django app into a generated project."""
    app = project / name
    (app / "migrations").mkdir(parents=True)
    (app / "__init__.py").write_text("")
    class_name = "".join(part.title() for part in name.split("_")) + "Config"
    label_line = f'    label = "{label}"\n' if label else ""
    (app / "apps.py").write_text(
        "from django.apps import AppConfig\n"
        "\n"
        "\n"
        f"class {class_name}(AppConfig):\n"
        '    default_auto_field = "django.db.models.BigAutoField"\n'
        f'    name = "{name}"\n'
        f"{label_line}"
    )
    (app / "models.py").write_text(
        "from django.db import models\n"
        "\n"
        "\n"
        f"class {name.title()}(models.Model):\n"
        "    title = models.CharField(max_length=200)\n"
    )
    (app / "views.py").write_text(
        "from django.http import HttpResponse\n"
        "\n"
        "\n"
        f"def {name}_index(request):\n"
        '    return HttpResponse("ok")\n'
    )
    (app / "urls.py").write_text(
        "from django.urls import path\n"
        "\n"
        "from . import views\n"
        "\n"
        "urlpatterns = [\n"
        f'    path("", views.{name}_index, name="{name}-index"),\n'
        "]\n"
    )
    (app / "admin.py").write_text("")
    (app / "migrations" / "0001_initial.py").write_text(
        f'DONOR_MIGRATION_MARKER = "{name}-donor-migration"\n'
    )


def _mount_app_in_package_urls(project: Path, package: str, app_name: str) -> None:
    """Add the app include to the generated package urls before its catch-all."""
    urls_path = project / package / "urls.py"
    lines = urls_path.read_text().splitlines(keepends=True)
    catch_all_index = next(
        index for index, line in enumerate(lines) if 're_path(r".*"' in line
    )
    block_index = catch_all_index
    while not lines[block_index].strip().startswith("urlpatterns += ["):
        block_index -= 1
    include_line = (
        f'urlpatterns += [path("api/{app_name}/", include("{app_name}.urls"))]\n'
    )
    urls_path.write_text(
        "".join(lines[:block_index] + [include_line] + lines[block_index:])
    )


def _add_frontend_dependencies(
    project: Path,
    *,
    dependencies: dict[str, str] | None = None,
    dev_dependencies: dict[str, str] | None = None,
) -> None:
    package_json_path = project / "frontend" / "package.json"
    data = json.loads(package_json_path.read_text())
    data.setdefault("dependencies", {}).update(dependencies or {})
    data.setdefault("devDependencies", {}).update(dev_dependencies or {})
    package_json_path.write_text(json.dumps(data, indent=2) + "\n")


def _run_fresh_first(
    monkeypatch: pytest.MonkeyPatch,
    donor: Path,
    recipient: Path,
) -> tuple[BetaMigrationReport, list[tuple[tuple[str, ...], Path]]]:
    calls = _install_subprocess_stub(monkeypatch)
    report = run_beta_migration(
        BetaMigrationInput(mode="fresh-first", donor=donor, recipient=recipient)
    )
    return report, calls


def test_fresh_first_carries_app_and_merges_frontend_dependencies(
    project_pair: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    donor, recipient = project_pair
    _add_project_app(donor, "properties")
    _mount_app_in_package_urls(donor, "beta_site", "properties")
    _add_frontend_dependencies(
        donor,
        dependencies={"axios": "^1.7.0", "zod": "^9.9.9"},
        dev_dependencies={"left-pad": "^1.3.0"},
    )
    recipient_zod = json.loads((recipient / "frontend" / "package.json").read_text())[
        "dependencies"
    ]["zod"]
    recipient_wiring = (recipient / "beta_site" / "settings" / "modules.py").read_text()
    donor_manifest = (donor / "frontend" / "package.json").read_text()

    report, calls = _run_fresh_first(monkeypatch, donor, recipient)
    assert report.status == "ready", report.blockers
    assert report.phase == "fresh-first-executed"

    # The app is copied without the donor migration history.
    assert (recipient / "properties" / "models.py").is_file()
    assert (recipient / "properties" / "urls.py").is_file()
    assert not (recipient / "properties" / "migrations").exists()
    assert (donor / "properties" / "migrations" / "0001_initial.py").is_file()

    # Registration lands in user-owned settings, not the managed wiring.
    settings_text = (recipient / "beta_site" / "settings" / "base.py").read_text()
    assert '"properties",' in settings_text
    assert (recipient / "beta_site" / "settings" / "modules.py").read_text() == (
        recipient_wiring
    )

    # The donor's URL mount is carried into the recipient.
    urls_text = (recipient / "beta_site" / "urls.py").read_text()
    assert 'path("api/properties/", include("properties.urls"))' in urls_text

    # Migrations regenerate recipient-locally through the verification stack.
    makemigrations = (
        "poetry",
        "run",
        "python",
        "manage.py",
        "makemigrations",
        "properties",
    )
    migrate = ("poetry", "run", "python", "manage.py", "migrate")
    verification_argv = [argv for argv, _cwd in calls]
    verification_cwds = dict(calls)
    assert makemigrations in verification_argv
    assert verification_argv.index(makemigrations) < verification_argv.index(migrate)
    assert verification_cwds[makemigrations] == recipient
    assert len(report.verification_results) == 8
    assert all(result.status == "passed" for result in report.verification_results)

    # Donor-only dependencies merge; the recipient's version wins conflicts.
    merged = json.loads((recipient / "frontend" / "package.json").read_text())
    assert merged["dependencies"]["axios"] == "^1.7.0"
    assert merged["devDependencies"]["left-pad"] == "^1.3.0"
    assert merged["dependencies"]["zod"] == recipient_zod
    assert report.frontend_dependency_merge is not None
    assert report.frontend_dependency_merge.donor_only == ["axios", "left-pad"]
    assert len(report.frontend_dependency_merge.conflicts) == 1
    assert "zod" in report.frontend_dependency_merge.conflicts[0]

    # Classification accepts the app files as project-owned, not unclassified.
    classification = report.donor_file_classification
    assert classification is not None
    assert classification.unclassified == []
    assert "properties/models.py" in classification.project_owned

    # The dry-run-style plan names the app-aware verification command too.
    stack_action = next(
        action
        for action in report.planned_actions
        if action.step == "run-verification-stack"
    )
    assert any(
        "makemigrations properties" in command for command in stack_action.commands
    )

    # The donor stayed read-only.
    assert (donor / "frontend" / "package.json").read_text() == donor_manifest


def test_project_app_urls_are_mounted_when_donor_root_omits_them(
    project_pair: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    donor, recipient = project_pair
    _add_project_app(donor, "properties")

    report, _calls = _run_fresh_first(monkeypatch, donor, recipient)
    assert report.status == "ready", report.blockers

    urls_path = recipient / "beta_site" / "urls.py"
    urls_text = urls_path.read_text()
    rebind = (
        'urlpatterns = [path("properties/", include("properties.urls"))] '
        "+ list(urlpatterns)"
    )
    assert rebind in urls_text
    assert urls_text.rstrip().endswith(rebind)
    compile(urls_text, str(urls_path), "exec")


def test_mount_is_runtime_safe_when_urlpatterns_starts_with_catch_all(
    project_pair: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A URLconf whose only prior pattern is the catch-all must still mount."""
    donor, recipient = project_pair
    _add_project_app(donor, "properties")
    (donor / "beta_site" / "urls.py").write_text(
        "from django.urls import include, path, re_path\n"
        "\n"
        'urlpatterns = [re_path(r".*", lambda request: None)]\n'
    )

    report, _calls = _run_fresh_first(monkeypatch, donor, recipient)
    assert report.status == "ready", report.blockers

    urls_path = recipient / "beta_site" / "urls.py"
    namespace: dict[str, object] = {}
    app_module = types.ModuleType("properties.urls")
    app_module.urlpatterns = []  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "properties.urls", app_module)
    exec(compile(urls_path.read_text(), str(urls_path), "exec"), namespace)

    urlpatterns = namespace["urlpatterns"]
    assert isinstance(urlpatterns, list)
    first = urlpatterns[0]
    assert getattr(first.pattern, "_route", None) == "properties/"


@pytest.mark.parametrize(
    ("header", "path_expression", "include_expression"),
    [
        ("from django.urls import include, path\n", "path", "include"),
        (
            "from django.urls import (\n    include,\n    path,\n)\n",
            "path",
            "include",
        ),
        (
            "from django.urls import include as inc, path as p\n",
            "p",
            "inc",
        ),
        ("import django.urls\n", "django.urls.path", "django.urls.include"),
        ("import django.urls as du\n", "du.path", "du.include"),
    ],
)
def test_mount_uses_the_url_helpers_the_module_actually_binds(
    project_pair: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
    header: str,
    path_expression: str,
    include_expression: str,
) -> None:
    """Bare, aliased, qualified, and multiline imports all mount correctly."""
    donor, recipient = project_pair
    _add_project_app(donor, "properties")
    (donor / "beta_site" / "urls.py").write_text(header + "\nurlpatterns = []\n")

    report, _calls = _run_fresh_first(monkeypatch, donor, recipient)
    assert report.status == "ready", report.blockers

    urls_path = recipient / "beta_site" / "urls.py"
    urls_text = urls_path.read_text()
    assert f"{path_expression}(" in urls_text
    assert f"{include_expression}(" in urls_text

    namespace: dict[str, object] = {}
    app_module = types.ModuleType("properties.urls")
    app_module.urlpatterns = []  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "properties.urls", app_module)
    exec(compile(urls_text, str(urls_path), "exec"), namespace)

    urlpatterns = namespace["urlpatterns"]
    assert isinstance(urlpatterns, list)
    first = urlpatterns[0]
    assert getattr(first.pattern, "_route", None) == "properties/"


def test_project_app_registration_uses_the_app_label_for_migrations(
    project_pair: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    donor, recipient = project_pair
    _add_project_app(donor, "properties", label="props")

    report, calls = _run_fresh_first(monkeypatch, donor, recipient)
    assert report.status == "ready", report.blockers

    verification_argv = [argv for argv, _cwd in calls]
    assert (
        "poetry",
        "run",
        "python",
        "manage.py",
        "makemigrations",
        "props",
    ) in verification_argv
    settings_text = (recipient / "beta_site" / "settings" / "base.py").read_text()
    assert '"properties",' in settings_text


def test_existing_appconfig_registration_is_not_duplicated(
    project_pair: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """An explicit AppConfig entry already registers the app's label."""
    donor, recipient = project_pair
    _add_project_app(donor, "properties")
    settings_path = recipient / "beta_site" / "settings" / "base.py"
    settings_path.write_text(
        settings_path.read_text().replace(
            "    # Add your apps here\n",
            '    "properties.apps.PropertiesConfig",\n    # Add your apps here\n',
        )
    )

    report, _calls = _run_fresh_first(monkeypatch, donor, recipient)

    assert report.status == "ready", report.blockers
    settings_text = settings_path.read_text()
    assert settings_text.count('"properties"') == 0
    assert '"properties.apps.PropertiesConfig",' in settings_text


def test_explicit_appconfig_selection_is_preserved(
    project_pair: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The donor's selected non-default AppConfig and label are preserved."""
    donor, recipient = project_pair
    _add_project_app(donor, "properties")
    (donor / "properties" / "apps.py").write_text(
        "from django.apps import AppConfig\n"
        "\n"
        "\n"
        "class DefaultPropertiesConfig(AppConfig):\n"
        '    default_auto_field = "django.db.models.BigAutoField"\n'
        '    name = "properties"\n'
        "    default = True\n"
        "\n"
        "\n"
        "class PropertiesConfig(AppConfig):\n"
        '    name = "properties"\n'
        '    label = "props"\n'
        "    default = False\n"
    )
    donor_settings = donor / "beta_site" / "settings" / "base.py"
    donor_settings.write_text(
        donor_settings.read_text().replace(
            "    # Add your apps here\n",
            '    "properties.apps.PropertiesConfig",\n    # Add your apps here\n',
        )
    )

    report, calls = _run_fresh_first(monkeypatch, donor, recipient)

    assert report.status == "ready", report.blockers
    recipient_settings = recipient / "beta_site" / "settings" / "base.py"
    recipient_text = recipient_settings.read_text()
    assert '"properties.apps.PropertiesConfig",' in recipient_text
    assert '"properties",' not in recipient_text
    verification_argv = [argv for argv, _cwd in calls]
    assert (
        "poetry",
        "run",
        "python",
        "manage.py",
        "makemigrations",
        "props",
    ) in verification_argv


def test_models_package_only_app_is_detected(
    project_pair: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """An app defined only by a models package is still carried and migrated."""
    donor, recipient = project_pair
    app = donor / "catalog"
    (app / "models").mkdir(parents=True)
    (app / "__init__.py").write_text("")
    (app / "models" / "__init__.py").write_text("from .item import CatalogItem\n")
    (app / "models" / "item.py").write_text(
        "from django.db import models\n"
        "\n"
        "\n"
        "class CatalogItem(models.Model):\n"
        "    title = models.CharField(max_length=200)\n"
    )

    report, calls = _run_fresh_first(monkeypatch, donor, recipient)

    assert report.status == "ready", report.blockers
    assert (recipient / "catalog" / "models" / "item.py").is_file()
    settings_text = (recipient / "beta_site" / "settings" / "base.py").read_text()
    assert '"catalog",' in settings_text
    verification_argv = [argv for argv, _cwd in calls]
    assert (
        "poetry",
        "run",
        "python",
        "manage.py",
        "makemigrations",
        "catalog",
    ) in verification_argv


def test_explicit_appconfig_inherited_label_is_resolved(
    project_pair: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A selected config inheriting its label from an in-module base resolves."""
    donor, recipient = project_pair
    _add_project_app(donor, "properties")
    (donor / "properties" / "apps.py").write_text(
        "from django.apps import AppConfig\n"
        "\n"
        "\n"
        "class BasePropertiesConfig(AppConfig):\n"
        '    name = "properties"\n'
        '    label = "props"\n'
        "    default = False\n"
        "\n"
        "\n"
        "class PropertiesConfig(BasePropertiesConfig):\n"
        "    default = False\n"
    )
    donor_settings = donor / "beta_site" / "settings" / "base.py"
    donor_settings.write_text(
        donor_settings.read_text().replace(
            "    # Add your apps here\n",
            '    "properties.apps.PropertiesConfig",\n    # Add your apps here\n',
        )
    )

    report, calls = _run_fresh_first(monkeypatch, donor, recipient)

    assert report.status == "ready", report.blockers
    verification_argv = [argv for argv, _cwd in calls]
    assert (
        "poetry",
        "run",
        "python",
        "manage.py",
        "makemigrations",
        "props",
    ) in verification_argv


def test_unresolvable_selected_appconfig_blocks_before_any_mutation(
    project_pair: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A selected config whose label comes from an import must fail closed."""
    donor, recipient = project_pair
    _add_project_app(donor, "properties")
    (donor / "properties" / "apps.py").write_text(
        "from third_party_base import BasePropertiesConfig\n"
        "\n"
        "\n"
        "class PropertiesConfig(BasePropertiesConfig):\n"
        "    pass\n"
    )
    donor_settings = donor / "beta_site" / "settings" / "base.py"
    donor_settings.write_text(
        donor_settings.read_text().replace(
            "    # Add your apps here\n",
            '    "properties.apps.PropertiesConfig",\n    # Add your apps here\n',
        )
    )
    calls = _install_subprocess_stub(monkeypatch)

    report = run_beta_migration(
        BetaMigrationInput(mode="fresh-first", donor=donor, recipient=recipient)
    )

    assert report.status == "blocked"
    assert report.changed_files == []
    assert calls == []
    assert any("defined outside this module" in blocker for blocker in report.blockers)


def test_unresolvable_inherited_label_with_direct_name_blocks(
    project_pair: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A direct name must not mask a label inherited from an imported base."""
    donor, recipient = project_pair
    _add_project_app(donor, "properties")
    (donor / "properties" / "apps.py").write_text(
        "from third_party_base import BasePropertiesConfig\n"
        "\n"
        "\n"
        "class PropertiesConfig(BasePropertiesConfig):\n"
        '    name = "properties"\n'
    )
    donor_settings = donor / "beta_site" / "settings" / "base.py"
    donor_settings.write_text(
        donor_settings.read_text().replace(
            "    # Add your apps here\n",
            '    "properties.apps.PropertiesConfig",\n    # Add your apps here\n',
        )
    )
    calls = _install_subprocess_stub(monkeypatch)

    report = run_beta_migration(
        BetaMigrationInput(mode="fresh-first", donor=donor, recipient=recipient)
    )

    assert report.status == "blocked"
    assert report.changed_files == []
    assert calls == []
    assert any("defined outside this module" in blocker for blocker in report.blockers)


def test_imported_first_base_blocks_a_later_in_module_label(
    project_pair: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """An imported earlier base can outrank a later in-module label base."""
    donor, recipient = project_pair
    _add_project_app(donor, "properties")
    (donor / "properties" / "apps.py").write_text(
        "from third_party_base import BasePropertiesConfig\n"
        "\n"
        "\n"
        "class LabelPropertiesConfig:\n"
        '    label = "props"\n'
        "\n"
        "\n"
        "class PropertiesConfig(BasePropertiesConfig, LabelPropertiesConfig):\n"
        '    name = "properties"\n'
    )
    donor_settings = donor / "beta_site" / "settings" / "base.py"
    donor_settings.write_text(
        donor_settings.read_text().replace(
            "    # Add your apps here\n",
            '    "properties.apps.PropertiesConfig",\n    # Add your apps here\n',
        )
    )
    calls = _install_subprocess_stub(monkeypatch)

    report = run_beta_migration(
        BetaMigrationInput(mode="fresh-first", donor=donor, recipient=recipient)
    )

    assert report.status == "blocked"
    assert report.changed_files == []
    assert calls == []
    assert any("defined outside this module" in blocker for blocker in report.blockers)


def test_imported_base_after_an_in_module_label_base_still_blocks(
    project_pair: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """An imported base anywhere makes an inherited label unprovable."""
    donor, recipient = project_pair
    _add_project_app(donor, "properties")
    (donor / "properties" / "apps.py").write_text(
        "from third_party_base import BasePropertiesConfig\n"
        "\n"
        "\n"
        "class LabelPropertiesConfig:\n"
        '    label = "props"\n'
        "\n"
        "\n"
        "class PropertiesConfig(LabelPropertiesConfig, BasePropertiesConfig):\n"
        '    name = "properties"\n'
    )
    donor_settings = donor / "beta_site" / "settings" / "base.py"
    donor_settings.write_text(
        donor_settings.read_text().replace(
            "    # Add your apps here\n",
            '    "properties.apps.PropertiesConfig",\n    # Add your apps here\n',
        )
    )
    calls = _install_subprocess_stub(monkeypatch)

    report = run_beta_migration(
        BetaMigrationInput(mode="fresh-first", donor=donor, recipient=recipient)
    )

    assert report.status == "blocked"
    assert report.changed_files == []
    assert calls == []
    assert any("defined outside this module" in blocker for blocker in report.blockers)


def test_diamond_base_label_follows_mro_precedence(
    project_pair: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A later first-base sibling outranks the shared ancestor's label."""
    donor, recipient = project_pair
    _add_project_app(donor, "properties")
    (donor / "properties" / "apps.py").write_text(
        "from django.apps import AppConfig\n"
        "\n"
        "\n"
        "class SharedPropertiesConfig(AppConfig):\n"
        '    name = "properties"\n'
        '    label = "shared_props"\n'
        "\n"
        "\n"
        "class LeftPropertiesConfig(SharedPropertiesConfig):\n"
        "    pass\n"
        "\n"
        "\n"
        "class RightPropertiesConfig(SharedPropertiesConfig):\n"
        '    label = "props"\n'
        "\n"
        "\n"
        "class PropertiesConfig(LeftPropertiesConfig, RightPropertiesConfig):\n"
        "    pass\n"
    )
    donor_settings = donor / "beta_site" / "settings" / "base.py"
    donor_settings.write_text(
        donor_settings.read_text().replace(
            "    # Add your apps here\n",
            '    "properties.apps.PropertiesConfig",\n    # Add your apps here\n',
        )
    )

    report, calls = _run_fresh_first(monkeypatch, donor, recipient)

    assert report.status == "ready", report.blockers
    verification_argv = [argv for argv, _cwd in calls]
    assert (
        "poetry",
        "run",
        "python",
        "manage.py",
        "makemigrations",
        "props",
    ) in verification_argv
    assert (
        "poetry",
        "run",
        "python",
        "manage.py",
        "makemigrations",
        "shared_props",
    ) not in verification_argv


def test_bare_registration_uses_the_default_appconfig(
    project_pair: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A bare registration resolves Django's default AppConfig selection."""
    donor, recipient = project_pair
    _add_project_app(donor, "properties")
    (donor / "properties" / "apps.py").write_text(
        "from django.apps import AppConfig\n"
        "\n"
        "\n"
        "class LegacyConfig(AppConfig):\n"
        '    name = "properties"\n'
        '    label = "legacy_props"\n'
        "    default = False\n"
        "\n"
        "\n"
        "class PropertiesConfig(AppConfig):\n"
        '    name = "properties"\n'
        '    label = "props"\n'
        "    default = True\n"
    )

    report, calls = _run_fresh_first(monkeypatch, donor, recipient)

    assert report.status == "ready", report.blockers
    settings_text = (recipient / "beta_site" / "settings" / "base.py").read_text()
    assert '"properties",' in settings_text
    verification_argv = [argv for argv, _cwd in calls]
    assert (
        "poetry",
        "run",
        "python",
        "manage.py",
        "makemigrations",
        "props",
    ) in verification_argv


def test_all_disabled_bare_registration_falls_back_to_the_directory_label(
    project_pair: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two candidates with default = False are both discarded by Django."""
    donor, recipient = project_pair
    _add_project_app(donor, "properties")
    (donor / "properties" / "apps.py").write_text(
        "from django.apps import AppConfig\n"
        "\n"
        "\n"
        "class LegacyConfig(AppConfig):\n"
        '    name = "properties"\n'
        '    label = "legacy_props"\n'
        "    default = False\n"
        "\n"
        "\n"
        "class PropertiesConfig(AppConfig):\n"
        '    name = "properties"\n'
        '    label = "props"\n'
        "    default = False\n"
    )

    report, calls = _run_fresh_first(monkeypatch, donor, recipient)

    assert report.status == "ready", report.blockers
    verification_argv = [argv for argv, _cwd in calls]
    assert (
        "poetry",
        "run",
        "python",
        "manage.py",
        "makemigrations",
        "properties",
    ) in verification_argv
    assert (
        "poetry",
        "run",
        "python",
        "manage.py",
        "makemigrations",
        "props",
    ) not in verification_argv


def test_candidate_without_an_explicit_default_is_selected(
    project_pair: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Django keeps a candidate whose default is absent and discards the rest."""
    donor, recipient = project_pair
    _add_project_app(donor, "properties")
    (donor / "properties" / "apps.py").write_text(
        "from django.apps import AppConfig\n"
        "\n"
        "\n"
        "class LegacyConfig(AppConfig):\n"
        '    name = "properties"\n'
        '    label = "legacy_props"\n'
        "    default = False\n"
        "\n"
        "\n"
        "class PropertiesConfig(AppConfig):\n"
        '    name = "properties"\n'
        '    label = "props"\n'
    )

    report, calls = _run_fresh_first(monkeypatch, donor, recipient)

    assert report.status == "ready", report.blockers
    verification_argv = [argv for argv, _cwd in calls]
    assert (
        "poetry",
        "run",
        "python",
        "manage.py",
        "makemigrations",
        "props",
    ) in verification_argv
    assert (
        "poetry",
        "run",
        "python",
        "manage.py",
        "makemigrations",
        "legacy_props",
    ) not in verification_argv


def test_aliased_appconfig_import_is_detected(
    project_pair: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A config deriving from an aliased Django AppConfig is still a candidate."""
    donor, recipient = project_pair
    _add_project_app(donor, "properties")
    (donor / "properties" / "apps.py").write_text(
        "from django.apps import AppConfig as DjangoAppConfig\n"
        "\n"
        "\n"
        "class PropertiesConfig(DjangoAppConfig):\n"
        '    name = "properties"\n'
        '    label = "props"\n'
    )

    report, calls = _run_fresh_first(monkeypatch, donor, recipient)

    assert report.status == "ready", report.blockers
    verification_argv = [argv for argv, _cwd in calls]
    assert (
        "poetry",
        "run",
        "python",
        "manage.py",
        "makemigrations",
        "props",
    ) in verification_argv
    assert (
        "poetry",
        "run",
        "python",
        "manage.py",
        "makemigrations",
        "properties",
    ) not in verification_argv


def test_module_aliased_appconfig_import_is_detected(
    project_pair: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """``from django import apps as x`` binds x.AppConfig as a candidate base."""
    donor, recipient = project_pair
    _add_project_app(donor, "properties")
    (donor / "properties" / "apps.py").write_text(
        "from django import apps as django_apps\n"
        "\n"
        "\n"
        "class PropertiesConfig(django_apps.AppConfig):\n"
        '    name = "properties"\n'
        '    label = "props"\n'
    )

    report, calls = _run_fresh_first(monkeypatch, donor, recipient)

    assert report.status == "ready", report.blockers
    verification_argv = [argv for argv, _cwd in calls]
    assert (
        "poetry",
        "run",
        "python",
        "manage.py",
        "makemigrations",
        "props",
    ) in verification_argv
    assert (
        "poetry",
        "run",
        "python",
        "manage.py",
        "makemigrations",
        "properties",
    ) not in verification_argv


def test_nonliteral_label_declaration_blocks_before_mutation(
    project_pair: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A label assigned a name shadows any literal; it must fail closed."""
    donor, recipient = project_pair
    _add_project_app(donor, "properties")
    (donor / "properties" / "apps.py").write_text(
        "from django.apps import AppConfig\n"
        "\n"
        "\n"
        'LABEL = "props"\n'
        "\n"
        "\n"
        "class PropertiesConfig(AppConfig):\n"
        '    name = "properties"\n'
        "    label = LABEL\n"
    )
    calls = _install_subprocess_stub(monkeypatch)

    report = run_beta_migration(
        BetaMigrationInput(mode="fresh-first", donor=donor, recipient=recipient)
    )

    assert report.status == "blocked"
    assert report.changed_files == []
    assert calls == []
    assert any("non-literal value" in blocker for blocker in report.blockers)


def test_reassigned_label_uses_the_last_assignment(
    project_pair: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A later literal assignment wins over an earlier one."""
    donor, recipient = project_pair
    _add_project_app(donor, "properties")
    (donor / "properties" / "apps.py").write_text(
        "from django.apps import AppConfig\n"
        "\n"
        "\n"
        "class PropertiesConfig(AppConfig):\n"
        '    name = "properties"\n'
        '    label = "old_props"\n'
        '    label = "props"\n'
    )

    report, calls = _run_fresh_first(monkeypatch, donor, recipient)

    assert report.status == "ready", report.blockers
    verification_argv = [argv for argv, _cwd in calls]
    assert (
        "poetry",
        "run",
        "python",
        "manage.py",
        "makemigrations",
        "props",
    ) in verification_argv
    assert (
        "poetry",
        "run",
        "python",
        "manage.py",
        "makemigrations",
        "old_props",
    ) not in verification_argv


def test_reassigned_nonliteral_label_blocks_before_mutation(
    project_pair: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A later non-literal assignment must not fall back to an earlier literal."""
    donor, recipient = project_pair
    _add_project_app(donor, "properties")
    (donor / "properties" / "apps.py").write_text(
        "from django.apps import AppConfig\n"
        "\n"
        "\n"
        'LABEL = "props"\n'
        "\n"
        "\n"
        "class PropertiesConfig(AppConfig):\n"
        '    name = "properties"\n'
        '    label = "old_props"\n'
        "    label = LABEL\n"
    )
    calls = _install_subprocess_stub(monkeypatch)

    report = run_beta_migration(
        BetaMigrationInput(mode="fresh-first", donor=donor, recipient=recipient)
    )

    assert report.status == "blocked"
    assert report.changed_files == []
    assert calls == []
    assert any("non-literal value" in blocker for blocker in report.blockers)


def test_qualified_imported_base_is_not_resolved_as_a_local_class(
    project_pair: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """``vendor.BaseConfig`` must not be substituted by a local BaseConfig."""
    donor, recipient = project_pair
    _add_project_app(donor, "properties")
    (donor / "properties" / "apps.py").write_text(
        "from django.apps import AppConfig\n"
        "import vendor\n"
        "\n"
        "\n"
        "class BaseConfig(AppConfig):\n"
        '    label = "local_label"\n'
        "\n"
        "\n"
        "class LaterLabelConfig:\n"
        '    label = "later_label"\n'
        "\n"
        "\n"
        "class PropertiesConfig(vendor.BaseConfig, LaterLabelConfig):\n"
        '    name = "properties"\n'
    )
    donor_settings = donor / "beta_site" / "settings" / "base.py"
    donor_settings.write_text(
        donor_settings.read_text().replace(
            "    # Add your apps here\n",
            '    "properties.apps.PropertiesConfig",\n    # Add your apps here\n',
        )
    )
    calls = _install_subprocess_stub(monkeypatch)

    report = run_beta_migration(
        BetaMigrationInput(mode="fresh-first", donor=donor, recipient=recipient)
    )

    assert report.status == "blocked"
    assert report.changed_files == []
    assert calls == []
    assert any(
        "base vendor.BaseConfig is defined outside this module" in blocker
        for blocker in report.blockers
    )


def test_recipient_registration_with_a_different_label_blocks(
    project_pair: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A recipient entry selecting another label must block before mutation."""
    donor, recipient = project_pair
    _add_project_app(donor, "properties")
    (donor / "properties" / "apps.py").write_text(
        "from django.apps import AppConfig\n"
        "\n"
        "\n"
        "class DefaultPropertiesConfig(AppConfig):\n"
        '    name = "properties"\n'
        '    label = "properties"\n'
        "\n"
        "\n"
        "class PropertiesConfig(AppConfig):\n"
        '    name = "properties"\n'
        '    label = "props"\n'
        "    default = False\n"
    )
    donor_settings = donor / "beta_site" / "settings" / "base.py"
    donor_settings.write_text(
        donor_settings.read_text().replace(
            "    # Add your apps here\n",
            '    "properties.apps.PropertiesConfig",\n    # Add your apps here\n',
        )
    )
    recipient_settings = recipient / "beta_site" / "settings" / "base.py"
    recipient_settings.write_text(
        recipient_settings.read_text().replace(
            "    # Add your apps here\n",
            '    "properties",\n    # Add your apps here\n',
        )
    )
    calls = _install_subprocess_stub(monkeypatch)

    report = run_beta_migration(
        BetaMigrationInput(mode="fresh-first", donor=donor, recipient=recipient)
    )

    assert report.status == "blocked"
    assert report.changed_files == []
    assert calls == []
    assert any(
        "differs from the donor's migration label" in blocker
        for blocker in report.blockers
    )


@pytest.mark.parametrize(
    "apps_py",
    [
        (
            "from django.apps import AppConfig\n"
            "\n"
            "\n"
            "class PropertiesConfig(AppConfig):\n"
            '    name = "properties"\n'
            '    label = "props"\n'
            "    default = False\n"
        ),
        (
            "from django.apps import AppConfig\n"
            "\n"
            "\n"
            "class DefaultsMixin:\n"
            "    default = False\n"
            "\n"
            "\n"
            "class PropertiesConfig(DefaultsMixin, AppConfig):\n"
            '    name = "properties"\n'
            '    label = "props"\n'
        ),
    ],
    ids=["direct", "inherited"],
)
def test_singleton_default_false_appconfig_falls_back_to_the_directory_label(
    project_pair: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
    apps_py: str,
) -> None:
    """Django ignores the only candidate when it sets default = False."""
    donor, recipient = project_pair
    _add_project_app(donor, "properties")
    (donor / "properties" / "apps.py").write_text(apps_py)

    report, calls = _run_fresh_first(monkeypatch, donor, recipient)

    assert report.status == "ready", report.blockers
    verification_argv = [argv for argv, _cwd in calls]
    assert (
        "poetry",
        "run",
        "python",
        "manage.py",
        "makemigrations",
        "properties",
    ) in verification_argv
    assert (
        "poetry",
        "run",
        "python",
        "manage.py",
        "makemigrations",
        "props",
    ) not in verification_argv


def test_models_package_layout_still_regenerates_migrations(
    project_pair: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    donor, recipient = project_pair
    _add_project_app(donor, "properties")
    app = donor / "properties"
    (app / "models.py").unlink()
    (app / "models").mkdir()
    (app / "models" / "__init__.py").write_text("from .property import Property\n")
    (app / "models" / "property.py").write_text(
        "from django.db import models\n"
        "\n"
        "\n"
        "class Property(models.Model):\n"
        "    title = models.CharField(max_length=200)\n"
    )

    report, calls = _run_fresh_first(monkeypatch, donor, recipient)
    assert report.status == "ready", report.blockers
    verification_argv = [argv for argv, _cwd in calls]
    assert (
        "poetry",
        "run",
        "python",
        "manage.py",
        "makemigrations",
        "properties",
    ) in verification_argv


def test_app_artifacts_and_migrations_are_never_copied(
    project_pair: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    donor, recipient = project_pair
    _add_project_app(donor, "properties")
    app = donor / "properties"
    (app / ".env").write_text("SECRET=donor\n")
    (app / ".git").mkdir()
    (app / ".git" / "config").write_text("[core]\n")
    (app / "node_modules").mkdir()
    (app / "node_modules" / "pkg.js").write_text("module.exports = 1;\n")

    report, _calls = _run_fresh_first(monkeypatch, donor, recipient)
    assert report.status == "ready", report.blockers

    copied_app = recipient / "properties"
    assert copied_app.is_dir()
    assert not (copied_app / ".env").exists()
    assert not (copied_app / ".git").exists()
    assert not (copied_app / "node_modules").exists()
    assert not (copied_app / "migrations").exists()


def test_invalid_donor_manifest_blocks_before_any_mutation(
    project_pair: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    donor, recipient = project_pair
    (donor / "frontend" / "package.json").write_text("{not json\n")
    calls = _install_subprocess_stub(monkeypatch)

    report = run_beta_migration(
        BetaMigrationInput(mode="fresh-first", donor=donor, recipient=recipient)
    )

    assert report.status == "blocked"
    assert report.changed_files == []
    assert calls == []
    assert any(
        "frontend" in blocker.lower() and "json" in blocker.lower()
        for blocker in report.blockers
    )


def test_malformed_app_python_blocks_before_any_mutation(
    project_pair: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    donor, recipient = project_pair
    _add_project_app(donor, "properties")
    (donor / "properties" / "apps.py").write_text("class Invalid(:\n")
    calls = _install_subprocess_stub(monkeypatch)

    report = run_beta_migration(
        BetaMigrationInput(mode="fresh-first", donor=donor, recipient=recipient)
    )

    assert report.status == "blocked"
    assert report.changed_files == []
    assert calls == []
    assert any("apps.py" in blocker for blocker in report.blockers)
    assert not (recipient / "properties").exists()


def test_excluded_artifact_python_does_not_block_the_preflight(
    project_pair: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Python inside a never-carried artifact tree must not fail validation."""
    donor, recipient = project_pair
    _add_project_app(donor, "properties")
    legacy_dir = donor / "properties" / "node_modules" / "old-gyp"
    legacy_dir.mkdir(parents=True)
    (legacy_dir / "legacy.py").write_text('print "legacy build tooling"\n')

    report, _calls = _run_fresh_first(monkeypatch, donor, recipient)

    assert report.status == "ready", report.blockers
    assert not (recipient / "properties" / "node_modules").exists()


def _migration_dependency_edges(path: Path) -> list[tuple[str, str]]:
    """Return the literal dependency edges declared by a migration file."""
    tree = ast.parse(path.read_text())
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if not any(
            isinstance(target, ast.Name) and target.id == "dependencies"
            for target in node.targets
        ):
            continue
        if not isinstance(node.value, ast.List):
            return []
        return [
            (element.elts[0].value, element.elts[1].value)
            for element in node.value.elts
            if isinstance(element, ast.Tuple) and len(element.elts) == 2
        ]
    return []


def _materialize_regenerated_migration(
    app_name: str,
    *,
    carried_name: str,
    observed: list[tuple[str, bool]],
):
    """Return a stub observer that writes makemigrations' regenerated 0001.

    The observer also records whether the carried migration exists at the
    makemigrations and migrate commands, proving the carry lands between them.
    """

    def observe(command: tuple[str, ...], working_dir: Path) -> None:
        carried = working_dir / app_name / "migrations" / carried_name
        if "makemigrations" in command:
            observed.append(("makemigrations", carried.exists()))
            migrations_dir = working_dir / app_name / "migrations"
            migrations_dir.mkdir(parents=True, exist_ok=True)
            (migrations_dir / "__init__.py").write_text("")
            (migrations_dir / "0001_initial.py").write_text(
                "from django.db import migrations\n"
                "\n"
                "\n"
                "class Migration(migrations.Migration):\n"
                "    initial = True\n"
                "    dependencies = []\n"
                "    operations = []\n"
            )
        elif "migrate" in command:
            observed.append(("migrate", carried.exists()))

    return observe


def test_migration_owned_operations_are_carried_after_makemigrations(
    project_pair: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A migration-owned RunPython is carried into an appended migration."""
    donor, recipient = project_pair
    _add_project_app(donor, "properties")
    (donor / "properties" / "migrations" / "0001_initial.py").write_text(
        "from django.db import migrations\n"
        "\n"
        "\n"
        "def forward(apps, schema_editor):\n"
        "    pass\n"
        "\n"
        "\n"
        "class Migration(migrations.Migration):\n"
        "    initial = True\n"
        "    dependencies = []\n"
        "    operations = [migrations.RunPython(forward)]\n"
    )
    observed: list[tuple[str, bool]] = []
    _install_subprocess_stub(
        monkeypatch,
        on_command=_materialize_regenerated_migration(
            "properties",
            carried_name="0002_carried_initial.py",
            observed=observed,
        ),
    )

    report = run_beta_migration(
        BetaMigrationInput(mode="fresh-first", donor=donor, recipient=recipient)
    )

    assert report.status == "ready", report.blockers
    carried_path = recipient / "properties" / "migrations" / "0002_carried_initial.py"
    assert carried_path.is_file()
    carried_text = carried_path.read_text()
    assert "migrations.RunPython(forward)" in carried_text
    assert 'dependencies = [("properties", "0001_initial")]' in carried_text
    assert str(carried_path) in report.changed_files
    assert any(
        step.step == "carry-project-app-migration-operations"
        and "RunPython" in step.detail
        for step in report.completed_steps
    )
    assert observed == [("makemigrations", False), ("migrate", True)]


def test_tuple_migration_operations_are_carried_after_makemigrations(
    project_pair: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A tuple-valued operations declaration is carried, not ignored."""
    donor, recipient = project_pair
    _add_project_app(donor, "properties")
    (donor / "properties" / "migrations" / "0001_initial.py").write_text(
        "from django.db import migrations\n"
        "\n"
        "\n"
        "class Migration(migrations.Migration):\n"
        "    initial = True\n"
        "    dependencies = []\n"
        "    operations = (\n"
        '        migrations.RunSQL("ALTER TABLE properties_property FORCE ROW LEVEL SECURITY"),\n'
        "    )\n"
    )
    observed: list[tuple[str, bool]] = []
    _install_subprocess_stub(
        monkeypatch,
        on_command=_materialize_regenerated_migration(
            "properties",
            carried_name="0002_carried_initial.py",
            observed=observed,
        ),
    )

    report = run_beta_migration(
        BetaMigrationInput(mode="fresh-first", donor=donor, recipient=recipient)
    )

    assert report.status == "ready", report.blockers
    carried_text = (
        recipient / "properties" / "migrations" / "0002_carried_initial.py"
    ).read_text()
    assert "migrations.RunSQL(" in carried_text
    assert "FORCE ROW LEVEL SECURITY" in carried_text
    assert observed == [("makemigrations", False), ("migrate", True)]


def test_unresolvable_operation_reference_blocks_before_mutation(
    project_pair: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A carried operation referencing no module-level name fails closed."""
    donor, recipient = project_pair
    _add_project_app(donor, "properties")
    (donor / "properties" / "migrations" / "0001_initial.py").write_text(
        "from django.db import migrations\n"
        "\n"
        "\n"
        "class Migration(migrations.Migration):\n"
        "    initial = True\n"
        "    dependencies = []\n"
        "    operations = [migrations.RunPython(missing_function)]\n"
    )
    calls = _install_subprocess_stub(monkeypatch)

    report = run_beta_migration(
        BetaMigrationInput(mode="fresh-first", donor=donor, recipient=recipient)
    )

    assert report.status == "blocked"
    assert report.changed_files == []
    assert calls == []
    assert any("missing_function" in blocker for blocker in report.blockers)
    assert not (recipient / "properties").exists()


def test_external_migration_dependency_blocks_before_mutation(
    project_pair: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A carried operation depending on another app's migration fails closed."""
    donor, recipient = project_pair
    _add_project_app(donor, "properties")
    (donor / "properties" / "migrations" / "0001_initial.py").write_text(
        "from django.db import migrations\n"
        "\n"
        "\n"
        "def forward(apps, schema_editor):\n"
        "    pass\n"
        "\n"
        "\n"
        "class Migration(migrations.Migration):\n"
        "    initial = True\n"
        '    dependencies = [("auth", "0001_initial")]\n'
        "    operations = [migrations.RunPython(forward)]\n"
    )
    calls = _install_subprocess_stub(monkeypatch)

    report = run_beta_migration(
        BetaMigrationInput(mode="fresh-first", donor=donor, recipient=recipient)
    )

    assert report.status == "blocked"
    assert report.changed_files == []
    assert calls == []
    assert any("depends on app 'auth'" in blocker for blocker in report.blockers)
    assert not (recipient / "properties").exists()


def test_dynamic_operations_declaration_blocks_before_mutation(
    project_pair: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """An operations declaration the tool cannot read statically fails closed."""
    donor, recipient = project_pair
    _add_project_app(donor, "properties")
    (donor / "properties" / "migrations" / "0001_initial.py").write_text(
        "from django.db import migrations\n"
        "\n"
        "\n"
        "def build_operations():\n"
        "    return []\n"
        "\n"
        "\n"
        "class Migration(migrations.Migration):\n"
        "    initial = True\n"
        "    dependencies = []\n"
        "    operations = build_operations()\n"
    )
    calls = _install_subprocess_stub(monkeypatch)

    report = run_beta_migration(
        BetaMigrationInput(mode="fresh-first", donor=donor, recipient=recipient)
    )

    assert report.status == "blocked"
    assert report.changed_files == []
    assert calls == []
    assert any(
        "operations declaration cannot be resolved statically" in blocker
        for blocker in report.blockers
    )
    assert not (recipient / "properties").exists()


def test_ledger_fixture_donor_carries_app_tokens_module_edit_and_pre_facade_settings(
    project_pair: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """One fixture donor covers both ledger fixes and the classification classes.

    The donor holds a project-owned app with an unreproducible migration
    operation, customized design tokens, a module edit, and a pre-facade
    ``settings/production.py``; a single fresh-first run must carry, port,
    classify, and rewrite all four without a blocker.
    """
    donor, recipient = project_pair
    _add_project_app(donor, "properties")
    (donor / "properties" / "migrations" / "0002_backfill.py").write_text(
        "from django.db import migrations\n"
        "\n"
        "\n"
        "def backfill(apps, schema_editor):\n"
        "    pass\n"
        "\n"
        "\n"
        "class Migration(migrations.Migration):\n"
        '    dependencies = [("properties", "0001_initial")]\n'
        "    operations = [migrations.RunPython(backfill)]\n"
    )
    (donor / "beta_site" / "settings" / "production.py").write_text(
        '"""Pre-facade donor production settings."""\n'
        "import dj_database_url\n"
        "from decouple import config\n"
        "\n"
        'database_url = config("DATABASE_URL", default=None)\n'
        'DATABASES = {"default": dj_database_url.parse(database_url)}\n'
        "\n"
        'CUSTOM_SITE_SETTING = "donor-kept"\n'
    )
    tokens_path = donor / "frontend" / "design" / "tokens.css"
    tokens_path.write_text(
        tokens_path.read_text() + "\n:root { --donor-brand: gold; }\n"
    )
    module_edit = donor / "modules" / "auth" / "donor_note.py"
    module_edit.parent.mkdir(parents=True)
    module_edit.write_text("DONOR_MODULE_EDIT = True\n")

    observed: list[tuple[str, bool]] = []
    _install_subprocess_stub(
        monkeypatch,
        on_command=_materialize_regenerated_migration(
            "properties",
            carried_name="0002_carried_backfill.py",
            observed=observed,
        ),
    )

    report = run_beta_migration(
        BetaMigrationInput(mode="fresh-first", donor=donor, recipient=recipient)
    )

    assert report.status == "ready", report.blockers
    rewritten = (recipient / "beta_site" / "settings" / "production.py").read_text()
    assert "resolve_runtime_database_url(" in rewritten
    assert 'CUSTOM_SITE_SETTING = "donor-kept"' in rewritten
    carried = recipient / "properties" / "migrations" / "0002_carried_backfill.py"
    assert carried.is_file()
    assert "migrations.RunPython(backfill)" in carried.read_text()
    assert (
        "--donor-brand: gold"
        in (recipient / "frontend" / "design" / "tokens.css").read_text()
    )
    classification = report.donor_file_classification
    assert classification is not None
    assert classification.unclassified == []
    assert "modules/auth/donor_note.py" in classification.module_edited
    assert observed == [("makemigrations", False), ("migrate", True)]
    prompt = (recipient / "MIGRATION_PROMPT.md").read_text()
    assert "RunPython" in prompt


def test_operations_mutated_after_declaration_blocks_before_mutation(
    project_pair: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A dynamic operations mutation must not escape inspection."""
    donor, recipient = project_pair
    _add_project_app(donor, "properties")
    (donor / "properties" / "migrations" / "0001_initial.py").write_text(
        "from django.db import migrations\n"
        "\n"
        "\n"
        "class Migration(migrations.Migration):\n"
        "    initial = True\n"
        "    dependencies = []\n"
        "    operations = []\n"
        '    operations.append(migrations.RunSQL("ALTER TABLE properties_property '
        'FORCE ROW LEVEL SECURITY"))\n'
    )
    calls = _install_subprocess_stub(monkeypatch)

    report = run_beta_migration(
        BetaMigrationInput(mode="fresh-first", donor=donor, recipient=recipient)
    )

    assert report.status == "blocked"
    assert report.changed_files == []
    assert calls == []
    assert any(
        "operations are built dynamically" in blocker for blocker in report.blockers
    )
    assert not (recipient / "properties").exists()


def test_operations_slice_assignment_blocks_before_mutation(
    project_pair: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A slice assignment to operations must not escape inspection."""
    donor, recipient = project_pair
    _add_project_app(donor, "properties")
    (donor / "properties" / "migrations" / "0001_initial.py").write_text(
        "from django.db import migrations\n"
        "\n"
        "\n"
        "class Migration(migrations.Migration):\n"
        "    initial = True\n"
        "    dependencies = []\n"
        "    operations = []\n"
        "    operations[:] = [migrations.RunSQL("
        '"ALTER TABLE properties_property FORCE ROW LEVEL SECURITY")]\n'
    )
    calls = _install_subprocess_stub(monkeypatch)

    report = run_beta_migration(
        BetaMigrationInput(mode="fresh-first", donor=donor, recipient=recipient)
    )

    assert report.status == "blocked"
    assert report.changed_files == []
    assert calls == []
    assert any(
        "operations are built dynamically" in blocker for blocker in report.blockers
    )
    assert not (recipient / "properties").exists()


def test_module_level_mutation_of_a_carried_binding_blocks(
    project_pair: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A mutated module-level binding must not be carried as its declaration."""
    donor, recipient = project_pair
    _add_project_app(donor, "properties")
    (donor / "properties" / "migrations" / "0002_mutated.py").write_text(
        "from django.db import migrations\n"
        "\n"
        'SQL = ["ALTER TABLE properties_property ENABLE ROW LEVEL SECURITY"]\n'
        'SQL.append("ALTER TABLE properties_property FORCE ROW LEVEL SECURITY")\n'
        "\n"
        "\n"
        "class Migration(migrations.Migration):\n"
        '    dependencies = [("properties", "0001_initial")]\n'
        "    operations = [migrations.RunSQL(SQL)]\n"
    )
    calls = _install_subprocess_stub(monkeypatch)

    report = run_beta_migration(
        BetaMigrationInput(mode="fresh-first", donor=donor, recipient=recipient)
    )

    assert report.status == "blocked"
    assert report.changed_files == []
    assert calls == []
    assert any(
        "module-level mutation of 'SQL'" in blocker for blocker in report.blockers
    )
    assert not (recipient / "properties").exists()


def test_loop_built_carried_binding_blocks_before_mutation(
    project_pair: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A mutation inside module-level control flow must block, not vanish."""
    donor, recipient = project_pair
    _add_project_app(donor, "properties")
    (donor / "properties" / "migrations" / "0002_loop_sql.py").write_text(
        "from django.db import migrations\n"
        "\n"
        'SQL = ["ALTER TABLE properties_property ENABLE ROW LEVEL SECURITY"]\n'
        "\n"
        'for table in ["properties_property"]:\n'
        '    SQL.append(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")\n'
        "\n"
        "\n"
        "class Migration(migrations.Migration):\n"
        '    dependencies = [("properties", "0001_initial")]\n'
        "    operations = [migrations.RunSQL(SQL)]\n"
    )
    calls = _install_subprocess_stub(monkeypatch)

    report = run_beta_migration(
        BetaMigrationInput(mode="fresh-first", donor=donor, recipient=recipient)
    )

    assert report.status == "blocked"
    assert report.changed_files == []
    assert calls == []
    assert any(
        "module-level mutation of 'SQL'" in blocker for blocker in report.blockers
    )
    assert not (recipient / "properties").exists()


@pytest.mark.parametrize(
    "migration_body",
    [
        'if True:\n        SQL = SQL + ["ALTER TABLE properties_property '
        'FORCE ROW LEVEL SECURITY"]\n',
        "match 1:\n"
        "    case 1:\n"
        '        SQL.append("ALTER TABLE properties_property '
        'FORCE ROW LEVEL SECURITY")\n',
        "try:\n"
        "    raise RuntimeError\n"
        "except* RuntimeError:\n"
        '    SQL.append("ALTER TABLE properties_property '
        'FORCE ROW LEVEL SECURITY")\n',
        "if True:\n"
        '    SQL, reverse_sql = (SQL + ["ALTER TABLE properties_property '
        'FORCE ROW LEVEL SECURITY"], [])\n',
        "for SQL in [["
        '"ALTER TABLE properties_property ENABLE ROW LEVEL SECURITY"]]:\n'
        "    pass\n",
        "if (SQL := SQL + ["
        '"ALTER TABLE properties_property FORCE ROW LEVEL SECURITY"]):\n'
        "    pass\n",
        'match ["ALTER TABLE properties_property ENABLE ROW LEVEL SECURITY"]:\n'
        "    case SQL:\n"
        "        pass\n",
    ],
    ids=[
        "conditional-rebinding",
        "match-body-append",
        "try-star-append",
        "unpacking-rebinding",
        "loop-target-rebinding",
        "walrus-rebinding",
        "match-capture-rebinding",
    ],
)
def test_control_flow_mutation_of_a_carried_binding_blocks(
    project_pair: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
    migration_body: str,
) -> None:
    """Every module-executed mutation path must block, not silently drop."""
    donor, recipient = project_pair
    _add_project_app(donor, "properties")
    (donor / "properties" / "migrations" / "0002_control_flow.py").write_text(
        "from django.db import migrations\n"
        "\n"
        'SQL = ["ALTER TABLE properties_property ENABLE ROW LEVEL SECURITY"]\n'
        "\n" + migration_body + "\n"
        "\n"
        "class Migration(migrations.Migration):\n"
        '    dependencies = [("properties", "0001_initial")]\n'
        "    operations = [migrations.RunSQL(SQL)]\n"
    )
    calls = _install_subprocess_stub(monkeypatch)

    report = run_beta_migration(
        BetaMigrationInput(mode="fresh-first", donor=donor, recipient=recipient)
    )

    assert report.status == "blocked"
    assert report.changed_files == []
    assert calls == []
    assert any(
        "module-level mutation of 'SQL'" in blocker for blocker in report.blockers
    )
    assert not (recipient / "properties").exists()


def test_nested_receiver_mutation_of_a_carried_binding_blocks(
    project_pair: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A mutating call on a nested container of a required binding blocks."""
    donor, recipient = project_pair
    _add_project_app(donor, "properties")
    (donor / "properties" / "migrations" / "0002_nested.py").write_text(
        "from django.db import migrations\n"
        "\n"
        'SQL = {"forward": ["ALTER TABLE properties_property '
        'ENABLE ROW LEVEL SECURITY"]}\n'
        'SQL["forward"].append("ALTER TABLE properties_property '
        'FORCE ROW LEVEL SECURITY")\n'
        "\n"
        "\n"
        "class Migration(migrations.Migration):\n"
        '    dependencies = [("properties", "0001_initial")]\n'
        '    operations = [migrations.RunSQL(SQL["forward"])]\n'
    )
    calls = _install_subprocess_stub(monkeypatch)

    report = run_beta_migration(
        BetaMigrationInput(mode="fresh-first", donor=donor, recipient=recipient)
    )

    assert report.status == "blocked"
    assert report.changed_files == []
    assert calls == []
    assert any(
        "module-level mutation of 'SQL'" in blocker for blocker in report.blockers
    )
    assert not (recipient / "properties").exists()


def test_carried_operation_keeps_multiline_string_literal_values(
    project_pair: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Re-indenting a carried operation must not change its string values."""
    donor, recipient = project_pair
    _add_project_app(donor, "properties")
    (donor / "properties" / "migrations" / "0002_sql.py").write_text(
        "from django.db import migrations\n"
        "\n"
        "\n"
        "class Migration(migrations.Migration):\n"
        '    dependencies = [("properties", "0001_initial")]\n'
        "    operations = [\n"
        '        migrations.RunSQL("""INSERT INTO notes (body) VALUES (\'hello\n'
        'world\')"""),\n'
        "    ]\n"
    )
    observed: list[tuple[str, bool]] = []
    _install_subprocess_stub(
        monkeypatch,
        on_command=_materialize_regenerated_migration(
            "properties",
            carried_name="0002_carried_sql.py",
            observed=observed,
        ),
    )

    report = run_beta_migration(
        BetaMigrationInput(mode="fresh-first", donor=donor, recipient=recipient)
    )

    assert report.status == "ready", report.blockers
    carried = (
        recipient / "properties" / "migrations" / "0002_carried_sql.py"
    ).read_text()
    assert "'hello\nworld'" in carried
    assert "'hello\n        world'" not in carried


def test_multiple_carried_migrations_chain_by_module_name(
    project_pair: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Each carried migration depends on the previous migration's module name."""
    donor, recipient = project_pair
    _add_project_app(donor, "properties")
    for number, stem in ((2, "first"), (3, "second")):
        previous = "0001_initial" if number == 2 else "0002_first"
        (donor / "properties" / "migrations" / f"{number:04d}_{stem}.py").write_text(
            "from django.db import migrations\n"
            "\n"
            "\n"
            f"def {stem}(apps, schema_editor):\n"
            "    pass\n"
            "\n"
            "\n"
            "class Migration(migrations.Migration):\n"
            f'    dependencies = [("properties", "{previous}")]\n'
            f"    operations = [migrations.RunPython({stem})]\n"
        )
    observed: list[tuple[str, bool]] = []
    _install_subprocess_stub(
        monkeypatch,
        on_command=_materialize_regenerated_migration(
            "properties",
            carried_name="0002_carried_first.py",
            observed=observed,
        ),
    )

    report = run_beta_migration(
        BetaMigrationInput(mode="fresh-first", donor=donor, recipient=recipient)
    )

    assert report.status == "ready", report.blockers
    first = recipient / "properties" / "migrations" / "0002_carried_first.py"
    second = recipient / "properties" / "migrations" / "0003_carried_second.py"
    assert first.is_file()
    assert second.is_file()
    assert 'dependencies = [("properties", "0001_initial")]' in first.read_text()
    assert 'dependencies = [("properties", "0002_carried_first")]' in second.read_text()

    graph = MigrationGraph()
    for path in (recipient / "properties" / "migrations").glob("*.py"):
        if path.name == "__init__.py":
            continue
        graph.add_node(("properties", path.stem), None)
        for app_label, dependency_name in _migration_dependency_edges(path):
            graph.add_dependency(
                None,
                ("properties", path.stem),
                (app_label, dependency_name),
            )
    assert ("properties", "0003_carried_second") in graph.leaf_nodes()


def test_carried_definition_keeps_decorators(
    project_pair: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A carried callback keeps the decorator it was defined with."""
    donor, recipient = project_pair
    _add_project_app(donor, "properties")
    (donor / "properties" / "migrations" / "0002_decorated.py").write_text(
        "from django.db import migrations\n"
        "\n"
        "\n"
        "def wrap(function):\n"
        "    return function\n"
        "\n"
        "\n"
        "@wrap\n"
        "def decorated(apps, schema_editor):\n"
        "    pass\n"
        "\n"
        "\n"
        "class Migration(migrations.Migration):\n"
        '    dependencies = [("properties", "0001_initial")]\n'
        "    operations = [migrations.RunPython(decorated)]\n"
    )
    observed: list[tuple[str, bool]] = []
    _install_subprocess_stub(
        monkeypatch,
        on_command=_materialize_regenerated_migration(
            "properties",
            carried_name="0002_carried_decorated.py",
            observed=observed,
        ),
    )

    report = run_beta_migration(
        BetaMigrationInput(mode="fresh-first", donor=donor, recipient=recipient)
    )

    assert report.status == "ready", report.blockers
    carried = (
        recipient / "properties" / "migrations" / "0002_carried_decorated.py"
    ).read_text()
    assert "@wrap" in carried
    assert "def decorated(apps, schema_editor):" in carried


def test_carried_migration_chains_after_a_multi_file_initial_graph(
    project_pair: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A carry chains from the terminal migration of a multi-file initial graph."""
    donor, recipient = project_pair
    _add_project_app(donor, "properties")
    (donor / "properties" / "migrations" / "0002_backfill.py").write_text(
        "from django.db import migrations\n"
        "\n"
        "\n"
        "def backfill(apps, schema_editor):\n"
        "    pass\n"
        "\n"
        "\n"
        "class Migration(migrations.Migration):\n"
        '    dependencies = [("properties", "0001_initial")]\n'
        "    operations = [migrations.RunPython(backfill)]\n"
    )

    def materialize(command: tuple[str, ...], working_dir: Path) -> None:
        if "makemigrations" not in command:
            return
        migrations_dir = working_dir / "properties" / "migrations"
        migrations_dir.mkdir(parents=True, exist_ok=True)
        (migrations_dir / "__init__.py").write_text("")
        (migrations_dir / "0001_initial.py").write_text(
            "from django.db import migrations\n"
            "\n"
            "\n"
            "class Migration(migrations.Migration):\n"
            "    initial = True\n"
            "    dependencies = []\n"
            "    operations = []\n"
        )
        (migrations_dir / "0002_initial.py").write_text(
            "from django.db import migrations\n"
            "\n"
            "\n"
            "class Migration(migrations.Migration):\n"
            "    initial = True\n"
            '    dependencies = [("properties", "0001_initial"), ("auth", "0001_initial")]\n'
            "    operations = []\n"
        )

    _install_subprocess_stub(monkeypatch, on_command=materialize)

    report = run_beta_migration(
        BetaMigrationInput(mode="fresh-first", donor=donor, recipient=recipient)
    )

    assert report.status == "ready", report.blockers
    carried = recipient / "properties" / "migrations" / "0003_carried_backfill.py"
    assert carried.is_file()
    assert 'dependencies = [("properties", "0002_initial")]' in carried.read_text()


def test_iterate_validates_donor_apps_before_regeneration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Malformed donor app code must block before the recipient is replaced."""
    donor = _generate_project(tmp_path / "donor-root", "iterate-donor")
    _add_project_app(donor, "properties")
    (donor / "properties" / "apps.py").write_text("class Invalid(:\n")
    recipient = tmp_path / "recipient"
    recipient.mkdir()
    (recipient / "quickscale.yml").write_text("previous recipient\n")
    (recipient / "keep.txt").write_text("keep\n")
    calls = _install_subprocess_stub(monkeypatch)

    report = run_beta_migration(
        BetaMigrationInput(mode="iterate", donor=donor, recipient=recipient)
    )

    assert report.status == "blocked"
    assert (recipient / "quickscale.yml").read_text() == "previous recipient\n"
    assert (recipient / "keep.txt").read_text() == "keep\n"
    assert not [call for call in calls if call[0][:2] == ("quickscale", "apply")]


def test_iterate_blocks_malformed_donor_dependency_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The donor manifest's dependency metadata is validated before apply runs."""
    donor = _generate_project(tmp_path / "donor-root", "iterate-donor")
    manifest_path = donor / "frontend" / "package.json"
    data = json.loads(manifest_path.read_text())
    data["dependencies"]["axios"] = 17
    manifest_path.write_text(json.dumps(data, indent=2) + "\n")
    recipient = tmp_path / "recipient"
    recipient.mkdir()
    (recipient / "quickscale.yml").write_text("previous recipient\n")
    (recipient / "keep.txt").write_text("keep\n")
    calls = _install_subprocess_stub(monkeypatch)

    report = run_beta_migration(
        BetaMigrationInput(mode="iterate", donor=donor, recipient=recipient)
    )

    assert report.status == "blocked"
    assert (recipient / "quickscale.yml").read_text() == "previous recipient\n"
    assert (recipient / "keep.txt").read_text() == "keep\n"
    assert not [call for call in calls if call[0][:2] == ("quickscale", "apply")]


def test_iterate_blocks_null_donor_dependency_section(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An explicitly null dependency section is malformed, not absent."""
    donor = _generate_project(tmp_path / "donor-root", "iterate-donor")
    manifest_path = donor / "frontend" / "package.json"
    data = json.loads(manifest_path.read_text())
    data["dependencies"] = None
    manifest_path.write_text(json.dumps(data, indent=2) + "\n")
    recipient = tmp_path / "recipient"
    recipient.mkdir()
    (recipient / "quickscale.yml").write_text("previous recipient\n")
    calls = _install_subprocess_stub(monkeypatch)

    report = run_beta_migration(
        BetaMigrationInput(mode="iterate", donor=donor, recipient=recipient)
    )

    assert report.status == "blocked"
    assert (recipient / "quickscale.yml").read_text() == "previous recipient\n"
    assert calls == []
    assert not _iterate_stage_dir(recipient).exists()


def test_missing_installed_apps_sentinel_blocks_before_any_mutation(
    project_pair: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    donor, recipient = project_pair
    _add_project_app(donor, "properties")
    settings_path = recipient / "beta_site" / "settings" / "base.py"
    settings_path.write_text(
        settings_path.read_text().replace("    # Add your apps here\n", "")
    )
    calls = _install_subprocess_stub(monkeypatch)

    report = run_beta_migration(
        BetaMigrationInput(mode="fresh-first", donor=donor, recipient=recipient)
    )

    assert report.status == "blocked"
    assert report.changed_files == []
    assert calls == []
    assert any("sentinel" in blocker for blocker in report.blockers)
    assert not (recipient / "properties").exists()


@pytest.mark.parametrize("link_kind", ["symlink", "hardlink"])
def test_registration_never_writes_through_a_linked_settings_file(
    project_pair: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
    link_kind: str,
) -> None:
    """A linked recipient settings file must be replaced, not written through."""
    donor, recipient = project_pair
    _add_project_app(donor, "properties")
    donor_settings = donor / "beta_site" / "settings" / "base.py"
    donor_bytes = donor_settings.read_bytes()
    recipient_settings = recipient / "beta_site" / "settings" / "base.py"
    recipient_settings.unlink()
    if link_kind == "symlink":
        recipient_settings.symlink_to(donor_settings)
    else:
        recipient_settings.hardlink_to(donor_settings)

    report, _calls = _run_fresh_first(monkeypatch, donor, recipient)

    assert report.status == "ready", report.blockers
    assert donor_settings.read_bytes() == donor_bytes
    assert not recipient_settings.is_symlink()
    assert recipient_settings.stat().st_nlink == 1
    assert '"properties",' in recipient_settings.read_text()


def test_insert_dependency_entries_expands_an_empty_object() -> None:
    text = (
        '{\n  "dependencies": {},\n'
        '  "devDependencies": {\n    "vite": "^1.0.0"\n  }\n}\n'
    )
    updated = _insert_dependency_entries(text, "dependencies", {"axios": "^1.7.0"})
    data = json.loads(updated)
    assert data["dependencies"] == {"axios": "^1.7.0"}
    assert data["devDependencies"] == {"vite": "^1.0.0"}


def test_insert_dependency_entries_preserves_same_line_siblings() -> None:
    text = (
        '{\n  "dependencies": {}, "scripts": {"build": "vite build"},\n'
        '  "name": "x"\n}\n'
    )
    updated = _insert_dependency_entries(text, "dependencies", {"axios": "^1.7.0"})
    data = json.loads(updated)
    assert data["dependencies"] == {"axios": "^1.7.0"}
    assert data["scripts"] == {"build": "vite build"}
    assert data["name"] == "x"


def test_insert_dependency_entries_expands_a_multiline_empty_object() -> None:
    text = '{\n  "dependencies": {\n  },\n  "name": "x"\n}\n'
    updated = _insert_dependency_entries(text, "dependencies", {"axios": "^1.7.0"})
    data = json.loads(updated)
    assert data["dependencies"] == {"axios": "^1.7.0"}
    assert data["name"] == "x"


def test_insert_dependency_entries_extends_a_compact_object() -> None:
    text = '{"dependencies":{"zod":"^3.0.0"},"name":"x"}\n'
    updated = _insert_dependency_entries(text, "dependencies", {"axios": "^1.7.0"})
    data = json.loads(updated)
    assert data["dependencies"] == {"axios": "^1.7.0", "zod": "^3.0.0"}
    assert data["name"] == "x"


def test_merge_extends_an_empty_multiline_recipient_dependencies(
    project_pair: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    donor, recipient = project_pair
    donor_manifest = donor / "frontend" / "package.json"
    donor_data = json.loads(donor_manifest.read_text())
    donor_data["devDependencies"] = {"axios": "^1.7.0"}
    donor_manifest.write_text(json.dumps(donor_data, indent=2) + "\n")
    recipient_manifest = recipient / "frontend" / "package.json"
    recipient_data = json.loads(recipient_manifest.read_text())
    recipient_data["devDependencies"] = {}
    recipient_manifest.write_text(
        json.dumps(recipient_data, indent=2).replace(
            '"devDependencies": {}', '"devDependencies": {\n  }'
        )
        + "\n"
    )

    report, _calls = _run_fresh_first(monkeypatch, donor, recipient)

    assert report.status == "ready", report.blockers
    merged = json.loads(recipient_manifest.read_text())
    assert merged["devDependencies"] == {"axios": "^1.7.0"}


def test_merge_ignores_nested_dependency_objects(
    project_pair: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A nested ``dependencies`` key must not capture the top-level merge."""
    donor, recipient = project_pair
    _add_frontend_dependencies(donor, dependencies={"axios": "^1.7.0"})
    manifest_path = recipient / "frontend" / "package.json"
    original = json.loads(manifest_path.read_text())
    nested_dependencies = {"left-pad": "^1.0.0"}
    rebuilt = {
        "pnpm": {
            "packageExtensions": {
                "some-package@*": {"dependencies": nested_dependencies},
            }
        },
        **original,
    }
    manifest_path.write_text(json.dumps(rebuilt, indent=2) + "\n")

    report, _calls = _run_fresh_first(monkeypatch, donor, recipient)

    assert report.status == "ready", report.blockers
    merged = json.loads(manifest_path.read_text())
    assert merged["dependencies"]["axios"] == "^1.7.0"
    assert (
        merged["pnpm"]["packageExtensions"]["some-package@*"]["dependencies"]
        == nested_dependencies
    )


def test_insert_dependency_entries_requires_the_section() -> None:
    with pytest.raises(ValueError, match="no top-level 'dependencies' section"):
        _insert_dependency_entries('{\n  "name": "x"\n}\n', "dependencies", {})
