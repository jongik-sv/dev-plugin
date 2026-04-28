# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

A Claude Code plugin (`dev`) that automates WBS-based and Feature-based TDD development cycles. It provides 12 skills installable via the Claude Code plugin system (`/plugin install dev@dev-tools`). The plugin namespace is `dev:`.

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
| `scripts/wbs-parse.py` | WBS task/WP extraction + Feature state.json read (`--feat`) + complexity scoring (`--complexity`) + `--tasks-all` (flat list of every Task across all WPs, for graph-stats input) → JSON. Prefers `state.json` over wbs.md status line when present. | dev, feat, dev-design/build/test/refactor, dev-team, wbs, wp-setup.py |
| `scripts/args-parse.py` | Argument parsing + source detection (wbs/feat) → JSON | dev, feat, dev-design/build/test/refactor, dev-team |
| `scripts/dep-analysis.py` | Dependency level calculation (topological sort) + `--graph-stats` mode for graph health metrics (max chain depth, fan-in, diamond patterns, review candidates) → JSON | dev-team, agent-pool, team-mode, wbs |
| `scripts/signal-helper.py` | Atomic signal file create/check/wait | dev-team, team-mode, agent-pool, DDTR workers |
| `scripts/wp-setup.py` | Worktree + prompt + tmux setup | dev-team |
| `scripts/wbs-transition.py` | Permissive DFA transition engine. Writes sidecar `state.json` (source of truth), syncs wbs.md status line. Undefined events are no-ops that still log to `phase_history`. Handles legacy `[dd!]`/`[im!]` migration, feat `status.json`→`state.json` rename, and `bypass` meta-event (sets `bypassed: true` without changing status). | dev-design, dev-build, dev-test, dev-refactor, dev-team (bypass) |
| `scripts/feat-init.py` | Feature directory initializer (`docs/features/{name}/spec.md + state.json`). Auto-renames legacy `status.json` → `state.json` on resume. | feat |
| `scripts/run-test.py` | Test command wrapper with timeout + process-group cleanup | dev-test, dev-build, dev-refactor |
| `scripts/e2e-server.py` | E2E server lifecycle management (check/start/stop). URL health check + background server + PID file. 서버 기동과 테스트 실행을 분리하여 타임아웃 체인 충돌 해소 | dev-test |
| `scripts/cleanup-orphaned.py` | Orphaned test process cleanup (legacy fallback) | manual use |
| `scripts/graceful-shutdown.py` | WP 창 정상 종료 (Mac/Linux tmux 전용). absolute `window_id`(`@N`)로 타겟 해석(`=name` exact-match + 결과 검증 → `list-windows` 스캔 폴백) + self-protection(기본 ON: 자기 window 타겟 시 abort). `--no-marker`로 머지 정리 경로(`.shutdown` 마커 생략) 겸용. **Windows(psmux)에서는 no-op** — psmux window 해석 신뢰성 문제로 엉뚱한 창을 kill하는 사고가 반복되어 창 종료를 사용자에게 위임한다(merge는 `.done` 시그널 기반이라 영향 없음) | dev-team, merge-procedure |
| `scripts/leader-autopsy.py` | WP 리더 비정상 사망 시 포렌식 덤프 (pane scrollback + signals + git + env → `docs/dev-team/autopsy/{WT_NAME}-{UTC_TS}/`). zero-LLM 스크립트 — 팀리더는 `summary.txt`만 Read. 가성비 기본값으로 transcript 생략, `--include-transcript`/`--transcript-tail N` 토글 | dev-team (Leader Death 복구 step 0) |
| `scripts/leader-watchdog.py` | WP별 백그라운드 데몬으로 WP 리더 pane을 주기적 감시(기본 30초). 사망 확정 시 `leader-autopsy.py` 호출 → 팀원 settle 대기 → `{WT_NAME}.needs-restart` 시그널 생성. **폴링당 토큰 0** — 팀리더 LLM은 시그널 본문(<1 KB)만 한 번 Read. 팀리더는 `.needs-restart` 감지 시 `wp-setup.py`로 WP resume하여 자동 재시작 | dev-team (WP spawn 직후 기동, 재시작마다 재기동) |
| `scripts/monitor-launcher.py` | dev-monitor 서버 기동/정지/상태 관리 헬퍼. PID 파일로 idempotent 기동, `--stop`/`--status` 서브커맨드, macOS·Linux·Windows 플랫폼별 프로세스 detach | dev-monitor |
| `scripts/monitor-server.py` | HTTP 대시보드 서버 라우팅·스캔 함수. `--port`/`--docs` 인자, on-demand 상태 조회 API 구현 (monitor-launcher.py가 subprocess로 호출) | dev-monitor |
| `scripts/decision-log.py` | 자율 결정 감사 로그 헬퍼 — `decisions.md`(task/feature/project 단위)에 (Phase / Decision needed / Decision made / Rationale) 4-필드를 append-only 기록. `append`/`list`/`validate` 서브커맨드. 자세한 호출 규약: `references/decisions-template.md` | dev-design, dev-build, dev-test, dev-refactor, wbs, feat, dev-team merge |
| `scripts/verify-phase.py` | DDTR phase 종료 verification 게이트 — design/build/test/refactor 각 phase의 산출물 구조 검사 + 동적 체크(`--check NAME:ok|fail:KEY=VAL,...`)를 합성하여 footer JSON 출력. 자세한 호출 흐름: `references/verification-protocol.md` | dev-design, dev-build, dev-test, dev-refactor, dev-team merge |
| `scripts/debug-evidence.py` | systematic-debugging 4단계 evidence 수집기 — dev-test 실패 시 escalation/bypass 진입 전 (에러 raw / 재현 가능성 / 최근 변경 / 컴포넌트 경계)를 수집. `collect`/`bypass-reason` 서브커맨드. wbs-transition.py `--debug-evidence` 플래그로 phase_history.debug_evidence 필드에 합성 | dev-test failure path |
| `scripts/prd-validate.py` | PRD/TRD 정합성 검사 — placeholder(TBD/TODO/???/<...>) / vague metric(fast/scalable 등 정량 hint 부재) / missing section(acceptance/NFR/constraints) 검출. `validate`/`assumptions-template` 서브커맨드 | wbs |
| `scripts/wbs-validate.py` | WBS Task 품질 검사 — Task별 acceptance 누락 / depends 미지정 / domain 미매핑 / 모호 동사(구현·배포·검증) 검출 | wbs |
| `scripts/_platform.py` | Cross-platform utilities (temp dir, JSON escape) | available for scripts |

