# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

A Claude Code plugin (`dev`) that automates WBS-based and Feature-based TDD development cycles. It provides 11 skills installable via the Claude Code plugin system (`/plugin install dev@dev-tools`). The plugin namespace is `dev:`.

## Architecture

```
.claude-plugin/          # Plugin metadata (plugin.json, marketplace.json)
skills/                  # Each subdirectory = one skill (SKILL.md is the entry point)
scripts/                 # Token-saving helper scripts (bash)
README.md                # User-facing documentation
```

### Helper Scripts (Token Optimization)

Skills delegate deterministic work to Python scripts (cross-platform: Mac/Linux/Windows) to reduce LLM token consumption:

| Script | Purpose | Used by |
|--------|---------|---------|
| `scripts/wbs-parse.py` | WBS task/WP extraction + Feature state.json read (`--feat`) + complexity scoring (`--complexity`) → JSON. Prefers `state.json` over wbs.md status line when present. | dev, feat, dev-design/build/test/refactor, dev-team, wp-setup.py |
| `scripts/args-parse.py` | Argument parsing + source detection (wbs/feat) → JSON | dev, feat, dev-design/build/test/refactor, dev-team |
| `scripts/dep-analysis.py` | Dependency level calculation (topological sort) → JSON | dev-team, agent-pool, team-mode |
| `scripts/signal-helper.py` | Atomic signal file create/check/wait | dev-team, team-mode, agent-pool, DDTR workers |
| `scripts/wp-setup.py` | Worktree + prompt + tmux setup | dev-team |
| `scripts/wbs-transition.py` | Permissive DFA transition engine. Writes sidecar `state.json` (source of truth), syncs wbs.md status line. Undefined events are no-ops that still log to `phase_history`. Handles legacy `[dd!]`/`[im!]` migration, feat `status.json`→`state.json` rename, and `bypass` meta-event (sets `bypassed: true` without changing status). | dev-design, dev-build, dev-test, dev-refactor, dev-team (bypass) |
| `scripts/feat-init.py` | Feature directory initializer (`docs/features/{name}/spec.md + state.json`). Auto-renames legacy `status.json` → `state.json` on resume. | feat |
| `scripts/run-test.py` | Test command wrapper with timeout + process-group cleanup | dev-test, dev-build, dev-refactor |
| `scripts/e2e-server.py` | E2E server lifecycle management (check/start/stop). URL health check + background server + PID file. 서버 기동과 테스트 실행을 분리하여 타임아웃 체인 충돌 해소 | dev-test |
| `scripts/cleanup-orphaned.py` | Orphaned test process cleanup (legacy fallback) | manual use |
| `scripts/_platform.py` | Cross-platform utilities (temp dir, JSON escape) | available for scripts |

All scripts use `${CLAUDE_PLUGIN_ROOT}/scripts/` as base path. Python 3 standard library only — no pip dependencies.

**CLI 작성 원칙 — 모든 새 CLI 기능은 Python으로 작성한다.** Bash/zsh/PowerShell 등 쉘 스크립트로 신규 CLI 도구를 만들지 않는다. 이유:
- 세 지원 플랫폼(macOS/Linux/WSL/네이티브 Windows+psmux)의 기본 쉘이 서로 달라 (bash/zsh/PowerShell) POSIX bash 구문은 PowerShell pane에서 동작하지 않음
- Python은 `pathlib` + `tempfile` + `subprocess`로 플랫폼 차이를 내부에서 흡수
- 이미 기존 스크립트 11개가 모두 Python stdlib로 작성되어 동일 런타임 의존성 유지
- 쉘 차이를 흡수하는 Python 래퍼 1개가 세 플랫폼에서 동일하게 동작

SKILL.md 예시에 필요한 쉘 명령은 **Python 래퍼 호출로 치환**해야 한다. 기존의 POSIX bash 예시(`rm -rf`, heredoc, `for ... do ... done` 등)는 점진적으로 Python 스크립트로 흡수한다. `scripts/legacy-bash/`는 참고용 동결본이며 새 기능 추가 금지.

### Skill Layers

**Layer 1 — Generic parallel engines** (no WBS dependency):
- `agent-pool`: N subagents in one session, slot-pool pattern with signal files (`/tmp/agent-pool-signals-{timestamp}/`). No tmux needed.
- `team-mode`: N independent claude processes in tmux panes, signal-file based task dispatch and pane recycling. Requires tmux.

**Layer 2 — Task/Feature development lifecycle** (source-agnostic DDTR engine):
- `wbs`: PRD/TRD → WBS generation (3-level or 4-level based on project scale)
- `dev`: **WBS orchestrator** — runs design→build→test→refactor for a `wbs.md` Task (`docs/tasks/{TSK-ID}/`)
- `feat`: **Feature orchestrator** — runs the same DDTR cycle for a WBS-independent feature (`docs/features/{name}/`). Thin wrapper that sets `SOURCE=feat` and reuses `dev-design/build/test/refactor`.
- `dev-design`, `dev-build`, `dev-test`, `dev-refactor`: Individual phase skills. Branch on `SOURCE` (wbs vs feat) — same DFA (`references/state-machine.json`), different requirement source and artifact location.

