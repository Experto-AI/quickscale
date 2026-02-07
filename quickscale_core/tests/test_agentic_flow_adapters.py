from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _run_adapter(
    script: str, extra_env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    """Run an adapter script and return completed process"""
    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)

    return subprocess.run(
        ["bash", script],
        cwd=REPO_ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )


def _build_ir() -> Path:
    """Build normalized agent IR and return output path"""
    _run_adapter(".agent/adapters/build-ir.sh")
    ir_path = REPO_ROOT / ".agent/.build/ir.json"
    assert ir_path.exists()
    return ir_path


def test_build_ir_contains_required_sections() -> None:
    """IR should include all required top-level sections"""
    ir_path = _build_ir()
    data = json.loads(ir_path.read_text(encoding="utf-8"))

    required_keys = {
        "schema_version",
        "generated_at",
        "config",
        "agents",
        "subagents",
        "skills",
        "workflows",
        "contexts",
        "diagnostics",
    }
    assert required_keys.issubset(data)
    assert data["diagnostics"]["errors"] == []

    platforms = data["config"]["platforms"]
    for key in (
        "claude_code",
        "gemini_cli",
        "gemini_antigravity",
        "github_copilot",
        "copilot_cli",
        "codex_cli",
        "opencode",
    ):
        assert set(platforms[key]) == {"enabled", "support_mode", "experimental"}


def test_claude_output_preserves_contract_metadata(tmp_path: Path) -> None:
    """Claude agent output should include contract metadata block"""
    ir_path = _build_ir()
    output_root = tmp_path / "claude-out"

    _run_adapter(
        ".agent/adapters/claude-adapter.sh",
        {
            "IR_FILE": str(ir_path),
            "OUTPUT_ROOT": str(output_root),
        },
    )

    task_implementer = output_root / ".claude/agents/task-implementer.md"
    assert task_implementer.exists()

    content = task_implementer.read_text(encoding="utf-8")
    assert "## Contract Metadata" in content
    assert "success_when:" in content


def test_copilot_release_prompt_uses_release_version_input(tmp_path: Path) -> None:
    """Copilot create-release prompt should target releaseVersion input"""
    ir_path = _build_ir()
    output_root = tmp_path / "copilot-out"

    _run_adapter(
        ".agent/adapters/copilot-adapter.sh",
        {
            "IR_FILE": str(ir_path),
            "OUTPUT_ROOT": str(output_root),
        },
    )

    prompt = output_root / ".github/prompts/create-release.prompt.md"
    assert prompt.exists()

    content = prompt.read_text(encoding="utf-8")
    assert "mode: release-manager" in content
    assert "Target: ${input:releaseVersion}" in content
    assert "./scripts/test_agentic_flow.sh" in content

    chatmode = output_root / ".github/chatmodes/release-manager.chatmode.md"
    assert chatmode.exists()
    assert "whenToUse:" in chatmode.read_text(encoding="utf-8")


def test_gemini_commands_use_prompt_field(tmp_path: Path) -> None:
    """Gemini command TOML must use prompt field and modern settings key."""
    ir_path = _build_ir()
    output_root = tmp_path / "gemini-out"

    _run_adapter(
        ".agent/adapters/gemini-adapter.sh",
        {
            "IR_FILE": str(ir_path),
            "OUTPUT_ROOT": str(output_root),
        },
    )

    command_file = output_root / ".gemini/commands/implement-task.toml"
    settings_file = output_root / ".gemini/settings.json"
    agent_file = output_root / ".gemini/agents/task-implementer.md"

    command_content = command_file.read_text(encoding="utf-8")
    settings_content = settings_file.read_text(encoding="utf-8")

    assert 'prompt = """' in command_content
    assert "steps = " not in command_content
    assert '"contextFileName": "GEMINI.md"' in settings_content
    assert agent_file.exists()


def test_gemini_antigravity_outputs_profile_and_commands(tmp_path: Path) -> None:
    """Gemini antigravity adapter should produce profile and command files"""
    ir_path = _build_ir()
    output_root = tmp_path / "gemini-antigravity-out"

    _run_adapter(
        ".agent/adapters/gemini-antigravity-adapter.sh",
        {
            "IR_FILE": str(ir_path),
            "OUTPUT_ROOT": str(output_root),
        },
    )

    profile = output_root / ".gemini/antigravity/ANTIGRAVITY.md"
    command = output_root / ".gemini/antigravity/commands/implement-task.md"
    settings = output_root / ".gemini/antigravity/settings.json"

    assert profile.exists()
    assert command.exists()
    assert settings.exists()