All scripts use `${CLAUDE_PLUGIN_ROOT}/scripts/` as base path. Python 3 standard library only — no pip dependencies.

**CLI 작성 원칙 — 모든 새 CLI 기능은 Python으로 작성한다.** Bash/zsh/PowerShell 등 쉘 스크립트로 신규 CLI 도구를 만들지 않는다. 이유:
- 세 지원 플랫폼(macOS/Linux/WSL/네이티브 Windows+psmux)의 기본 쉘이 서로 달라 (bash/zsh/PowerShell) POSIX bash 구문은 PowerShell pane에서 동작하지 않음
- Python은 `pathlib` + `tempfile` + `subprocess`로 플랫폼 차이를 내부에서 흡수
- 이미 기존 스크립트 14개가 모두 Python stdlib로 작성되어 동일 런타임 의존성 유지
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
- `dev-team`: Distributes WP's Tasks across team-mode workers. Each worker runs the full DDTR cycle. Uses git worktrees per WP, merges back to main. **WBS only** — Feature mode is not supported for team parallelization. `--sequential` flag enables sequential-WP mode: WPs run one at a time (no worktrees, direct commit to current branch), but each WP's internal tasks still run in parallel across tmux panes.

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

### Shared Reference Files

| File | Purpose |
|------|---------|
| `references/test-commands.md` | Dev Config loading protocol (feat-local → wbs → default) — domain test command 출처 |
| `references/signal-protocol.md` | Signal file protocol (`.running`/`.done`/`.failed`) |
| `references/state-machine.json` | DFA definition shared by WBS and Feature modes |
| `references/default-dev-config.md` | Global default Dev Config (final fallback for feat mode) |
| `references/status-notation.md` | 외부 도구 연동용 상태 코드 매핑표 (`[xx]`→✅ 등). 플러그인 내부는 raw 코드 유지 |
| `references/decisions-template.md` | 자율 결정 감사 로그(`decisions.md`) 스키마 + 호출 규약 + 비자명 결정 판별 휴리스틱 |

자율 결정 로그 정책의 본문(언제 기록할지, intake 예외 등)은 사용자 런타임 동작이므로 각 phase SKILL.md(`dev-design`, `dev-build`, …)와 `references/decisions-template.md`에서 관리한다. CLAUDE.md는 "비자명 자율 결정은 `decisions.md`에 append-only — 상세는 `references/decisions-template.md`"라는 계약만 기억하면 된다.

## Cross-Platform 코딩 규칙

플러그인 사용자(macOS / Linux / WSL / 네이티브 Windows+psmux) 안내는 README.md 소관. 여기서는 **plugin 코드를 작성·수정할 때 지켜야 하는 규칙**만 둔다.

- **Mux 추상화**: `detect_mux()`가 `tmux -V` 프로브로 tmux/psmux를 식별 → 호출부는 분기 없이 동일 명령을 사용한다.
- **Python 런처**: pane에 투입되는 런처(예: `{WT_NAME}-run.py`)는 bash가 아니라 Python으로 생성한다. cmd.exe / PowerShell / bash 어느 기본 쉘에서도 동일하게 동작해야 하기 때문.
- **`python3` 하드코딩 금지**: 내부 subprocess에는 `sys.executable`을, mux로 전달하는 명령에는 `"{sys.executable}" "{abs_path}"` 형태를 쓴다. (Windows에서 MS Store App Execution Alias가 `python3.exe`를 가로채 rc=9009를 반환)
- **파일 쓰기 newline**: 모든 파일 출력은 `open(..., "w", encoding="utf-8", newline="\n")`. 기본 text 모드가 Windows에서 `\n`→`\r\n`으로 변환해 bash 런처가 CRLF로 깨지는 회귀 방지.
- **경로 해석**: `__file__` + `pathlib`로 경로를 산출해 `C:\`, `/c/`, `/mnt/c/` 규칙 차이를 흡수한다.
- **Shared signal directory**: `tempfile.gettempdir()` (via `scripts/_platform.py:TEMP_DIR`)만 사용한다. NFS v3 / SMB / sshfs는 `create → rename → check` 원자성이 보장되지 않으므로 네트워크 마운트로 override 금지.
- **POSIX 잔재**: `team-mode`, `agent-pool` 스킬의 bash 예제(`cd {dir} && claude ...`)는 아직 POSIX 의존 — Windows pane 호환을 위해 점진적으로 Python 런처로 이관해야 한다(개선 백로그).
