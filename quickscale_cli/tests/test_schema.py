"""Tests for QuickScale configuration schema validation"""

import pytest

from quickscale_cli.schema.config_schema import (
    ConfigValidationError,
    DockerConfig,
    ModuleConfig,
    ProjectConfig,
    QuickScaleConfig,
    generate_yaml,
    parse_config,
    validate_config,
)


class TestValidConfigParsing:
    """Tests for valid configuration parsing"""

    def test_minimal_valid_config(self):
        """Test parsing minimal valid configuration"""
        yaml_content = """
version: "1"
project:
  name: myapp
  theme: showcase_html
"""
        config = validate_config(yaml_content)

        assert config.version == "1"
        assert config.project.name == "myapp"
        assert config.project.theme == "showcase_html"
        assert config.modules == {}
        assert config.docker.start is True
        assert config.docker.build is True

    def test_full_config_with_modules(self):
        """Test parsing full configuration with modules"""
        yaml_content = """
version: "1"
project:
  name: myproject
  theme: showcase_html
modules:
  auth:
    registration: true
    email_verification: false
  blog:
    posts_per_page: 10
docker:
  start: true
  build: false
"""
        config = validate_config(yaml_content)

        assert config.project.name == "myproject"
        assert "auth" in config.modules
        assert "blog" in config.modules
        assert config.modules["auth"].options["registration"] is True
        assert config.modules["blog"].options["posts_per_page"] == 10
        assert config.docker.start is True
        assert config.docker.build is False

    def test_config_with_empty_modules(self):
        """Test config with modules section but empty options"""
        yaml_content = """
version: "1"
project:
  name: myapp
  theme: showcase_html
modules:
  auth:
  listings:
"""
        config = validate_config(yaml_content)

        assert "auth" in config.modules
        assert "listings" in config.modules
        assert config.modules["auth"].options == {}
        assert config.modules["listings"].options == {}

    def test_config_without_docker(self):
        """Test config without docker section uses defaults"""
        yaml_content = """
version: "1"
project:
  name: myapp
"""
        config = validate_config(yaml_content)

        assert config.docker.start is True
        assert config.docker.build is True

    def test_config_with_docker_disabled(self):
        """Test config with docker disabled"""
        yaml_content = """
version: "1"
project:
  name: myapp
docker:
  start: false
  build: false
"""
        config = validate_config(yaml_content)

        assert config.docker.start is False
        assert config.docker.build is False

    def test_all_valid_modules(self):
        """Test that all valid modules are accepted"""
        yaml_content = """
version: "1"
project:
  name: myapp
modules:
  auth:
  billing:
  teams:
  blog:
  listings:
"""
        config = validate_config(yaml_content)

        assert len(config.modules) == 5
        assert set(config.modules.keys()) == {
            "auth",
            "billing",
            "teams",
            "blog",
            "listings",
        }

    def test_all_valid_themes(self):
        """Test that all valid themes are accepted"""
        for theme in ["showcase_html", "showcase_htmx", "showcase_react"]:
            yaml_content = f"""
version: "1"
project:
  name: myapp
  theme: {theme}
"""
            config = validate_config(yaml_content)
            assert config.project.theme == theme

    def test_parse_config_alias(self):
        """Test that parse_config is an alias for validate_config"""
        yaml_content = """
version: "1"
project:
  name: myapp
"""
        config = parse_config(yaml_content)
        assert config.project.name == "myapp"


