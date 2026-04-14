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

> **타이브레이커 (양방향)**:
> - **2개 이상의 기준이 대규모에 해당** → 4단계 선택
> - **2개 이상의 기준이 중소규모에 해당** → 3단계 선택
> - **2:2로 갈리는 경우에만** 큰 규모(4단계)를 선택한다. 4단계에서 불필요한 Activity 레벨은 제거하기 쉽지만, 3단계에서 누락된 Activity를 나중에 추가하는 것은 재작업이 크기 때문.

### ID 패턴

| 레벨 | 4단계 | 3단계 |
|------|-------|-------|
| WP | `## WP-XX:` | `## WP-XX:` |
| ACT | `### ACT-XX-XX:` | — |
| TSK | `#### TSK-XX-XX-XX:` | `### TSK-XX-XX:` |

- `WP-00`은 프로젝트 초기화용으로 예약

### Task category

`development` / `defect` / `infrastructure` 세 가지 모두 동일 DDTR 워크플로우(`[ ]`→`[dd]`→`[im]`→`[ts]`→`[xx]`)를 따른다. 상태 전이와 실패 처리 규칙은 `${CLAUDE_PLUGIN_ROOT}/references/state-machine.json`에 정의되어 있다.

**부가 Task(seed data / test fixture / API 키 설정 등) 분류 규칙 — 공유 범위 기반**:

| 부가 Task 종류 | 공유 범위 | category | domain | 배치 |
|----------------|-----------|----------|--------|------|
| 시드 데이터 (초기 관리자 계정, 샘플 상품 등) | 여러 기능에서 재사용 | `infrastructure` | `database` | WP-00 선행 Task |
| 시드 데이터 | 1개 feature 전용 (예: 로그인 데모용 계정) | 해당 feature와 동일 (`development`) | 해당 feature의 domain | 해당 feature Task에 흡수 |
| 테스트 Fixture / Factory | 프로젝트 전반 | `infrastructure` | `test` | WP-00 또는 별도 Task |
| 테스트 Fixture | 1개 feature 전용 | 해당 feature와 동일 | 해당 feature의 domain | 해당 feature Task에 흡수 |
| 외부 API 키·시크릿 등록 절차 | 프로젝트 전반 (CI/CD, prod env 모두 적용) | `infrastructure` | `infra` | WP-00 선행 Task (`depends`로 연결) |
| 외부 API 클라이언트 래퍼 | 단일 도메인 사용 | `development` | 해당 domain | 해당 기능 Task에 포함 |

판단 기준은 "이 Task가 누락돼도 다른 모든 feature가 정상 동작하는가?". 한 feature만 영향 받으면 흡수, 둘 이상이면 선행 분리.

### Task domain

PRD/TRD를 분석하여 프로젝트에 맞는 domain을 자유롭게 정의한다 (예: `frontend`, `backend`, `infra`, `ml-pipeline`, `etl`, `fullstack`). domain 이름은 제약 없음.

**category × domain × model 권장 조합 (F12 — 비일관 조합 방지)**:

| category | 일반적 domain | 일반적 model |
|----------|---------------|--------------|
| `development` | `frontend` / `backend` / `fullstack` (+프로젝트 고유) | fullstack이나 다중 시스템 교차면 `opus`, 그 외 `sonnet` |
| `defect` | 결함이 위치한 domain 그대로 | 원인 분석에 따라 `opus`(근본 수정) 또는 `sonnet`(국소 수정) |
| `infrastructure` | `infra` / `database` / `test` | 대부분 `sonnet` (마이그레이션·보안 설계가 섞이면 `opus`) |

위는 **권장** 매핑이다. 강제 규칙은 아니지만, 이 표에서 벗어난 조합(예: `category: infrastructure` + `domain: frontend`)은 WBS 재검토 대상이다.

### Dev Config 생성

WBS 생성 시 `## Dev Config` 섹션을 **정확히 한 번** 삽입한다.

**삽입 위치 (강제)**: 최상단 메타데이터 블록(`# WBS - {프로젝트명}`과 그 아래 `> version:`/`> depth:`/`> start-date:` 등 `>` 인용 라인들) 다음의 `---` 구분선 바로 아래, 그리고 **첫 번째 `## WP-` 헤더 앞**. WP 내부에 중첩하거나 다른 `##` 섹션 뒤로 옮기면 `wbs-parse.py --dev-config` 파서가 잘못된 블록을 읽을 수 있다. 파서는 `^##\s+Dev\s+Config\s*$` 패턴으로 섹션을 탐지하고 다음 `## ` 헤더까지를 섹션 본문으로 간주한다.