**Layer 3 — Team parallel development** (combines Layer 1 + Layer 2):
- `dev-team`: Distributes WP's Tasks across team-mode workers. Each worker runs the full DDTR cycle. Uses git worktrees per WP, merges back to main. **WBS only** — Feature mode is not supported for team parallelization.

### Key Patterns

- **Signal files**: All inter-agent communication uses file-based signals (`.done` files). Absolute paths are mandatory in worktree contexts.
- **Signal directory naming** (intentionally scoped differently per skill — do not unify):
  - `agent-pool`: `{TEMP}/agent-pool-signals-{timestamp}-$$` — session-scoped so concurrent pools don't collide
  - `team-mode`: `{TEMP}/claude-signals/{window_name}` — window-scoped, reused when the window is reused
  - `dev-team`: `{TEMP}/claude-signals/{PROJECT_NAME}{WINDOW_SUFFIX}` — project-scoped so cross-WP `wait {dep-TSK-ID}` works
- **DDTR cycle**: Design `[dd]` → TDD Build `[im]` → Test `[ts]` → Refactor `[xx]` — success transitions only. Failures do not advance status; they are recorded in `state.json.phase_history` and the `last` field, while `status` stays at the most recent successful position. `/dev` or `/feat` re-runs resume from `state.json.status.phase_start` — identical for success-pending and failure-retry cases. State machine defined in `references/state-machine.json` and shared across both sources.
- **State storage (sidecar `state.json`)**: Source of truth for status is the sidecar `state.json` — `docs/tasks/{TSK-ID}/state.json` (WBS) or `docs/features/{name}/state.json` (Feature). Schema: `{status, started_at?, last: {event, at}, phase_history: [{event, from, to, at, elapsed_seconds?}, ...], updated, completed_at?, elapsed_seconds?, bypassed?, bypassed_reason?}`. wbs.md's `- status: [xxx]` line is a human-readable view synced by `wbs-transition.py`; `wbs-parse.py --phase-start` reads state.json when present and emits a `drift_warning` if the wbs.md line disagrees.
- **Bypass mechanism**: When a task fails tests after escalation retries (Sonnet→Opus), the WP leader marks it as bypassed (`wbs-transition.py bypass`). `state.json` gets `bypassed: true` while status stays at the actual failure point (e.g., `[im]`). `dep-analysis.py` treats bypassed tasks as dependency-satisfied, unblocking dependent tasks. Signal: `.bypassed` file, detected by `signal-helper.py wait` alongside `.done`/`.failed`.
- **Source abstraction**: `dev-design/build/test/refactor` accept a `SOURCE` variable in the caller's prompt (`SOURCE=wbs` default, `SOURCE=feat` for feature mode). WBS mode branches on `{DOCS_DIR}/wbs.md` + `{DOCS_DIR}/tasks/{TSK-ID}/`; Feature mode on `{FEAT_DIR}/spec.md` + `{FEAT_DIR}/state.json`. DFA and templates are identical.
- **Pane recycling** (team-mode): After a worker completes a task, send `/clear` then assign the next task via `tmux send-keys` with prompt files (never inline — tmux truncates long strings).
- **Slot-pool** (agent-pool): Maintain exactly N concurrent agents; when one completes, immediately launch the next eligible task.
- **Templates**: `skills/dev-design/template.md`, `skills/dev-test/template.md`, `skills/dev-refactor/template.md` define output formats for each phase.
- **Design model selection**: Priority chain: `--model` CLI > wbs.md `- model:` field > auto scoring. WBS `model` field (`opus`/`sonnet`) is set at WBS creation time by the LLM using full PRD/TRD context. Auto scoring (fallback for WBS without `model` field): `wbs-parse.py --complexity` computes score from depends/domain/keywords (metadata lines excluded); score ≥ 3 → Opus, otherwise Sonnet. Build/Refactor always Sonnet, Test always Haiku (with Sonnet escalation).
- **Escalation retry on failure**: In `dev-team` mode, when a task fails (test/build), the WP leader retries with model escalation: 1st retry same model, 2nd retry Opus, 3rd failure triggers bypass. Configurable via `MAX_ESCALATION` (default 2). See `state-machine.json._bypass_semantics`.

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

Test commands, design guidance, and cleanup process names are **project-configured**. WBS mode reads `{DOCS_DIR}/wbs.md` `## Dev Config` section. Feature mode uses a fallback chain (feat-local → wbs → default) resolved by `wbs-parse.py --feat ... --dev-config`. See `references/test-commands.md` for the config loading protocol.

### Shared Reference Files

| File | Purpose |
|------|---------|
| `references/test-commands.md` | Domain-specific unit/E2E test commands + Dev Config loading protocol |
| `references/signal-protocol.md` | Signal file protocol (`.running`/`.done`/`.failed`) |
| `references/state-machine.json` | DFA definition shared by WBS and Feature modes |
| `references/default-dev-config.md` | Global default Dev Config (final fallback for feat mode) |
| `references/status-notation.md` | 외부 도구 연동용 상태 코드 매핑표 (`[xx]`→✅ 등). 플러그인 내부는 raw 코드 유지, 외부 통합 시에만 참조 |

