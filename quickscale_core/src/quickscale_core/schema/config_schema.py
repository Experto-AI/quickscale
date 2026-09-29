"""Dataclasses and validation for quickscale.yml configuration files."""

import keyword
import re
from dataclasses import dataclass, field
from typing import Any

import yaml

from quickscale_core.contracts import (
    get_discovered_module_names,
    get_module_readiness_reason,
    sanitize_module_options,
)
from quickscale_core.utils.file_utils import validate_project_name
from quickscale_core.utils.theme_validation import (
    _CONFIG_LABEL,
    _validate_theme_value,
)


class ConfigValidationError(Exception):
    def __init__(
        self, message: str, line: int | None = None, suggestion: str | None = None
    ):
        self.message = message
        self.line = line
        self.suggestion = suggestion
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        parts = []
        if self.line:
            parts.append(f"Line {self.line}: {self.message}")
        else:
            parts.append(self.message)
        if self.suggestion:
            parts.append(f"  Suggestion: {self.suggestion}")
        return "\n".join(parts)


@dataclass
class ModuleConfig:
    name: str
    options: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.options = sanitize_module_options(self.name, self.options)


@dataclass
class ProjectConfig:
    slug: str
    package: str
    theme: str = "showcase_react"


@dataclass
class DockerConfig:
    start: bool = True
    build: bool = True
    create_superuser: bool = False


@dataclass
class QuickScaleConfig:
    version: str
    project: ProjectConfig
    modules: dict[str, ModuleConfig] = field(default_factory=dict)
    docker: DockerConfig = field(default_factory=DockerConfig)


# Valid keys at each level.
VALID_TOP_LEVEL_KEYS = {"version", "project", "modules", "docker"}
VALID_PROJECT_KEYS = {"slug", "package", "theme"}
VALID_DOCKER_KEYS = {"start", "build", "create_superuser"}
VALID_THEMES = {"showcase_react"}


def _find_line_number(yaml_content: str, key: str) -> int | None:
    for i, line in enumerate(yaml_content.splitlines(), start=1):
        if line.strip().startswith(f"{key}:") or f" {key}:" in line:
            return i
    return None


def _suggest_similar_key(invalid_key: str, valid_keys: set[str]) -> str | None:
    if not invalid_key:
        return None
    for valid_key in valid_keys:
        # Simple similarity check: same first letter and close length
        if (
            invalid_key[0].lower() == valid_key[0].lower()
            and abs(len(invalid_key) - len(valid_key)) <= 2
        ):
            return valid_key
    return None


def _validate_unknown_keys(
    data: dict, valid_keys: set[str], yaml_content: str, section_name: str = ""
) -> None:
    section_prefix = f" in {section_name} section" if section_name else ""
    for key in data.keys():
        if key not in valid_keys:
            line = _find_line_number(yaml_content, key)
            suggestion = _suggest_similar_key(key, valid_keys)
            suggestion_text = f"did you mean '{suggestion}'?" if suggestion else None
            raise ConfigValidationError(
                f"Unknown key '{key}'{section_prefix}",
                line=line,
                suggestion=suggestion_text,
            )


def _validate_version(data: dict, yaml_content: str) -> None:
    """Validate the version field."""
    if "version" not in data:
        raise ConfigValidationError(
            "Missing required key 'version'",
            suggestion="Add 'version: \"1\"' at the top of your configuration",
        )

    if data["version"] != "1":
        line = _find_line_number(yaml_content, "version")
        raise ConfigValidationError(
            f"Unsupported version '{data['version']}'",
            line=line,
            suggestion="Use 'version: \"1\"'",
        )


