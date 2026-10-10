"""Control cases for the docs module-convention rules."""

from __future__ import annotations

from dataclasses import replace

from scripts import check_module_conventions as checker
from scripts.tests_module_conventions._support import (
    _golden_module,
    _violations,
    _with_files,
)


def test_readme_content_control() -> None:
    module = _golden_module()
    broken = replace(
        module,
        root_files={
            **module.root_files,
            "README.md": module.root_files["README.md"].replace(
                "`api_rate_limit` - throttle rate.", ""
            ),
        },
    )
    assert any(
        "api_rate_limit" in violation
        for violation in _violations(checker.rule_38_readme_content, broken)
    )


def test_readme_role_listing_control() -> None:
    module = _with_files(
        _golden_module(),
        views=(
            "from quickscale_modules_orgs.permissions import OrgRoleMixin\n\n"
            "class DashboardView(OrgRoleMixin):\n"
            "    min_org_role = 'viewer'\n"
        ),
    )
    assert any(
        "does not list the minimum role" in violation
        for violation in _violations(checker.rule_38_readme_content, module)
    )
    role_word_only = replace(
        module,
        root_files={
            **module.root_files,
            "README.md": module.root_files["README.md"].replace(
                "Nothing.", "Uses organization roles."
            ),
        },
    )
    assert any(
        "does not list the minimum role" in violation
        for violation in _violations(checker.rule_38_readme_content, role_word_only)
    )
    empty_role_heading = replace(
        module,
        root_files={
            **module.root_files,
            "README.md": module.root_files["README.md"].replace(
                "Nothing.", "### Role requirements"
            ),
        },
    )
    assert any(
        "does not list the minimum role" in violation
        for violation in _violations(checker.rule_38_readme_content, empty_role_heading)
    )
    tool_name_only = replace(
        module,
        root_files={
            **module.root_files,
            "README.md": module.root_files["README.md"].replace(
                "Nothing.", "Uses min_org_role to authorize actions."
            ),
        },
    )
    assert any(
        "does not list the minimum role" in violation
        for violation in _violations(checker.rule_38_readme_content, tool_name_only)
    )
    empty_tool_heading = replace(
        module,
        root_files={
            **module.root_files,
            "README.md": module.root_files["README.md"].replace("Nothing.", "### min_org_role"),
        },
    )
    assert any(
        "does not list the minimum role" in violation
        for violation in _violations(checker.rule_38_readme_content, empty_tool_heading)
    )
    incidental_role_mention = replace(
        module,
        root_files={
            **module.root_files,
            "README.md": module.root_files["README.md"].replace(
                "Nothing.", "Provides member management APIs and a Django admin interface."
            ),
        },
    )
    assert any(
        "does not list the minimum role" in violation
        for violation in _violations(checker.rule_38_readme_content, incidental_role_mention)
    )
    empty_role_word_heading = replace(
        module,
        root_files={
            **module.root_files,
            "README.md": module.root_files["README.md"].replace(
                "Nothing.", "### Member management"
            ),
        },
    )
    assert any(
        "does not list the minimum role" in violation
        for violation in _violations(checker.rule_38_readme_content, empty_role_word_heading)
    )
    incidental_admin_surface = replace(
        module,
        root_files={
            **module.root_files,
            "README.md": module.root_files["README.md"].replace(
                "Nothing.", "Admin: `OrganizationAdmin` surfaces."
            ),
        },
    )
    assert any(
        "does not list the minimum role" in violation
        for violation in _violations(checker.rule_38_readme_content, incidental_admin_surface)
    )
    documented = replace(
        module,
        root_files={
            **module.root_files,
            "README.md": module.root_files["README.md"].replace(
                "Nothing.", "Minimum role: `viewer`."
            ),
        },
    )
    assert _violations(checker.rule_38_readme_content, documented) == []
    admin_documented = replace(
        module,
        root_files={
            **module.root_files,
            "README.md": module.root_files["README.md"].replace(
                "Nothing.", "Minimum role: `admin`."
            ),
        },
    )
    assert _violations(checker.rule_38_readme_content, admin_documented) == []
    table_form = replace(
        module,
        root_files={
            **module.root_files,
            "README.md": module.root_files["README.md"].replace(
                "Nothing.", "| Role | Behavior |\n|------|----------|\n| `member` | reads |"
            ),
        },
    )
    assert _violations(checker.rule_38_readme_content, table_form) == []
    unbackticked_table_form = replace(
        module,
        root_files={
            **module.root_files,
            "README.md": module.root_files["README.md"].replace(
                "Nothing.",
                "| Action | Minimum role |\n|--------|--------------|\n"
                "| Organization reads and dashboard | viewer |\n"
                "| Member management | admin |",
            ),
        },
    )
    assert _violations(checker.rule_38_readme_content, unbackticked_table_form) == []
    table_without_role_header = replace(
        module,
        root_files={
            **module.root_files,
            "README.md": module.root_files["README.md"].replace(
                "Nothing.", "| URL | Purpose |\n|-----|---------|\n| /admin/ | Django admin |"
            ),
        },
    )
    assert any(
        "does not list the minimum role" in violation
        for violation in _violations(checker.rule_38_readme_content, table_without_role_header)
    )