## Target Project Requirements

**WBS mode** (`/dev`, `/dev-team`, etc.):
- `docs/PRD.md`, `docs/TRD.md`, `docs/wbs.md`
- WBS Tasks formatted as `### TSK-XX-XX:` with metadata (category, domain, status, depends, etc.)
- Task artifacts go to `docs/tasks/{TSK-ID}/` (design.md, test-report.md, refactor.md)

**Feature mode** (`/feat`):
- `docs/` directory must exist (parent of `docs/features/`)
- Individual features are created on demand via `feat-init.py` under `docs/features/{name}/`
- Each feature has `spec.md` (user requirements), `state.json` (state tracker — same schema as WBS `state.json`), and DDTR artifacts (design.md, test-report.md, refactor.md). Legacy `status.json` is auto-renamed to `state.json` on first resume.
- **Dev Config fallback chain** (resolved by `wbs-parse.py --feat {FEAT_DIR} --dev-config {DOCS_DIR}`):
  1. `{FEAT_DIR}/dev-config.md` — per-feature override (whole file is parsed as a Dev Config section)
  2. `{DOCS_DIR}/wbs.md` `## Dev Config` section — project-shared setup
  3. `references/default-dev-config.md` — global default bundled with the plugin
  The result JSON includes a `source` field (`feat-local`/`wbs`/`default`) so callers can verify which config was applied.

## dev-team Execution Modes

- **tmux required**: `/dev-team` only runs inside a tmux session. Creates a git worktree per WP, spawns the WP leader as a tmux window, and the leader manages worker panes via the team-mode protocol. Supports early merge (merge completed WPs while others are still running).
- **tmux missing**: The skill aborts immediately with a guidance message directing users to run `/dev {TSK-ID}` sequentially for each Task. Parallel development requires installing tmux and starting a session (`tmux new -s dev`). The non-tmux Agent-tool fallback was removed because its merge/recovery procedure was undefined.

### Skill-Local References (dev-team)

`skills/dev-team/references/` 하위는 dev-team 스킬이 런타임에 Read하는 프롬프트 템플릿 및 절차 문서다. 최상위 `references/`와 달리 dev-team 전용이며 다른 스킬에서 참조하지 않는다.

| File | Purpose |
|------|---------|
| `wp-leader-prompt.md` | WP 리더 tmux window 스폰 시 주입되는 프롬프트 템플릿. `{WP-ID}`, `{WT_NAME}`, `{TEAM_SIZE}`, `{SHARED_SIGNAL_DIR}` 등 치환 |
| `wp-leader-cleanup.md` | WP 리더 종료 시 팀리더에 완료 보고 + 워크트리 정리 절차 |
| `ddtr-prompt-template.md` | Worker pane에 투입되는 DDTR 사이클(설계→TDD→테스트→리팩토링) 프롬프트 |
| `ddtr-design-template.md` | DDTR의 Design phase 전용 단축 프롬프트 (설계 한정 워커용) |
| `merge-procedure.md` | 팀리더의 WP 머지 절차 (early merge + full merge) |
| `config-schema.md` | wp-setup.py의 JSON config 스키마 |

## Platform Support

`/dev-team`, `/team-mode`, `/agent-pool` need Python 3 + a `tmux`-compatible process manager (first two skills).

| Environment | Status | Temp dir | Notes |
|-------------|--------|----------|-------|
| macOS / Linux | ✅ Native support | `$TMPDIR` or `/tmp` | tmux from package manager. Shell is bash/zsh. |
| WSL2 (Windows) | ✅ Native support | `/tmp` | tmux inside WSL. Shell is bash. |
| Native Windows | ⚠️ Partial via **psmux** | `%TEMP%` | psmux aliased to `tmux` passes the `command -v tmux` gate. **BUT psmux's default pane shell is PowerShell**, not bash. Current skill examples are POSIX bash (`rm -rf`, heredoc, `for ... do ... done`) and do NOT run in PowerShell panes as written. Treat native Windows as a known target whose full support requires rewriting shell examples or routing everything through Python wrappers. Python scripts themselves (`pathlib` + `tempfile`) are already platform-neutral. |

**Shared signal directory** resolves from `tempfile.gettempdir()` via `scripts/_platform.py:TEMP_DIR`. All three platforms produce a per-user local path, so cross-WP signal sharing works automatically — there is no need for NFS/SMB. **Do not override this with a network-mounted path**: signal file atomicity (create → rename → check) is not guaranteed on NFS v3, SMB, or sshfs. Keep `SHARED_SIGNAL_DIR` on local disk.

**Do not assume "Windows = unsupported".** psmux keeps the plugin's `tmux` detection valid on native Windows. The remaining gap is shell example compatibility (PowerShell vs bash), which is a separate workstream from signal routing.