def _validate_package_name(package_name: str, yaml_content: str) -> None:
    """Validate Python package name field."""
    if not package_name:
        line = _find_line_number(yaml_content, "package")
        raise ConfigValidationError(
            "'project.package' must be a non-empty string",
            line=line,
        )

    if not package_name.isidentifier():
        line = _find_line_number(yaml_content, "package")
        raise ConfigValidationError(
            f"Invalid package name '{package_name}'",
            line=line,
            suggestion=(
                "Package must be a valid Python identifier using lowercase letters, "
                "numbers, and underscores"
            ),
        )

    if keyword.iskeyword(package_name):
        line = _find_line_number(yaml_content, "package")
        raise ConfigValidationError(
            f"Invalid package name '{package_name}'",
            line=line,
            suggestion=f"'{package_name}' is a Python keyword and cannot be used",
        )

    if not re.match(r"^[a-z][a-z0-9_]*$", package_name):
        line = _find_line_number(yaml_content, "package")
        raise ConfigValidationError(
            f"Invalid package name '{package_name}'",
            line=line,
            suggestion=(
                "Package must start with a lowercase letter and contain only "
                "lowercase letters, numbers, and underscores"
            ),
        )


def _project_mapping(data: dict, yaml_content: str) -> dict:
    if "project" not in data:
        raise ConfigValidationError(
            "Missing required key 'project'",
            suggestion=(
                "Add 'project:\n  slug: your-project\n  package: your_project\n"
                "  theme: showcase_react'"
            ),
        )

    project_data = data["project"]
    if not isinstance(project_data, dict):
        line = _find_line_number(yaml_content, "project")
        raise ConfigValidationError("'project' must be a mapping", line=line)

    return project_data


def _validate_project_identity(
    project_data: dict, yaml_content: str
) -> tuple[str, str]:
    _validate_unknown_keys(project_data, VALID_PROJECT_KEYS, yaml_content, "project")

    if "slug" not in project_data:
        line = _find_line_number(yaml_content, "project")
        raise ConfigValidationError(
            "Missing required key 'project.slug'",
            line=line,
            suggestion="Add 'slug: your-project-slug' under project",
        )

    if "package" not in project_data:
        line = _find_line_number(yaml_content, "project")
        raise ConfigValidationError(
            "Missing required key 'project.package'",
            line=line,
            suggestion="Add 'package: your_python_package' under project",
        )

    project_slug = project_data["slug"]
    if not isinstance(project_slug, str) or not project_slug:
        line = _find_line_number(yaml_content, "slug")
        raise ConfigValidationError(
            "'project.slug' must be a non-empty string", line=line
        )

    is_valid_slug, slug_error = validate_project_name(project_slug)
    if not is_valid_slug:
        line = _find_line_number(yaml_content, "slug")
        raise ConfigValidationError(
            f"Invalid project slug '{project_slug}'",
            line=line,
            suggestion=slug_error,
        )

    package_name = project_data["package"]
    if not isinstance(package_name, str):
        line = _find_line_number(yaml_content, "package")
        raise ConfigValidationError(
            "'project.package' must be a non-empty string",
            line=line,
        )
    _validate_package_name(package_name, yaml_content)

    return project_slug, package_name


def _validate_project_theme(project_data: dict, yaml_content: str) -> str:
    theme = project_data.get("theme", "showcase_react")
    try:
        _validate_theme_value(str(theme), _CONFIG_LABEL)
    except ValueError as exc:
        line = _find_line_number(yaml_content, "theme")
        if str(theme) == "showcase_html":
            suggestion = (
                "'showcase_html' has been retired. Use 'showcase_react' instead."
            )
        else:
            suggestion = (
                "Only 'showcase_react' is supported. Use 'showcase_react' instead."
            )
        raise ConfigValidationError(
            f"Unknown theme '{theme}'",
            line=line,
            suggestion=suggestion,
        ) from exc

    return str(theme)


def _validate_project_section(data: dict, yaml_content: str) -> tuple[str, str, str]:
    """Validate project section and return (slug, package, theme)."""
    project_data = _project_mapping(data, yaml_content)
    project_slug, package_name = _validate_project_identity(project_data, yaml_content)
    theme = _validate_project_theme(project_data, yaml_content)

    return project_slug, package_name, theme


