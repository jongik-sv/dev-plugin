---
name: wbs
description: "PRD/TRD를 기반으로 WBS를 생성한다. 프로젝트 규모에 따라 4단계(대규모)/3단계(중소규모) 구조를 자동 선택. 사용법: /wbs [SUBPROJECT | /absolute/path/to/wbs.md] [--scale large|medium] [--start-date YYYY-MM-DD] [--estimate-only]"
---

# /wbs - PRD/TRD 기반 WBS 생성

> **PRD/TRD → WBS 자동 변환**: `{DOCS_DIR}/PRD.md`, `{DOCS_DIR}/TRD.md`를 분석하여 계층적 WBS를 `{DOCS_DIR}/wbs.md`로 생성한다.

인자: `$ARGUMENTS` (옵션)
- `SUBPROJECT`: (옵션) 하위 프로젝트 폴더 이름. 예: `p1` → `docs/p1/` 하위에서 동작
- `/absolute/path/to/wbs.md`: (옵션) 기존 WBS 파일의 절대 경로. 해당 파일을 읽어 내용을 표시하고, 디렉토리를 `DOCS_DIR`로 사용
- `--scale [large|medium]`: 프로젝트 규모 강제 지정 (기본: 자동 산정)
- `--start-date YYYY-MM-DD`: 프로젝트 시작일 (기본: 오늘)
- `--estimate-only`: 규모 산정만 실행, WBS 생성 안 함

## 0. 인자 파싱 — 서브프로젝트 감지 (공통 규칙)

`$ARGUMENTS`를 공백으로 토큰화하여 첫 번째 토큰을 검사한다:

1. **절대 경로 감지** — 토큰이 `/`로 시작하는 경우:
   - 해당 파일이 존재하면:
     - `WBS_FILE={절대경로}`, `DOCS_DIR={파일의 디렉토리}` 설정
     - 파일 내용을 읽어 사용자에게 표시
     - `VIEW_MODE=true` — WBS 생성을 건너뛰고 기존 파일 조회 모드로 동작
   - 파일이 존재하지 않으면: 에러 "`{경로}` 파일이 존재하지 않습니다" 보고 후 종료
   - 해당 토큰을 `$ARGUMENTS`에서 제거
2. 토큰이 없거나 `--`로 시작 → 서브프로젝트 없음, `DOCS_DIR=docs`
3. `^(WP|TSK)-` 패턴 → 서브프로젝트 없음, `DOCS_DIR=docs` (토큰은 그대로 유지)
4. 그 외 문자열 → 서브프로젝트 이름 후보
   - `docs/{토큰}/` 디렉토리가 존재하면: `SUBPROJECT={토큰}`, `DOCS_DIR=docs/{토큰}`, 해당 토큰을 `$ARGUMENTS`에서 제거
   - 존재하지 않고 `--estimate-only`도 아니면: 사용자에게 "`docs/{토큰}/`가 없습니다. 생성하시겠습니까?" 확인 후 `mkdir -p docs/{토큰}` 생성 후 진행
   - 혹은 단순 오타일 수 있으므로 에러 보고 후 종료

이후 모든 경로는 하드코딩된 `docs` 대신 `{DOCS_DIR}`을 사용한다.

## 입력 파일 (자동 감지)

- **PRD**: `{DOCS_DIR}/PRD.md`
- **TRD**: `{DOCS_DIR}/TRD.md`

두 파일이 없으면 에러를 보고하고 중단한다.

---

## 계층 구조

```
Project
├── Work Package (WP) — 주요 기능 묶음 (1~3개월)
│   ├── Activity (ACT) — 세부 활동 (1~4주)        ← 4단계(대규모)만
│   │   └── Task (TSK) — 실제 작업 (1일~1주)
│   └── Task (TSK) — 실제 작업 (1일~1주)           ← 3단계(중소규모)
```

### 규모 판별 기준

