#!/usr/bin/env python3
"""
Render a Jinja2 template with lint-optimized dummy context.

Replaces the sed-based render_template() in lint_frontend.sh.
Handles all Jinja2 constructs: {% if %}, {% for %}, {% set %},
{% raw %}...{% endraw %}, whitespace control, {{ variables }}, etc.

Usage: render_j2_template.py <source.j2> <destination>
"""

from __future__ import annotations

import os
import sys


def get_lint_context() -> dict:
    """
    Return rendering context that produces maximal lint coverage.

    Strategy: treat all module features as enabled so that ESLint and
    TypeScript can validate every code path in the rendered output.
    """
    _all_modules = [
        "auth",
        "blog",
        "listings",
        "crm",
        "forms",
        "storage",
        "backups",
        "notifications",
        "analytics",
        "billing",
        "social",
    ]

    # Allow SELECTED_MODULES env var override so the lint pipeline can
    # render a no-social variant for TypeScript validation coverage.
    env_modules = os.environ.get("SELECTED_MODULES")
    if env_modules is not None:
        import json

        try:
            modules = json.loads(env_modules)
        except json.JSONDecodeError as exc:
            print(
                f"Warning: SELECTED_MODULES is not valid JSON ({exc}), "
                "falling back to all modules.",
                file=sys.stderr,
            )
            modules = _all_modules
    else:
        modules = _all_modules

    return {
        "project_name": "MyApp",
        "package_name": "myapp",
        "project_description": "A QuickScale project",
        # Full module list so 'foo in selected_modules' is always True
        # and 'selected_modules is none' is False for maximal coverage.
        "selected_modules": modules,
    }


def main() -> None:
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <source.j2> <destination>", file=sys.stderr)
        sys.exit(1)

    src = sys.argv[1]
    dest = sys.argv[2]

    # Read the template source
    try:
        with open(src) as f:
            template_source = f.read()
    except FileNotFoundError:
        print(f"Error: source file not found: {src}", file=sys.stderr)
        sys.exit(1)
    except OSError as e:
        print(f"Error reading {src}: {e}", file=sys.stderr)
        sys.exit(1)

    # Import lazily — fail with a clear message if Jinja2 isn't available
    try:
        from jinja2 import Environment, Undefined
    except ImportError:
        print(
            "Error: Jinja2 is not installed. Run: poetry install",
            file=sys.stderr,
        )
        sys.exit(1)

    env = Environment(
        # Silently resolve unknown variables to empty string so templates
        # that reference variables we haven't provided still render cleanly.
        undefined=Undefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )

    try:
        rendered = env.from_string(template_source).render(**get_lint_context())
    except Exception as e:
        print(f"Error rendering {src}: {e}", file=sys.stderr)
        sys.exit(1)

    # Ensure destination directory exists
    dest_dir = os.path.dirname(dest)
    if dest_dir:
        os.makedirs(dest_dir, exist_ok=True)

    try:
        with open(dest, "w") as f:
            f.write(rendered)
    except OSError as e:
        print(f"Error writing {dest}: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