def _validate_docker_section(data: dict, yaml_content: str) -> DockerConfig:
    """Validate docker section and return DockerConfig."""
    docker_data = data.get("docker", {})
    if not isinstance(docker_data, dict):
        line = _find_line_number(yaml_content, "docker")
        raise ConfigValidationError("'docker' must be a mapping", line=line)

    _validate_unknown_keys(docker_data, VALID_DOCKER_KEYS, yaml_content, "docker")

    docker_start = docker_data.get("start", True)
    docker_build = docker_data.get("build", True)
    docker_create_superuser = docker_data.get("create_superuser", False)

    if not isinstance(docker_start, bool):
        line = _find_line_number(yaml_content, "start")
        raise ConfigValidationError(
            "'docker.start' must be a boolean (true/false)", line=line
        )

    if not isinstance(docker_build, bool):
        line = _find_line_number(yaml_content, "build")
        raise ConfigValidationError(
            "'docker.build' must be a boolean (true/false)", line=line
        )

    if not isinstance(docker_create_superuser, bool):
        line = _find_line_number(yaml_content, "create_superuser")
        raise ConfigValidationError(
            "'docker.create_superuser' must be a boolean (true/false)",
            line=line,
        )

    return DockerConfig(
        start=docker_start,
        build=docker_build,
        create_superuser=docker_create_superuser,
    )


def _validate_declared_module_keys(
    module_name: str,
    module_options: dict[str, Any],
    yaml_content: str,
) -> None:
    """Refuse a module option key the module's manifest does not declare.

    A manifest's declared option set is the only option surface: a
    ``quickscale.yml`` key outside it is refused with the key named rather
    than silently dropped later.  The check judges the module's *canonicalized*
    keys: a legacy key the module's normalizer migrates (backups' and storage's
    raw credential keys) is consumed before this check, while a retired key
    already failed with the manifest's own removal message in the
    option-validation engine, which runs before this check.  A normalizer that
    refuses a key with its own authored message (a legacy notifications key)
    lets that message stand.
    """
    from quickscale_core.contracts.resolvers import (
        load_module_manifest_with_fallback,
    )

    if not module_options:
        return

    canonical = sanitize_module_options(module_name, module_options)
    manifest = load_module_manifest_with_fallback(module_name)
    declared = set(manifest.get_all_options())
    unknown = sorted(
        (
            key
            for key in canonical
            if key not in declared and key not in manifest.retired_options
        ),
        key=str,
    )
    if not unknown:
        return

    key = str(unknown[0])
    suggestion = _suggest_similar_key(key, declared)
    raise ConfigValidationError(
        f"Unknown key '{key}' in modules.{module_name} section",
        line=_find_line_number(yaml_content, key),
        suggestion=(
            f"Use modules.{module_name}.{suggestion} instead."
            if suggestion
            else "Supported keys: "
            + ", ".join(f"modules.{module_name}.{name}" for name in sorted(declared))
        ),
    )


def _manifest_option_issue(
    module_name: str,
    module_options: dict[str, Any],
) -> Any:
    """Return the first manifest-declared option issue for *module_name*.

    Loads the module's manifest through the source-then-bundled resolution
    contract (AF7) and runs the same option-validation engine the generated
    project's startup check will use, so a ``quickscale.yml`` value is judged
    by the constraints authored next to the option.  Values are first put
    through the module's canonicalization (``sanitize_module_options``), the
    same step ``ModuleConfig`` applies, so an alias or casing the CLI accepts
    is not rejected for a spelling the manifest names in canonical form.
    """
    from quickscale_core.contracts.resolvers import (
        load_module_manifest_with_fallback,
    )
    from quickscale_core.manifest.option_validation import (
        collect_option_validation_issues,
    )

    manifest = load_module_manifest_with_fallback(module_name)
    try:
        normalized = sanitize_module_options(module_name, module_options)
    except ConfigValidationError:
        # A retired key is the module normalizer's to name; the module's own
        # validator reports it with its authored guidance.  Check the values
        # that are still declared without its translation.
        normalized = dict(module_options)
    issues = collect_option_validation_issues(
        manifest, normalized, supplied=module_options
    )
    return issues[0] if issues else None


