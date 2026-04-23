---
name: dev-help
description: "Dev 플러그인의 모든 스킬 사용법을 안내한다. 사용법: /dev-help"
---

# /dev-help - Dev 플러그인 사용법 안내

아래 내용을 사용자에게 **그대로** 출력하라. 추가 설명이나 도구 호출 없이 텍스트만 출력한다.

---

## Dev 플러그인 스킬 가이드

WBS 기반 TDD 개발 자동화 플러그인입니다. 설계 → TDD 구현 → 테스트 → 리팩토링 사이클과 팀 병렬 개발을 지원합니다.

### 스킬 목록

| 스킬 | 설명 | 사용법 |
|------|------|--------|
| `/wbs` | PRD/TRD → WBS 자동 생성 | `/wbs` 또는 `/wbs p1` |
| `/dev-team` | WP 단위 팀 병렬 개발 (tmux+워크트리) | `/dev-team WP-04` 또는 `/dev-team p1 WP-01` |
| `/dev-seq` | WP 단위 **순차** 개발 (tmux/워크트리 없음, 현재 세션·현재 브랜치) | `/dev-seq WP-04` 또는 `/dev-seq p1 WP-01 WP-02` |
| `/team-mode` | tmux 기반 N개 claude 세션 병렬 실행 (범용) | `/team-mode 작업 지시` |
| `/agent-pool` | 서브에이전트 풀 병렬 실행 (범용, tmux 불필요) | `/agent-pool 작업 지시` |
| `/dev` | WBS Task 전체 사이클 (설계→TDD→테스트→리팩토링) | `/dev TSK-00-01` 또는 `/dev p1 TSK-01-01` |
| `/feat` | WBS 독립 Feature 전체 사이클 (WBS가 없는 즉석 개발용, 이름 생략 시 자동 생성) | `/feat login-2fa "2FA 추가"` 또는 `/feat "add rate limiter"` |
| `/dev-design` | 설계 → design.md 생성 | `/dev-design [p1] TSK-00-01` |
| `/dev-build` | TDD 구현 (테스트 먼저 → 구현) | `/dev-build [p1] TSK-00-01` |
| `/dev-test` | 테스트 실행, 실패 시 수정 반복 (최대 3회) | `/dev-test [p1] TSK-00-01` |
| `/dev-refactor` | 리팩토링 후 테스트 확인 | `/dev-refactor [p1] TSK-00-01` |
| `/dev-help` | 이 안내 메시지 표시 | `/dev-help` |

### 서브프로젝트(하위 폴더) 지원

하나의 저장소 안에서 여러 프로젝트를 관리하고 싶을 때, 첫 인자로 **하위 폴더 이름**을 지정할 수 있습니다.

- 지정 안 함 → `docs/PRD.md`, `docs/TRD.md`, `docs/wbs.md`, `docs/tasks/{TSK-ID}/` 사용
- `p1` 지정 → `docs/p1/PRD.md`, `docs/p1/TRD.md`, `docs/p1/wbs.md`, `docs/p1/tasks/{TSK-ID}/` 사용

```
/wbs p1                         # docs/p1/wbs.md 생성
/dev p1 TSK-01-01               # docs/p1/ 하위에서 전체 사이클
/dev-team p1 WP-01              # docs/p1/wbs.md의 WP-01 병렬 개발
/dev-team p1                    # docs/p1/에서 실행 가능 WP 자동 선정
/dev-design p1 TSK-01-01
```

판별 규칙: 첫 번째 토큰이 `WP-*`/`TSK-*`/`--*` 패턴이 아니고 `docs/{토큰}/`가 존재하면 서브프로젝트로 간주합니다.

---

### `/wbs` — PRD/TRD 기반 WBS 생성

`docs/PRD.md`, `docs/TRD.md`(또는 `docs/{sub}/PRD.md`, `docs/{sub}/TRD.md`)를 분석하여 계층적 WBS(`docs/wbs.md` 또는 `docs/{sub}/wbs.md`)를 자동 생성합니다. 규모에 따라 4단계/3단계 구조 자동 선택.

```
/wbs                          # docs/ 기준 WBS 생성
/wbs p1                       # docs/p1/ 기준 WBS 생성
/wbs --scale large            # 4단계(대규모) 강제 지정
/wbs p1 --start-date 2026-04-01
/wbs --estimate-only          # 규모 산정만 (WBS 생성 안 함)
```

---

### `/team-mode` — tmux 병렬 세션

N개의 독립 claude 세션을 tmux pane에서 병렬 실행합니다. 작업 리스트를 지시하면 자동으로 분배합니다. tmux 환경 필요.

```
/team-mode M473020030, M473020040, M473020050 서비스 레거시 분석해줘
/team-mode --team-size 5 WP-01 ~ WP-05 각각 설계 문서 작성해줘
팀모드로 M473020030, M473020040, M473020050 서비스 레거시 분석해줘
```

