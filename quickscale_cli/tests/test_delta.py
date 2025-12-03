"""Tests for delta detection"""

from quickscale_cli.schema.config_schema import (
    DockerConfig,
    ModuleConfig,
    ProjectConfig,
    QuickScaleConfig,
)
from quickscale_cli.schema.delta import compute_delta, format_delta
from quickscale_cli.schema.state_schema import (
    ModuleState,
    ProjectState,
    QuickScaleState,
)


class TestComputeDelta:
    """Tests for compute_delta function"""

    def test_delta_no_state_new_project(self):
        """Test delta computation for a new project with no existing state"""
        # Desired config
        config = QuickScaleConfig(
            version="1",
            project=ProjectConfig(name="myapp", theme="showcase_html"),
            modules={
                "auth": ModuleConfig(name="auth", options={}),
                "blog": ModuleConfig(name="blog", options={}),
            },
            docker=DockerConfig(start=True, build=True),
        )

        # No existing state
        delta = compute_delta(config, None)

        assert delta.has_changes is True
        assert set(delta.modules_to_add) == {"auth", "blog"}
        assert delta.modules_to_remove == []
        assert delta.modules_unchanged == []
        assert delta.theme_changed is False
        assert delta.new_theme == "showcase_html"

    def test_delta_no_changes(self):
        """Test delta computation when config matches state"""
        # Desired config
        config = QuickScaleConfig(
            version="1",
            project=ProjectConfig(name="myapp", theme="showcase_html"),
            modules={
                "auth": ModuleConfig(name="auth", options={}),
            },
            docker=DockerConfig(start=True, build=True),
        )

        # Existing state matches config
        state = QuickScaleState(
            version="1",
            project=ProjectState(name="myapp", theme="showcase_html"),
            modules={
                "auth": ModuleState(name="auth", options={}),
            },
        )

        delta = compute_delta(config, state)

        assert delta.has_changes is False
        assert delta.modules_to_add == []
        assert delta.modules_to_remove == []
        assert set(delta.modules_unchanged) == {"auth"}
        assert delta.theme_changed is False

    def test_delta_add_modules(self):
        """Test delta computation when adding new modules"""
        # Desired config with new module
        config = QuickScaleConfig(
            version="1",
            project=ProjectConfig(name="myapp", theme="showcase_html"),
            modules={
                "auth": ModuleConfig(name="auth", options={}),
                "blog": ModuleConfig(name="blog", options={}),
            },
            docker=DockerConfig(start=True, build=True),
        )

        # Existing state without blog module
        state = QuickScaleState(
            version="1",
            project=ProjectState(name="myapp", theme="showcase_html"),
            modules={
                "auth": ModuleState(name="auth", options={}),
            },
        )

        delta = compute_delta(config, state)

        assert delta.has_changes is True
        assert set(delta.modules_to_add) == {"blog"}
        assert delta.modules_to_remove == []
        assert set(delta.modules_unchanged) == {"auth"}
        assert delta.theme_changed is False

    def test_delta_remove_modules(self):
        """Test delta computation when removing modules"""
        # Desired config without blog module
        config = QuickScaleConfig(
            version="1",
            project=ProjectConfig(name="myapp", theme="showcase_html"),
            modules={
                "auth": ModuleConfig(name="auth", options={}),
            },
            docker=DockerConfig(start=True, build=True),
        )

        # Existing state with blog module
        state = QuickScaleState(
            version="1",
            project=ProjectState(name="myapp", theme="showcase_html"),
            modules={
                "auth": ModuleState(name="auth", options={}),
                "blog": ModuleState(name="blog", options={}),
            },
        )

        delta = compute_delta(config, state)

        assert delta.has_changes is True
        assert delta.modules_to_add == []
        assert set(delta.modules_to_remove) == {"blog"}
        assert set(delta.modules_unchanged) == {"auth"}
        assert delta.theme_changed is False

    def test_delta_theme_change(self):
        """Test delta computation when theme changes"""
        # Desired config with different theme
        config = QuickScaleConfig(
            version="1",
            project=ProjectConfig(name="myapp", theme="showcase_htmx"),
            modules={
                "auth": ModuleConfig(name="auth", options={}),
            },
            docker=DockerConfig(start=True, build=True),
        )

        # Existing state with different theme
        state = QuickScaleState(
            version="1",
            project=ProjectState(name="myapp", theme="showcase_html"),
            modules={
                "auth": ModuleState(name="auth", options={}),
            },
        )

        delta = compute_delta(config, state)

        assert delta.has_changes is True
        assert delta.modules_to_add == []
        assert delta.modules_to_remove == []
        assert set(delta.modules_unchanged) == {"auth"}
        assert delta.theme_changed is True
        assert delta.old_theme == "showcase_html"
        assert delta.new_theme == "showcase_htmx"

    def test_delta_multiple_changes(self):
        """Test delta computation with multiple changes"""
        # Desired config
        config = QuickScaleConfig(
            version="1",
            project=ProjectConfig(name="myapp", theme="showcase_html"),
            modules={
                "auth": ModuleConfig(name="auth", options={}),
                "listings": ModuleConfig(name="listings", options={}),
            },
            docker=DockerConfig(start=True, build=True),
        )

        # Existing state
        state = QuickScaleState(
            version="1",
            project=ProjectState(name="myapp", theme="showcase_html"),
            modules={
                "auth": ModuleState(name="auth", options={}),
                "blog": ModuleState(name="blog", options={}),
            },
        )

        delta = compute_delta(config, state)

        assert delta.has_changes is True
        assert set(delta.modules_to_add) == {"listings"}
        assert set(delta.modules_to_remove) == {"blog"}
        assert set(delta.modules_unchanged) == {"auth"}
        assert delta.theme_changed is False