섹션 골격과 각 항목의 의미(`domain`/`unit-test`/`e2e-test`/`Design Guidance`/`Quality Commands`/`Cleanup Processes`, `-` 표기, `fullstack` 정책)는 `${CLAUDE_PLUGIN_ROOT}/skills/wbs/references/dev-config-template.md` 단일 소스를 참조한다. 템플릿을 Read하여 복사한 뒤, TRD의 기술 스택 정보로 명령과 아키텍처 설명을 채우고 추론할 수 없는 값은 사용자에게 확인한다.

---

## 실행 플로우

### 0.5단계: VIEW_MODE 분기

`VIEW_MODE=true`(절대 경로로 기존 wbs.md를 지정한 경우):
1. 해당 파일의 **전체 내용**을 사용자에게 표시한다. 여기서 "전체"란 YAML/헤더 메타데이터, `## Dev Config` 섹션, 모든 `## WP-XX` 블록, Activity·Task 전부를 포함한다 (어떤 섹션도 축약·생략하지 않는다).
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

### 4단계: Task 분해 및 category/domain/model 분류

**0단계 — 공유 엔티티 사전 분석 (필수, Task 분해 전에 수행)**:

기능을 Task로 쪼개기 **전에** PRD/TRD의 data-model 섹션을 훑어 "어떤 테이블/엔티티가 2개 이상 feature에서 참조되는가"를 먼저 식별한다. 이 판정을 Task 분해 중에 하면 같은 엔티티가 fullstack 흡수와 독립 database Task에 동시에 들어가는 충돌이 발생한다.

| 엔티티 공유 상태 | 배치 |
|------------------|------|
| **2개 이상 feature가 참조** (예: `users`가 로그인·프로필·관리자 3곳에서 사용) | WP-00 또는 별도 `infra`/`database` Task로 선행 등록. 이후 모든 feature Task는 이 선행 Task를 `depends`로 연결한다. |
| **1개 feature 전용** (예: `orders`가 주문 플로우에서만 사용) | 해당 feature Task에 마이그레이션·스키마 변경 포함 (수직 슬라이스) |

Task 분해 표의 "공유 DB/인프라" 행은 이 사전 분석 결과를 그대로 반영한다. 충돌 판정 이후에 아래 표를 적용하라.

**Task 분해 원칙 — UI 동반 시 fullstack 묶음 (필수)**:

기능을 Task로 쪼갤 때 UI 화면 유무를 먼저 확인한다.

| 기능 특성 | 분해 방식 | domain | 진입점 요구 |
|----------|----------|--------|-------------|
| 사용자 화면이 있는 기능 (로그인 폼, 대시보드, 설정 페이지 등) | 해당 화면 + 연관 백엔드 API/로직 + 전용 DB 변경을 **하나의 Task로 묶어서** 할당 | `fullstack` | **필수** — `entry-point` 필드에 메뉴/사이드바/라우트 중 최소 1개를 기입한다. 예: `- entry-point: /settings/profile (사이드바 > 설정 > 프로필)` |
| 화면이 없는 순수 백엔드 기능 (크론잡, 내부 API, 이벤트 컨슈머 등) + 해당 기능 전용 DB 변경 | 백엔드만 단독 할당 (전용 스키마/마이그레이션 포함) | `backend` | 불요 (`- entry-point: -`) |
| 화면이 없는 순수 프론트엔드 기능 (정적 페이지, 공통 UI 컴포넌트 라이브러리, 디자인 시스템 등) | 프론트만 단독 할당 | `frontend` | **필수** — 라우트가 있는 페이지는 `entry-point`에 진입 경로 기입. 공통 컴포넌트 라이브러리처럼 페이지가 아니면 `- entry-point: library` 처럼 비-페이지 표식을 남긴다. |
| **여러 기능이 공유**하는 DB/인프라 초기 세팅, cross-cutting 미들웨어 (base 스키마, docker-compose, CI, 인증/로깅 미들웨어, 레이트 리밋 등) | 독립 Task로 선행 (WP-00 또는 별도 TSK), feature Task들이 `depends`로 연결 | `infra` / `database` | 불요 (`- entry-point: -`) |

> **왜 entry-point를 강제하나**: 화면을 구현했는데 메뉴·라우터 연결을 빠뜨려도 E2E 테스트가 `page.goto('/new-page')`로 URL 직접 진입하면 통과해버린다. 결과적으로 실서비스에는 도달 수단이 없는 orphan page가 배포된다. Task 속성에 진입점을 강제하면 설계·빌드·테스트 체인 전체가 이 정보를 공유한다(`dev-design/template.md`의 "진입점" 섹션, `dev-build`의 TDD Step 0, `dev-test`의 reachability gate로 이어짐).

**DB/인프라 판정 기준 — "공유성(shared-ness)"**:

