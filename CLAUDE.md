# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

A Claude Code plugin (`dev`) that automates WBS-based TDD development cycles. It provides 10 skills installable via the Claude Code plugin system (`/plugin install dev@dev-tools`). The plugin namespace is `dev:`.

## Architecture

```
.claude-plugin/          # Plugin metadata (plugin.json, marketplace.json)
skills/                  # Each subdirectory = one skill (SKILL.md is the entry point)
README.md                # User-facing documentation
```

### Skill Layers

**Layer 1 — Generic parallel engines** (no WBS dependency):
- `agent-pool`: N subagents in one session, slot-pool pattern with signal files (`/tmp/agent-pool-signals/`). No tmux needed.
- `team-mode`: N independent claude processes in tmux panes, signal-file based task dispatch and pane recycling. Requires tmux.

**Layer 2 — WBS development lifecycle** (operates on `docs/wbs.md` Tasks):
- `wbs`: PRD/TRD → WBS generation (3-level or 4-level based on project scale)
- `dev`: Orchestrator — runs design→build→test→refactor as sequential subagents for a single Task
- `dev-design`, `dev-build`, `dev-test`, `dev-refactor`: Individual phase skills

**Layer 3 — Team parallel development** (combines Layer 1 + Layer 2):
- `dev-team`: Distributes WP's Tasks across team-mode workers. Each worker runs the full DDTR cycle. Uses git worktrees per WP, merges back to main.

### Key Patterns

- **Signal files**: All inter-agent communication uses file-based signals (`.done` files). Absolute paths are mandatory in worktree contexts.
- **DDTR cycle**: Design `[dd]` → TDD Build `[im]` → Test → Refactor `[xx]` — status tracked in `docs/wbs.md`.
- **Pane recycling** (team-mode): After a worker completes a task, send `/clear` then assign the next task via `tmux send-keys` with prompt files (never inline — tmux truncates long strings).
- **Slot-pool** (agent-pool): Maintain exactly N concurrent agents; when one completes, immediately launch the next eligible task.
- **Templates**: `skills/dev-design/template.md`, `skills/dev-test/template.md`, `skills/dev-refactor/template.md` define output formats for each phase.

## Skill File Convention

Each skill is a directory under `skills/` containing a `SKILL.md` with YAML frontmatter:

```yaml
---
name: skill-name
description: "Trigger description — also used for natural language matching"
---
```

The `description` field doubles as NL trigger keywords (e.g., "팀모드", "team mode", "에이전트 풀"). Arguments are passed via `$ARGUMENTS`.

## Domain-Specific Test Commands

Skills reference these based on the Task's `domain` field:
- `backend`: `bundle exec rspec`
- `frontend`: `npm run test`
- `sidecar`: `uv run pytest`
- `fullstack`: all of the above

## Target Project Requirements

The plugin expects the consuming project to have:
- `docs/PRD.md`, `docs/TRD.md`, `docs/wbs.md`
- WBS Tasks formatted as `### TSK-XX-XX:` with metadata (category, domain, status, depends, etc.)
- Task artifacts go to `docs/tasks/{TSK-ID}/` (design.md, test-report.md, refactor.md)

## dev-team Execution Modes

- **tmux present**: Creates git worktree per WP, spawns WP leader as tmux window, leader manages worker panes via team-mode protocol. Supports early merge (merge completed WPs while others are still running).
- **tmux absent**: Falls back to Agent tool with `isolation: "worktree"` and `run_in_background: true`, using agent-pool slot management.
