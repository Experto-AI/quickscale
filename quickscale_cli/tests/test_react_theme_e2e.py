"""
End-to-end tests for React theme (showcase_react) from user perspective.

These tests verify the complete workflow a user would experience:
1. Plan project with React theme
2. Apply the plan to generate project
3. Verify frontend structure and configuration
4. (Optional) Run pnpm install and build

Run with: pytest -m e2e
Note: Some tests require pnpm to be installed
"""

import json
import os
import subprocess

import pytest
from click.testing import CliRunner

from quickscale_cli.main import cli
from quickscale_core.generator import ProjectGenerator


@pytest.mark.e2e
class TestReactThemeUserWorkflow:
    """End-to-end tests for React theme user workflow."""

    @pytest.fixture
    def runner(self):
        """Create CLI runner for tests"""
        return CliRunner()

    def test_plan_apply_react_theme_workflow(self, tmp_path, runner):
        """
        Test complete user workflow: plan → apply with React theme.

        Simulates what a user does to create a new project with React theme.
        """
        project_name = "myreactapp"

        with runner.isolated_filesystem(temp_dir=tmp_path):
            # Step 1: Plan the project (creates quickscale.yml)
            # Provide input: theme=1 (showcase_react), no modules, docker start=N, save=Y
            result = runner.invoke(cli, ["plan", project_name], input="1\n\nN\nY\n")
            assert result.exit_code == 0, f"plan failed: {result.output}"
            # Default theme is showcase_react
            assert "showcase_react" in result.output

            # Verify quickscale.yml was created in project directory
            assert os.path.exists(os.path.join(project_name, "quickscale.yml"))

            # Step 2: Change to project directory and apply
            os.chdir(project_name)
            # Apply needs confirmation with "Y"
            result = runner.invoke(cli, ["apply", "--no-docker"], input="Y\n")
            assert result.exit_code == 0, f"apply failed: {result.output}"

            # Step 3: Verify project structure (we're already in project_name dir)
            # Check Django structure
            assert os.path.exists("manage.py")
            assert os.path.exists("docker-compose.yml")
            assert os.path.exists("Dockerfile")

            # Check frontend structure
            assert os.path.isdir("frontend")
            assert os.path.exists("frontend/package.json")
            assert os.path.exists("frontend/vite.config.ts")
            assert os.path.exists("frontend/tsconfig.json")
            assert os.path.exists("frontend/src/App.tsx")
            assert os.path.exists("frontend/src/main.tsx")

    def test_generated_react_project_structure_complete(self, tmp_path):
        """
        Verify generated React project has all required files.

        This tests from the user's perspective what they would expect
        after running quickscale commands.
        """
        generator = ProjectGenerator(theme="showcase_react")
        project_name = "user_react_project"
        project_path = tmp_path / project_name

        generator.generate(project_name, project_path)

        # ===============================
        # Backend (Django) verification
        # ===============================
        assert (project_path / "manage.py").exists()
        assert (project_path / "pyproject.toml").exists()
        assert (project_path / "docker-compose.yml").exists()
        assert (project_path / "Dockerfile").exists()
        assert (project_path / ".env.example").exists()

        # Core app structure (named after project)
        core_app = project_path / project_name
        assert core_app.is_dir()
        # Settings is a package (directory)
        assert (core_app / "settings").is_dir()
        assert (core_app / "settings" / "base.py").exists()
        assert (core_app / "urls.py").exists()
        assert (core_app / "wsgi.py").exists()

        # ===============================
        # Frontend (React) verification
        # ===============================
        frontend = project_path / "frontend"
        assert frontend.is_dir()

        # Package management
        assert (frontend / "package.json").exists()

        # Build tooling
        assert (frontend / "vite.config.ts").exists()

        # TypeScript configuration
        assert (frontend / "tsconfig.json").exists()

        # Styling
        assert (frontend / "tailwind.config.js").exists()
        assert (frontend / "postcss.config.js").exists()

        # shadcn/ui configuration
        assert (frontend / "components.json").exists()

        # Source files
        src = frontend / "src"
        assert src.is_dir()
        assert (src / "main.tsx").exists()
        assert (src / "App.tsx").exists()
        assert (src / "index.css").exists()

        # Component utilities (shadcn/ui)
        assert (src / "lib" / "utils.ts").exists()

        # Components directory
        assert (src / "components").is_dir()

    def test_package_json_valid_and_complete(self, tmp_path):
        """
        Verify package.json is valid JSON with all required fields.

        Users should be able to run 'pnpm install' without errors.
        """
        generator = ProjectGenerator(theme="showcase_react")
        project_name = "pkg_json_test"
        project_path = tmp_path / project_name

        generator.generate(project_name, project_path)

        package_json_path = project_path / "frontend" / "package.json"
        assert package_json_path.exists()

        # Parse JSON (should not raise)
        with open(package_json_path) as f:
            package = json.load(f)

        # Required fields
        assert "name" in package
        assert "version" in package
        assert "scripts" in package
        assert "dependencies" in package
        assert "devDependencies" in package

        # Required scripts
        scripts = package["scripts"]
        assert "dev" in scripts
        assert "build" in scripts
        assert "test" in scripts

        # Essential dependencies
        deps = package["dependencies"]
        assert "react" in deps
        assert "react-dom" in deps
        assert "react-router-dom" in deps

        # Essential devDependencies
        dev_deps = package["devDependencies"]
        assert "typescript" in dev_deps
        assert "vite" in dev_deps

    def test_vite_config_valid_typescript(self, tmp_path):
        """Verify vite.config.ts is valid TypeScript syntax"""
        generator = ProjectGenerator(theme="showcase_react")
        project_name = "vite_config_test"
        project_path = tmp_path / project_name

        generator.generate(project_name, project_path)

        vite_config_path = project_path / "frontend" / "vite.config.ts"
        assert vite_config_path.exists()

        content = vite_config_path.read_text()

        # Should have proper imports
        assert "import" in content
        assert "defineConfig" in content

        # Should export default config
        assert "export default" in content

        # Should have React plugin
        assert "react" in content.lower()

    def test_tsconfig_valid_json(self, tmp_path):
        """Verify tsconfig.json exists and has required content"""
        generator = ProjectGenerator(theme="showcase_react")
        project_name = "tsconfig_test"
        project_path = tmp_path / project_name

        generator.generate(project_name, project_path)

        tsconfig_path = project_path / "frontend" / "tsconfig.json"
        assert tsconfig_path.exists()

        content = tsconfig_path.read_text()
        assert "compilerOptions" in content
        assert "strict" in content

    def test_components_json_valid_shadcn_config(self, tmp_path):
        """Verify components.json is valid shadcn/ui configuration"""
        generator = ProjectGenerator(theme="showcase_react")
        project_name = "shadcn_config_test"
        project_path = tmp_path / project_name

        generator.generate(project_name, project_path)

        components_json_path = project_path / "frontend" / "components.json"
        assert components_json_path.exists()

        # Parse JSON (should not raise)
        with open(components_json_path) as f:
            config = json.load(f)

        # shadcn/ui required fields
        assert "style" in config
        assert "aliases" in config


