# Adapter Source Specifications

This file tracks the **official documentation sources** used to validate platform adapters.

Verification date: **2026-02-07**.

## Platform Reference Table

| Platform | Documentation Source | Adapter Focus | Tier |
|----------|----------------------|---------------|------|
| Claude Code | https://docs.anthropic.com/en/docs/claude-code/sub-agents and https://docs.anthropic.com/en/docs/claude-code/slash-commands | `.claude/commands/`, `.claude/agents/`, `CLAUDE.md` | verified |
| Gemini CLI | https://geminicli.com/docs/ and https://geminicli.com/docs/cli/configuration | `.gemini/commands/*.toml` (`prompt` field), `.gemini/settings.json`, `.gemini/agents/` | verified |
| GitHub Copilot (VS Code) | https://code.visualstudio.com/docs/copilot/copilot-customization#_prompt-files-experimental and https://code.visualstudio.com/docs/copilot/chat/chat-modes | `.github/prompts/*.prompt.md`, `.github/chatmodes/*.chatmode.md`, `.github/instructions/` | verified |
| Codex CLI | https://developers.openai.com/codex/agents.md and https://developers.openai.com/codex/config | `AGENTS.md`, `.codex/config.toml` | verified |
| Gemini Antigravity | Gemini ecosystem compatibility surface (no stable public spec) | `.gemini/antigravity/` | experimental |
| Copilot CLI | https://docs.github.com/en/copilot (partial, evolving CLI behavior) | `.github/copilot-cli/` | experimental |
| OpenCode | https://opencode.ai/docs/config | `.opencode.json`, `.opencode/` | experimental |

## Implementation Notes

- Adapters consume the normalized IR at `.agent/.build/ir.json`.
- Capability declarations in `.agent/adapters/capabilities/*.yaml` are treated as adapter contracts.
- Strict mode (`workflows.stage_validation: strict`) fails generation on capability mismatches.
- Profile-based template selection is controlled by `project.profile` in `.agent/config.yaml`.

## Updating Adapters

1. Re-validate documentation sources above.
2. Update capability declaration for the platform.
3. Update adapter script and tests.
4. Regenerate outputs via `.agent/adapters/generate-all.sh`.
5. Update this file and `docs/technical/agentic-flow.md` with the new verification date.
