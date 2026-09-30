"""Tests for the required_modules entry parser."""

from __future__ import annotations

import pytest

from quickscale_core.manifest.loader import ManifestError
from quickscale_core.manifest.required_modules import parse_required_module_entry


class TestParseRequiredModuleEntry:
    """Tests for parse_required_module_entry."""

    def test_simple_name(self) -> None:
        """A plain module name returns the bare name."""
        assert parse_required_module_entry("orgs") == "orgs"

    def test_whitespace_is_stripped(self) -> None:
        """Surrounding whitespace is stripped from the name."""
        assert parse_required_module_entry("  orgs  ") == "orgs"

    def test_module_name_with_hyphen(self) -> None:
        """Module names with hyphens are accepted."""
        assert parse_required_module_entry("my-module") == "my-module"

    def test_module_name_with_underscore(self) -> None:
        """Module names with underscores are accepted."""
        assert parse_required_module_entry("my_module") == "my_module"

    def test_module_name_with_digits(self) -> None:
        """Module names may carry digits after the first letter."""
        assert parse_required_module_entry("module2") == "module2"

    def test_empty_string_raises(self) -> None:
        """An empty entry raises ManifestError."""
        with pytest.raises(ManifestError, match="must not be empty"):
            parse_required_module_entry("")

    def test_whitespace_only_raises(self) -> None:
        """Whitespace-only entry raises ManifestError."""
        with pytest.raises(ManifestError, match="must not be empty"):
            parse_required_module_entry("  ")

    def test_version_floor_is_refused(self) -> None:
        """A version floor is retired and refused, naming the rule."""
        with pytest.raises(ManifestError, match="version specifiers are retired"):
            parse_required_module_entry("orgs>=0.86.0")

    def test_bare_operator_is_refused(self) -> None:
        """A bare comparison operator is refused."""
        with pytest.raises(ManifestError, match="Expected a bare module name"):
            parse_required_module_entry("orgs>=")

    def test_garbage_is_refused(self) -> None:
        """Garbage input is refused."""
        with pytest.raises(ManifestError, match="Expected a bare module name"):
            parse_required_module_entry("!!!invalid!!!")

    def test_leading_digit_is_refused(self) -> None:
        """A name starting with a digit is refused."""
        with pytest.raises(ManifestError, match="Expected a bare module name"):
            parse_required_module_entry("2orgs")

    def test_non_string_is_refused(self) -> None:
        """A non-string entry is refused instead of coerced."""
        with pytest.raises(ManifestError, match="Expected a bare module name"):
            parse_required_module_entry(5)  # type: ignore[arg-type]

    def test_module_name_in_error_message(self) -> None:
        """The owning module name appears in the refusal."""
        with pytest.raises(ManifestError, match=r"\[billing\]"):
            parse_required_module_entry("orgs>=0.86.0", "billing")
