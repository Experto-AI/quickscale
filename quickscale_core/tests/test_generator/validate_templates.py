#!/usr/bin/env python
"""
Validation script for QuickScale templates.

This script renders all templates with test data and validates the output.
Useful for manual inspection and debugging.
"""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader


def main():
    """Render all templates with test data."""
    # Get templates directory
    core_dir = Path(__file__).parent.parent.parent / "src" / "quickscale_core"
    templates_dir = core_dir / "generator" / "templates"

    print(f"Templates directory: {templates_dir}")
    print(f"Templates directory exists: {templates_dir.exists()}")

    # Create Jinja2 environment
    env = Environment(loader=FileSystemLoader(str(templates_dir)))

    # Test context
    context = {"project_name": "testproject"}

    # List of templates to render
    templates = [
        "manage.py.j2",
        "project_name/__init__.py.j2",
        "project_name/settings/__init__.py.j2",
        "project_name/settings/base.py.j2",
        "project_name/settings/local.py.j2",
        "project_name/settings/production.py.j2",
        "project_name/urls.py.j2",
        "project_name/wsgi.py.j2",
        "project_name/asgi.py.j2",
    ]

    print("\n" + "=" * 80)
    print("RENDERING TEMPLATES")
    print("=" * 80)

    for template_name in templates:
        print(f"\n--- {template_name} ---")
        try:
            template = env.get_template(template_name)
            output = template.render(context)
            print(f"✓ Rendered successfully ({len(output)} characters)")

            # Show first few lines
            lines = output.split("\n")[:5]
            for line in lines:
                print(f"  {line}")
            if len(output.split("\n")) > 5:
                print(f"  ... ({len(output.split('\n')) - 5} more lines)")

        except Exception as e:
            print(f"✗ Error: {e}")

    print("\n" + "=" * 80)
    print("VALIDATION COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()
