"""Tests for ProjectGenerator class"""

import os

import pytest

from quickscale_core.generator import ProjectGenerator


class TestProjectGeneratorInit:
    """Tests for ProjectGenerator initialization"""

    def test_init_with_default_template_dir(self):
        """Should initialize with default template directory"""
        generator = ProjectGenerator()

        assert generator.template_dir.exists()
        assert generator.template_dir.name == "templates"
        assert generator.env is not None

    def test_init_with_custom_template_dir(self, tmp_path):
        """Should initialize with custom template directory"""
        custom_dir = tmp_path / "custom_templates"
        custom_dir.mkdir()

        # Create required themes directory structure
        themes_dir = custom_dir / "themes" / "starter_html"
        themes_dir.mkdir(parents=True)

        generator = ProjectGenerator(template_dir=custom_dir)

        assert generator.template_dir == custom_dir

    def test_init_with_nonexistent_dir(self, tmp_path):
        """Should raise FileNotFoundError for nonexistent directory"""
        nonexistent = tmp_path / "nonexistent"

        with pytest.raises(FileNotFoundError, match="Template directory not found"):
            ProjectGenerator(template_dir=nonexistent)


class TestProjectGeneratorValidation:
    """Tests for project name validation in generator"""

    def test_generate_with_invalid_name(self, tmp_path):
        """Should raise ValueError for invalid project name"""
        generator = ProjectGenerator()

        with pytest.raises(ValueError, match="Invalid project name"):
            generator.generate("123invalid", tmp_path / "output")

    def test_generate_with_keyword_name(self, tmp_path):
        """Should raise ValueError for Python keyword"""
        generator = ProjectGenerator()

        with pytest.raises(ValueError, match="Invalid project name"):
            generator.generate("class", tmp_path / "output")

    def test_generate_with_reserved_name(self, tmp_path):
        """Should raise ValueError for reserved name"""
        generator = ProjectGenerator()

        with pytest.raises(ValueError, match="Invalid project name"):
            generator.generate("test", tmp_path / "output")


class TestProjectGeneratorPathChecks:
    """Tests for output path validation"""

    def test_generate_to_existing_path(self, tmp_path):
        """Should raise FileExistsError if output path exists"""
        generator = ProjectGenerator()
        existing_dir = tmp_path / "existing"
        existing_dir.mkdir()

        with pytest.raises(FileExistsError, match="Output path already exists"):
            generator.generate("myproject", existing_dir)

    def test_generate_to_unwritable_parent(self, tmp_path):
        """Should raise PermissionError for unwritable parent directory"""
        generator = ProjectGenerator()

        # Create a directory and make it read-only
        readonly_dir = tmp_path / "readonly"
        readonly_dir.mkdir()
        readonly_dir.chmod(0o444)

        try:
            with pytest.raises(PermissionError):
                generator.generate("myproject", readonly_dir / "output")
        finally:
            # Restore permissions for cleanup
            readonly_dir.chmod(0o755)

    def test_generate_creates_parent_directory(self, tmp_path):
        """Should create parent directory if it does not exist"""
        generator = ProjectGenerator()
        project_name = "myproject"

        # Create a nested path where intermediate directories don't exist
        output_path = tmp_path / "level1" / "level2" / project_name

        # Parent directories should not exist yet
        assert not (tmp_path / "level1").exists()

        # Generate project - should create parent directories
        generator.generate(project_name, output_path)

        # Verify project was created
        assert output_path.exists()
        assert (output_path / "manage.py").exists()
        assert (tmp_path / "level1").exists()
        assert (tmp_path / "level1" / "level2").exists()