---

### `/agent-pool` — 서브에이전트 풀

하나의 세션에서 N개 서브에이전트를 pool 패턴으로 병렬 실행합니다. tmux 불필요.

```
/agent-pool M47 모듈의 서비스 10개 BPA 문서 생성해줘
/agent-pool --pool-size 5 PL_M30_STOCK_CSM, PL_M30_ORDER_MGR, PL_M30_INV_CALC 프로시저 분석해줘
/analyze-plsql agent pool 스킬로 plsql폴더의 프로시저 분석해줘. agent 개수 10개.
```

---

### `/dev-team` — WP 팀 병렬 개발

WP(Work Package) 단위로 하위 Task들을 여러 팀원에게 분배하여 병렬로 개발합니다.
병렬 처리를 위한 핵심 스킬입니다.

```
/dev-team WP-04                 # 단일 WP 실행 (docs/ 기준)
/dev-team p1 WP-01              # 서브프로젝트 docs/p1/에서 WP-01 실행
/dev-team WP-04 WP-05           # 복수 WP 동시 실행
/dev-team p1 WP-01 WP-02        # 서브프로젝트에서 복수 WP 동시 실행
/dev-team                       # 실행 가능 WP 자동 선정 (docs/)
/dev-team p1                    # docs/p1/에서 실행 가능 WP 자동 선정
/dev-team WP-04 --team-size 5   # 팀원 수 변경 (기본: 3명)
```

**아키텍처** (tmux 환경): 팀리더(현재 세션) → WP마다 tmux window 1개 → pane 0 (WP 리더, 스케줄링) + pane 1~N (팀원, Task 수행). 자세한 구조는 `skills/dev-team/SKILL.md` 참조.

**동작**:
- WBS에서 WP 하위 Task를 수집하고 의존성 레벨을 분석
- 같은 레벨의 Task는 병렬 실행, 레벨 간에는 순차 진행
- 각 팀원이 Task마다 설계→TDD→테스트→리팩토링 전체 사이클 수행
- 시그널 파일 기반 완료 감지, cross-WP 의존성 동기화
- 완료된 WP는 즉시 main에 머지 (조기 머지)

**요구사항**: tmux 세션 내에서 실행 필요. tmux 없으면 Agent 백그라운드 모드로 전환됩니다.

---

### `/dev-seq` — WP 순차 개발 (단일 모드)

`/dev-team`과 동일한 인자 형태지만 **tmux·워크트리·WP 리더·팀원 pane을 모두 사용하지 않습니다**. 여러 WP를 인자 순서대로 직렬 처리하고, WP 내부 Task도 의존성 위상정렬 순서로 직렬 실행합니다. 각 Task의 Design/Build/Test/Refactor Phase는 서브에이전트로 실행됩니다.

```
/dev-seq WP-04                      # 단일 WP 순차 실행 (docs/ 기준)
/dev-seq p1 WP-01                   # 서브프로젝트 docs/p1/에서 WP-01
/dev-seq WP-01 WP-02 WP-03          # 여러 WP 인자 순서대로 직렬 처리
/dev-seq p1                         # docs/p1/에서 실행 가능 WP 자동 선정
/dev-seq WP-04 --on-fail strict     # 테스트 실패 시 즉시 전체 중단
/dev-seq WP-04 --on-fail fast       # 실패 시 에스컬레이션 스킵, 즉시 bypass
/dev-seq WP-04 --model opus         # 전 단계 Opus
```

**`--team-size`는 지원하지 않습니다** (항상 1명 순차). 병렬이 필요하면 `/dev-team`을 사용하세요.

**언제 쓰나**:
- tmux가 없거나 쓰기 번거로운 환경
- 진행 상황을 눈으로 따라가며 검증하고 싶을 때
- 소규모 WP·적은 Task로 병렬 오버헤드가 아깝다고 판단될 때
- 리소스 제약(동시 Opus 다중 호출 피하고 싶을 때)

⚠️ `/dev-seq`는 **현재 브랜치에 직접 커밋**합니다. 격리가 필요하면 `/dev-team`(별도 워크트리+브랜치)을 사용하세요.

---

### `/dev` — WBS Task 전체 개발 사이클

```
/dev TSK-00-01                  # 전체 사이클 (docs/ 기준)
/dev p1 TSK-01-01               # 서브프로젝트 docs/p1/ 기준 전체 사이클
/dev TSK-00-01 --only design    # 특정 단계만 실행 (design|build|test|refactor)
/dev p1 TSK-01-01 --only build
```

---

### `/feat` — WBS 독립 Feature 전체 사이클

WBS가 없거나 과한 상황(즉석 기능 추가, 버그 수정, 프로토타입, 오픈소스 기여, 단독 리팩토링)에서 사용합니다. `/dev`와 동일한 DFA/Phase 스킬을 공유하며, 요구사항 원천과 산출물 경로만 다릅니다.

