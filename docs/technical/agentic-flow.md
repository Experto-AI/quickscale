# Agentic Flow: Cross-Platform AI Agent Architecture

> **Document Type**: Technical Specification & Implementation Plan
> **Status**: 📋 PROPOSAL
> **Created**: 2026-02-04
> **Updated**: 2026-02-05
> **Related**: `.github/prompts/`, `docs/contrib/shared/`

---

## Executive Summary

This document defines a **unified agent architecture** that converts the existing `.github/prompts/` workflow prompts into a modular, cross-platform agent system. The architecture supports:

- **Skills**: Reusable capability modules (extracted from `docs/contrib/shared/`)
- **Agents**: Autonomous task executors with defined roles and workflows
- **Subagents**: Composable agent delegation for complex workflows
- **Workflows**: Explicit, step-by-step execution plans
- **Platform Adapters**: Transpilers for Claude Code, Gemini CLI, GitHub Copilot, Codex CLI, and OpenCode

---

## Table of Contents

1. [Glossary](#glossary)
2. [Prerequisites](#prerequisites)
3. [Quick Start](#quick-start)
4. [Architecture Overview](#architecture-overview)
5. [Directory Structure](#directory-structure)
6. [User Guide](#user-guide)
7. [Skills System](#skills-system)
8. [Agents System](#agents-system)
9. [Workflows System](#workflows-system)
10. [Subagent Composition](#subagent-composition)
11. [Platform Adapters](#platform-adapters)
12. [Migration Plan](#migration-plan)
13. [Platform Compatibility](#platform-compatibility)
14. [Platform Specifications & References](#platform-specifications--references)
15. [Appendices](#appendix-a-file-format-specifications)

---

## Glossary

| Term | Definition |
|------|------------|
| **Agent** | An autonomous task executor with a defined role, inputs, outputs, and workflow. Agents can delegate to subagents and invoke skills. |
| **Subagent** | A specialized, composable agent that handles a specific aspect of a larger workflow. Subagents are invoked by parent agents. |
| **Skill** | A reusable capability module containing domain knowledge, checklists, and structured instructions for specific tasks. |
| **Workflow** | An explicit, step-by-step execution plan that agents follow. Workflows define stages and success criteria. |
| **Adapter** | A transpiler script that converts the unified `.agent/` format to platform-specific configurations (Claude, Gemini, Copilot, etc.). |
| **DSL** | Domain-Specific Language—the `<!-- invoke-skill: X -->` syntax used to declare dependencies between agents, skills, and workflows. |
| **Platform** | An AI coding assistant (Claude Code, Gemini CLI, GitHub Copilot, Codex CLI, OpenCode) that consumes the generated configurations. |

---

## Prerequisites

### Required Tools

| Tool | Purpose | Installation |
|------|---------|-------------|
| **Bash 4.0+** | Adapter script execution | Pre-installed on most systems |
| **Git** | Version control, diff operations | `apt install git` / `brew install git` |
| **yq** (optional) | YAML frontmatter parsing | `pip install yq` / `brew install yq` |

### Platform-Specific Requirements

| Platform | Requirements |
|----------|-------------|
| **Claude Code** | Claude Code extension installed, API access configured |
| **Gemini CLI** | `gemini` CLI installed, authenticated |
| **GitHub Copilot** | VS Code with Copilot extension, active subscription |
| **Codex CLI** | `codex` CLI installed, API key configured |
| **OpenCode** | OpenCode installed with `.opencode` configuration |

### Repository Setup

Before using the agentic flow system:

```bash
# Verify .agent/ directory exists
ls -la .agent/

# Make adapter scripts executable
chmod +x .agent/adapters/*.sh

# Generate platform configurations
.agent/adapters/generate-all.sh
```

---

## Quick Start

### 5-Minute Setup

1. **Generate platform configurations:**
   ```bash
   .agent/adapters/generate-all.sh
   ```

2. **Invoke your first workflow (Claude Code):**
   ```
   /implement-task
   ```
   Or in chat: "Run the task-implementer agent for the next roadmap task"

3. **Invoke your first workflow (Gemini CLI):**
   ```bash
   gemini chat
   # Then: "Follow the implement-task workflow from GEMINI.md"
   ```

### Common Commands

| Task | Claude Code | Gemini CLI | Copilot | Codex CLI |
|------|-------------|------------|---------|-----------|
| Implement next task | `/implement-task` | `/implement-task` | `#implement-task` | "implement-task from AGENTS.md" |
| Review staged code | `/review-code` | `/review-code` | `#review-code` | "review-code from AGENTS.md" |
| Plan next sprint | `/plan-sprint` | `/plan-sprint` | `#plan-sprint` | "plan-sprint from AGENTS.md" |
| Create release | `/create-release` | `/create-release` | `#create-release` | "create-release from AGENTS.md" |

### Troubleshooting First Run

| Issue | Solution |
|-------|----------|
| "Skill not found" | Run `ls .agent/skills/` to list available skills |
| "Agent not found" | Run `ls .agent/agents/` to list available agents |
| Adapter script fails | Check `bash --version` (requires 4.0+) |
| Generated file empty | Verify source files exist in `.agent/` |

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         AGENTIC FLOW ARCHITECTURE                       │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                        ORCHESTRATION LAYER                      │    │
│  │                                                                 │    │
│  │   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │    │
│  │   │   Roadmap    │  │    Task      │  │    Code      │          │    │
│  │   │   Planner    │─▶│ Implementer  │─▶│   Reviewer   │          │    │
│  │   │    Agent     │  │    Agent     │  │    Agent     │          │    │
│  │   └──────────────┘  └──────────────┘  └──────────────┘          │    │
│  │          │                  │                  │                │    │
│  │          ▼                  ▼                  ▼                │    │
│  │   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │    │
│  │   │   Release    │  │   Scope      │  │   Quality    │          │    │
│  │   │   Manager    │  │  Validator   │  │   Checker    │          │    │
│  │   │    Agent     │  │  (subagent)  │  │  (subagent)  │          │    │
│  │   └──────────────┘  └──────────────┘  └──────────────┘          │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                    │                                    │
│                                    ▼                                    │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                          SKILLS LAYER                           │    │
│  │                                                                 │    │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌────────────┐ │    │
│  │  │    Code     │ │   Testing   │ │Architecture │ │    Git     │ │    │
│  │  │  Principles │ │  Standards  │ │  Guidelines │ │ Operations │ │    │
│  │  └─────────────┘ └─────────────┘ └─────────────┘ └────────────┘ │    │
│  │                                                                 │    │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌────────────┐ │    │
│  │  │Documentation│ │ Task Focus  │ │   Review    │ │  Roadmap   │ │    │
│  │  │  Standards  │ │  Guidelines │ │  Checklist  │ │ Navigation │ │    │
│  │  └─────────────┘ └─────────────┘ └─────────────┘ └────────────┘ │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                    │                                    │
│                                    ▼                                    │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                        WORKFLOWS LAYER                          │    │
│  │                                                                 │    │
│  │  ┌──────────────────┐  ┌──────────────────┐  ┌────────────────┐ │    │
│  │  │  implement-task  │  │   review-code    │  │ create-release │ │    │
│  │  │     workflow     │  │     workflow     │  │    workflow    │ │    │
│  │  └──────────────────┘  └──────────────────┘  └────────────────┘ │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                    │                                    │
│                                    ▼                                    │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                      PLATFORM ADAPTERS                          │    │
│  │                                                                 │    │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐ │    │
│  │  │  Claude  │ │  Gemini  │ │  GitHub  │ │  Codex   │ │OpenCode│ │    │
│  │  │   Code   │ │   CLI    │ │  Copilot │ │   CLI    │ │   AI   │ │    │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └────────┘ │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Directory Structure

```
.agent/
├── README.md                           # Quick start guide
├── config.yaml                         # Global agent configuration
│
├── agents/                             # Main agent definitions
│   ├── roadmap-planner.md              # Sprint planning & validation
│   ├── task-implementer.md             # Code implementation
│   ├── code-reviewer.md                # Quality assurance
│   └── release-manager.md              # Release finalization
│
├── subagents/                          # Composable sub-agents
│   ├── scope-validator.md              # Scope compliance checking
│   ├── architecture-checker.md         # Tech stack validation
│   ├── code-quality-reviewer.md        # SOLID/DRY/KISS validation
│   ├── test-reviewer.md                # Test quality assurance
│   ├── doc-reviewer.md                 # Documentation validation
│   └── report-generator.md             # Review report generation
│
├── skills/                             # Reusable capability modules
│   ├── code-principles/
│   │   ├── SKILL.md                    # Main skill instructions
│   │   └── examples/                   # Usage examples
│   ├── testing-standards/
│   │   ├── SKILL.md
│   │   └── templates/                  # Test templates
│   ├── architecture-guidelines/
│   │   └── SKILL.md
│   ├── documentation-standards/
│   │   └── SKILL.md
│   ├── task-focus/
│   │   └── SKILL.md
│   ├── development-workflow/
│   │   └── SKILL.md                    # Feature dev, bug fix stages
│   ├── git-operations/
│   │   ├── SKILL.md
│   │   └── scripts/                    # Git helper scripts
│   └── roadmap-navigation/
│       └── SKILL.md
│
├── workflows/                          # Explicit execution workflows
│   ├── implement-task.md               # Task implementation workflow
│   ├── review-code.md                  # Code review workflow
│   ├── plan-sprint.md                  # Sprint planning workflow
│   └── create-release.md               # Release creation workflow
│
├── contexts/                           # Shared context definitions
│   ├── authoritative-files.md          # File reference index
│   └── project-conventions.md          # Project-specific rules
│
└── adapters/                           # Platform transpilers
    ├── claude-adapter.sh               # Claude Code adapter
    ├── gemini-adapter.sh               # Gemini CLI adapter
    ├── copilot-adapter.sh              # GitHub Copilot adapter
    ├── codex-adapter.sh                # Codex CLI adapter
    ├── opencode-adapter.sh             # OpenCode adapter
    └── generate-all.sh                 # Generate all platforms
```

> **Note:** The `.agent/` directory contains source-of-truth definitions for the project's AI workflows. It **must be committed** to the repository to ensure all developers use consistent agent logic. Do not add `.agent/` to `.gitignore`.

---

## User Guide

This section explains how to interact with the Agentic Flow system across different platforms.

### Migration from `.github/prompts/` System

**Previous System (GitHub Copilot Prompts):**
- Users invoked prompts via VS Code's `/` commands
- Example: `/roadmap-task-implementation` to start implementing a task
- Prompts were Copilot-specific and required manual workflow management

**New System (Agentic Flow):**
- Agents are invoked through platform-native mechanisms
- Workflows are explicit and self-documenting
- Skills are automatically loaded based on agent requirements

### Invocation by Platform

#### Claude Code

Claude Code has native support for the agent architecture:

```bash
# Use slash commands generated from workflows
/implement-task
/review-code
/plan-sprint
/create-release

# Or invoke agents directly in chat
"Run the task-implementer agent for task T4.3"
"Start the code-reviewer agent on my staged changes"
```

Claude automatically reads `CLAUDE.md` and has access to `.agent/skills/`.

#### Gemini CLI

```bash
# Start Gemini with the project context
gemini chat

# Invoke by referencing the workflow
"Follow the implement-task workflow from GEMINI.md"
"Review my code using the review-code workflow"
```

Gemini reads `GEMINI.md` which contains flattened workflows and skills.

#### GitHub Copilot (VS Code)

```
# In Copilot Chat, reference the agent files directly
@workspace Follow the task implementation workflow in .agent/workflows/implement-task.md

# Or use the condensed instructions
@workspace Apply the coding guidelines from .github/copilot-instructions.md
```

> **Note:** Copilot has limited agent support. Complex workflows may need manual step-by-step guidance.

#### Codex CLI

```bash
# Start Codex with AGENTS.md context
codex --instructions AGENTS.md

# Then invoke workflows
"Execute the implement-task workflow"
```

#### OpenCode

```bash
# OpenCode reads .opencode configuration
opencode

# Invoke workflows in chat
"Follow implement-task workflow"
```

### Common User Workflows

#### 1. Implementing a Roadmap Task

```
User: "Implement the next roadmap task"

Agent Actions:
1. Reads docs/technical/roadmap.md
2. Identifies first uncompleted task
3. Follows implement-task workflow
4. Invokes code-principles, testing-standards skills
5. Creates implementation + tests
6. Updates roadmap checkboxes
```

#### 2. Reviewing Code Changes

```
User: "Review my staged changes"

Agent Actions:
1. Runs git diff --cached
2. Invokes code-reviewer agent
3. Delegates to subagents (scope-validator, test-reviewer, etc.)
4. Generates review report with findings
```

#### 3. Creating a Release

```
User: "Create release for completed sprint"

Agent Actions:
1. Invokes release-manager agent
2. Validates all tasks complete
3. Generates commit message
4. Creates release document
5. Cleans up roadmap
```

### Skill and Agent Invocation Syntax (DSL Reference)

The architecture uses a **Domain-Specific Language (DSL)** for declaring dependencies:

```markdown
<!-- invoke-skill: code-principles -->
<!-- invoke-skill: testing-standards -->
<!-- invoke-agent: code-reviewer -->
<!-- invoke-workflow: implement-task -->
```

**DSL Directive Format:**

| Directive | Purpose | Processed At |
|-----------|---------|-------------|
| `<!-- invoke-skill: NAME -->` | Load a skill module | Generation time + Runtime |
| `<!-- invoke-agent: NAME -->` | Delegate to another agent | Runtime only |
| `<!-- invoke-workflow: NAME -->` | Reference a workflow | Generation time |

**Processing Semantics:**

1. **Generation Time (Adapter Scripts):**
   - Directives are parsed by adapter scripts during `generate-*.sh` execution
   - For Claude Code: Directives become native skill/tool references
   - For Gemini/Codex: Skill content is inlined at the directive location
   - For Copilot: Key principles are extracted into the instructions file

2. **Runtime (AI Agent Execution):**
   - Agent reads referenced skill/agent files from `.agent/`
   - Applies skill checklists and guidelines
   - Reports violations using the skill's output format
   - Delegates to referenced agents as needed

3. **Dependency Resolution:** (See [Appendix D](#appendix-d-dependency-resolution-algorithm))
   - Transitive dependencies are resolved automatically
   - Circular dependencies are detected and reported

4. **Error Handling:**
   - **Skill not found:** Agent reports error and lists available skills
   - **Agent not found:** Fallback to manual workflow steps
   - **Version mismatch:** Warning logged, latest version used
   - **Circular dependency:** Generation fails with dependency chain report

### Quick Reference Card

| Action | Claude Code | Gemini CLI | Copilot | Codex CLI |
|--------|-------------|------------|---------|-----------|
| Implement task | `/implement-task` | `/implement-task` or "Follow implement-task workflow" | `#implement-task` or `@task-implementer` | "Follow implement-task from AGENTS.md" |
| Review code | `/review-code` | `/review-code` or "Follow review-code workflow" | `#review-code` or `@code-reviewer` | "Follow review-code from AGENTS.md" |
| Plan sprint | `/plan-sprint` | `/plan-sprint` or "Follow plan-sprint workflow" | `#plan-sprint` or `@roadmap-planner` | "Follow plan-sprint from AGENTS.md" |
| Create release | `/create-release` | `/create-release` or "Follow create-release workflow" | `#create-release` or `@release-manager` | "Follow create-release from AGENTS.md" |

---

## Skills System

Skills are **reusable capability modules** that agents can invoke. Each skill encapsulates domain knowledge and provides structured instructions for specific tasks.

### Skill File Format

```markdown
---
name: code-principles
version: 0.74.0
description: SOLID, DRY, KISS principles for code quality
provides:
  - solid_validation
  - dry_check
  - kiss_assessment
  - explicit_failure_patterns
requires: []
---

# Code Principles Skill

## Overview
This skill provides guidance on applying fundamental code quality principles.

## Capabilities

### SOLID Principles

#### Single Responsibility Principle (SRP)
Each class/function should have one reason to change.

**Validation Checklist:**
- [ ] Class has a single, focused responsibility
- [ ] Function does one thing well
- [ ] No "god objects" or utility dumping grounds

**Example - Good:**
```python
class UserRepository:
    """Handles user data persistence"""
    def save(self, user: User) -> None: ...
    def find_by_id(self, user_id: int) -> User: ...
```

**Example - Bad:**
```python
class UserManager:  # Too many responsibilities
    def save_user(self): ...
    def send_email(self): ...
    def generate_report(self): ...
    def validate_input(self): ...
```

#### Open/Closed Principle (OCP)
Open for extension, closed for modification.

[... additional content ...]

### DRY (Don't Repeat Yourself)

**Validation Steps:**
1. Search for duplicate code blocks (>5 lines identical)
2. Identify repeated logic patterns
3. Check for copy-pasted implementations
4. Verify utility functions are properly extracted

### KISS (Keep It Simple)

**Assessment Criteria:**
- Solution complexity matches problem complexity
- No premature abstractions
- Clear, readable implementations
- Avoids overengineering

### Explicit Failure

**Patterns to Enforce:**
- Raise typed exceptions with clear messages
- No bare `except:` clauses
- No silent failures or swallowed errors
- Fail fast with actionable error messages

## Invocation

When an agent invokes this skill, apply the following:

1. Read the code file(s) being validated
2. Run through each principle's checklist
3. Report findings with file:line references
4. Provide specific recommendations for violations

## Related Skills
- `testing-standards` - For test quality validation
- `documentation-standards` - For docstring format
```

### Skills Extracted from Current Prompts

| Source File | New Skill | Key Capabilities |
|-------------|-----------|------------------|
| `docs/contrib/shared/code_principles.md` | `code-principles` | SOLID, DRY, KISS, explicit failure |
| `docs/contrib/shared/testing_standards.md` | `testing-standards` | Test isolation, mocking, coverage |
| `docs/contrib/shared/architecture_guidelines.md` | `architecture-guidelines` | Tech stack, layer boundaries |
| `docs/contrib/shared/documentation_standards.md` | `documentation-standards` | Docstrings, comments, README |
| `docs/contrib/shared/task_focus_guidelines.md` | `task-focus` | Scope discipline, boundary enforcement |
| `docs/contrib/shared/development_workflow.md` | `development-workflow` | Feature development, bug fixing, workflow stages |
| *New* | `git-operations` | Commits, staging, tags, diffs |
| *New* | `roadmap-navigation` | Task detection, checklist parsing |

> **Note:** All 6 files from `docs/contrib/shared/` are mapped. The `development-workflow` skill captures the staged approach (PLAN → CODE → REVIEW → TEST → COMPLETE) used across agents.

---

## Agents System

Agents are **autonomous task executors** with defined roles, inputs, outputs, and workflows.

### Agent File Format

```markdown
---
name: task-implementer
version: 0.74.0
description: Implements roadmap tasks with staged workflow
mode: adaptive

# Agent capabilities and dependencies
skills:
  - code-principles
  - testing-standards
  - architecture-guidelines
  - task-focus
  - git-operations

# Agents or subagents this agent can delegate to
delegates_to:
  - scope-validator
  - code-reviewer

# Workflows this agent can execute
workflows:
  - implement-task

# Input/output contract
inputs:
  - name: task_id
    type: string
    required: false
    priority: 1       # Order to read inputs (lower = earlier)
    auto_detect:
      method: scan_roadmap
      file: docs/technical/roadmap.md
      criteria: first_uncompleted_task
outputs:
  - name: implementation_files
    type: file_list
  - name: test_files
    type: file_list

# Success criteria
success_when:
  - all_checklist_items_complete: true
  - validation:
      - command: ./scripts/lint.sh
        expect: exit_code_0
      - command: ./scripts/test_unit.sh
        expect: exit_code_0
---

# Task Implementer Agent

## Role

You are an expert software engineer and code assistant specializing in Python,
CLI tools, and project scaffolding. You have deep knowledge of best practices
in code quality, testing, and documentation.

## Goal

Implement the specified roadmap task or sprint with high-quality, in-scope code,
tests, and verifiable validation. This agent enforces strict scope discipline,
references authoritative docs, and requires measurable validation.

## Authoritative Context

Before any implementation, read these files in order:

**Development Stage Files:**
1. `docs/contrib/plan.md` — Review task scope before coding
2. `docs/contrib/code.md` — Implementation rules and patterns
3. `docs/contrib/review.md` — Quality checklist (after code, before testing)
4. `docs/contrib/testing.md` — Test generation (after review)

**Project Context:**
5. `README.md` — General project understanding
6. `docs/technical/roadmap.md` — Task checklist and deliverables
7. `docs/technical/decisions.md` — IN vs OUT of scope
8. `docs/technical/scaffolding.md` — Directory layout conventions

## Scope Rules

**MANDATORY - Enforce these rules strictly:**

- Implement ONLY items explicitly listed in the roadmap task checklist
- Do NOT add features outside the task scope
- If a minor helper is required, keep it minimal and document justification
- Any scope questions → delegate to `scope-validator` subagent

## Workflow

This agent follows the `implement-task` workflow. See `.agent/workflows/implement-task.md`.

### Stage Overview

```
┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐     ┌──────────┐
│  PLAN   │────▶│  CODE   │────▶│ REVIEW  │────▶│  TEST   │────▶│ COMPLETE │
│         │     │         │     │         │     │         │     │          │
│ Read    │     │ Write   │     │ Validate│     │ Run     │     │ Document │
│ context │     │ code    │     │ quality │     │ tests   │     │ progress │
└─────────┘     └─────────┘     └─────────┘     └─────────┘     └──────────┘
                                     │
                                     ▼
                              ┌─────────────┐
                              │code-reviewer│
                              │   agent     │
                              └─────────────┘
```

## Skill Invocations

During implementation, invoke these skills:

| Stage | Skill | Purpose |
|-------|-------|---------|
| CODE | `code-principles` | Validate SOLID/DRY/KISS |
| CODE | `architecture-guidelines` | Verify tech stack compliance |
| CODE | `task-focus` | Enforce scope boundaries |
| TEST | `testing-standards` | Generate proper tests |
| COMPLETE | `git-operations` | Stage changes, verify status |

## Delegation

| Condition | Delegate To | Purpose |
|-----------|-------------|---------|
| Scope unclear | `scope-validator` | Verify change is in-scope |
| Code complete | `code-reviewer` | Full quality review |

## Error Handling

- **Invalid inputs**: Raise clear error with actionable message
- **Scope violation detected**: Stop and report, do not implement
- **Tests fail**: Fix issues before proceeding to COMPLETE stage
- **Lint fails**: Fix all lint errors before proceeding

## Completion Checklist

- [ ] All roadmap checklist items implemented
- [ ] All items marked `[x]` in `docs/technical/roadmap.md`
- [ ] `./scripts/lint.sh` passes
- [ ] `./scripts/test_unit.sh` passes
- [ ] Task-specific validation commands succeed
- [ ] No out-of-scope features introduced
```

### Agents Derived from Current Prompts

| Source Prompt | Agent Name | Primary Responsibility |
|---------------|------------|------------------------|
| `roadmap-plan-review-and-update.prompt.md` | `roadmap-planner` | Sprint planning, release selection, roadmap validation |
| `roadmap-task-implementation.prompt.md` | `task-implementer` | Code implementation with staged workflow |
| `roadmap-task-review.prompt.md` | `code-reviewer` | Quality assurance, scope compliance, code review |
| `release-commit-message-and-roadmap-cleaning.prompt.md` | `release-manager` | Release commits, roadmap cleanup, version tagging |

---

## Workflows System

Workflows are **explicit, step-by-step execution plans** that agents follow.

### Workflow File Format

```markdown
---
name: implement-task
description: End-to-end task implementation workflow
version: 0.74.0
agent: task-implementer
stages: 5
estimated_duration: 30-120 minutes
---

# Implement Task Workflow

This workflow guides the task implementation process from planning through completion.

## Prerequisites

- Task ID identified (auto-detect if not provided)
- Clean git working directory
- Development environment ready

---

## Stage 1: PLAN

**Context File**: `docs/contrib/plan.md`

### Step 1.1: Read Authoritative Docs
Read these files to understand context:
- `README.md`
- `docs/technical/roadmap.md`
- `docs/technical/decisions.md`
- `docs/technical/scaffolding.md`

### Step 1.2: Identify Task
If `task_id` not provided:
1. Open `docs/technical/roadmap.md`
2. Find first release section with uncompleted tasks
3. Select first task without `✅` on its key deliverable
4. Record Task ID and full checklist

### Step 1.3: Review Scope
- Compare task against `decisions.md` IN/OUT scope
- Identify files to create/modify
- Plan for testability

### Step 1.4: Confirm Understanding
Before proceeding, verify:
- [ ] Task checklist is clear
- [ ] Deliverables are identified
- [ ] No scope ambiguities

---

## Stage 2: CODE

**Context File**: `docs/contrib/code.md`

<!-- invoke-skill: code-principles -->
<!-- invoke-skill: architecture-guidelines -->

### Step 2.1: Implement Core Functionality
```bash
# Verify starting state
git status
```

Follow these principles:
- SOLID, DRY, KISS from `code-principles` skill
- Tech stack from `architecture-guidelines` skill
- Keep changes focused and in-scope

### Step 2.2: Write Type Hints and Docstrings
- Type hints for all public functions
- Google-style docstrings (follow `docs/contrib/documentation_standards.md`)

### Step 2.3: Run Initial Lint
```bash
./scripts/lint.sh
```

Fix any lint errors before proceeding.

---

## Stage 3: REVIEW

**Context File**: `docs/contrib/review.md`

<!-- invoke-agent: code-reviewer -->

### Step 3.1: Self-Review
Review implementation against `review.md` checklist:
- [ ] Technical stack compliance
- [ ] Architecture adherence
- [ ] Scope compliance
- [ ] Documentation completeness

### Step 3.2: Delegate to Code Reviewer (Optional)
For complex changes, delegate to `code-reviewer` agent for full review.

---

## Stage 4: TEST

**Context File**: `docs/contrib/testing.md`

<!-- invoke-skill: testing-standards -->

### Step 4.1: Generate Tests
Write tests AFTER code review is complete (implementation-first approach).
Tests must validate the logic established in the CODE and REVIEW stages.
- Unit tests for new functionality
- Integration tests when required
- Follow test patterns from `testing-standards` skill

### Step 4.2: Run Test Suite
```bash
./scripts/test_unit.sh
```

### Step 4.3: Run Task Validation
```bash
# Run task-specific validation commands from roadmap
[VALIDATION_COMMANDS]
```

Fix any failures before proceeding.

---

## Stage 5: COMPLETE

### Step 5.1: Update Roadmap
Open `docs/technical/roadmap.md` and mark all completed items `[x]`.

### Step 5.2: Verify Completion
```bash
# Final verification
./scripts/lint.sh
./scripts/test_unit.sh
git status
```

### Step 5.3: Stage Changes (Do Not Commit)
Keep changes staged for final review.

---

## Success Criteria

All of the following must be true:

| Criterion | Validation |
|-----------|------------|
| All checklist items complete | Visual inspection of roadmap |
| Roadmap items marked `[x]` | `docs/technical/roadmap.md` updated |
| Lint passes | `./scripts/lint.sh` exit code 0 |
| Tests pass | `./scripts/test_unit.sh` exit code 0 |
| Task validation succeeds | Custom validation commands |
| No scope creep | Review confirms in-scope only |
```

---

## Subagent Composition

Subagents are **specialized, composable agents** that handle specific aspects of a larger workflow.

### Decomposition of `code-reviewer` Agent

The original `roadmap-task-review.prompt.md` (873 lines) is decomposed into focused subagents:

```
┌─────────────────────────────────────────────────────────────────────┐
│                        CODE-REVIEWER (Main Agent)                    │
│                                                                      │
│  Orchestrates the review process, delegates to subagents            │
│                                                                      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────────┐    ┌──────────────────┐    ┌────────────────┐ │
│  │  scope-validator │    │architecture-check│    │ code-quality-  │ │
│  │                  │    │       er         │    │   reviewer     │ │
│  │  • Deliverable   │    │  • Tech stack    │    │  • SOLID       │ │
│  │    matching      │    │  • Layers        │    │  • DRY/KISS    │ │
│  │  • Scope creep   │    │  • Boundaries    │    │  • Style       │ │
│  │  • Task bounds   │    │  • Patterns      │    │  • Naming      │ │
│  └────────┬─────────┘    └────────┬─────────┘    └───────┬────────┘ │
│           │                       │                       │          │
│           ▼                       ▼                       ▼          │
│  ┌──────────────────┐    ┌──────────────────┐    ┌────────────────┐ │
│  │  test-reviewer   │    │   doc-reviewer   │    │report-generator│ │
│  │                  │    │                  │    │                │ │
│  │  • Isolation     │    │  • Docstrings    │    │  • Findings    │ │
│  │  • No global     │    │  • Comments      │    │  • Metrics     │ │
│  │    mocking       │    │  • Coverage      │    │  • Recommend-  │ │
│  │  • Coverage      │    │  • Standards     │    │    ations      │ │
│  └──────────────────┘    └──────────────────┘    └────────────────┘ │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### Subagent File Format

```markdown
---
name: scope-validator
version: 0.74.0
description: Validates changes are within task scope
parent: code-reviewer
type: subagent

skills:
  - task-focus
  - roadmap-navigation

inputs:
  - name: staged_files
    type: file_list
  - name: task_id
    type: string
  - name: roadmap_checklist
    type: checklist

outputs:
  - name: scope_status
    type: enum
    values: [PASS, FAIL, ISSUES]
  - name: violations
    type: list
  - name: recommendations
    type: list
---

# Scope Validator Subagent

## Purpose

Validate that all staged changes are within the defined task scope.
Flag any out-of-scope additions or scope creep.

## Invocation

Called by `code-reviewer` agent during review workflow.

## Process

### Step 1: Load Task Scope
1. Read `docs/technical/roadmap.md`
2. Extract checklist for `{task_id}`
3. Identify expected deliverables (files, features)

### Step 2: Analyze Staged Changes
```bash
git diff --cached --stat
git diff --cached --name-only
```

### Step 3: Compare Against Scope
For each staged file:
- [ ] File is a deliverable mentioned in task checklist
- [ ] Changes relate to task requirements
- [ ] No unrelated refactoring introduced
- [ ] No "nice-to-have" features added

### Step 4: Flag Violations
For any out-of-scope change:
- Record file:line reference
- Explain why it's out of scope
- Recommend: remove, defer, or request scope expansion

## Output Format

```yaml
scope_status: PASS | FAIL | ISSUES
violations:
  - file: path/to/file.py
    line: 42
    type: out_of_scope_feature
    description: "Added caching layer not in task checklist"
    recommendation: "Remove or defer to dedicated caching task"
recommendations:
  - "Consider adding caching to roadmap as separate task"
```

## Related Subagents
- `architecture-checker` - Validates tech stack compliance
- `code-quality-reviewer` - Validates code principles
```

### Subagent Mapping

| Responsibility | Subagent | Steps Covered |
|----------------|----------|---------------|
| Scope compliance | `scope-validator` | Review steps 6-9 |
| Architecture check | `architecture-checker` | Review steps 10-13 |
| Code quality | `code-quality-reviewer` | Review steps 14-19 |
| Test quality | `test-reviewer` | Review steps 20-26 |
| Documentation | `doc-reviewer` | Review steps 27-30 |
| Report generation | `report-generator` | Review steps 35-42 |

---

## Platform Adapters

Adapters **transpile** the unified agent format to platform-specific configurations.

### Adapter Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                    .agent/ (Source of Truth)                      │
│                                                                   │
│  agents/*.md  +  skills/*.md  +  workflows/*.md  +  subagents/   │
└───────────────────────────┬──────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────────┐
│                 .agent/adapters/generate-all.sh                   │
└───────────────────────────┬──────────────────────────────────────┘
                            │
    ┌───────────┬───────────┼───────────┬───────────┐
    │           │           │           │           │
    ▼           ▼           ▼           ▼           ▼
┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐
│ Claude │ │ Gemini │ │Copilot │ │ Codex  │ │Open   │
│  Code  │ │  CLI   │ │        │ │  CLI   │ │ Code  │
│        │ │        │ │        │ │        │ │       │
│CLAUDE  │ │GEMINI  │ │copilot-│ │AGENTS  │ │.open- │
│.md     │ │.md     │ │instruc-│ │.md     │ │code.  │
│.claude/│ │.gemini/│ │tions.md│ │.codex/ │ │json   │
│  cmds/ │ │  cmds/ │ │prompts/│ │config  │ │.open- │
│  agents│ │  sett- │ │agents/ │ │.toml   │ │code/  │
│        │ │  ings  │ │instruc-│ │        │ │cmds/  │
│        │ │        │ │tions/  │ │        │ │       │
└────────┘ └────────┘ └────────┘ └────────┘ └────────┘
```

> **Note:** All adapters are implemented as Bash 4.0+ scripts using shared helpers for YAML frontmatter extraction, body content parsing, and TOML/JSON escaping.

### Claude Code Adapter

Claude Code has the richest native support. The adapter maps `.agent/` concepts almost 1:1.

**Output Structure:**
```
CLAUDE.md                    # Project instructions with @import syntax
.claude/
├── commands/                # Slash commands (from .agent/workflows/)
│   ├── implement-task.md    #   - description frontmatter
│   ├── review-code.md       #   - $ARGUMENTS support
│   ├── plan-sprint.md       #   - Step summaries from workflow
│   └── create-release.md
└── agents/                  # Custom agents (from .agent/agents/ + subagents/)
    ├── task-implementer.md  #   - name/description frontmatter only
    ├── code-reviewer.md     #   - Skills mapped to /command references
    ├── roadmap-planner.md   #   - delegates_to mapped to agent delegation
    ├── release-manager.md
    ├── scope-validator.md   # Subagents also become agents
    ├── architecture-checker.md
    └── ...
```

**Key Mappings:**
- `CLAUDE.md` uses `@.agent/contexts/*.md` import syntax (max 5 hops)
- Workflows → `.claude/commands/*.md` with `description:` frontmatter
- Agents + Subagents → `.claude/agents/*.md` with Claude-supported frontmatter only
- Source `skills:` list → `/command` references in agent body
- Source `delegates_to:` → delegation instructions in agent body
- Preserves `.claude/settings.local.json` (never overwritten)

### Gemini CLI Adapter

Gemini CLI supports custom TOML commands with file injection and argument interpolation.

**Output Structure:**
```
GEMINI.md                    # Project context with @path imports
.gemini/
├── settings.json            # Skills + experimental agents enabled
└── commands/                # TOML custom commands (from .agent/workflows/)
    ├── implement-task.toml  #   - @{path} file injection
    ├── review-code.toml     #   - {{args}} interpolation
    ├── plan-sprint.toml     #   - Agent role + skill references
    └── create-release.toml
.geminiignore                # Created if absent (preserves user edits)
```

**Key Mappings:**
- `GEMINI.md` uses `@.agent/contexts/*.md` import syntax
- Workflows → `.gemini/commands/*.toml` with `@{path}` file injection
- Skills referenced via `@{.agent/skills/NAME/SKILL.md}` in commands
- Agent roles embedded in command steps via `@{.agent/agents/NAME.md}`
- `settings.json` enables `skills.enabled` and `experimental.enableAgents`

### GitHub Copilot Adapter

Copilot now has rich native support for agents, prompts, and path-specific instructions.

**Output Structure:**
```
.github/
├── copilot-instructions.md              # Always-on project guidance
├── prompts/                             # Reusable prompt files (from workflows)
│   ├── implement-task.prompt.md         #   - mode: agent
│   ├── review-code.prompt.md            #   - tools: list
│   ├── plan-sprint.prompt.md            #   - ${input:varName} variables
│   └── create-release.prompt.md
├── agents/                              # Custom agents
│   ├── task-implementer.agent.md        #   - tools: list
│   ├── code-reviewer.agent.md           #   - agents: subagent references
│   ├── scope-validator.agent.md         # Subagents also become agents
│   └── ...
└── instructions/                        # Path-specific instructions
    ├── python.instructions.md           #   - applyTo: "**/*.py"
    ├── testing.instructions.md          #   - applyTo: "**/test_*.py"
    ├── frontend.instructions.md         #   - applyTo: "**/*.{ts,tsx}"
    └── docs.instructions.md             #   - applyTo: "**/*.md"
```

**Key Mappings:**
- Workflows → `.github/prompts/*.prompt.md` with `mode: agent` and `tools:` list
- Agents + Subagents → `.github/agents/*.agent.md` with `agents:` for delegation
- Skills referenced as file paths in agent/prompt body
- Path-specific instructions generated for Python, tests, frontend, docs
- `copilot-instructions.md` includes dynamic tables of prompts, agents, and skills

### Codex CLI Adapter

Codex uses `AGENTS.md` as its primary instruction file (auto-read at startup).

**Output Structure:**
```
AGENTS.md                    # Hierarchical project instructions (primary)
.codex/
└── config.toml              # Sandbox mode, fallback filenames
```

**Key Mappings:**
- All agents, skills, and workflows summarized in `AGENTS.md`
- Workflow steps extracted and listed under each workflow heading
- `.codex/config.toml` sets `sandbox_mode` and `project_doc_fallback_filenames`
- Skills in `.agent/skills/*/SKILL.md` are already agentskills.io-compatible
- Subagents flattened into instruction text (no native subagent support)
- Config only created if absent (preserves user customization)

### OpenCode Adapter

OpenCode is archived (succeeded by Crush) but supported for compatibility.

**Output Structure:**
```
.opencode.json               # Project config (agents, LSP)
.opencode/
└── commands/                # Custom commands (from .agent/workflows/)
    ├── implement-task.md    #   - $TASK_ID argument
    ├── review-code.md
    ├── plan-sprint.md
    └── create-release.md
```

**Key Mappings:**
- `.opencode.json` configures `coder` and `task` agents with system prompts
- Workflows → `.opencode/commands/*.md` with `$NAME` argument placeholders
- Skills/subagents flattened into system prompt and command instructions
- LSP config for Python (pyright) included by default

---

## Migration Plan

### Phase 1: Extract Skills

Convert existing shared docs to skill format:

| Source | Destination | Status |
|--------|-------------|--------|
| `docs/contrib/shared/code_principles.md` | `.agent/skills/code-principles/SKILL.md` | ✅ DONE |
| `docs/contrib/shared/testing_standards.md` | `.agent/skills/testing-standards/SKILL.md` | ✅ DONE |
| `docs/contrib/shared/architecture_guidelines.md` | `.agent/skills/architecture-guidelines/SKILL.md` | ✅ DONE |
| `docs/contrib/shared/documentation_standards.md` | `.agent/skills/documentation-standards/SKILL.md` | ✅ DONE |
| `docs/contrib/shared/task_focus_guidelines.md` | `.agent/skills/task-focus/SKILL.md` | ✅ DONE |
| `docs/contrib/shared/development_workflow.md` | `.agent/skills/development-workflow/SKILL.md` | ✅ DONE |
| *New* | `.agent/skills/git-operations/SKILL.md` | ✅ DONE |
| *New* | `.agent/skills/roadmap-navigation/SKILL.md` | ✅ DONE |

### Phase 2: Create Agents

Convert prompts to agent format:

| Source | Destination | Status |
|--------|-------------|--------|
| `roadmap-plan-review-and-update.prompt.md` | `.agent/agents/roadmap-planner.md` | ✅ DONE |
| `roadmap-task-implementation.prompt.md` | `.agent/agents/task-implementer.md` | ✅ DONE |
| `roadmap-task-review.prompt.md` | `.agent/agents/code-reviewer.md` | ✅ DONE |
| `release-commit-message-and-roadmap-cleaning.prompt.md` | `.agent/agents/release-manager.md` | ✅ DONE |

### Phase 3: Create Subagents

Decompose `code-reviewer` into subagents:

| Subagent | Source Sections | Status |
|----------|-----------------|--------|
| `scope-validator` | Review steps 6-9 | ✅ DONE |
| `architecture-checker` | Review steps 10-13 | ✅ DONE |
| `code-quality-reviewer` | Review steps 14-19 | ✅ DONE |
| `test-reviewer` | Review steps 20-26 | ✅ DONE |
| `doc-reviewer` | Review steps 27-30 | ✅ DONE |
| `report-generator` | Review steps 35-42 | ✅ DONE |

### Phase 4: Create Workflows

Extract explicit workflows:

| Workflow | Source | Status |
|----------|--------|--------|
| `implement-task` | `roadmap-task-implementation.prompt.md` WORKFLOW section | ✅ DONE |
| `review-code` | `roadmap-task-review.prompt.md` REVIEW WORKFLOW section | ✅ DONE |
| `plan-sprint` | `roadmap-plan-review-and-update.prompt.md` steps | ✅ DONE |
| `create-release` | `release-commit-message-and-roadmap-cleaning.prompt.md` | ✅ DONE |

### Phase 5: Implement Adapters

| Adapter | Target Platform | Priority | Status |
|---------|-----------------|----------|--------|
| `claude-adapter.sh` | Claude Code | 🔴 High | ✅ DONE |
| `gemini-adapter.sh` | Gemini CLI | 🔴 High | ✅ DONE |
| `copilot-adapter.sh` | GitHub Copilot | 🟡 Medium | ✅ DONE |
| `codex-adapter.sh` | Codex CLI | 🟢 Low | ✅ DONE |
| `opencode-adapter.sh` | OpenCode | 🟢 Low | ✅ DONE |

### Phase 6: Validation & Cleanup

**Validation Checklist:**

- [ ] Test all agents on Claude Code
- [ ] Test all agents on Gemini CLI
- [ ] Test Copilot instructions integration
- [ ] Compare output quality to original prompts
- [ ] Run sample task through each workflow
- [ ] Verify skill invocations work correctly
- [ ] Check adapter output matches expected format

**Acceptance Criteria:**

| Test | Expected Result | Validation Method |
|------|-----------------|------------------|
| Agent invocation | Agent starts and reads context | Manual test on each platform |
| Skill loading | Skill principles applied to output | Code review of generated code |
| Workflow stages | All 5 stages complete in order | Trace log review |
| Subagent delegation | Subagent returns valid report | Output format validation |
| Cross-platform parity | Same task produces similar quality | Side-by-side comparison |

**Rollback Plan:**

If issues arise during migration:

1. **Keep `.github/prompts/` functional** throughout migration
2. **Parallel operation**: Both systems can coexist
3. **Incremental rollout**: Migrate one agent at a time
4. **Quick revert**: Original prompts remain unchanged until validation complete

```bash
# Rollback command (if needed)
git checkout HEAD -- .github/prompts/
rm -rf .agent/  # Remove new system
rm -f CLAUDE.md GEMINI.md  # Remove generated files
```

**Cleanup (after validation passes):**

- [x] Archive `.github/prompts/` to `docs/legacy/prompts/`
- [ ] Update README.md with new agent instructions
- [ ] Update CONTRIBUTING.md
- [ ] Remove adapter generation from CI (if applicable)

---

## Platform Compatibility

### Feature Support Matrix

| Feature | Claude Code | Gemini CLI | Copilot | Codex CLI | OpenCode |
|---------|:-----------:|:----------:|:-------:|:---------:|:------:|
| **Platform Status** | ✅ Active | ✅ Active | ✅ Active | ✅ Active | ❌ Archived (Sep 2025) |
| **Markdown Instructions** | ✅ CLAUDE.md | ✅ GEMINI.md | ✅ copilot-instructions.md | ✅ AGENTS.md | ⚠️ JSON config |
| **Import Syntax** | ✅ `@path` | ✅ `@path` | ❌ No | ✅ Concatenation | ❌ No |
| **Custom Commands** | ✅ `.claude/commands/` (Skills) | ✅ `.gemini/commands/*.toml` | ✅ `.github/prompts/*.prompt.md` | ✅ Skills | ✅ `.opencode/commands/` |
| **Custom Agents** | ✅ `.claude/agents/` | ✅ Stable (v0.27.0+) | ⚠️ Experimental | ❌ No | ❌ No |
| **Subagent Delegation** | ✅ Native | ❌ Flatten | ✅ `agents:` frontmatter | ❌ Flatten | ❌ Built-in only |
| **Path-Specific Rules** | ✅ `.claude/rules/` | ❌ No | ✅ `.github/instructions/` | ❌ Nested dirs only | ❌ No |
| **Skills/Tools** | ✅ Native | ✅ Stable (v0.27.0+) | ⚠️ Experimental | ✅ agentskills.io | ❌ No |
| **MCP Support** | ✅ `.mcp.json` | ✅ `mcpServers` in settings | ✅ VS Code settings | ✅ `config.toml` | ✅ JSON config |
| **AGENTS.md Support** | ❌ No | ❌ No | ✅ Since Aug 2025 | ✅ Primary | ❌ No |
| **Lifecycle Hooks** | ✅ Rich | ✅ Rich | ❌ No | ⚠️ `notify` only | ❌ No |
| **File References** | ✅ Yes | ✅ `@{path}` injection | ⚠️ Limited | ✅ Yes | ✅ Yes |
| **Command Execution** | ✅ Yes | ✅ Yes | ✅ `runInTerminal` tool | ✅ Yes | ✅ Yes |
| **Multi-File Editing** | ✅ Yes | ✅ Yes | ✅ `editFiles` tool | ✅ Yes | ✅ Yes |
| **Sandboxing** | ✅ Yes | ✅ Docker/Seatbelt | ❌ No | ✅ `sandbox_mode` | ❌ No |

### Adapter Strategy by Platform

| Platform | Strategy | Output Files | Complexity |
|----------|----------|-------------|------------|
| **Claude Code** | Full native — agents, skills (merged Jan 2026), @imports | `CLAUDE.md`, `.claude/commands/`, `.claude/agents/` | Low (1:1 mapping) |
| **Gemini CLI** | Commands via TOML, @imports, event-driven (v0.27.0) | `GEMINI.md`, `.gemini/commands/`, `.gemini/settings.json` | Medium |
| **GitHub Copilot** | Rich — prompts, agents, AGENTS.md (Aug 2025) | `.github/copilot-instructions.md`, `prompts/`, `agents/`, `instructions/` | Low (rich native support) |
| **Codex CLI** | AGENTS.md primary (auto-read), skills via agentskills.io | `AGENTS.md`, `.codex/config.toml` | Medium |
| **OpenCode** | Archived (Sep 2025) — compatibility only | `.opencode.json`, `.opencode/commands/` | High (limited features) |

---

## Platform Specifications & References

This section documents the technical specifications and documentation sources used to develop the transpiler adapters.

### Claude Code
- **Source**: [Anthropic Claude Code Documentation](https://docs.anthropic.com/en/docs/agents-and-tools/claude-code)
- **Key Specifications**:
  - `CLAUDE.md`: Use of `@import` syntax for context modularity.
  - `.claude/commands/`: YAML frontmatter with `description:` and `$ARGUMENTS` interpolation.
    - **Note**: Slash commands merged into skills system (Jan 24, 2026) — commands are now treated as skills automatically.
  - `.claude/agents/`: Native agent persona definitions with role-based instructions.
- **Verification Method**: Iterative testing with `claude-code` CLI version 1.2+ (as of Feb 2026).

### Gemini CLI
- **Source**: [Google Gemini Developer CLI Reference](https://github.com/google-gemini/gemini-cli)
- **Key Specifications**:
  - `GEMINI.md`: Path-relative imports using `@{path}` marker.
  - `.gemini/settings.json`: Configuration for native agent support.
    - **Note**: Agent Skills promoted to stable in v0.27.0 (Feb 3, 2026) with event-driven architecture.
  - TOML Commands: Use of `{{args}}` for dynamic command interpolation and shell execution hooks.
- **Verification Method**: Command validation against `gemini config --schema` (v0.27.0+).

### GitHub Copilot
- **Source**: [GitHub Copilot Customization Guide](https://docs.github.com/en/copilot/using-github-copilot/customizing-copilot-with-custom-instructions) and [VS Code Copilot Wiki](https://github.com/microsoft/vscode-copilot/wiki).
- **Key Specifications**:
  - `.github/copilot-instructions.md`: Unified markdown rules for workspace-wide context.
  - `AGENTS.md`: Official support added Aug 28, 2025 (Linux Foundation/Agentic AI Foundation open standard).
  - `.agent.md`: Role-based agent discovery (supported by agentskills.io extension).
  - `.prompt.md`: Structured task markers for prompt-discovery in Copilot Chat.
  - **Note**: Experimental Agent Skills in active development (VS Code 1.108+).
- **Verification Method**: Manual inspection of `.github/` artifacts and integration with VS Code Copilot Chat (v1.108+).

### Codex CLI
- **Source**: [Codex Agents Protocol Specification](https://github.com/openai/codex-agents)
- **Key Specifications**:
  - `AGENTS.md`: Primary instruction file (automatically read by Codex CLI).
    - **Note**: Part of the Linux Foundation/Agentic AI Foundation open standard.
  - `.codex/config.toml`: Registry of skills and tool-call mapping with fallback filenames.
  - Command Hooks: Execution of `.agent/adapters/` scripts as native pre-processing hooks.
- **Verification Method**: Linting generated TOML against established Codex CLI schema.

### OpenCode
- **Status**: ⚠️ **ARCHIVED** (September 2025) — Succeeded by Crush
- **Source**: [OpenCode Developer Portal](https://opencode.ai/docs) (archived)
- **Key Specifications**:
  - `.opencode.json`: Centralized JSON descriptor for agents and their associated skills.
  - `.opencode/`: Workspace directory for command logic and session-persistent state.
  - Context Injection: Usage of `$WORKSPACE_ROOT` for path-agnostic configurations.
- **Verification Method**: Schema validation of generated `.opencode.json` using `opencode-cli validate`.
- **Note**: Adapter maintained for compatibility with existing installations only. New projects should use Claude Code, Gemini CLI, GitHub Copilot, or Codex CLI.

---

## Platform Updates (2026)

This section documents major platform changes and updates as of early 2026 that affect the agentic flow implementation.

### Claude Code
- **Jan 24, 2026**: Slash commands merged into skills system
  - All `.claude/commands/` files now function as skills automatically
  - No breaking changes — existing command files continue to work
  - Skills and commands are now treated as unified functionality

### Gemini CLI
- **Feb 3, 2026**: v0.27.0 released with event-driven architecture
  - Agent Skills promoted from experimental to stable
  - Improved performance and reliability through event-driven design
  - `experimental.enableAgents` setting retained for backward compatibility

### GitHub Copilot
- **Aug 28, 2025**: AGENTS.md support added (VS Code 1.108+)
  - Adopts Linux Foundation/Agentic AI Foundation open standard
  - AGENTS.md auto-read in workspace root
  - Experimental Agent Skills in active development
  - Enhanced integration with agentskills.io ecosystem

### AGENTS.md Standard
- **2025-2026**: Became open standard under Linux Foundation/Agentic AI Foundation
  - Adopted by GitHub Copilot (Aug 2025) and Codex CLI
  - Provides unified instruction format across platforms
  - Auto-read by supporting platforms (no manual configuration needed)

### OpenCode
- **September 2025**: Project archived and succeeded by Crush
  - No longer actively maintained
  - Existing installations continue to function
  - QuickScale adapter maintained for compatibility only
  - Users encouraged to migrate to active platforms

### Impact on QuickScale

The agentic flow transpiler has been updated to reflect these changes:
- Adapter comments updated with 2026 platform information
- Documentation reflects current platform capabilities
- Deprecation notices added for archived platforms
- No breaking changes to existing workflows

---

## Appendix A: File Format Specifications

### Agent Frontmatter Schema

```yaml
---
name: string              # Unique identifier (kebab-case)
version: 0.74.0
description: string       # One-line description
mode: adaptive | ask      # Interaction mode

skills: string[]          # List of skill names to use
delegates_to: string[]    # List of agent or subagent names
workflows: string[]       # List of workflow names

inputs:                   # Input parameters
  - name: string
    type: string | file | file_list | checklist
    required: boolean
    priority: number      # Optional: Order to read inputs (lower = earlier)
    auto_detect:          # Optional auto-detection config
      method: string
      file: string
      criteria: string

outputs:                  # Output definitions
  - name: string
    type: string | file | file_list | enum
    path: string          # Optional file path template

success_when:             # Success criteria
  - all_checklist_items_complete: boolean
  - validation:
      - command: string
        expect: string
---
```

### Subagent Frontmatter Schema

```yaml
---
name: string              # Unique identifier (kebab-case)
version: 0.74.0
description: string       # One-line description
parent: string            # Parent agent name
type: subagent            # Fixed value

skills: string[]          # List of skill names to use

inputs:                   # Input parameters
  - name: string
    type: string | file | file_list | checklist
    required: boolean

outputs:                  # Output definitions
  - name: string
    type: string | file | file_list | enum
---
```

### Skill Frontmatter Schema

```yaml
---
name: string              # Unique identifier (kebab-case)
version: 0.74.0
description: string       # One-line description

provides: string[]        # Capabilities this skill provides
requires: string[]        # Other skills this depends on
---
```

### Workflow Frontmatter Schema

```yaml
---
name: string              # Unique identifier (kebab-case)
description: string       # One-line description
version: 0.74.0
agent: string             # Primary agent that uses this workflow
stages: number            # Number of stages
estimated_duration: string # Human-readable duration estimate
---
```

---

## Appendix B: Comparison with Current System

### Before (Current `.github/prompts/`)

```
.github/prompts/
├── roadmap-plan-review-and-update.prompt.md     (81 lines)
├── roadmap-task-implementation.prompt.md        (180 lines)
├── roadmap-task-review.prompt.md                (873 lines) ← Monolithic
└── release-commit-message-and-roadmap-cleaning.prompt.md (112 lines)
```

**Issues:**
- 🔴 Monolithic files (especially review at 873 lines)
- 🔴 No reusability (skills duplicated in each prompt)
- 🔴 Platform-specific (GitHub Copilot format)
- 🔴 No subagent composition
- 🔴 Implicit workflows (embedded in prompts)

### After (New `.agent/` System)

```
.agent/
├── agents/          (4 files, ~150 lines each)
├── subagents/       (6 files, ~50 lines each)
├── skills/          (7 directories with SKILL.md)
├── workflows/       (4 files, ~100 lines each)
└── adapters/        (5 shell scripts)
```

**Benefits:**
- ✅ Modular, composable components
- ✅ Reusable skills across agents
- ✅ Cross-platform compatibility
- ✅ Subagent delegation for complex tasks
- ✅ Explicit, traceable workflows
- ✅ Easier maintenance and updates

---

## Appendix C: Related Documentation

- `docs/contrib/plan.md` - Planning methodology
- `docs/contrib/code.md` - Implementation guidelines
- `docs/contrib/review.md` - Review checklist
- `docs/contrib/testing.md` - Testing standards
- `docs/technical/decisions.md` - Architecture decisions
- `docs/technical/scaffolding.md` - Directory structure

---

## Appendix D: Dependency Resolution Algorithm

When adapter scripts process DSL directives, they must resolve transitive dependencies. This section defines the resolution algorithm.

### Algorithm Overview

```
INPUT: Root file (agent or workflow)
OUTPUT: Ordered list of all dependencies

1. Parse root file for DSL directives
2. For each directive:
   a. Add to dependency set
   b. Recursively parse referenced file
   c. Track dependency chain for cycle detection
3. Perform topological sort on dependency graph
4. Return sorted list (dependencies before dependents)
```

### Pseudocode Implementation

```bash
#!/bin/bash
# resolve_dependencies.sh

declare -A VISITED
declare -A IN_STACK
declare -a RESOLVED

resolve() {
    local file="$1"
    local type="$2"  # skill, agent, workflow

    # Cycle detection
    if [[ "${IN_STACK[$file]}" == "true" ]]; then
        echo "ERROR: Circular dependency detected: $file" >&2
        echo "Chain: ${!IN_STACK[@]}" >&2
        exit 1
    fi

    # Skip if already resolved
    if [[ "${VISITED[$file]}" == "true" ]]; then
        return 0
    fi

    IN_STACK[$file]="true"

    # Parse directives from file
    while IFS= read -r directive; do
        case "$directive" in
            *invoke-skill:*)
                skill_name=$(echo "$directive" | sed 's/.*invoke-skill: \([^-]*\).*/\1/' | xargs)
                skill_path=".agent/skills/$skill_name/SKILL.md"
                resolve "$skill_path" "skill"
                ;;
            *invoke-agent:*)
                agent_name=$(echo "$directive" | sed 's/.*invoke-agent: \([^-]*\).*/\1/' | xargs)
                agent_path=".agent/agents/$agent_name.md"
                resolve "$agent_path" "agent"
                ;;
        esac
    done < <(grep -E '<!--\s*invoke-(skill|agent|workflow):' "$file" 2>/dev/null)

    unset 'IN_STACK[$file]'
    VISITED[$file]="true"
    RESOLVED+=("$file")
}

# Usage: resolve ".agent/agents/task-implementer.md" "agent"
# Result: RESOLVED array contains files in dependency order
```

### Handling Edge Cases

| Scenario | Behavior |
|----------|----------|
| **Circular dependency** | Fail with error, report full cycle chain |
| **Missing dependency** | Warn and continue, or fail (configurable) |
| **Duplicate dependency** | Include only once (deduplication) |
| **Version conflict** | Use latest version, emit warning |
| **Self-reference** | Ignore (not a cycle) |

### Dependency Graph Example

```
task-implementer (agent)
├── code-principles (skill)
├── testing-standards (skill)
│   └── code-principles (skill)  ← Already included, deduplicated
├── architecture-guidelines (skill)
├── task-focus (skill)
├── scope-validator (subagent)
│   ├── task-focus (skill)        ← Already included, deduplicated
│   └── roadmap-navigation (skill)
└── code-reviewer (agent)         ← Delegation, not inlined
```

**Resolution Order:**
1. `code-principles`
2. `testing-standards`
3. `architecture-guidelines`
4. `task-focus`
5. `roadmap-navigation`
6. `scope-validator`
7. `task-implementer`

---

## Appendix E: Versioning Policy

### Version Format

All agents, skills, subagents, and workflows use **semantic versioning**:

```
MAJOR.MINOR.PATCH
```

| Component | Increment When |
|-----------|----------------|
| **MAJOR** | Breaking changes to inputs, outputs, or behavior |
| **MINOR** | New capabilities added, backward compatible |
| **PATCH** | Bug fixes, documentation updates |

### Version Field Examples

```yaml
---
name: code-principles
version: 0.74.0
---
```

### Compatibility Rules

1. **Skills**: Must support N-1 backward compatibility
   - Version 2.x must work for agents expecting 1.x
   - Breaking changes require MAJOR version bump

2. **Agents**: Should declare minimum skill versions
   ```yaml
   skills:
     - name: code-principles
       min_version: "1.0"
   ```

3. **Adapters**: Pin to specific versions or use latest
   ```yaml
   adapter_settings:
     version_strategy: latest  # or "pinned"
   ```

### Deprecation Process

1. **Announce**: Mark with `deprecated: true` in frontmatter
2. **Grace Period**: Maintain for at least 2 releases
3. **Document**: Add migration guide to skill/agent file
4. **Remove**: Delete in subsequent MAJOR version

```yaml
---
name: old-skill
version: 0.74.0
deprecated: true
deprecation_notice: "Use new-skill instead. Migration guide below."
removal_version: "2.0.0"
---
```

---

## Appendix F: Security Considerations

### Command Execution Sandboxing

Agents may execute shell commands. Apply these restrictions:

| Control | Implementation |
|---------|---------------|
| **Allowlist commands** | Define permitted commands per agent |
| **Working directory** | Restrict to repository root |
| **Network access** | Block external requests unless explicitly allowed |
| **File system** | Limit writes to specific directories |

**Example Permission Configuration:**

```yaml
# In agent frontmatter
permissions:
  commands:
    allow:
      - "./scripts/lint.sh"
      - "./scripts/test_unit.sh"
      - "git status"
      - "git diff"
    deny:
      - "rm -rf"
      - "curl"
      - "wget"

  file_access:
    read: ["**/*"]
    write: ["src/**", "tests/**", "docs/**"]
    deny_write: [".git/**", "*.env", "secrets/**"]
```

### Secrets Handling

**Never include in agent files:**
- API keys
- Passwords
- Private keys
- Environment-specific secrets

**Recommended approach:**

```yaml
# Agent references environment variable, never the value
inputs:
  - name: api_key
    type: secret
    source: env
    env_var: AGENT_API_KEY  # Agent reads from environment
```

### Input Validation

Agents should validate all inputs:

```yaml
inputs:
  - name: task_id
    type: string
    validation:
      pattern: "^T[0-9]+\\.[0-9]+$"  # e.g., T4.3
      max_length: 10
  - name: file_path
    type: file
    validation:
      must_exist: true
      within: ["src/", "tests/", "docs/"]
```

### Audit Trail

For sensitive operations, agents should log:
- Timestamp
- Agent name and version
- Action performed
- Files modified
- User/invoker identity

---

## Appendix G: Configuration File Specification

### `.agent/config.yaml`

```yaml
# Agentic Flow Configuration
# This file controls global behavior for all agents and adapters.

# Version of the agentic flow schema
schema_version: "1.0"

# Default settings applied to all agents
defaults:
  mode: adaptive              # adaptive | ask
  max_iterations: 10          # Max workflow loops before forcing stop
  timeout_seconds: 3600       # 1 hour max per agent invocation

# Skill loading behavior
skills:
  directory: ".agent/skills"
  auto_load: true             # Load skills referenced in agents
  version_strategy: latest    # latest | pinned

# Agent settings
agents:
  directory: ".agent/agents"
  delegation_depth: 3         # Max subagent nesting
  parallel_subagents: false   # Run subagents in parallel

# Workflow settings
workflows:
  directory: ".agent/workflows"
  stage_validation: strict    # strict | permissive
  allow_stage_skip: false     # Allow skipping workflow stages

# Adapter generation settings
adapters:
  output_directory: "."       # Where to write generated files
  platforms:                  # Enable/disable specific platforms
    claude_code: true
    gemini_cli: true
    github_copilot: true
    codex_cli: false
    opencode: false

# Security settings
security:
  command_allowlist: true     # Enforce command allowlists
  sandbox_mode: false         # Run commands in restricted sandbox
  secrets_env_prefix: "AGENT_"  # Environment variable prefix for secrets

# Context files to always include
context:
  always_read:
    - "README.md"
    - "docs/technical/roadmap.md"
    - "docs/technical/decisions.md"

# Project-specific overrides
project:
  name: "QuickScale"
  language: "python"
  test_command: "./scripts/test_unit.sh"
  lint_command: "./scripts/lint.sh"
```

### Configuration Precedence

1. **Agent frontmatter** (highest priority)
2. **`.agent/config.yaml`** (project defaults)
3. **Built-in defaults** (lowest priority)

---

## Appendix H: Error Recovery Patterns

### Workflow State Persistence

Workflows can checkpoint state to enable recovery:

```yaml
# Workflow frontmatter
---
name: implement-task
checkpoint:
  enabled: true
  storage: ".agent/state/"
  format: yaml
---
```

**Checkpoint File Example:**

```yaml
# .agent/state/implement-task-T4.3.yaml
workflow: implement-task
task_id: T4.3
started_at: "2026-02-05T10:30:00Z"
current_stage: 3  # REVIEW
completed_stages:
  - stage: 1
    name: PLAN
    completed_at: "2026-02-05T10:32:00Z"
  - stage: 2
    name: CODE
    completed_at: "2026-02-05T11:15:00Z"
modified_files:
  - src/quickscale/cli.py
  - tests/test_cli.py
rollback_available: true
```

### Recovery Commands

```bash
# List interrupted workflows
.agent/scripts/recovery.sh list

# Resume from last checkpoint
.agent/scripts/recovery.sh resume implement-task-T4.3

# Rollback to before workflow started
.agent/scripts/recovery.sh rollback implement-task-T4.3

# Clear all checkpoints (start fresh)
.agent/scripts/recovery.sh clear
```

### Error Classification

| Error Type | Recovery Action |
|------------|----------------|
| **Transient** (network timeout) | Retry with backoff |
| **Validation** (lint failure) | Fix and retry stage |
| **Scope violation** | Stop, report, require human decision |
| **Fatal** (missing file) | Rollback, report error |
| **User interrupt** (Ctrl+C) | Save checkpoint, allow resume |

### Manual Intervention Triggers

Certain conditions should pause and request human input:

```yaml
# Agent frontmatter
pause_conditions:
  - scope_violation_detected
  - test_failure_after_3_retries
  - security_warning_raised
  - ambiguous_requirement
```

**Agent behavior on pause:**
1. Save current state to checkpoint
2. Output clear summary of situation
3. List options: resume, skip, rollback, abort
4. Wait for human response

---

## Appendix I: Workflow Stage Flexibility

### Stage Override Configuration

Not all tasks require all 5 stages. Configure overrides:

```yaml
# Workflow frontmatter
---
name: implement-task
stages: 5
stage_definitions:
  - name: PLAN
    required: true
    skip_conditions: []
  - name: CODE
    required: true
    skip_conditions: ["task_type == 'documentation'"]
  - name: REVIEW
    required: true
    skip_conditions: []
  - name: TEST
    required: true
    skip_conditions: ["task_type == 'documentation'"]
  - name: COMPLETE
    required: true
    skip_conditions: []
---
```

### Task Type Variants

| Task Type | Stages Used | Notes |
|-----------|-------------|-------|
| **Feature** | All 5 | Full workflow |
| **Bug Fix** | CODE → REVIEW → TEST → COMPLETE | Skip PLAN for simple fixes |
| **Documentation** | PLAN → CODE → COMPLETE | Skip REVIEW, TEST |
| **Refactoring** | PLAN → CODE → REVIEW → COMPLETE | Skip TEST if no behavior change |
| **Hotfix** | CODE → TEST → COMPLETE | Minimal flow for urgent fixes |

### Declaring Task Type

```yaml
# In agent invocation or workflow input
inputs:
  - name: task_type
    type: enum
    values: [feature, bug_fix, documentation, refactoring, hotfix]
    default: feature
```

### Runtime Stage Skip

Agents can skip stages with documented justification:

```markdown
## Stage Skip Report

**Stage Skipped:** TEST
**Reason:** Documentation-only change. No testable code modified.
**Justification:** Task T4.5 updates README.md and docs/api.md only.
**Files Changed:**
- README.md (documentation)
- docs/api.md (documentation)

**Approval:** Auto-approved (documentation-only detected)
```

---

## Appendix J: Frequently Asked Questions

### General

**Q: Can I use this system without any AI platform?**

A: The `.agent/` files are human-readable markdown. You can follow the workflows manually, treating them as checklists. However, the system is designed for AI agent execution.

**Q: Which platform should I start with?**

A: Claude Code has the most complete native support for agents, skills, and subagent delegation. Start there if available.

**Q: Can I add custom agents for my project?**

A: Yes. Create a new file in `.agent/agents/your-agent.md` following the [Agent Frontmatter Schema](#agent-frontmatter-schema). Then run the adapter script to regenerate platform configs.

### Skills

**Q: How do I create a new skill?**

A: Create a directory in `.agent/skills/your-skill/` with a `SKILL.md` file. Follow the [Skill Frontmatter Schema](#skill-frontmatter-schema). Add example files if helpful.

**Q: Can skills depend on other skills?**

A: Yes. Use the `requires` field in skill frontmatter:
```yaml
requires:
  - code-principles
```

**Q: What if a skill is too large?**

A: Split into multiple skills with focused responsibilities. Use `requires` to compose them.

### Workflows

**Q: Can I run workflows out of order?**

A: By default, stages must complete in order. Set `allow_stage_skip: true` in config.yaml to permit skipping. Always document justification.

**Q: How do I add a custom workflow?**

A: Create `.agent/workflows/your-workflow.md` following the [Workflow Frontmatter Schema](#workflow-frontmatter-schema). Reference it from an agent.

### Platforms

**Q: Why does Copilot get less functionality?**

A: GitHub Copilot has limited agent support (no subagent delegation, no command execution in chat). The adapter extracts key principles into a single instructions file.

**Q: How do I update generated files after changing .agent/?**

A: Run `.agent/adapters/generate-all.sh` after any changes to regenerate all platform configurations.

**Q: Can I manually edit generated files (CLAUDE.md, GEMINI.md)?**

A: You can, but changes will be overwritten on next generation. Make changes in `.agent/` source files instead.

### Troubleshooting

**Q: Agent says "skill not found"**

A: Check that the skill exists: `ls .agent/skills/`. Verify the skill name matches exactly (case-sensitive).

**Q: Adapter script fails with "command not found"**

A: Ensure bash 4.0+ is installed: `bash --version`. Make scripts executable: `chmod +x .agent/adapters/*.sh`.

**Q: Generated file is empty or incomplete**

A: Check adapter script output for errors. Verify source files exist and have valid frontmatter.

**Q: Circular dependency error**

A: Review the reported dependency chain. Refactor to break the cycle (extract shared logic to a separate skill).

---

*Document maintained by: AI Development Team*
*Last updated: 2026-02-05*