DB 스키마 변경이나 인프라 세팅을 독립 Task로 뽑을지 feature Task에 흡수할지는 **공유 범위**로 판단한다.

| 공유 범위 | 처리 |
|----------|------|
| **2개 이상 feature가 공유** | 독립 Task로 선행 — 병렬 분배 시 `depends`로 연결 |
| **1개 feature 전용** (예: 로그인의 `users` 테이블, 주문의 `orders` 테이블) | 해당 feature Task에 흡수 — 수직 슬라이스 원칙 |

**Why:**
- feature 전용 DB 변경을 분리하면 스키마-API-UI 계약이 3개 Task에 흩어져 수정·테스트가 맞물려 실패 (화면/API 분리와 동일한 문제)
- 반대로 공유 인프라를 1개 feature Task에 묻으면 다른 feature들이 그 Task를 기다려야 해서 병렬성 손실

**예시**:
- `users` 테이블 생성이 로그인에서만 쓰이면 → 로그인 fullstack Task에 마이그레이션 포함
- `users` 테이블이 로그인·프로필·관리자 페이지에서 모두 쓰이면 → 독립 `database` Task로 선행

**금지 패턴** — "로그인 API"와 "로그인 화면"을 별도 Task(`backend` + `frontend`)로 분리하지 않는다. 화면과 백엔드를 **한 Task 안에서 함께 추가하고 함께 테스트**해야 수정이 쉽다. layer 분리 시 발생하는 문제:
- 화면-API 계약이 두 Task에 걸쳐 분산되어 한쪽만 수정하면 다른 쪽과 어긋난다
- 테스트/리팩토링 단계에서 서로 맞물려 실패한다
- 병렬 할당 시 의존성이 꼬인다
- 기능 전체를 한 번에 검증(E2E)할 수 없다

화면이 포함된 사용자 기능은 **end-to-end로 완결되는 하나의 `fullstack` Task**로 묶는 것이 원칙이다.

**예외** — 동일 화면이 매우 큰 경우(최대 1주 초과), 화면+API를 함께 담은 채로 기능 슬라이스(예: 로그인 기본 플로우 / 2FA 확장)로 **수직 분할**하라. 수평 분할(layer 분할: UI/API/DB)은 금지.

**Task 크기 검증**:
- 최소: 4시간 / 권장: 1~3일 / 최대: 1주 (초과 시 수직 분할)

**Design 모델 판정 (`model` 필드)**:

각 Task의 설계 복잡도를 PRD/TRD 맥락을 종합하여 판정하고 `- model: opus` 또는 `- model: sonnet`을 기입한다. 이 필드가 있으면 자동 점수 판정을 건너뛴다. 생략하면 런타임에 키워드·의존성 기반 fallback 점수로 결정된다.

| 모델 | 기준 | 예시 |
|------|------|------|
| `opus` | 다중 시스템 교차, 아키텍처 결정, 상태머신, 보안 핵심, 미들웨어 체인 등 설계 판단이 복잡한 Task | FSM 설계, RBAC 미들웨어, WebSocket 게이트웨이, 보안 훅 |
| `sonnet` | 단일 도메인 CRUD, 표준 UI 컴포넌트, 인프라 세팅, 테스트, 문서 등 설계 패턴이 명확한 Task | tRPC 라우터, 폼 화면, Docker 구성, E2E 시나리오 |

판정 시 고려할 신호:
- 의존성 4개 이상 → 다중 시스템 교차 가능성 높음
- fullstack 도메인 → 프론트+백엔드 양쪽 설계 필요
- 보안/인증/권한 핵심 로직 → 설계 실수 비용이 높음
- 표준 패턴으로 해결 가능 여부 → 가능하면 sonnet

**자동 점수 체계 (fallback — `model` 필드 생략 시)**:

`wbs-parse.py --complexity`가 계산한다. 구현 기준은 `scripts/wbs-parse.py`의 `compute_complexity()`. 아래 표가 LLM이 자신의 Task가 어떤 모델로 분류될지 예측하기 위한 근거다.

| 신호 | 가중치 | 설명 |
|------|-------|------|
| `depends` 개수 ≥ 4 | **+2** | 다중 시스템 교차 |
| `depends` 개수 2–3 | **+1** | 통합 포인트 존재 |
| `domain: fullstack` | **+2** | 프론트+백엔드 양쪽 설계 |
| `domain: frontend` | **+1** | UI 설계 복잡도 |
| `domain: docs` / `test` | **−1** | 단순 작업 |
| 키워드 매치 (아키텍처/마이그레이션/인프라/통합/리팩토링/미들웨어/트랜잭션/동시성/상태머신/인증체계/architecture/migration/infrastructure/integration/refactor/middleware/transaction/concurrency/websocket/fsm/oauth/rbac) — Task 설명·requirements·acceptance·tech-spec 본문에서 검색 (메타데이터 줄 제외) | **+2** | 설계 판단이 복잡한 시그널 |
| `category: config` / `docs` / `documentation` | **−1** | 설계 경량 카테고리 |

