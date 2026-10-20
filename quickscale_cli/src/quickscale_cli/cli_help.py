"""Help-tree machinery shared by the QuickScale CLI commands.

Click's default group help lists only each subcommand's name and one-line
summary.  The CLI contract asks for the full tree, so :class:`QuickScaleGroup`
writes every reachable command's own help beneath its own.  This module also
owns the help that Click cannot infer: per-command examples, positional
argument descriptions (Click 8.4 arguments carry none), and the ``--tail``
value type used by ``quickscale logs``.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

import click
import yaml

from quickscale_core.contracts.module_catalog import MODULE_CATALOG


_MODULE_NAMES = ", ".join(sorted(entry.name for entry in MODULE_CATALOG))
_DEFAULT_COMPOSE_SERVICES = ("backend", "frontend", "db")

EXAMPLES: dict[str, str] = {
    "quickscale": (
        "quickscale --help\nquickscale plan my-app\nquickscale apply\nquickscale up"
    ),
    "quickscale apply": (
        "quickscale apply\n"
        "quickscale apply myapp/quickscale.yml\n"
        "quickscale apply --force --no-docker"
    ),
    "quickscale deploy": (
        "quickscale deploy railway\nquickscale deploy railway --project-name my-app"
    ),
    "quickscale deploy railway": (
        "quickscale deploy railway\nquickscale deploy railway --project-name my-app"
    ),
    "quickscale down": "quickscale down\nquickscale down --volumes",
    "quickscale dr": (
        "quickscale dr capture --route local-to-railway-develop\n"
        "quickscale dr report --route local-to-railway-develop --snapshot-id <id>"
    ),
    "quickscale dr capture": (
        "quickscale dr capture --route local-to-railway-develop\n"
        "quickscale dr capture --route railway-develop-to-railway-production "
        "--source-service my-app --json"
    ),
    "quickscale dr execute": (
        "quickscale dr execute --route local-to-railway-develop --snapshot-id <id> "
        "--target-service my-app --database\n"
        "quickscale dr execute --route railway-develop-to-railway-production "
        "--snapshot-id <id> --source-service my-app --target-service my-app --resume"
    ),
    "quickscale dr plan": (
        "quickscale dr plan --route local-to-railway-develop --snapshot-id <id> "
        "--target-service my-app\n"
        "quickscale dr plan --route railway-develop-to-railway-production "
        "--snapshot-id <id> --source-service my-app --target-service my-app --json"
    ),
    "quickscale dr report": (
        "quickscale dr report --route local-to-railway-develop --snapshot-id <id>"
    ),
    "quickscale logs": (
        "quickscale logs\n"
        "quickscale logs backend --follow\n"
        "quickscale logs db --tail 100"
    ),
    "quickscale manage": (
        "quickscale manage\n"
        "quickscale manage migrate\n"
        "quickscale manage createsuperuser"
    ),
    "quickscale plan": (
        "quickscale plan my-app\n"
        "quickscale plan my-app --package my_app\n"
        "quickscale plan --add\n"
        "quickscale plan --reconfigure"
    ),
    "quickscale ps": "quickscale ps",
    "quickscale push": (
        "quickscale push --module auth\n"
        "quickscale push --module auth --branch feature/fix-email-validation"
    ),
    "quickscale remove": "quickscale remove auth\nquickscale remove billing --keep-data",
    "quickscale shell": (
        'quickscale shell\nquickscale shell -c "python manage.py check"'
    ),
    "quickscale status": "quickscale status\nquickscale status --json",
    "quickscale up": "quickscale up\nquickscale up --build\nquickscale up --no-cache",
    "quickscale update": "quickscale update\nquickscale update --no-preview",
    "quickscale version": "quickscale version",
}

ARGUMENT_HELP: dict[str, dict[str, str]] = {
    "quickscale apply": {
        "config": "Path to the configuration file (default: quickscale.yml in the current directory).",
    },
    "quickscale logs": {
        "service": (
            "Compose service to show logs for: backend, frontend, or db in "
            "generated projects (read from the project's docker-compose.yml)."
        ),
    },
    "quickscale manage": {
        "args": (
            "Django management command and its arguments, for example: migrate, "
            "createsuperuser. Omit it, or pass --help, to list the project's commands."
        ),
    },
    "quickscale plan": {
        "project_slug": "Project slug to configure; omit it with --add or --reconfigure.",
    },
    "quickscale remove": {
        "module_name": (
            f"Embedded module to remove. Valid shipped modules: {_MODULE_NAMES}."
        ),
    },
}


class TailLines(click.ParamType):
    """Accept a non-negative line count or the literal ``all``."""

    name = "LINES|all"

    def convert(
        self,
        value: Any,
        param: click.Parameter | None,
        ctx: click.Context | None,
    ) -> Any:
        if value is None:
            return None
        text = str(value).strip()
        if text.lower() == "all":
            return "all"
        try:
            lines = int(text)
        except ValueError:
            self.fail("must be a non-negative integer or 'all'", param, ctx)
        if lines < 0:
            self.fail("must be a non-negative integer or 'all'", param, ctx)
        return str(lines)


TAIL_LINES = TailLines()


def _declared_compose_services() -> tuple[str, ...] | None:
    """Return the Compose services declared in the current project, if any."""
    compose_file = Path("docker-compose.yml")
    try:
        data = yaml.safe_load(compose_file.read_text(encoding="utf-8")) or {}
    except OSError, yaml.YAMLError:
        return None
    services = data.get("services") if isinstance(data, dict) else None
    if not isinstance(services, dict) or not services:
        return None
    return tuple(sorted(str(name) for name in services))


def _compose_service_help(default: str) -> str:
    """Name the project's declared services in the logs argument help."""
    services = _declared_compose_services()
    if services is None:
        return default
    return (
        f"Compose service to show logs for: {', '.join(services)} "
        "(from the project's docker-compose.yml)."
    )