def _validate_modules_section(data: dict, yaml_content: str) -> dict[str, ModuleConfig]:
    """Validate modules section and return dict of ModuleConfig.

    Module discovery is performed lazily — only when the ``modules`` mapping
    is non-empty — so that import-time filesystem discovery is eliminated.

    Discovery uses :func:`get_discovered_module_names` which resolves source
    inventory first and falls back to authoritative bundled inventory.  If
    neither is available, :exc:`ImproperlyConfigured` propagates as a fail-hard
    validation error.
    """
    modules_data = data.get("modules", {})
    if not isinstance(modules_data, dict):
        line = _find_line_number(yaml_content, "modules")
        raise ConfigValidationError("'modules' must be a mapping", line=line)

    # Discover modules lazily only when there are entries to validate.
    if modules_data:
        _discovered = get_discovered_module_names()
        _available_modules: set[str] = set(_discovered)
        _ready_modules: set[str] = set(_discovered)
    else:
        _available_modules = set()
        _ready_modules = set()

    modules: dict[str, ModuleConfig] = {}
    for module_name, module_options in modules_data.items():
        if module_name not in _available_modules:
            line = _find_line_number(yaml_content, module_name)
            suggestion = _suggest_similar_key(module_name, _available_modules)
            suggestion_text = f"did you mean '{suggestion}'?" if suggestion else None
            raise ConfigValidationError(
                f"Unknown module '{module_name}'",
                line=line,
                suggestion=suggestion_text
                or f"Available modules: {', '.join(sorted(_available_modules))}",
            )

        if module_options is None:
            module_options = {}
        elif not isinstance(module_options, dict):
            line = _find_line_number(yaml_content, module_name)
            raise ConfigValidationError(
                f"Module '{module_name}' options must be a mapping or empty",
                line=line,
            )

        manifest_issue = _manifest_option_issue(module_name, module_options)
        if manifest_issue is not None:
            line = _find_line_number(yaml_content, manifest_issue.option_name)
            if line is None:
                line = _find_line_number(yaml_content, module_name)
            raise ConfigValidationError(
                manifest_issue.message,
                line=line,
                suggestion=(
                    f"Fix modules.{module_name}.{manifest_issue.option_name} in "
                    "quickscale.yml; the module manifest declares the allowed "
                    "values."
                ),
            )

        _validate_declared_module_keys(module_name, module_options, yaml_content)

        readiness_reason = get_module_readiness_reason(module_name)
        if readiness_reason is not None:
            line = _find_line_number(yaml_content, module_name)
            raise ConfigValidationError(
                readiness_reason,
                line=line,
                suggestion=(
                    "Remove it from quickscale.yml and choose a shipped module: "
                    + ", ".join(sorted(_ready_modules))
                ),
            )

        modules[module_name] = ModuleConfig(name=module_name, options=module_options)

    return modules


def validate_config(yaml_content: str) -> QuickScaleConfig:
    """Validate YAML content and return a QuickScaleConfig."""
    try:
        data = yaml.safe_load(yaml_content)
    except yaml.YAMLError as e:
        raise ConfigValidationError(f"Invalid YAML syntax: {e}") from e

    if not isinstance(data, dict):
        raise ConfigValidationError("Configuration must be a YAML mapping (dictionary)")

    _validate_unknown_keys(data, VALID_TOP_LEVEL_KEYS, yaml_content)
    _validate_version(data, yaml_content)

    project_slug, project_package, theme = _validate_project_section(data, yaml_content)
    docker_config = _validate_docker_section(data, yaml_content)
    modules = _validate_modules_section(data, yaml_content)

    return QuickScaleConfig(
        version=data["version"],
        project=ProjectConfig(
            slug=project_slug,
            package=project_package,
            theme=theme,
        ),
        modules=modules,
        docker=docker_config,
    )


def parse_config(yaml_content: str) -> QuickScaleConfig:
    """Parse and validate YAML configuration content."""
    return validate_config(yaml_content)


def generate_yaml(config: QuickScaleConfig) -> str:
    """Generate YAML string from a QuickScaleConfig object."""
    data: dict[str, Any] = {
        "version": config.version,
        "project": {
            "slug": config.project.slug,
            "package": config.project.package,
            "theme": config.project.theme,
        },
    }

    if config.modules:
        modules: dict[str, Any] = {}
        for name, module in config.modules.items():
            normalized_options = sanitize_module_options(name, module.options)
            modules[name] = normalized_options or None
        data["modules"] = modules

    data["docker"] = {
        "start": config.docker.start,
        "build": config.docker.build,
        "create_superuser": config.docker.create_superuser,
    }

    return yaml.dump(data, default_flow_style=False, sort_keys=False)