class TestProjectGeneratorGeneration:
    """Tests for successful project generation"""

    def test_generate_creates_project_structure(self, tmp_path):
        """Should create complete project structure"""
        generator = ProjectGenerator()
        project_name = "testproject"
        output_path = tmp_path / project_name

        generator.generate(project_name, output_path)

        # Check root files exist
        assert (output_path / "manage.py").exists()
        assert (output_path / "pyproject.toml").exists()
        assert (output_path / "poetry.lock").exists()
        assert (output_path / ".gitignore").exists()
        assert (output_path / "Dockerfile").exists()
        assert (output_path / "docker-compose.yml").exists()

        # Check project package exists
        assert (output_path / project_name / "__init__.py").exists()
        assert (output_path / project_name / "urls.py").exists()
        assert (output_path / project_name / "wsgi.py").exists()
        assert (output_path / project_name / "asgi.py").exists()

        # Check settings package exists
        assert (output_path / project_name / "settings" / "__init__.py").exists()
        assert (output_path / project_name / "settings" / "base.py").exists()
        assert (output_path / project_name / "settings" / "local.py").exists()
        assert (output_path / project_name / "settings" / "production.py").exists()

        # Check templates and static files
        assert (output_path / "templates" / "index.html").exists()
        assert (output_path / "static" / "css" / "style.css").exists()

    def test_manage_py_is_executable(self, tmp_path):
        """Should make manage.py executable"""
        generator = ProjectGenerator()
        project_name = "testproject"
        output_path = tmp_path / project_name

        generator.generate(project_name, output_path)

        manage_py = output_path / "manage.py"
        assert os.access(manage_py, os.X_OK)

    def test_generated_files_contain_project_name(self, tmp_path):
        """Generated files should contain the project name"""
        generator = ProjectGenerator()
        project_name = "myapp"
        output_path = tmp_path / project_name

        generator.generate(project_name, output_path)

        # Check that project name appears in key files
        pyproject_content = (output_path / "pyproject.toml").read_text()
        assert f'name = "{project_name}"' in pyproject_content

        urls_content = (output_path / project_name / "urls.py").read_text()
        assert project_name in urls_content

    def test_generated_python_files_are_valid(self, tmp_path):
        """Generated Python files should be syntactically valid"""
        generator = ProjectGenerator()
        project_name = "validproject"
        output_path = tmp_path / project_name

        generator.generate(project_name, output_path)

        # Try to compile Python files
        python_files = [
            output_path / "manage.py",
            output_path / project_name / "__init__.py",
            output_path / project_name / "urls.py",
            output_path / project_name / "wsgi.py",
            output_path / project_name / "asgi.py",
            output_path / project_name / "settings" / "base.py",
            output_path / project_name / "settings" / "local.py",
            output_path / project_name / "settings" / "production.py",
        ]

        for py_file in python_files:
            # This will raise SyntaxError if file is invalid
            compile(py_file.read_text(), str(py_file), "exec")


class TestProjectGeneratorAtomicCreation:
    """Tests for atomic project creation (rollback on failure)"""

    def test_rollback_on_template_error(self, tmp_path):
        """Should clean up temp directory if template rendering fails"""
        # Create generator with nonexistent template
        generator = ProjectGenerator()

        # Monkey-patch to force an error during generation
        original_method = generator._generate_project

        def failing_generate(*args, **kwargs):
            raise RuntimeError("Simulated template error")

        generator._generate_project = failing_generate

        output_path = tmp_path / "failproject"

        with pytest.raises(RuntimeError, match="Failed to generate project"):
            generator.generate("validname", output_path)

        # Output path should not exist (rollback)
        assert not output_path.exists()

        # Restore original method
        generator._generate_project = original_method


class TestProjectGeneratorMultipleProjects:
    """Tests for generating multiple projects"""

    def test_generate_multiple_projects(self, tmp_path):
        """Should be able to generate multiple projects"""
        generator = ProjectGenerator()

        projects = ["project1", "project2", "project3"]

        for project_name in projects:
            output_path = tmp_path / project_name
            generator.generate(project_name, output_path)

            assert output_path.exists()
            assert (output_path / "manage.py").exists()
            assert (output_path / project_name / "settings" / "base.py").exists()
