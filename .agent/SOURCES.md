# Adapter Source Specifications

This file tracks the documentation and specifications used to develop the platform-specific adapters in `.agent/adapters/`.

## Platform Reference Table

| Platform | Core Documentation Source | Specification Focus |
|----------|---------------------------|---------------------|
| **Claude Code** | [Anthropic Docs](https://docs.anthropic.com/en/docs/agents-and-tools/claude-code) | `@import`, `.claude/commands`, `.claude/agents` |
| **Gemini CLI** | [Gemini CLI Repo](https://github.com/google-gemini/gemini-cli) | `@{path}`, TOML command mapping, `{{args}}` |
| **GitHub Copilot** | [GitHub Copilot Customization](https://docs.github.com/en/copilot/using-github-copilot/customizing-copilot-with-custom-instructions) | `.agent.md`, `.prompt.md`, `.instructions.md` |
| **Codex CLI** | [Codex Agents Protocol](https://github.com/openai/codex-agents) | `AGENTS.md`, `.codex/config.toml` |
| **OpenCode** | [OpenCode Portal](https://opencode.ai/docs) | `.opencode.json`, `.opencode/` commands |

## Technical Implementation Notes

- **YAML Parsing**: All adapters use a standardized Bash-based frontmatter extractor to ensure consistent metadata handling across the unified source files.
- **Context Injection**: Platforms supporting native lazy-loading (Claude, Gemini, Codex) use `@` or `@{}` syntax to prevent context bloating in the primary instruction files.
- **Command Translation**: Workflows from `.agent/workflows/*.md` are transpiled to native command formats (Bash scripts, TOML definitions, or Markdown prompts) depending on platform capability.

## Updating Adapters

When updating an adapter:
1. Verify the current schema in the linked documentation sources.
2. Update the corresponding `.agent/adapters/*.sh` script.
3. Run `.agent/adapters/generate-all.sh` and verify output in the target platform environment.
4. Update the verification method in `docs/technical/agentic-flow.md#platform-specifications--references`.
