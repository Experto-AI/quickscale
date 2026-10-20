"""The CLI help tree is complete and self-describing (SA303)."""

from __future__ import annotations

import subprocess

import click
import pytest
from click.testing import CliRunner

from quickscale_cli.cli_help import ARGUMENT_HELP, EXAMPLES, TAIL_LINES
from quickscale_cli.commands import development_commands
from quickscale_cli.main import cli


def _invoke(runner: CliRunner, args: list[str]):
    return runner.invoke(cli, args, prog_name="quickscale")


def _walk_group(group: click.Group, ctx: click.Context):
    for name in group.list_commands(ctx):
        command = group.get_command(ctx, name)
        if command is None or command.hidden:
            continue
        sub_ctx = click.Context(command, info_name=name, parent=ctx)
        yield sub_ctx, command
        if isinstance(command, click.Group):
            yield from _walk_group(command, sub_ctx)


def _walk_commands():
    root = click.Context(cli, info_name="quickscale")
    yield root, cli
    yield from _walk_group(cli, root)


def test_bare_invocation_and_help_show_the_full_tree(cli_runner: CliRunner) -> None:
    for args, expected_exit in (([], 2), (["--help"], 0)):
        result = _invoke(cli_runner, args)
        assert result.exit_code == expected_exit, result.output
        for ctx, _ in _walk_commands():
            assert ctx.command_path in result.output


def test_top_level_help_lists_every_option_and_argument(
    cli_runner: CliRunner,
) -> None:
    output = _invoke(cli_runner, ["--help"]).output
    for ctx, command in _walk_commands():
        for param in command.get_params(ctx):
            if isinstance(param, click.Argument):
                assert param.make_metavar(ctx) in output, ctx.command_path
                continue
            for option in param.opts:
                assert option in output, (ctx.command_path, option)


def test_every_command_has_help_text_and_an_example(cli_runner: CliRunner) -> None:
    paths = {ctx.command_path for ctx, _ in _walk_commands()}
    assert set(EXAMPLES) == paths
    for ctx, command in _walk_commands():
        help_text = command.get_help(ctx)
        assert command.help and command.help.strip()
        assert "Examples:" in help_text, ctx.command_path
        assert EXAMPLES[ctx.command_path].splitlines()[0] in help_text


def test_every_option_has_help_text() -> None:
    for ctx, command in _walk_commands():
        for param in command.get_params(ctx):
            if isinstance(param, click.Option):
                assert param.help and param.help.strip(), (
                    ctx.command_path,
                    param.name,
                )


def test_every_argument_has_documented_help() -> None:
    argument_commands = set()
    for ctx, command in _walk_commands():
        documented = ARGUMENT_HELP.get(ctx.command_path, {})
        for param in command.params:
            if not isinstance(param, click.Argument):
                continue
            argument_commands.add(ctx.command_path)
            help_text = documented.get(param.name)
            assert help_text and help_text.strip(), (ctx.command_path, param.name)
            normalized = " ".join(command.get_help(ctx).split())
            assert param.make_metavar(ctx) in normalized
            assert " ".join(help_text.split()) in normalized
    assert set(ARGUMENT_HELP) == argument_commands


@pytest.mark.parametrize("group_name", ["deploy", "dr"])
def test_group_without_subcommand_shows_its_subcommands(
    cli_runner: CliRunner, group_name: str
) -> None:
    result = _invoke(cli_runner, [group_name])
    group = cli.commands[group_name]
    assert isinstance(group, click.Group)
    for subcommand in group.commands:
        assert subcommand in result.output


def test_manage_lists_django_commands(
    cli_runner: CliRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[tuple[tuple, dict]] = []
    monkeypatch.setattr(
        development_commands, "_validate_project_and_docker", lambda: True
    )
    monkeypatch.setattr(
        development_commands, "get_backend_container_name", lambda: "proj_backend"
    )
    monkeypatch.setattr(
        development_commands,
        "_run_docker_exec_command",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )

    for args in (["manage"], ["manage", "--help"]):
        result = _invoke(cli_runner, args)
        assert result.exit_code == 0, result.output

    assert calls == [
        (("proj_backend", ["python", "manage.py", "help"]), {"capture": True}),
        (("proj_backend", ["python", "manage.py", "help"]), {"capture": True}),
    ]


def test_manage_reports_a_stopped_stack(
    cli_runner: CliRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        development_commands, "_validate_project_and_docker", lambda: True
    )
    monkeypatch.setattr(
        development_commands, "get_backend_container_name", lambda: "proj_backend"
    )

    def _fail(*args, **kwargs):
        raise subprocess.CalledProcessError(1, ["docker", "exec"])

    monkeypatch.setattr(development_commands, "_run_docker_exec_command", _fail)
    result = _invoke(cli_runner, ["manage"])
    assert result.exit_code == 1
    assert "Backend container is not running" in result.output
    assert "quickscale up" in result.output


def test_logs_help_names_the_compose_services(cli_runner: CliRunner) -> None:
    result = _invoke(cli_runner, ["logs", "--help"])
    assert result.exit_code == 0
    for service in ("backend", "frontend", "db"):
        assert service in result.output


def test_logs_help_reads_the_project_compose_file(
    cli_runner: CliRunner, tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "docker-compose.yml").write_text(
        "services:\n"
        "  backend:\n"
        "    image: app\n"
        "  db:\n"
        "    image: db\n"
        "  worker:\n"
        "    image: worker\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    result = _invoke(cli_runner, ["logs", "--help"])
    assert result.exit_code == 0
    assert "worker" in result.output
    assert "frontend" not in result.output


def test_logs_rejects_a_service_the_compose_file_lacks(
    cli_runner: CliRunner, tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "docker-compose.yml").write_text(
        "services:\n  backend:\n    image: app\n", encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        development_commands, "_validate_project_and_docker", lambda: True
    )
    result = _invoke(cli_runner, ["logs", "worker"])
    assert result.exit_code == 2
    assert "is not declared in docker-compose.yml" in result.output


def test_logs_tail_rejects_a_non_integer(cli_runner: CliRunner) -> None:
    result = _invoke(cli_runner, ["logs", "--tail", "many"])
    assert result.exit_code == 2
    assert "non-negative integer or 'all'" in result.output


def test_tail_accepts_a_count_or_all() -> None:
    assert TAIL_LINES.convert("10", None, None) == "10"
    assert TAIL_LINES.convert("all", None, None) == "all"
    with pytest.raises(click.BadParameter):
        TAIL_LINES.convert("-1", None, None)


def test_plan_usage_marks_the_slug_optional(cli_runner: CliRunner) -> None:
    result = _invoke(cli_runner, ["plan", "--help"])
    assert "[PROJECT_SLUG]" in result.output
    assert "Usage: quickscale plan [OPTIONS] PROJECT_SLUG" not in result.output


def test_apply_help_has_no_rest_double_backticks(cli_runner: CliRunner) -> None:
    result = _invoke(cli_runner, ["apply", "--help"])
    assert "``" not in result.output


def test_remove_help_numbering_is_aligned(cli_runner: CliRunner) -> None:
    lines = _invoke(cli_runner, ["remove", "--help"]).output.splitlines()
    numbered = [
        line for line in lines if line.strip()[:2] in {"1.", "2.", "3.", "4.", "5."}
    ]
    assert len(numbered) == 5
    assert len({len(line) - len(line.lstrip()) for line in numbered}) == 1
