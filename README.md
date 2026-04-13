# dev-plugin

> WBS 기반 TDD 개발 자동화 플러그인 — 설계→TDD구현→테스트→리팩토링 사이클과 팀 병렬 개발을 지원하는 Claude Code 플러그인

## 목차

- [Features](#features)
- [사전 요구사항](#사전-요구사항)
- [설치](#설치)
- [포함된 스킬](#포함된-스킬)
- [사용법](#사용법)
- [프로젝트 요구사항](#프로젝트-요구사항)
- [Architecture](#architecture)
- [관리](#관리)
- [문제 해결](#문제-해결)

---

## Features

- **WBS-driven development** — PRD/TRD에서 WBS를 생성하고, Task 단위로 전체 개발 사이클(DDTR)을 자동 수행
- **TDD by default** — 테스트를 먼저 작성하고 구현하여 통과시키는 TDD 워크플로우
- **Team parallel execution** — tmux 기반 다중 세션으로 Work Package 단위 병렬 개발
- **Agent pool** — tmux 없이도 서브에이전트 슬롯 풀 패턴으로 병렬 실행 가능

---

## 사전 요구사항

### Claude Code CLI

`claude` CLI가 설치되어 있어야 합니다. 팀 병렬 실행 시 `claude --dangerously-skip-permissions`로 worker를 생성합니다.

### tmux / psmux (team-mode, dev-team 사용 시 필수)

`team-mode`와 `dev-team`은 tmux 세션 안에서 실행해야 합니다. tmux 없이 병렬 실행이 필요하면 `agent-pool`을 사용하세요.

#### 설치 방법

| 플랫폼 | 설치 명령 |
|--------|-----------|
| **macOS** | `brew install tmux` |
| **Ubuntu / Debian** | `sudo apt install tmux` |
| **Fedora / RHEL** | `sudo dnf install tmux` |
| **Arch Linux** | `sudo pacman -S tmux` |
| **Windows** | [psmux](https://github.com/psmux/psmux) — tmux 호환 Windows 구현 |

#### 설치 확인 및 세션 시작

```bash
# 설치 확인
tmux -V

# 새 세션 시작
tmux new-session -s dev

# 세션 안에서 Claude Code 실행
claude
```

> **Windows(psmux) 참고**: psmux는 현재 세션을 자동 추론하지 않으므로, 플러그인 내부에서 모든 tmux 명령에 세션 이름을 명시합니다. 별도 설정은 필요 없습니다.

---

## 설치

### Step 1. 마켓플레이스 등록

```bash
/plugin marketplace add jongik-sv/dev-plugin
```

### Step 2. 플러그인 설치

```bash
# 사용자 레벨 (모든 프로젝트에서 사용)
/plugin install dev@dev-tools --scope user

# 또는 프로젝트 레벨 (현재 프로젝트에서만 사용)
/plugin install dev@dev-tools --scope project
```

### Step 3. 설치 확인

```bash
# 플러그인 목록 확인
/plugin list

# 스킬 목록에서 dev: 네임스페이스 확인
/skills
```

11개 스킬이 표시되면 설치 완료:
`wbs`, `agent-pool`, `team-mode`, `dev-team`, `dev`, `feat`, `dev-design`, `dev-build`, `dev-test`, `dev-refactor`, `dev-help`

---

## 포함된 스킬

**병렬 실행 엔진 (Layer 1)** — WBS 의존성 없이 범용 사용 가능:

| 스킬 | 설명 | 사용법 |
|------|------|--------|
| **agent-pool** | N개의 서브에이전트를 슬롯 풀 방식으로 병렬 실행 (tmux 불필요) | `/agent-pool [task-file] [--pool-size N]` |
| **team-mode** | N개의 독립 claude 세션을 tmux pane으로 병렬 실행 | `/team-mode [manifest] [--team-size N]` |

**개발 자동화 (Layer 2)** — WBS Task 단위 개발 사이클:

| 스킬 | 설명 | 사용법 |
|------|------|--------|
| **wbs** | PRD/TRD로부터 WBS 생성 (규모별 3/4단계 자동 선택) | `/wbs [--scale large\|medium]` |
| **dev** | WBS Task 전체 개발 사이클 오케스트레이터 (설계→TDD→테스트→리팩토링) | `/dev TSK-00-01` |
| **feat** | WBS 독립 Feature 전체 개발 사이클 (즉석 기능/버그/리팩토링) | `/feat rate-limiter` |
| **dev-design** | 설계 단계 — design.md 생성 | `/dev-design TSK-00-01` |
| **dev-build** | TDD 구현 — 테스트 먼저 작성 후 구현하여 통과 | `/dev-build TSK-00-01` |
| **dev-test** | 테스트 실행 — 실패 시 수정 반복 (최대 3회) | `/dev-test TSK-00-01` |
| **dev-refactor** | 리팩토링 — 코드 품질 개선 후 테스트 확인 | `/dev-refactor TSK-00-01` |

**팀 병렬 개발 (Layer 3)** — Layer 1 + Layer 2 조합:

| 스킬 | 설명 | 사용법 |
|------|------|--------|
| **dev-team** | WP 단위로 하위 Task들을 팀원에게 분배하여 병렬 개발 | `/dev-team WP-04 [--team-size 5]` |
| **dev-help** | 전체 스킬 사용법 안내 | `/dev-help` |

---

## 사용법

### WBS 생성 — `/wbs`

PRD/TRD 문서로부터 WBS를 생성합니다.

```bash
# 규모 자동 판단
/wbs

# 규모 지정
/wbs --scale large        # 4단계: Phase → WP → Task → SubTask
/wbs --scale medium       # 3단계: WP → Task → SubTask

# 일정 추정만
/wbs --estimate-only
```

### 단일 Task 개발 — `/dev`

하나의 Task를 설계부터 리팩토링까지 전체 사이클로 실행합니다.

```bash
# 전체 사이클 (설계 → TDD → 테스트 → 리팩토링)
/dev TSK-00-01

# 특정 단계만 실행
/dev TSK-00-01 --only design
/dev TSK-00-01 --only build
/dev TSK-00-01 --only test
/dev TSK-00-01 --only refactor
```

**개발 사이클 흐름 (DDTR)**:
```
[ ] → [dd] 설계 → [im] TDD 구현 → 테스트 → [xx] 리팩토링 완료
```

### Phase별 모델 선정 기준

각 Phase는 작업 특성에 맞는 모델을 자동 선택합니다:

| Phase | 기본 모델 | 선정 근거 |
|-------|-----------|-----------|
| **Design** | **복잡도 기반** (Sonnet 또는 Opus) | 아래 복잡도 점수로 자동 결정 |
| **Build** | Sonnet | TDD 구현은 설계 문서를 따르는 기계적 작업 |
| **Test** | Haiku (→ 실패 시 Sonnet 에스컬레이션 → 실패 시 Opus 에스컬레이션) | 에러 파싱→수정→재실행 루프는 가장 기계적 |
| **Refactor** | Sonnet | 코드 품질 개선은 중간 수준의 판단 필요 |

#### Design 모델 선택

`--model` 미지정 시, Design 모델은 아래 우선순위로 결정됩니다:

**우선순위**: `--model` CLI 옵션 > wbs.md `- model:` 필드 > 자동 점수 판정

**1. WBS `model` 필드 (권장)** — `/wbs`로 WBS 생성 시 LLM이 PRD/TRD 맥락을 종합하여 Task별 설계 모델을 직접 판정합니다:

```markdown
### TSK-04-03: pretool_bash_guard 바이너리
- category: development
- domain: sidecar
- model: opus          ← WBS 생성 시 결정
```

유효값: `opus`, `sonnet`. 이 필드가 있으면 자동 점수 계산을 건너뜁니다.

**2. 자동 점수 (fallback)** — `model` 필드가 없는 기존 WBS와 호환:

**WBS 모드** (`/dev`) — `wbs-parse.py --complexity`가 메타데이터 기반으로 산정:

| 신호 | 조건 | 점수 |
|------|------|------|
| depends | 0-1개: 0 / 2-3개: +1 / 4개+: +2 | 0~2 |
| domain | default/backend: 0 / frontend: +1 / fullstack: +2 / docs,test: -1 | -1~2 |
| 키워드 | 아키텍처, 미들웨어, 트랜잭션, WebSocket, FSM 등 (메타데이터 줄 제외) | +2 |
| category | config, docs | -1 |

**Feature 모드** (`/feat`) — 오케스트레이터가 spec.md + 프로젝트 구조를 확인:

| 신호 | 조건 | 점수 |
|------|------|------|
| 도메인 | spec.md의 도메인 값 (backend→0, frontend→+1, fullstack→+2) | 0~2 |
| 키워드 | spec.md 본문의 복잡도 키워드 | +2 |
| 영향 범위 | 모노레포 다수 패키지에 걸치면 | +1 |

**임계값: 3점 이상 → Opus, 미만 → Sonnet**

```bash
# 수동 오버라이드 (최우선)
/dev TSK-01-02 --model opus    # 강제 Opus
/feat login-2fa --model opus   # 강제 Opus
```

### 독립 Feature 개발 — `/feat`

WBS 없이 즉석 기능 추가, 버그 수정, 프로토타입 등을 전체 사이클(DDTR)로 실행합니다.

```bash
# 이름 지정
/feat rate-limiter

# 이름 + 설명
/feat rate-limiter "API 레이트 리미터 추가"

# 설명만 (이름 자동 생성)
/feat "로그인 2FA 기능 추가"

# 특정 단계만 실행
/feat rate-limiter --only design
/feat rate-limiter --only build

# 서브프로젝트 지정
/feat p1 rate-limiter
```

산출물은 `docs/features/{name}/` 하위에 생성됩니다:

```
docs/features/rate-limiter/
├── spec.md          # 요구사항
├── state.json       # 상태 추적
├── design.md        # 설계 문서
├── test-report.md   # 테스트 결과
└── refactor.md      # 리팩토링 내역
```

### 개별 단계 실행

전체 사이클 대신 각 단계를 독립적으로 실행할 수 있습니다.

```bash
/dev-design TSK-00-01     # design.md 생성, status → [dd]
/dev-build TSK-00-01      # 테스트 작성 + 구현, status → [im]
/dev-test TSK-00-01       # 테스트 실행, test-report.md 생성
/dev-refactor TSK-00-01   # 코드 개선, status → [xx]
```

각 단계의 산출물은 `docs/tasks/{TSK-ID}/` 하위에 생성됩니다:

```
docs/tasks/TSK-00-01/
├── design.md        # 설계 문서
├── test-report.md   # 테스트 결과
└── refactor.md      # 리팩토링 내역
```

### 팀 병렬 개발 — `/dev-team`

WP(Work Package) 단위로 하위 Task들을 팀원에게 분배하여 병렬 개발합니다.
tmux 환경에서 WP 리더 + 팀원 pane 구조로 동작합니다.

```bash
# 단일 WP 실행
/dev-team WP-04

# 복수 WP 동시 실행
/dev-team WP-06 WP-07

# WP 자동 선정 (실행 가능한 WP 자동 탐색)
/dev-team

# 팀원 수 조절 (기본: 3명)
/dev-team WP-04 --team-size 5

# 테스트 실패 모드 지정
/dev-team WP-04 --on-fail strict    # 강력 검증: 실패 시 즉시 중단
/dev-team WP-04 --on-fail bypass    # 에스컬레이션 (기본값)
/dev-team WP-04 --on-fail fast      # 속도 우선: 즉시 다음 진행
```

**아키텍처**:
```
팀리더 (현재 세션)
 ├─ [tmux window: WP-04]
 │   ├─ [pane 0] WP 리더 (스케줄링)
 │   ├─ [pane 1] 팀원1 (Task 수행)
 │   ├─ [pane 2] 팀원2 (Task 수행)
 │   └─ [pane 3] 팀원3 (Task 수행)
 └─ [tmux window: WP-05]
     └─ ... (동일 구조)
```

#### 테스트 실패 모드 (`--on-fail`)

Task가 테스트에 실패했을 때 의존 Task의 진행 방식을 제어합니다:

| 모드 | 설명 | 재시도 | 의존 Task |
|------|------|--------|-----------|
| **`strict`** | 강력 검증 | 없음 | WP 전체 중단, 사용자 보고 |
| **`bypass`** (기본) | 에스컬레이션 | 1차 Sonnet, 2차 Opus | 소진 시 임시 완료(`bypassed`) 처리 후 계속 |
| **`fast`** | 속도 우선 | 없음 | 즉시 임시 완료 처리 후 계속 |

- `bypass`/`fast` 모드에서 임시 완료된 Task는 `state.json`에 `bypassed: true`로 기록되며, 실제 상태(예: `[im]`)는 그대로 유지됩니다.
- 향후 MCP/CLI를 통해 bypass된 Task를 사람에게 이슈로 전달하는 기능이 추가될 예정입니다.

> tmux가 없으면 `/dev TSK-ID`로 순차 개발하세요.

### 범용 병렬 실행 — `/agent-pool`, `/team-mode`

WBS와 무관하게 임의의 작업을 병렬로 실행합니다.

```bash
# agent-pool: tmux 불필요, 서브에이전트 슬롯 풀
/agent-pool --pool-size 4
# 또는 task 파일 지정
/agent-pool tasks.md --pool-size 3

# team-mode: tmux 기반 독립 세션
/team-mode --team-size 3
# 또는 manifest 파일 지정
/team-mode manifest.md --team-size 5
```

---

## 프로젝트 요구사항

이 플러그인은 아래 구조를 갖춘 프로젝트에서 사용합니다.

### 필수 파일

| 파일 | 용도 |
|------|------|
| `docs/PRD.md` | 제품 요구사항 정의서 |
| `docs/TRD.md` | 기술 요구사항 정의서 |
| `docs/wbs.md` | WBS 정의 (WP, Task, 의존성, 상태) |

### WBS Task 형식

`docs/wbs.md`에 아래 형식으로 Task가 정의되어야 합니다:

```markdown
### TSK-00-01: Task 제목
- category: development
- domain: backend | frontend | sidecar | fullstack
- status: [ ] | [dd] | [im] | [xx]
- priority: critical | high | medium | low
- depends: TSK-XX-XX, TSK-YY-YY

#### PRD 요구사항
- requirements:
  - ...
- acceptance:
  - ...

#### 기술 스펙 (TRD)
- tech-spec:
  - ...
```

### 상태값 의미

| 상태 | 의미 |
|------|------|
| `[ ]` | 미착수 |
| `[dd]` | 설계 완료 (design done) |
| `[im]` | 구현 완료 (implementation) |
| `[xx]` | 전체 완료 |

### Dev Config (프로젝트별 설정)

`docs/wbs.md` 상단에 `## Dev Config` 섹션을 추가하여 domain별 테스트 명령, 설계 가이드, 정리 대상 프로세스를 정의합니다.
`/wbs`로 WBS를 생성하면 TRD 기반으로 자동 생성됩니다.

```markdown
## Dev Config

### Domains
| domain | description | unit-test | e2e-test |
|--------|-------------|-----------|----------|
| backend | Server API | `your-unit-test-cmd` | `your-e2e-test-cmd` |
| frontend | Client UI | `your-unit-test-cmd` | `your-e2e-test-cmd` |
| database | Data layer | - | - |
| fullstack | Full stack | - | - |

### Design Guidance
| domain | architecture |
|--------|-------------|
| backend | Your backend architecture description |
| frontend | Your frontend architecture description |

### Cleanup Processes
node, vitest
```

- `unit-test`/`e2e-test`에 `-`를 쓰면 해당 테스트는 N/A로 처리됩니다
- `fullstack` domain은 테스트 명령이 있는 모든 domain을 순차 실행합니다 (fail-fast)
- `## Dev Config` 섹션이 없으면 스킬 실행 시 에러와 함께 템플릿이 안내됩니다

---

## Architecture

```
dev-plugin/
├── .claude-plugin/
│   ├── plugin.json              # 플러그인 메타데이터 (이름, 버전)
│   └── marketplace.json         # 마켓플레이스 등록 정보
├── skills/                      # 스킬 (10개, 각 디렉토리의 SKILL.md가 진입점)
│   ├── agent-pool/              # Layer 1: 서브에이전트 슬롯 풀
│   ├── team-mode/               # Layer 1: tmux 병렬 세션
│   ├── wbs/                     # Layer 2: WBS 생성
│   ├── dev/                     # Layer 2: DDTR 오케스트레이터 (WBS Task)
│   ├── feat/                    # Layer 2: DDTR 오케스트레이터 (독립 Feature)
│   ├── dev-design/              # Layer 2: 설계 단계
│   ├── dev-build/               # Layer 2: TDD 구현 단계
│   ├── dev-test/                # Layer 2: 테스트 단계
│   ├── dev-refactor/            # Layer 2: 리팩토링 단계
│   ├── dev-team/                # Layer 3: 팀 병렬 개발
│   └── dev-help/                # 사용법 안내
├── CLAUDE.md                    # Claude Code 프로젝트 지침
└── README.md
```

### Key Patterns

- **Signal files** — 에이전트 간 통신은 파일 기반 시그널(`.done`, `.running`, `.failed`, `.bypassed`) 사용. worktree에서는 절대경로 필수.
- **Pane recycling** — 팀원이 Task 완료 후 `/clear` → 다음 Task 할당 (prompt 파일 경유, tmux send-keys 길이 제한 회피)
- **Slot pool** — 정확히 N개의 동시 에이전트 유지; 슬롯이 비면 다음 Task 즉시 실행
- **Git worktrees** — `dev-team`은 WP별 격리된 worktree 생성, 완료 시 main에 머지
- **Heartbeat** — worker가 주기적으로 `.running` 파일을 touch, 리더가 stale 감지

---

## 관리

### 플러그인 업데이트

```bash
/plugin update dev@dev-tools
```

### 플러그인 제거

```bash
/plugin uninstall dev@dev-tools
```

### 플러그인 재로드

스킬이 보이지 않을 때:
```bash
/reload-plugins
```

---

## 문제 해결

### tmux가 설치되어 있지 않음

`team-mode` 또는 `dev-team` 실행 시 tmux가 없으면 설치 안내가 표시됩니다.

| 플랫폼 | 설치 명령 |
|--------|-----------|
| macOS | `brew install tmux` |
| Ubuntu / Debian | `sudo apt install tmux` |
| Fedora / RHEL | `sudo dnf install tmux` |
| Arch Linux | `sudo pacman -S tmux` |
| Windows | [psmux](https://github.com/psmux/psmux) 설치 |

tmux 없이 병렬 실행이 필요하면 `/agent-pool`을 사용하세요.

### tmux 세션 밖에서 실행

```bash
# 세션 시작 후 Claude Code 실행
tmux new-session -s dev
claude
```

`dev-team`은 tmux 없이 실행하면 Agent 도구 백그라운드 모드로 자동 전환됩니다.

### 스킬이 `/skills` 목록에 표시되지 않음

1. `/plugin list`에서 설치 여부 확인
2. `/reload-plugins` 실행
3. 네임스페이스 충돌 확인 — 프로젝트 `.claude/skills/`에 동일 이름 스킬이 있으면 프로젝트 스킬이 우선

### 네임스페이스 충돌

프로젝트에 동일 이름 스킬이 있으면 플러그인 스킬이 가려집니다.

```bash
# 플러그인 스킬 명시 호출
/dev:dev-team WP-04

# 또는 프로젝트 스킬 삭제 후 플러그인 사용
rm -rf .claude/skills/dev-team
```

**우선순위** (높은 순):
1. 프로젝트 스킬 (`.claude/skills/`)
2. 사용자 스킬 (`~/.claude/skills/`)
3. 플러그인 스킬

---

## License

MIT
