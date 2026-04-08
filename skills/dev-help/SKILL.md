---
name: dev-help
description: "Dev 플러그인의 모든 스킬 사용법을 안내한다. 사용법: /dev-help"
user_invocable: true
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
| `/dev-team` | WP 단위 팀 병렬 개발 (핵심 스킬) | `/dev-team WP-04` 또는 `/dev-team p1 WP-01` |
| `/team-mode` | tmux 기반 N개 claude 세션 병렬 실행 (범용) | `/team-mode 작업 지시` |
| `/agent-pool` | 서브에이전트 풀 병렬 실행 (범용, tmux 불필요) | `/agent-pool 작업 지시` |
| `/dev` | Task 전체 사이클 (설계→TDD→테스트→리팩토링) | `/dev TSK-00-01` 또는 `/dev p1 TSK-01-01` |
| `/dev-design` | 설계 → design.md 생성 | `/dev-design [p1] TSK-00-01` |
| `/dev-build` | TDD 구현 (테스트 먼저 → 구현) | `/dev-build [p1] TSK-00-01` |
| `/dev-test` | 테스트 실행, 실패 시 수정 반복 (최대 3회) | `/dev-test [p1] TSK-00-01` |
| `/dev-refactor` | 리팩토링 후 테스트 확인 | `/dev-refactor [p1] TSK-00-01` |

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
/generate-bpa 팀모드로 M473020030, M473020040, M473020050 서비스 레거시 분석해줘
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

**아키텍처** (tmux 환경):
```
팀리더 (현재 세션)
 ├─ [tmux window: WP-04]
 │   ├─ [pane 0] WP 리더 (스케줄링)
 │   ├─ [pane 1~N] 팀원 (Task 수행)
 └─ [tmux window: WP-05]
     └─ ... (동일 구조)
```

**동작**:
- WBS에서 WP 하위 Task를 수집하고 의존성 레벨을 분석
- 같은 레벨의 Task는 병렬 실행, 레벨 간에는 순차 진행
- 각 팀원이 Task마다 설계→TDD→테스트→리팩토링 전체 사이클 수행
- 시그널 파일 기반 완료 감지, cross-WP 의존성 동기화
- 완료된 WP는 즉시 main에 머지 (조기 머지)

**요구사항**: tmux 세션 내에서 실행 필요. tmux 없으면 Agent 백그라운드 모드로 전환됩니다.

---

### `/dev` — Task 전체 개발 사이클

```
/dev TSK-00-01                  # 전체 사이클 (docs/ 기준)
/dev p1 TSK-01-01               # 서브프로젝트 docs/p1/ 기준 전체 사이클
/dev TSK-00-01 --only design    # 특정 단계만 실행 (design|build|test|refactor)
/dev p1 TSK-01-01 --only build
```

---

### 프로젝트 필수 파일

| 파일 | 용도 |
|------|------|
| `docs/wbs.md` (또는 `docs/{sub}/wbs.md`) | WBS 정의 (WP, Task, 의존성, 상태) |
| `docs/PRD.md` (또는 `docs/{sub}/PRD.md`) | 제품 요구사항 정의서 |
| `docs/TRD.md` (또는 `docs/{sub}/TRD.md`) | 기술 요구사항 정의서 |

### WBS 상태값

| 상태 | 의미 | 변경 스킬 |
|------|------|-----------|
| `[ ]` | 미착수 | — |
| `[dd]` | 설계 완료 | `/dev-design` |
| `[im]` | 구현 완료 | `/dev-build` |
| `[xx]` | 전체 완료 | `/dev-refactor` |