@pytest.mark.e2e
class TestReactThemePnpmIntegration:
    """Tests requiring pnpm to be installed"""

    @pytest.fixture
    def pnpm_available(self):
        """Check if pnpm is available"""
        try:
            result = subprocess.run(
                ["pnpm", "--version"],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                pytest.skip("pnpm is not installed")
        except FileNotFoundError:
            pytest.skip("pnpm is not installed")

    def test_pnpm_install_succeeds(self, tmp_path, pnpm_available):
        """
        Verify 'pnpm install' succeeds with generated package.json.

        This is what a user would do after project generation.
        """
        generator = ProjectGenerator(theme="showcase_react")
        project_name = "pnpm_install_test"
        project_path = tmp_path / project_name

        generator.generate(project_name, project_path)

        frontend_path = project_path / "frontend"

        # Run pnpm install
        result = subprocess.run(
            ["pnpm", "install"],
            cwd=frontend_path,
            capture_output=True,
            text=True,
            timeout=120,  # 2 minutes for install
        )

        assert result.returncode == 0, f"pnpm install failed: {result.stderr}"

        # Verify node_modules created
        assert (frontend_path / "node_modules").is_dir()

        # Verify lockfile created
        assert (frontend_path / "pnpm-lock.yaml").exists()

    def test_pnpm_type_check_succeeds(self, tmp_path, pnpm_available):
        """
        Verify TypeScript compilation succeeds after install.

        Users expect 'pnpm run type-check' to pass.
        """
        generator = ProjectGenerator(theme="showcase_react")
        project_name = "type_check_test"
        project_path = tmp_path / project_name

        generator.generate(project_name, project_path)

        frontend_path = project_path / "frontend"

        # First install dependencies
        install_result = subprocess.run(
            ["pnpm", "install"],
            cwd=frontend_path,
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert (
            install_result.returncode == 0
        ), f"pnpm install failed: {install_result.stderr}"

        # Check if type-check script exists
        with open(frontend_path / "package.json") as f:
            package = json.load(f)

        if "type-check" in package.get("scripts", {}):
            # Run type check
            result = subprocess.run(
                ["pnpm", "run", "type-check"],
                cwd=frontend_path,
                capture_output=True,
                text=True,
                timeout=60,
            )
            assert result.returncode == 0, f"Type check failed: {result.stderr}"

    def test_pnpm_lint_succeeds(self, tmp_path, pnpm_available):
        """
        Verify linting succeeds after install.

        Users expect 'pnpm run lint' to pass (or at least not have broken config).
        """
        generator = ProjectGenerator(theme="showcase_react")
        project_name = "lint_test"
        project_path = tmp_path / project_name

        generator.generate(project_name, project_path)

        frontend_path = project_path / "frontend"

        # First install dependencies
        install_result = subprocess.run(
            ["pnpm", "install"],
            cwd=frontend_path,
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert (
            install_result.returncode == 0
        ), f"pnpm install failed: {install_result.stderr}"

        # Run lint
        result = subprocess.run(
            ["pnpm", "run", "lint"],
            cwd=frontend_path,
            capture_output=True,
            text=True,
            timeout=60,
        )
        # Lint should succeed (exit 0)
        assert result.returncode == 0, f"Lint failed: {result.stderr}"


@pytest.mark.e2e
class TestReactThemeDockerIntegration:
    """E2E tests for React theme with Docker"""

    @pytest.fixture
    def docker_available(self):
        """Check if Docker is available"""
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            pytest.skip("Docker is not running")

    def test_dockerfile_builds_with_react(self, tmp_path, docker_available):
        """
        Verify Dockerfile builds successfully with React frontend.

        This tests the complete Docker build including frontend compilation.
        """
        generator = ProjectGenerator(theme="showcase_react")
        project_name = "docker_build_test"
        project_path = tmp_path / project_name

        generator.generate(project_name, project_path)

        # Build Docker image
        result = subprocess.run(
            ["docker", "build", "-t", "quickscale-react-test", "."],
            cwd=project_path,
            capture_output=True,
            text=True,
            timeout=300,  # 5 minutes for build
        )

        assert result.returncode == 0, f"Docker build failed: {result.stderr}"

        # Cleanup: remove test image
        subprocess.run(
            ["docker", "rmi", "quickscale-react-test"],
            capture_output=True,
            timeout=30,
        )


@pytest.mark.e2e
class TestReactThemeVerboseDockerOption:
    """Tests for the new verbose-docker option"""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    def test_apply_help_shows_verbose_docker_option(self, runner):
        """Verify --verbose-docker option is documented in help"""
        result = runner.invoke(cli, ["apply", "--help"])
        assert result.exit_code == 0
        assert "--verbose-docker" in result.output

    def test_apply_accepts_verbose_docker_flag(self, tmp_path, runner):
        """Verify apply command accepts --verbose-docker flag"""
        with runner.isolated_filesystem(temp_dir=tmp_path):
            # Create plan first with inputs (theme=1, no modules, docker start=N, save=Y)
            result = runner.invoke(cli, ["plan", "testapp"], input="1\n\nN\nY\n")
            assert result.exit_code == 0

            # Change to project directory
            os.chdir("testapp")

            # Apply with verbose docker (and no docker to avoid actually running)
            # Provide "Y" to confirm apply
            result = runner.invoke(
                cli, ["apply", "--no-docker", "--verbose-docker"], input="Y\n"
            )
            # Should not fail due to unknown option
            assert result.exit_code == 0