class TestInvalidConfigErrors:
    """Tests for configuration validation errors"""

    def test_missing_version(self):
        """Test error for missing version"""
        yaml_content = """
project:
  name: myapp
"""
        with pytest.raises(ConfigValidationError) as exc:
            validate_config(yaml_content)

        assert "Missing required key 'version'" in str(exc.value)
        assert "Add 'version:" in str(exc.value)

    def test_unsupported_version(self):
        """Test error for unsupported version"""
        yaml_content = """
version: "2"
project:
  name: myapp
"""
        with pytest.raises(ConfigValidationError) as exc:
            validate_config(yaml_content)

        assert "Unsupported version '2'" in str(exc.value)
        assert "Line" in str(exc.value)  # Should have line number

    def test_missing_project(self):
        """Test error for missing project section"""
        yaml_content = """
version: "1"
"""
        with pytest.raises(ConfigValidationError) as exc:
            validate_config(yaml_content)

        assert "Missing required key 'project'" in str(exc.value)

    def test_missing_project_name(self):
        """Test error for missing project.name"""
        yaml_content = """
version: "1"
project:
  theme: showcase_html
"""
        with pytest.raises(ConfigValidationError) as exc:
            validate_config(yaml_content)

        assert "Missing required key 'project.name'" in str(exc.value)

    def test_invalid_project_name(self):
        """Test error for invalid project name"""
        yaml_content = """
version: "1"
project:
  name: 123invalid
"""
        with pytest.raises(ConfigValidationError) as exc:
            validate_config(yaml_content)

        assert "Invalid project name '123invalid'" in str(exc.value)
        assert "Python identifier" in str(exc.value)

    def test_empty_project_name(self):
        """Test error for empty project name"""
        yaml_content = """
version: "1"
project:
  name: ""
"""
        with pytest.raises(ConfigValidationError) as exc:
            validate_config(yaml_content)

        assert "non-empty string" in str(exc.value)

    def test_unknown_theme(self):
        """Test error for unknown theme"""
        yaml_content = """
version: "1"
project:
  name: myapp
  theme: unknown_theme
"""
        with pytest.raises(ConfigValidationError) as exc:
            validate_config(yaml_content)

        assert "Unknown theme 'unknown_theme'" in str(exc.value)
        assert "Available themes" in str(exc.value)

    def test_unknown_module(self):
        """Test error for unknown module"""
        yaml_content = """
version: "1"
project:
  name: myapp
modules:
  unknown_module:
"""
        with pytest.raises(ConfigValidationError) as exc:
            validate_config(yaml_content)

        assert "Unknown module 'unknown_module'" in str(exc.value)

    def test_unknown_top_level_key(self):
        """Test error for unknown top-level key"""
        yaml_content = """
version: "1"
project:
  name: myapp
unknown_key: value
"""
        with pytest.raises(ConfigValidationError) as exc:
            validate_config(yaml_content)

        assert "Unknown key 'unknown_key'" in str(exc.value)

    def test_unknown_project_key(self):
        """Test error for unknown key in project section"""
        yaml_content = """
version: "1"
project:
  name: myapp
  unknown_option: value
"""
        with pytest.raises(ConfigValidationError) as exc:
            validate_config(yaml_content)

        assert "Unknown key 'unknown_option' in project section" in str(exc.value)

    def test_unknown_docker_key(self):
        """Test error for unknown key in docker section"""
        yaml_content = """
version: "1"
project:
  name: myapp
docker:
  unknown_docker_option: true
"""
        with pytest.raises(ConfigValidationError) as exc:
            validate_config(yaml_content)

        assert "Unknown key 'unknown_docker_option' in docker section" in str(exc.value)

    def test_invalid_yaml_syntax(self):
        """Test error for invalid YAML syntax"""
        yaml_content = """
version: "1"
project:
  name: myapp
  invalid: [unclosed bracket
"""
        with pytest.raises(ConfigValidationError) as exc:
            validate_config(yaml_content)

        assert "Invalid YAML syntax" in str(exc.value)

    def test_non_dict_root(self):
        """Test error when YAML root is not a dict"""
        yaml_content = "just a string"

        with pytest.raises(ConfigValidationError) as exc:
            validate_config(yaml_content)

        assert "must be a YAML mapping" in str(exc.value)

    def test_docker_start_not_bool(self):
        """Test error when docker.start is not a boolean"""
        yaml_content = """
version: "1"
project:
  name: myapp
docker:
  start: "yes"
"""
        with pytest.raises(ConfigValidationError) as exc:
            validate_config(yaml_content)

        assert "'docker.start' must be a boolean" in str(exc.value)

    def test_docker_build_not_bool(self):
        """Test error when docker.build is not a boolean"""
        yaml_content = """
version: "1"
project:
  name: myapp
docker:
  build: 1
"""
        with pytest.raises(ConfigValidationError) as exc:
            validate_config(yaml_content)

        assert "'docker.build' must be a boolean" in str(exc.value)


