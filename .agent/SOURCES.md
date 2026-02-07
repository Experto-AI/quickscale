# Adapter Source Specifications

This file tracks the **official documentation sources** used to validate platform adapters.

Verification date: **2026-02-07**.

## Platform Reference Table

| Platform | Documentation Source | Adapter Focus | Tier |
|----------|----------------------|---------------|------|
| Claude Code | https://docs.anthropic.com/en/docs/claude-code/sub-agents and https://docs.anthropic.com/en/docs/claude-code/slash-commands | `.claude/commands/`, `.claude/agents/`, `CLAUDE.md` | verified |
| Gemini CLI | https://geminicli.com/docs/ and https://geminicli.com/docs/cli/configuration | `.gemini/commands/*.toml` (`prompt` field), `.gemini/settings.json`, `.gemini/agents/` | verified |
| GitHub Copilot (VS Code) | https://code.visualstudio.com/docs/copilot/copilot-customization and https://code.visualstudio.com/docs/copilot/chat/chat-agent-mode | `.github/prompts/*.prompt.md`, `.github/agents/*.agent.md`, `.github/instructions/` | verified |
| Codex CLI | https://developers.openai.com/codex/agents.md and https://developers.openai.com/codex/config | `AGENTS.md`, `.codex/config.toml` | verified |

## Implementation Notes

- Adapters consume the normalized IR at `.agent/.build/ir.json`.
- Capability declarations in `.agent/adapters/capabilities/*.yaml` are treated as adapter contracts.
- Experimental adapters/capabilities are archived under `.agent/archive/experimental/` and excluded from active generation.
- Strict mode (`workflows.stage_validation: strict`) fails generation on capability mismatches.
- Profile-based template selection is controlled by `project.profile` in `.agent/config.yaml`.

## Updating Adapters

1. Re-validate documentation sources above.
2. Update capability declaration for the platform.
3. Update adapter script and tests.
4. Regenerate outputs via `.agent/adapters/generate-all.sh`.
5. Update this file and `docs/technical/agentic-flow.md` with the new verification date.