| 기준 | 대규모 (4단계) | 중소규모 (3단계) |
|------|---------------|-----------------|
| 예상 기간 | 12개월+ | 12개월 미만 |
| 팀 규모 | 10명+ | 10명 미만 |
| 기능 영역 수 | 5개+ | 5개 미만 |
| 예상 Task 수 | 50개+ | 50개 미만 |

> **타이브레이커**: 기준 간 판단이 갈리면 큰 규모(4단계)를 선택한다. 4단계에서 불필요한 Activity 레벨은 제거하기 쉽지만, 3단계에서 누락된 Activity를 나중에 추가하는 것은 재작업이 크다.

### ID 패턴

| 레벨 | 4단계 | 3단계 |
|------|-------|-------|
| WP | `## WP-XX:` | `## WP-XX:` |
| ACT | `### ACT-XX-XX:` | — |
| TSK | `#### TSK-XX-XX-XX:` | `### TSK-XX-XX:` |

- `WP-00`은 프로젝트 초기화용으로 예약

### Task category

`development` / `defect` / `infrastructure` 세 가지 모두 동일 DDTR 워크플로우(`[ ]`→`[dd]`→`[im]`→`[ts]`→`[xx]`)를 따른다. 상태 전이와 실패 처리 규칙은 `${CLAUDE_PLUGIN_ROOT}/references/state-machine.json`에 정의되어 있다.

### Task domain

PRD/TRD를 분석하여 프로젝트에 맞는 domain을 자유롭게 정의한다 (예: `frontend`, `backend`, `infra`, `ml-pipeline`, `etl`, `fullstack`). domain 이름은 제약 없음.

### Dev Config 생성

WBS 생성 시, 헤더 블록과 첫 번째 WP 사이에 `## Dev Config` 섹션을 삽입한다. 섹션 골격과 각 항목의 의미(`domain`/`unit-test`/`e2e-test`/`Design Guidance`/`Cleanup Processes`, `-` 표기, `fullstack` 정책)는 `${CLAUDE_PLUGIN_ROOT}/skills/wbs/references/dev-config-template.md` 단일 소스를 참조한다. 템플릿을 Read하여 복사한 뒤, TRD의 기술 스택 정보로 명령과 아키텍처 설명을 채우고 추론할 수 없는 값은 사용자에게 확인한다.

---

## 실행 플로우

### 0.5단계: VIEW_MODE 분기

`VIEW_MODE=true`(절대 경로로 기존 wbs.md를 지정한 경우):
1. 해당 파일을 읽어 전체 내용을 사용자에게 표시
2. 같은 디렉토리에 PRD.md가 있으면 프로젝트 요약 정보도 함께 표시
3. 이후 단계를 건너뛰고 종료

### 1단계: PRD/TRD 분석 및 규모 산정

1. `{DOCS_DIR}/PRD.md` 읽기 — 기능 요구사항, 마일스톤, 우선순위 파악
2. `{DOCS_DIR}/TRD.md` 읽기 — 기술 스택, API 설계, 데이터 모델 파악
3. 규모 판별 기준에 따라 4단계/3단계 결정 (`--scale` 지정 시 해당 값 사용)
4. `--estimate-only`이면 규모 산정 결과만 출력하고 종료

### 2단계: PRD → Work Package 매핑

| PRD 섹션 | WP 매핑 |
|----------|---------|
| 프로젝트 초기화 | WP-00 |
| MVP 핵심 기능 (P0) | WP-01 ~ WP-0N |
| MVP 중요 기능 (P1) | WP-0N+1 ~ WP-0M |
| Phase 2+ (P2~P3) | 참고용 WP (상세 분해 미실시) |

### 3단계: WP → Activity 분해 (4단계만)

- 사용자 관점 기능 단위로 분해
- 1~4주 규모 검증
- MECE 원칙 (상호 배타적 + 전체 포괄)

### 4단계: Task 분해 및 category/domain 분류

**Task 크기 검증**:
- 최소: 4시간 / 권장: 1~3일 / 최대: 1주 (초과 시 분할)

### 5단계: PRD/TRD 컨텍스트 주입

각 Task에 관련 정보를 직접 포함하여 **자기 완결적**으로 만든다.

**PRD → Task**:

| PRD 섹션 | Task 속성 |
|----------|----------|
| 기능 요구사항 | prd-ref, requirements |
| 인수 조건 | acceptance |
| 비기능 요구사항 | constraints |

**TRD → Task**:

| TRD 섹션 | Task 속성 |
|----------|----------|
| 기술 스택 | tech-spec |
| API 설계 | api-spec |
| 데이터 모델 | data-model |
| UI 컴포넌트 | ui-spec |

**상세도 레벨**:

| Task 특성 | 레벨 |
|----------|------|
| 인프라/설정 | minimal |
| 단순 CRUD | standard |
| 비즈니스 로직 | detailed |
| 핵심/신규 개발 | full |

### 6단계: 일정 계산

| category | 기본 기간 | 범위 |
|----------|----------|------|
| development | 10일 | 5~15일 |
| defect | 3일 | 2~5일 |
| infrastructure | 5일 | 2~10일 |

의존성(`depends`) 기반으로 시작일/종료일 산출.

### 7단계: 프로젝트 정보 자동 채우기

WBS 헤더에 프로젝트 메타데이터를 PRD/TRD에서 추출하여 자동으로 채운다:

| 필드 | 추출 소스 | 폴백 |
|------|----------|------|
| **프로젝트명** | PRD 제목 (`# ` 뒤의 텍스트) | 서브프로젝트 디렉토리명 |
| **설명** | PRD 첫 번째 요약 문단 또는 `## 개요` 섹션 | `-` |
| **시작일** | `--start-date` 플래그 > PRD 마일스톤 시작일 > 오늘 날짜 | 오늘 날짜 |
| **목표일** | PRD 마일스톤 최종 기한 > 일정 계산 결과의 최종 종료일 | 일정 계산 결과 |

### 8단계: wbs.md 생성

`{DOCS_DIR}/wbs.md` 파일을 생성한다.

---

## 출력 형식

```markdown
# WBS - {프로젝트명}

> version: 1.0
> description: {프로젝트 설명 — PRD에서 추출}
> depth: {3 또는 4}
> start-date: {시작일}
> target-date: {목표일}
> updated: {날짜}

---

## WP-00: 프로젝트 초기화
- status: planned
- priority: critical
- schedule: {시작일} ~ {종료일}
- progress: 0%

### TSK-00-01: {Task명}
- category: infrastructure
- domain: infra
- status: [ ]
- priority: critical
- assignee: -
- schedule: {시작일} ~ {종료일}
- tags: setup, init
- depends: -

---

## WP-01: {Work Package명}
- status: planned
- priority: high
- schedule: {시작일} ~ {종료일}
- progress: 0%

### TSK-01-01: {Task명}
- category: development
- domain: backend
- status: [ ]
- priority: high
- assignee: -
- schedule: {시작일} ~ {종료일}
- tags: {관련 태그}
- depends: -

#### PRD 요구사항
- prd-ref: {PRD 섹션 참조}
- requirements:
  - {요구사항 1}
  - {요구사항 2}
- acceptance:
  - {인수조건 1}
  - {인수조건 2}
- constraints:
  - {제약사항}

#### 기술 스펙 (TRD)
- tech-spec:
  - {기술 스택}
- api-spec:
  - {API 엔드포인트, 스키마}
- data-model:
  - {엔티티, 필드, 관계}
```

### Task 속성 목록

- **기본**: category, domain, status, priority, assignee, schedule, tags, depends, blocked-by, note
- **PRD 연동**: prd-ref, requirements, acceptance, constraints, test-criteria
- **TRD 연동**: tech-spec, api-spec, data-model, ui-spec

---

## 성공 기준

- **요구사항 커버리지**: PRD 모든 기능이 Task로 분해됨
- **적정 규모**: 모든 Task가 1일~1주 범위 내
- **추적성**: 각 Task에 prd-ref 연결
- **컨텍스트 완전성**: 개발 Task는 requirements, acceptance, tech-spec 필수 포함
- **자기 완결성**: Task만 보고 개발 착수 가능한 수준