class TestFormatDelta:
    """Tests for format_delta function"""

    def test_format_no_changes(self):
        """Test formatting delta with no changes"""
        # Create delta with no changes
        config = QuickScaleConfig(
            version="1",
            project=ProjectConfig(name="myapp", theme="showcase_html"),
            modules={
                "auth": ModuleConfig(name="auth", options={}),
            },
            docker=DockerConfig(start=True, build=True),
        )
        state = QuickScaleState(
            version="1",
            project=ProjectState(name="myapp", theme="showcase_html"),
            modules={
                "auth": ModuleState(name="auth", options={}),
            },
        )
        delta = compute_delta(config, state)

        formatted = format_delta(delta)

        assert "No changes detected" in formatted
        assert "Configuration matches applied state" in formatted

    def test_format_add_modules(self):
        """Test formatting delta with modules to add"""
        config = QuickScaleConfig(
            version="1",
            project=ProjectConfig(name="myapp", theme="showcase_html"),
            modules={
                "auth": ModuleConfig(name="auth", options={}),
                "blog": ModuleConfig(name="blog", options={}),
            },
            docker=DockerConfig(start=True, build=True),
        )
        state = QuickScaleState(
            version="1",
            project=ProjectState(name="myapp", theme="showcase_html"),
            modules={
                "auth": ModuleState(name="auth", options={}),
            },
        )
        delta = compute_delta(config, state)

        formatted = format_delta(delta)

        assert "Changes to apply:" in formatted
        assert "Modules to add" in formatted
        assert "+ blog" in formatted
        assert "Modules unchanged" in formatted
        assert "auth" in formatted

    def test_format_remove_modules(self):
        """Test formatting delta with modules to remove"""
        config = QuickScaleConfig(
            version="1",
            project=ProjectConfig(name="myapp", theme="showcase_html"),
            modules={
                "auth": ModuleConfig(name="auth", options={}),
            },
            docker=DockerConfig(start=True, build=True),
        )
        state = QuickScaleState(
            version="1",
            project=ProjectState(name="myapp", theme="showcase_html"),
            modules={
                "auth": ModuleState(name="auth", options={}),
                "blog": ModuleState(name="blog", options={}),
            },
        )
        delta = compute_delta(config, state)

        formatted = format_delta(delta)

        assert "Changes to apply:" in formatted
        assert "Modules to remove" in formatted
        assert "- blog" in formatted

    def test_format_theme_change(self):
        """Test formatting delta with theme change"""
        config = QuickScaleConfig(
            version="1",
            project=ProjectConfig(name="myapp", theme="showcase_htmx"),
            modules={},
            docker=DockerConfig(start=True, build=True),
        )
        state = QuickScaleState(
            version="1",
            project=ProjectState(name="myapp", theme="showcase_html"),
            modules={},
        )
        delta = compute_delta(config, state)

        formatted = format_delta(delta)

        assert "Changes to apply:" in formatted
        assert "Theme:" in formatted
        assert "showcase_html" in formatted
        assert "showcase_htmx" in formatted
        assert "WARNING" in formatted
