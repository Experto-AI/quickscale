# Agentic Flow System

> **Quick Start**: Run `.agent/adapters/generate-all.sh` to generate platform configurations.

This directory contains the unified AI agent architecture and transpiler pipeline for QuickScale development workflows.

## Platform Policy (Verified 2026-02-07)

- **Verified/Native**: Claude Code, Gemini CLI, GitHub Copilot (VS Code), Codex CLI
- **Experimental/Emulated**: Gemini Antigravity, Copilot CLI, OpenCode
- Experimental platforms are disabled by default in `.agent/config.yaml`.

## Directory Structure

```
.agent/
├── README.md                  # This file
├── config.yaml                # Global agent configuration
├── agents/                    # Main agent definitions
├── subagents/                 # Composable sub-agents
├── skills/                    # Reusable capability modules
├── workflows/                 # Explicit execution workflows
├── contexts/                  # Shared context definitions
└── adapters/                  # Platform transpilers
```

## Quick Commands

| Task | Claude Code | Gemini CLI | Copilot |
|------|-------------|------------|---------|
| Implement task | `/implement-task` | `/implement-task` | `#implement-task` |
| Review code | `/review-code` | `/review-code` | `#review-code` |
| Plan sprint | `/plan-sprint` | `/plan-sprint` | `#plan-sprint` |
| Create release | `/create-release` | `/create-release` | `#create-release` |

## Generate Platform Configurations

```bash
# Make adapters executable
chmod +x .agent/adapters/*.sh

# Generate all platform configs
.agent/adapters/generate-all.sh
```

This creates:
- `CLAUDE.md` + `.claude/` for Claude Code
- `GEMINI.md` + `.gemini/` for Gemini CLI
- `.github/copilot-instructions.md` + `.github/prompts/` + `.github/chatmodes/` for Copilot VS Code
- `AGENTS.md` + `.codex/` for Codex CLI

Optional (when explicitly enabled):
- `.gemini/antigravity/` for Gemini Antigravity
- `.github/copilot-cli/` for Copilot CLI
- `.opencode.json` + `.opencode/` for OpenCode

Generation is config-driven via `.agent/config.yaml` (`adapters.platforms.*`, per-platform `support_mode`, and `adapters.output_directory`).

## Project-Agnostic Profiles

- Header templates are resolved by profile: `.agent/templates/<profile>/`.
- Configure with `project.profile` in `.agent/config.yaml`.
- Fallback order: selected profile -> `quickscale` -> `default`.

## Agentic Flow Validation

Use dedicated scripts for `.agent` quality checks:

```bash
./scripts/lint_agentic_flow.sh
./scripts/test_agentic_flow.sh
```

## Documentation

For complete documentation, see:
- **Technical Spec**: `docs/technical/agentic-flow.md`
- **Migration Plan**: Section 12 of agentic-flow.md
- **Platform Compatibility**: Section 13 of agentic-flow.md
- **Adapter Specifications**: Section 14 of agentic-flow.md

## Adding Custom Agents

1. Create `.agent/agents/your-agent.md` following the agent frontmatter schema
2. Reference skills from `.agent/skills/`
3. Run `.agent/adapters/generate-all.sh` to update platform configs

## Adding Custom Skills

1. Create `.agent/skills/your-skill/SKILL.md`
2. Reference in agent files via `<!-- invoke-skill: your-skill -->`
3. Run adapters to regenerate platform configs
