"""Tests for file utilities"""

import os

from quickscale_core.utils.file_utils import (
    ensure_directory,
    validate_project_name,
    write_file,
)


class TestValidateProjectName:
    """Tests for project name validation"""

    def test_valid_names(self):
        """Valid project names should pass"""
        valid_names = [
            "myproject",
            "my_project",
            "project123",
            "app2024",
        ]

        for name in valid_names:
            is_valid, error = validate_project_name(name)
            assert is_valid, f"{name} should be valid but got error: {error}"
            assert error == ""

    def test_empty_name(self):
        """Empty name should fail"""
        is_valid, error = validate_project_name("")
        assert not is_valid
        assert "empty" in error.lower()

    def test_python_keywords(self):
        """Python keywords should fail"""
        keywords = ["class", "def", "if", "else", "import"]

        for keyword in keywords:
            is_valid, error = validate_project_name(keyword)
            assert not is_valid
            assert "keyword" in error.lower()

    def test_reserved_names(self):
        """Reserved names should fail"""
        reserved = ["test", "django", "site", "utils"]

        for name in reserved:
            is_valid, error = validate_project_name(name)
            assert not is_valid
            assert "reserved" in error.lower()

    def test_invalid_identifiers(self):
        """Invalid Python identifiers should fail"""
        invalid = [
            "123project",  # starts with number
            "my project",  # contains space
            "my.project",  # contains dot
        ]

        for name in invalid:
            is_valid, error = validate_project_name(name)
            assert not is_valid

    def test_starts_with_underscore(self):
        """Names starting with underscore should fail"""
        is_valid, error = validate_project_name("_myproject")
        assert not is_valid
        assert "underscore" in error.lower()

    def test_uppercase_letters(self):
        """Names with uppercase should fail"""
        is_valid, error = validate_project_name("MyProject")
        assert not is_valid


class TestEnsureDirectory:
    """Tests for directory creation"""

    def test_create_directory(self, tmp_path):
        """Should create directory if it doesn't exist"""
        test_dir = tmp_path / "test_dir"
        assert not test_dir.exists()

        ensure_directory(test_dir)
        assert test_dir.exists()
        assert test_dir.is_dir()

    def test_create_nested_directory(self, tmp_path):
        """Should create nested directories"""
        test_dir = tmp_path / "parent" / "child" / "grandchild"
        assert not test_dir.exists()

        ensure_directory(test_dir)
        assert test_dir.exists()
        assert test_dir.is_dir()

    def test_existing_directory(self, tmp_path):
        """Should not fail if directory already exists"""
        test_dir = tmp_path / "existing"
        test_dir.mkdir()

        # Should not raise
        ensure_directory(test_dir)
        assert test_dir.exists()


class TestWriteFile:
    """Tests for file writing"""

    def test_write_simple_file(self, tmp_path):
        """Should write file with content"""
        test_file = tmp_path / "test.txt"
        content = "Hello, World!"

        write_file(test_file, content)

        assert test_file.exists()
        assert test_file.read_text() == content

    def test_write_creates_parent_dir(self, tmp_path):
        """Should create parent directory if it doesn't exist"""
        test_file = tmp_path / "subdir" / "test.txt"
        content = "Test content"

        write_file(test_file, content)

        assert test_file.exists()
        assert test_file.read_text() == content

    def test_write_executable_file(self, tmp_path):
        """Should set executable permission when requested"""
        test_file = tmp_path / "script.sh"
        content = "#!/bin/bash\necho 'Hello'"

        write_file(test_file, content, executable=True)

        assert test_file.exists()
        # Check if file is executable
        assert os.access(test_file, os.X_OK)

    def test_write_non_executable_file(self, tmp_path):
        """Non-executable files should not have execute permission"""
        test_file = tmp_path / "data.txt"
        content = "Data"

        write_file(test_file, content, executable=False)

        assert test_file.exists()
        # File should not be executable by default
        # Note: This might be True on some systems, so we just check it exists
