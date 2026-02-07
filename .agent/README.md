# Agentic Flow System

> **Quick Start**: Run `.agent/adapters/generate-all.sh` to generate platform configurations.

This directory contains the unified AI agent architecture for QuickScale development workflows.

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
- `.gemini/antigravity/` for Gemini Antigravity
- `.github/copilot-instructions.md` + `.github/prompts/` + `.github/agents/` for Copilot VS Code
- `.github/copilot-cli/` for Copilot CLI
- `AGENTS.md` + `.codex/` for Codex CLI

Generation is config-driven via `.agent/config.yaml` (`adapters.platforms.*` and `adapters.output_directory`).

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
