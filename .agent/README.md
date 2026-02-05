# 🤖 Agentic Flow System

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

| Task | Claude Code | Gemini CLI |
|------|-------------|------------|
| Implement task | `/implement-task` | "Follow implement-task workflow" |
| Review code | `/review-code` | "Follow review-code workflow" |
| Plan sprint | `/plan-sprint` | "Follow plan-sprint workflow" |
| Create release | `/create-release` | "Follow create-release workflow" |

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
- `.github/copilot-instructions.md` for GitHub Copilot

## Documentation

For complete documentation, see:
- **Technical Spec**: `docs/technical/agentic-flow.md`
- **Migration Plan**: Section 12 of agentic-flow.md
- **Platform Compatibility**: Section 13 of agentic-flow.md

## Adding Custom Agents

1. Create `.agent/agents/your-agent.md` following the agent frontmatter schema
2. Reference skills from `.agent/skills/`
3. Run `.agent/adapters/generate-all.sh` to update platform configs

## Adding Custom Skills

1. Create `.agent/skills/your-skill/SKILL.md`
2. Reference in agent files via `<!-- invoke-skill: your-skill -->`
3. Run adapters to regenerate platform configs
