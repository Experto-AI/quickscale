# Orchestrating the 3-track roadmap workflow — research & alternatives

## Context

The 3-track parallel-worktree plan in `roadmap.md` (`quickscale-wt-track{1,2,3}` → merge into `v87`) is currently run by hand: copy/pasting a fixed prompt into 3 opencode sessions, watching for blockers, answering them, and pasting a "stop and update roadmap" prompt when something can't be unblocked offline. The goal is to keep **OpenCode** as the worker CLI (Claude Code usage isn't cost-effective at this volume unless a Codex account or OpenCode's own multi-provider/subagents get wired in), while reducing human involvement to answering genuine blockers only — via either a terminal or visual-dashboard experience.

This is a brainstorm/options memo, not an implementation plan — nothing has been built yet. No equivalent automation exists in this repo today (confirmed via a scan of `scripts/`, `.github/workflows/`, and the root `Makefile`).

## What already exists that fits this pattern

**Tier 1 — purpose-built for exactly this shape of work (OpenCode + worktrees + "only interrupt me when blocked"):**

- **[opencode-mission-control](https://github.com/nigel-dev/opencode-mission-control)** (npm plugin, `nigel-dev`). Orchestrates parallel OpenCode agents in tmux-isolated git worktrees. Takes a **DAG-based plan** (jobs + dependencies) — this maps almost directly onto the dependency table already in `roadmap.md`'s "Dependency & parallelization overview" section (SA13.1 → SA13.2/13.3 → SA13.4, etc.). Three run modes:
  - **autopilot** — launches, merges, tests, and opens a PR automatically, no human touch.
  - **supervisor** — same, but **pauses for your review** on merge-train test failures or flagged jobs — this is the "only be human in the loop when something's genuinely blocked" behavior described above.
  - **copilot** — a middle mode.
  It also has a **merge train**: runs your test suite after each merge, auto-rolls-back on failure — this could directly replace the manual "`git merge v87` → verify → `git merge --no-ff wt-track{N}`" procedure. Has a dashboard overview + agent status + in-chat notifications.
  - Caveat: independent community plugin (not OpenCode-official), v1.6.0 on npm — worth a small trial before trusting it with a real merge train.

- **[opencode-ensemble](https://github.com/hueyexe/opencode-ensemble)** — "agent teams for OpenCode": peer-to-peer messaging between agents, a task board with dependency arrows, activity feed. Closer to Claude Code's own "Agent Teams" concept (see below) but implemented for OpenCode. Less merge-automation than mission-control; stronger on visualizing what each track is doing.

**Tier 2 — general multi-CLI-agent terminal managers (OpenCode is one of several supported backends; you'd still need to add your own "escalate only on block" logic on top):**

- **[claude-squad](https://github.com/smtg-ai/claude-squad)** (`cs`) — mature, open-source, tmux + git-worktrees. Explicitly lists OpenCode as a supported agent via configurable launch commands (also Claude Code, Codex, Aider, Gemini). Gives a terminal dashboard of all sessions/panes at once — closest fit to a "visual dashboard" preference without being OpenCode-specific tooling.
- Newer/less-proven entrants surfaced in search but not verified in depth: `dux`, `jean`, `clideck` — terminal/desktop/web UIs that also drive OpenCode+worktrees. Worth a bookmark, not a first pick.

**Tier 3 — DIY scripted loop (most control, most build effort):**

OpenCode's CLI supports a non-interactive `opencode run` and an `--auto` flag that auto-approves permission prompts not explicitly denied (interactive TUI still needed for anything explicitly set to "ask"). A DIY option:
1. A small driver (shell script, or a dedicated orchestrator loop) runs `opencode run --auto "<the standard track prompt>"` per worktree.
2. The track prompt is amended to require the agent to print a fixed sentinel (e.g. `BLOCKED: <question>`) when — and only when — it truly can't proceed without a human, mirroring the existing "stop here and update roadmap.md" fallback prompt.
3. The driver greps output for that sentinel; on a hit, it pushes a notification (Slack webhook, desktop notify-send, etc.) with the question, and pauses that track only. No sentinel → it proceeds straight to the next pending task in that track, unattended.
This is effectively a lightweight version of what mission-control's "supervisor mode" already does — worth trying only if Tier 1 tools don't fit the merge-train/test-gating specifics.

**Tier 4 — Claude Code's own primitives (for completeness, deprioritized per the budget constraint):**
- Claude Code's experimental **Agent Teams** (`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`) — a lead session spawns teammates (one per track), shared task list with dependency-aware unblocking, teammate permission prompts bubble up to the lead so blockers are approved/rejected in one place. Very close match to the manual workflow today, but runs Claude Code models for every track's actual coding work — the cost problem this needs to avoid.
- Claude Code's `Agent` tool (worktree isolation + background execution + resume-by-message) — same cost caveat; only worth revisiting if a Codex/other provider gets connected to reduce spend.

## Recommendation

Trial **opencode-mission-control** first: the roadmap's dependency graph is already hand-authored in a form that maps onto its DAG plan format, "supervisor mode" is a near-exact match for the human-in-the-loop rule, and its merge train can absorb the `git merge v87` → test → `git merge --no-ff` procedure `roadmap.md`'s "Merge procedure" section documents today. If its merge-train/test-gating doesn't fit cleanly, fall back to **claude-squad** for the visual multi-pane view (lower automation, but rock-solid isolation + OpenCode support) plus a thin custom script for the "notify only on block" behavior. Keep the Tier 3 DIY loop as a fallback if neither plugin's assumptions match the actual test/merge setup.

## Suggested next step (not started)

A small spike: install `opencode-mission-control` in one worktree, feed it a DAG built from the Track 2 dependency slice (SA15.3 already done → SA17.1–SA17.8, mostly independent), and see whether its supervisor-mode pause/resume and merge-train match the actual CI/test commands before committing to it for all 3 tracks.
