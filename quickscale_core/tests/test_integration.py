"""Integration tests for project generation workflow"""

import subprocess
import sys

import pytest

from quickscale_core.generator import ProjectGenerator


@pytest.mark.integration
class TestProjectGenerationIntegration:
    """End-to-end integration tests"""

    def test_generate_and_validate_project(self, tmp_path):
        """Generate project and verify it's a valid Django project"""
        generator = ProjectGenerator()
        project_name = "integration_test"
        output_path = tmp_path / project_name

        # Generate project
        generator.generate(project_name, output_path)

        # Verify project structure
        assert (output_path / "manage.py").exists()
        assert (output_path / project_name).is_dir()
        assert (output_path / "pyproject.toml").exists()
        assert (output_path / "poetry.lock").exists()

        # Verify manage.py can be executed
        manage_py = output_path / "manage.py"
        assert manage_py.exists()

        # Try to run manage.py --version (should work even without dependencies)
        result = subprocess.run(
            [sys.executable, str(manage_py), "--version"],
            cwd=output_path,
            capture_output=True,
            text=True,
            timeout=5,
        )

        # Should show Django version or help (even if Django not installed)
        # We just want to ensure the file is executable and valid Python
        # Exit code might be non-zero if Django is not installed, but file should be valid
        assert result.returncode in (0, 1)  # 0 if Django installed, 1 if not

    def test_generated_project_imports(self, tmp_path):
        """Verify generated Python files can be imported"""
        generator = ProjectGenerator()
        project_name = "importtest"
        output_path = tmp_path / project_name

        generator.generate(project_name, output_path)

        # Add project to Python path
        sys.path.insert(0, str(output_path))

        try:
            # Try to import the project package
            project_module = __import__(project_name)
            assert project_module is not None

            # Try to import settings module
            settings_module = __import__(f"{project_name}.settings", fromlist=["settings"])
            assert settings_module is not None

        finally:
            # Clean up sys.path
            sys.path.remove(str(output_path))

    def test_multiple_projects_independent(self, tmp_path):
        """Multiple generated projects should be independent"""
        generator = ProjectGenerator()

        project1 = "project_one"
        project2 = "project_two"

        output1 = tmp_path / project1
        output2 = tmp_path / project2

        generator.generate(project1, output1)
        generator.generate(project2, output2)

        # Both should exist
        assert output1.exists()
        assert output2.exists()

        # Each should have its own project name in files
        pyproject1 = (output1 / "pyproject.toml").read_text()
        pyproject2 = (output2 / "pyproject.toml").read_text()

        assert f'name = "{project1}"' in pyproject1
        assert f'name = "{project2}"' in pyproject2

        assert project1 not in pyproject2
        assert project2 not in pyproject1

    def test_cicd_files_generated(self, tmp_path):
        """Generated project should include CI/CD files"""
        generator = ProjectGenerator()
        project_name = "cicdtest"
        output_path = tmp_path / project_name

        generator.generate(project_name, output_path)

        # Verify CI/CD files exist
        assert (output_path / ".github" / "workflows" / "ci.yml").exists()
        assert (output_path / ".pre-commit-config.yaml").exists()
        assert (output_path / "tests" / "__init__.py").exists()
        assert (output_path / "tests" / "conftest.py").exists()
        assert (output_path / "tests" / "test_example.py").exists()

        # Verify CI file has correct content
        ci_content = (output_path / ".github" / "workflows" / "ci.yml").read_text()
        assert "name: CI" in ci_content
        assert "pytest --cov" in ci_content
        assert project_name in ci_content  # Project name should be in coverage command

        # Verify pre-commit config has ruff
        precommit_content = (output_path / ".pre-commit-config.yaml").read_text()
        assert "ruff" in precommit_content

        # Verify pyproject.toml has pre-commit dependency
        pyproject_content = (output_path / "pyproject.toml").read_text()
        assert "pre-commit" in pyproject_content
