"""QuickScale Configuration Schema

Dataclasses and validation for quickscale.yml configuration files.
Implements Terraform-style declarative project configuration.
"""

from dataclasses import dataclass, field
from typing import Any

import yaml


class ConfigValidationError(Exception):
    """Configuration validation error with line number context"""

    def __init__(
        self, message: str, line: int | None = None, suggestion: str | None = None
    ):
        self.message = message
        self.line = line
        self.suggestion = suggestion
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        """Format error message with line number and suggestion"""
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
    """Configuration for a single module"""

    name: str
    options: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProjectConfig:
    """Project-level configuration"""

    name: str
    theme: str = "showcase_html"


@dataclass
class DockerConfig:
    """Docker-related configuration"""

    start: bool = True
    build: bool = True


@dataclass
class QuickScaleConfig:
    """Complete QuickScale configuration from quickscale.yml"""

    version: str
    project: ProjectConfig
    modules: dict[str, ModuleConfig] = field(default_factory=dict)
    docker: DockerConfig = field(default_factory=DockerConfig)


# Valid keys at each level
VALID_TOP_LEVEL_KEYS = {"version", "project", "modules", "docker"}
VALID_PROJECT_KEYS = {"name", "theme"}
VALID_DOCKER_KEYS = {"start", "build"}
VALID_THEMES = {"showcase_html", "showcase_htmx", "showcase_react"}
AVAILABLE_MODULES = {"auth", "billing", "teams", "blog", "listings", "crm"}


def _find_line_number(yaml_content: str, key: str) -> int | None:
    """Find the line number where a key appears in YAML content"""
    for i, line in enumerate(yaml_content.splitlines(), start=1):
        if line.strip().startswith(f"{key}:") or f" {key}:" in line:
            return i
    return None


def _suggest_similar_key(invalid_key: str, valid_keys: set[str]) -> str | None:
    """Suggest a similar key from valid keys"""
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
    """Validate that all keys in data are in valid_keys."""
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


def _validate_project_section(data: dict, yaml_content: str) -> tuple[str, str]:
    """Validate project section and return (project_name, theme)."""
    if "project" not in data:
        raise ConfigValidationError(
            "Missing required key 'project'",
            suggestion="Add 'project:\\n  name: your_project_name\\n  theme: showcase_html'",
        )

    project_data = data.get("project", {})
    if not isinstance(project_data, dict):
        line = _find_line_number(yaml_content, "project")
        raise ConfigValidationError("'project' must be a mapping", line=line)

    _validate_unknown_keys(project_data, VALID_PROJECT_KEYS, yaml_content, "project")

    if "name" not in project_data:
        line = _find_line_number(yaml_content, "project")
        raise ConfigValidationError(
            "Missing required key 'project.name'",
            line=line,
            suggestion="Add 'name: your_project_name' under project",
        )

    project_name = project_data["name"]
    if not isinstance(project_name, str) or not project_name:
        line = _find_line_number(yaml_content, "name")
        raise ConfigValidationError(
            "'project.name' must be a non-empty string", line=line
        )

    if not project_name.isidentifier():
        line = _find_line_number(yaml_content, "name")
        raise ConfigValidationError(
            f"Invalid project name '{project_name}'",
            line=line,
            suggestion="Project name must be a valid Python identifier (letters, numbers, underscores, not starting with a number)",
        )

    theme = project_data.get("theme", "showcase_html")
    if theme not in VALID_THEMES:
        line = _find_line_number(yaml_content, "theme")
        raise ConfigValidationError(
            f"Unknown theme '{theme}'",
            line=line,
            suggestion=f"Available themes: {', '.join(sorted(VALID_THEMES))}",
        )

    return project_name, theme


def _validate_docker_section(data: dict, yaml_content: str) -> DockerConfig:
    """Validate docker section and return DockerConfig."""
    docker_data = data.get("docker", {})
    if not isinstance(docker_data, dict):
        line = _find_line_number(yaml_content, "docker")
        raise ConfigValidationError("'docker' must be a mapping", line=line)

    _validate_unknown_keys(docker_data, VALID_DOCKER_KEYS, yaml_content, "docker")

    docker_start = docker_data.get("start", True)
    docker_build = docker_data.get("build", True)

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

    return DockerConfig(start=docker_start, build=docker_build)


def _validate_modules_section(data: dict, yaml_content: str) -> dict[str, ModuleConfig]:
    """Validate modules section and return dict of ModuleConfig."""
    modules_data = data.get("modules", {})
    if not isinstance(modules_data, dict):
        line = _find_line_number(yaml_content, "modules")
        raise ConfigValidationError("'modules' must be a mapping", line=line)

    modules: dict[str, ModuleConfig] = {}
    for module_name, module_options in modules_data.items():
        if module_name not in AVAILABLE_MODULES:
            line = _find_line_number(yaml_content, module_name)
            suggestion = _suggest_similar_key(module_name, AVAILABLE_MODULES)
            suggestion_text = f"did you mean '{suggestion}'?" if suggestion else None
            raise ConfigValidationError(
                f"Unknown module '{module_name}'",
                line=line,
                suggestion=suggestion_text
                or f"Available modules: {', '.join(sorted(AVAILABLE_MODULES))}",
            )

        if module_options is None:
            module_options = {}
        elif not isinstance(module_options, dict):
            line = _find_line_number(yaml_content, module_name)
            raise ConfigValidationError(
                f"Module '{module_name}' options must be a mapping or empty",
                line=line,
            )

        modules[module_name] = ModuleConfig(name=module_name, options=module_options)

    return modules


def validate_config(yaml_content: str) -> QuickScaleConfig:
    """Validate YAML content and return a QuickScaleConfig

    Args:
        yaml_content: Raw YAML string

    Returns:
        QuickScaleConfig: Validated configuration object

    Raises:
        ConfigValidationError: If validation fails with helpful error message

    """
    try:
        data = yaml.safe_load(yaml_content)
    except yaml.YAMLError as e:
        raise ConfigValidationError(f"Invalid YAML syntax: {e}") from e

    if not isinstance(data, dict):
        raise ConfigValidationError("Configuration must be a YAML mapping (dictionary)")

    # Validate top-level structure
    _validate_unknown_keys(data, VALID_TOP_LEVEL_KEYS, yaml_content)
    _validate_version(data, yaml_content)

    # Validate each section
    project_name, theme = _validate_project_section(data, yaml_content)
    docker_config = _validate_docker_section(data, yaml_content)
    modules = _validate_modules_section(data, yaml_content)

    return QuickScaleConfig(
        version=data["version"],
        project=ProjectConfig(name=project_name, theme=theme),
        modules=modules,
        docker=docker_config,
    )


def parse_config(yaml_content: str) -> QuickScaleConfig:
    """Parse and validate YAML configuration content

    Alias for validate_config for semantic clarity.
    """
    return validate_config(yaml_content)


def generate_yaml(config: QuickScaleConfig) -> str:
    """Generate YAML string from a QuickScaleConfig object

    Args:
        config: QuickScaleConfig object

    Returns:
        YAML string representation

    """
    data: dict[str, Any] = {
        "version": config.version,
        "project": {
            "name": config.project.name,
            "theme": config.project.theme,
        },
    }

    if config.modules:
        data["modules"] = {
            name: module.options if module.options else None
            for name, module in config.modules.items()
        }

    data["docker"] = {
        "start": config.docker.start,
        "build": config.docker.build,
    }

    return yaml.dump(data, default_flow_style=False, sort_keys=False)