```
/feat login-2fa "로그인에 2FA 추가"        # 이름 명시 + 설명
/feat login-2fa                              # 기존 Feature 재개 (상태에 따라 해당 Phase부터)
/feat login-2fa --only design                # 특정 단계만 실행
/feat p1 login-2fa "..."                     # 서브프로젝트 docs/p1/features/에 생성

# 이름 자동 생성 (설명만 제공)
/feat "add rate limiter middleware"          # → add-rate-limiter-middleware
/feat add rate limiter middleware            # 따옴표 없이도 동일
/feat fix the race condition in worker pool  # → fix-the-race-condition-in-worker-pool
/feat "로그인에 2FA 추가"                    # 한국어만 → feat-YYYYMMDD-HHMMSS (timestamp fallback)
```

**이름 입력 방식**:

| 입력 형태 | 해석 |
|-----------|------|
| 하이픈 포함 토큰 (`rate-limiter`) | 이름으로 사용 |
| 하이픈 없는 단일 토큰 (`login`) | 이름으로 사용 |
| 하이픈 없는 첫 토큰 + 추가 토큰 (`add rate limiter`) | 전체를 설명 취급, 슬러그로 자동 생성 |
| 대문자/공백 포함 (`"Add rate limit"`) | 전체를 설명 취급, 슬러그로 자동 생성 |
| 비-ASCII (한국어 등) | 설명으로 저장하되 이름은 `feat-YYYYMMDD-HHMMSS` fallback |

**이름 규칙**: kebab-case (`^[a-z][a-z0-9-]*$`). 자동 생성도 동일 규칙을 따른다.

**저장 위치**:
| 항목 | 경로 |
|------|------|
| 요구사항 | `{DOCS_DIR}/features/{name}/spec.md` |
| 상태 | `{DOCS_DIR}/features/{name}/state.json` |
| 설계 | `{DOCS_DIR}/features/{name}/design.md` |
| 테스트 리포트 | `{DOCS_DIR}/features/{name}/test-report.md` |
| 리팩토링 리포트 | `{DOCS_DIR}/features/{name}/refactor.md` |

**WBS 모드와의 차이점**:
| 항목 | `/dev` (WBS) | `/feat` (Feature) |
|------|--------------|-------------------|
| 요구사항 원천 | `wbs.md`의 Task 블록 + PRD/TRD | `spec.md` (사용자 직접 입력) |
| 상태 저장 (원천) | `docs/tasks/{TSK-ID}/state.json` (wbs.md의 `- status:` 줄은 파생 뷰) | `docs/features/{name}/state.json` |
| 산출물 위치 | `{DOCS_DIR}/tasks/{TSK-ID}/` | `{DOCS_DIR}/features/{name}/` |
| DFA / Phase 스킬 | 공통 (`references/state-machine.json`, `dev-design/build/test/refactor`) | 공통 |
| 팀 병렬(`/dev-team`) | O | X — 개별 Feature로 운영 |

---

### 프로젝트 필수 파일

| 파일 | 용도 |
|------|------|
| `docs/wbs.md` (또는 `docs/{sub}/wbs.md`) | WBS 정의 (WP, Task, 의존성, 상태) |
| `docs/PRD.md` (또는 `docs/{sub}/PRD.md`) | 제품 요구사항 정의서 |
| `docs/TRD.md` (또는 `docs/{sub}/TRD.md`) | 기술 요구사항 정의서 |

### 상태값 (WBS 및 Feature 공통 DFA)

성공 전이만 상태를 전진시킵니다. 실패는 상태를 유지한 채 state.json의 `last.event`와 `phase_history`에만 기록됩니다.

| 상태 | 의미 | phase_start | 전진 이벤트 |
|------|------|-------------|-------------|
| `[ ]` | 미착수 / 설계 미완료 | `design` | `design.ok` → `[dd]` |
| `[dd]` | 설계 완료 / 빌드 대기 또는 재시도 | `build` | `build.ok` → `[im]` |
| `[im]` | 빌드 완료 / 테스트 대기 또는 재시도 | `test` | `test.ok` → `[ts]` |
| `[ts]` | 테스트 통과 / 리팩토링 대기 또는 재시도 | `refactor` | `refactor.ok` → `[xx]` |
| `[xx]` | 전체 완료 | `done` | — |

`build.fail`/`test.fail`/`refactor.fail` 이벤트는 상태를 전진시키지 않고 `last.event`와 `phase_history`에만 기록됩니다. `/dev` 또는 `/feat` 재실행 시 status가 그대로이므로 동일 Phase부터 자연 재개됩니다. 마지막 시도가 무엇이었는지(성공 직후인지 실패 후인지)는 `state.json`의 `last` 필드로 구분할 수 있습니다.

전체 상태 전이 규칙은 `references/state-machine.json`에 정의되어 있으며, WBS 모드와 Feature 모드가 동일한 DFA를 공유합니다.