- **Threshold**: `점수 ≥ 3` → `opus`, 그 외 `sonnet`. 점수는 0 미만으로 내려가지 않는다 (`max(score, 0)`).
- `- model: opus` 또는 `- model: sonnet`이 **명시되어 있으면 점수 계산을 생략**하고 그 값을 그대로 사용한다. LLM이 맥락을 가장 잘 반영하므로 WBS 생성 시 가능한 한 명시한다.
- Build/Refactor는 항상 Sonnet, Test는 Haiku (필요 시 Sonnet 에스컬레이션)로 고정. `model` 필드는 Design Phase에만 영향.

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
- schedule: {시작일} ~ {종료일}
- description: {선택 — 이 WP가 다루는 범위 1줄 요약}

> WP 레벨에는 `status`/`priority`/`progress`를 **쓰지 않는다**. WP의 진행도는 하위 Task 상태(`[ ]`/`[dd]`/`[im]`/`[ts]`/`[xx]`)의 집계로 계산되며, 별도 필드로 유지하면 Task 상태와 drift가 발생한다. 우선순위는 Task 레벨에서만 관리한다.

### TSK-00-01: {Task명}
- category: infrastructure
- domain: infra
- model: sonnet
- status: [ ]
- priority: critical
- assignee: -
- schedule: {시작일} ~ {종료일}
- tags: setup, init
- depends: -

---

## WP-01: {Work Package명}
- schedule: {시작일} ~ {종료일}
- description: {선택 — 이 WP가 다루는 범위 1줄 요약}

### TSK-01-01: {Task명}
- category: development
- domain: fullstack
- model: {opus 또는 sonnet}
- status: [ ]
- priority: high
- assignee: -
- schedule: {시작일} ~ {종료일}
- tags: {관련 태그}
- depends: -
- blocked-by: -
- entry-point: {메뉴/사이드바/라우트 — fullstack·frontend 필수, backend는 '-'}
- note: -

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
- test-criteria:
  - {검증 기준 (선택)}

#### 기술 스펙 (TRD)
- tech-spec:
  - {기술 스택}
- api-spec:
  - {API 엔드포인트, 스키마}
- data-model:
  - {엔티티, 필드, 관계}
- ui-spec:
  - {UI 구성 요소 (fullstack/frontend 한정)}
```

### Task 속성 목록

| 구분 | 필드 | 포맷 |
|------|------|------|
| **단일행 스칼라** | category, domain, model, status, priority, assignee, schedule, tags, depends, blocked-by, note, entry-point, prd-ref | `- field: value` |
| **리스트** (CSV 또는 bullet) | requirements, acceptance, constraints, test-criteria, tech-spec, api-spec, data-model, ui-spec | `- field: v1, v2` 또는 다음 줄에 `  - item` |

- **리스트 필드 파싱 규칙** (`wbs-parse.py parse_list_field`):
  - `- field: -` → 빈 리스트
  - `- field: a, b, c` → 인라인 CSV, `["a", "b", "c"]`
  - `- field:` + 다음 줄의 `  - item` 라인들 → bullet 리스트 (다음 `- name:` 필드나 빈 줄에서 종료)
- **단일행 필드**는 값에 콤마가 있어도 분할하지 않는다(`get_field`). 리스트 성격 값은 반드시 리스트 필드로 선언하라.
- JSON 출력의 키는 하이픈이 언더스코어로 치환된다 (`blocked-by` → `blocked_by`, `entry-point` → `entry_point`).
- `entry-point`는 domain이 `fullstack` 또는 `frontend`인 Task에서 **필수**. 자세한 요구는 "분해 원칙" 표와 "성공 기준" 참조.

---

## 성공 기준

- **요구사항 커버리지**: PRD 모든 기능이 Task로 분해됨
- **적정 규모**: 모든 Task가 1일~1주 범위 내
- **추적성**: 각 Task에 prd-ref 연결
- **컨텍스트 완전성**: 개발 Task는 requirements, acceptance, tech-spec 필수 포함
- **자기 완결성**: Task만 보고 개발 착수 가능한 수준
- **UI 접근성 (reachability)**: `domain`이 `fullstack`/`frontend`인 Task는 `entry-point` 필드가 **반드시** 채워져 있어야 한다 (비-페이지 UI는 `library` 등 명시적 표식). 누락 시 orphan page 리스크로 간주하여 WBS 재감수. 이 기준은 dev-design/dev-build/dev-test 체인 전반에서 검증된다.