class TestLineNumberErrors:
    """Tests for error messages with line numbers"""

    def test_error_includes_line_number(self):
        """Test that errors include line numbers"""
        yaml_content = """version: "1"
project:
  name: myapp
moduels:
  auth:
"""
        with pytest.raises(ConfigValidationError) as exc:
            validate_config(yaml_content)

        assert "Line 4" in str(exc.value)
        assert "moduels" in str(exc.value)

    def test_typo_suggestion_modules(self):
        """Test suggestion for typo in 'modules'"""
        yaml_content = """
version: "1"
project:
  name: myapp
moduels:
  auth:
"""
        with pytest.raises(ConfigValidationError) as exc:
            validate_config(yaml_content)

        assert "did you mean 'modules'" in str(exc.value)


class TestConfigValidationErrorClass:
    """Tests for ConfigValidationError class"""

    def test_error_with_line_only(self):
        """Test error formatting with line number only"""
        error = ConfigValidationError("test message", line=5)
        assert "Line 5: test message" in str(error)

    def test_error_with_suggestion_only(self):
        """Test error formatting with suggestion only"""
        error = ConfigValidationError("test message", suggestion="try this")
        assert "test message" in str(error)
        assert "Suggestion: try this" in str(error)

    def test_error_with_line_and_suggestion(self):
        """Test error formatting with both line and suggestion"""
        error = ConfigValidationError("test message", line=5, suggestion="try this")
        assert "Line 5: test message" in str(error)
        assert "Suggestion: try this" in str(error)

    def test_error_attributes(self):
        """Test that error attributes are accessible"""
        error = ConfigValidationError("msg", line=10, suggestion="hint")
        assert error.message == "msg"
        assert error.line == 10
        assert error.suggestion == "hint"


class TestGenerateYaml:
    """Tests for YAML generation from config objects"""

    def test_generate_minimal_config(self):
        """Test generating YAML from minimal config"""
        config = QuickScaleConfig(
            version="1",
            project=ProjectConfig(name="myapp", theme="showcase_html"),
            modules={},
            docker=DockerConfig(start=True, build=True),
        )
        yaml_output = generate_yaml(config)

        # Parse it back and verify
        parsed = validate_config(yaml_output)
        assert parsed.project.name == "myapp"
        assert parsed.project.theme == "showcase_html"

    def test_generate_config_with_modules(self):
        """Test generating YAML with modules"""
        config = QuickScaleConfig(
            version="1",
            project=ProjectConfig(name="myapp", theme="showcase_html"),
            modules={
                "auth": ModuleConfig(name="auth", options={"registration": True}),
                "blog": ModuleConfig(name="blog", options={}),
            },
            docker=DockerConfig(start=False, build=False),
        )
        yaml_output = generate_yaml(config)

        # Parse it back and verify
        parsed = validate_config(yaml_output)
        assert "auth" in parsed.modules
        assert "blog" in parsed.modules
        assert parsed.docker.start is False

    def test_roundtrip_config(self):
        """Test that generate_yaml -> validate_config is lossless"""
        original = QuickScaleConfig(
            version="1",
            project=ProjectConfig(name="testproject", theme="showcase_htmx"),
            modules={
                "auth": ModuleConfig(name="auth", options={"key": "value"}),
            },
            docker=DockerConfig(start=True, build=False),
        )
        yaml_output = generate_yaml(original)
        parsed = validate_config(yaml_output)

        assert parsed.version == original.version
        assert parsed.project.name == original.project.name
        assert parsed.project.theme == original.project.theme
        assert set(parsed.modules.keys()) == set(original.modules.keys())
        assert parsed.docker.start == original.docker.start
        assert parsed.docker.build == original.docker.build


class TestDataclasses:
    """Tests for dataclass behavior"""

    def test_module_config_defaults(self):
        """Test ModuleConfig default values"""
        config = ModuleConfig(name="test")
        assert config.name == "test"
        assert config.options == {}

    def test_project_config_defaults(self):
        """Test ProjectConfig default values"""
        config = ProjectConfig(name="test")
        assert config.name == "test"
        assert config.theme == "showcase_html"

    def test_docker_config_defaults(self):
        """Test DockerConfig default values"""
        config = DockerConfig()
        assert config.start is True
        assert config.build is True

    def test_quickscale_config_defaults(self):
        """Test QuickScaleConfig default values"""
        config = QuickScaleConfig(
            version="1",
            project=ProjectConfig(name="test"),
        )
        assert config.modules == {}
        assert isinstance(config.docker, DockerConfig)