def validate_compose_service(service: str | None) -> None:
    """Reject a service name the project's Compose file does not declare."""
    if service is None:
        return
    services = _declared_compose_services()
    if services is None:
        return
    if service not in services:
        choices = ", ".join(services)
        raise click.BadParameter(
            f"{service!r} is not declared in docker-compose.yml; choose one of: {choices}",
            param_hint="SERVICE",
        )


def list_django_commands(run_exec: Callable[..., None], container_name: str) -> None:
    """List the project's Django commands through manage.py help."""
    click.echo("Django management commands, grouped by app:")
    try:
        run_exec(container_name, ["python", "manage.py", "help"], capture=True)
    except subprocess.CalledProcessError as error:
        click.secho(
            "❌ Error: Backend container is not running or manage.py help failed",
            fg="red",
            err=True,
        )
        click.echo("💡 Start the stack with 'quickscale up' and try again.", err=True)
        raise SystemExit(error.returncode) from error


def _help_key(ctx: click.Context) -> str:
    """Return the registry key for a context, independent of the program name."""
    root = ctx.find_root()
    if ctx is root:
        return "quickscale"
    suffix = ctx.command_path[len(root.command_path) :].strip()
    return f"quickscale {suffix}"


def _write_argument_help(
    ctx: click.Context, formatter: click.HelpFormatter, command: click.Command
) -> None:
    """Write the documented positional arguments, if this command has any."""
    key = _help_key(ctx)
    documented = ARGUMENT_HELP.get(key, {})
    rows = []
    for param in command.get_params(ctx):
        if isinstance(param, click.Argument):
            help_text = documented.get(param.name)
            if key == "quickscale logs" and param.name == "service":
                help_text = _compose_service_help(help_text or "")
            if help_text:
                rows.append((param.make_metavar(ctx), help_text))
    if rows:
        with formatter.section("Arguments"):
            formatter.write_dl(rows)


def _write_examples(ctx: click.Context, formatter: click.HelpFormatter) -> None:
    """Write the registered examples for this command, if it has any."""
    examples = EXAMPLES.get(_help_key(ctx))
    if not examples:
        return
    formatter.write_paragraph()
    formatter.write("Examples:\n")
    for line in examples.splitlines():
        formatter.write(f"  {line}\n")


class QuickScaleCommand(click.Command):
    """A command whose help carries examples and argument descriptions."""

    def format_help_text(
        self, ctx: click.Context, formatter: click.HelpFormatter
    ) -> None:
        super().format_help_text(ctx, formatter)
        _write_argument_help(ctx, formatter, self)
        _write_examples(ctx, formatter)


class QuickScaleGroup(click.Group):
    """A group that prints its full command tree beneath its own help."""

    command_class = QuickScaleCommand

    def format_help_text(
        self, ctx: click.Context, formatter: click.HelpFormatter
    ) -> None:
        super().format_help_text(ctx, formatter)
        _write_argument_help(ctx, formatter, self)
        _write_examples(ctx, formatter)

    def format_commands(
        self, ctx: click.Context, formatter: click.HelpFormatter
    ) -> None:
        commands = []
        for name in self.list_commands(ctx):
            command = self.get_command(ctx, name)
            if command is not None and not command.hidden:
                commands.append((name, command))
        if not commands:
            return
        formatter.write_paragraph()
        formatter.write_heading("Commands")
        for name, command in commands:
            sub_ctx = click.Context(command, info_name=name, parent=ctx)
            formatter.write_paragraph()
            for line in command.get_help(sub_ctx).splitlines():
                formatter.write(f"{line}\n")


class PassThroughCommand(QuickScaleCommand):
    """A command that forwards unknown options, including ``--help``."""

    def get_help_option(self, ctx: click.Context) -> click.Option | None:
        return None
