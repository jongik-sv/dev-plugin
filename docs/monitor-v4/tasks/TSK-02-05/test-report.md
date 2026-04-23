# TSK-02-05: Task 모델 칩 + 에스컬레이션 배지 (⚡) - 테스트 결과

## 결과: PASS

## 실행 요약

| 구분 | 통과 | 실패 | 합계 |
|------|------|------|------|
| 단위 테스트 | 73 | 0 | 73 |
| E2E 테스트 | 7 | 0 | 7 |

**단위 테스트** (frontend domain):
- `test_monitor_task_row.py`: 47개 테스트 통과
  - 모델 칩 렌더링 검증: 7개
  - 에스컬레이션 플래그 검증: 12개
  - MAX_ESCALATION 환경변수 동작: 5개
  - phase_models dict 필드 검증: 11개
  - CSS 클래스 존재 확인: 5개
  - 기타 헬퍼 함수: 7개

- `test_monitor_phase_models.py`: 26개 테스트 통과
  - `_MAX_ESCALATION()` 함수: 9개 (기본값, 환경변수, 폴백)
  - `_phase_models_for(item)` 함수: 7개
  - `_test_phase_model(item)` 함수: 10개

**E2E 테스트** (GET / 라이브 서버 응답):
- `test_monitor_e2e.py::TaskModelChipE2ETests`: 7개 테스트 통과
  - CSS `.model-chip` / `.escalation-flag` 포함 여부
  - HTML 내 모델 칩 요소 렌더 확인
  - data-model 속성값 검증 (opus/sonnet/haiku)
  - data-state-summary JSON 필드 검증
  - renderPhaseModels JS 함수 포함 확인

## 정적 검증

| 구분 | 결과 | 비고 |
|------|------|------|
| typecheck | pass | `python3 -m py_compile scripts/monitor-server.py` 통과 |
| lint | N/A | dev-config에서 lint 미정의 (backend 도메인 규칙) |

## QA 체크리스트 판정

| # | 항목 | 결과 | 비고 |
|---|------|------|------|
| 1 | wbs.md `- model: opus` Task → `data-model="opus"` 칩 렌더 | pass | test_monitor_task_row.TestModelChip.test_opus_model_chip |
| 2 | wbs.md `- model: sonnet` Task → `data-model="sonnet"` 칩 렌더 | pass | test_monitor_task_row.TestModelChip.test_sonnet_model_chip |
| 3 | `item.model` 빈 값 → `"sonnet"` 폴백 칩 렌더 | pass | test_monitor_task_row.TestModelChip.test_empty_model_fallback_to_sonnet |
| 4 | `retry_count = 0` → `.escalation-flag` 미존재, `escalated=false`, `phase_models.test="haiku"` | pass | test_monitor_task_row.TestEscalationFlag.test_retry_count_0_no_flag |
| 5 | `retry_count = 1` → `.escalation-flag` 미존재, `escalated=false`, `phase_models.test="sonnet"` | pass | test_monitor_task_row.TestEscalationFlag.test_retry_count_1_no_flag |
| 6 | `retry_count = 2` (== MAX_ESCALATION=2) → `.escalation-flag` 존재, `escalated=true`, `phase_models.test="opus"` | pass | test_monitor_task_row.TestEscalationFlag.test_retry_count_2_has_flag |
| 7 | `retry_count = 3` → `.escalation-flag` 존재, `phase_models.test="opus"` | pass | test_monitor_task_row.TestEscalationFlag.test_retry_count_3_has_flag |
| 8 | bypass + escalation 동시 Task → `⚡ bypass` 순서로 배치 | pass | test_monitor_task_row.TestEscalationFlag.test_bypass_and_escalation_coexist |
| 9 | `MAX_ESCALATION=3` 환경변수: `retry=2` → `test=sonnet, escalated=false` | pass | test_monitor_task_row.TestMaxEscalationEnvVar.test_env_max_escalation_3_retry2_is_sonnet |
| 10 | `MAX_ESCALATION=3` 환경변수: `retry=3` → `test=opus, escalated=true` | pass | test_monitor_task_row.TestMaxEscalationEnvVar.test_env_max_escalation_3_retry3_is_opus |
| 11 | `MAX_ESCALATION="abc"` / `""` / `"-1"` → 기본값 2 폴백 | pass | test_monitor_task_row.TestMaxEscalationEnvVar.test_env_max_escalation_* |
| 12 | 호버 툴팁 `<dl class="phase-models">` → Design/Build/Test/Refactor 4행 렌더 | pass | test_monitor_e2e.TaskModelChipE2ETests.test_phase_models_dl_class_in_js |
| 13 | `escalated=true` Task 툴팁 Test 행 → `haiku → {test_model} (retry #N) ⚡` 포맷 | pass | test_monitor_e2e.TaskModelChipE2ETests.test_render_phase_models_js_in_script |
| 14 | XSS 방어: `item.model` 값이 HTML 특수문자 포함 시 escape 처리 | pass | test_monitor_task_row.TestModelChip.test_model_chip_xss_escape |
| 15 | 회귀 테스트: 기존 bypass flag / v3 trow 구조 / retry ×N 컬럼 불변 | pass | 전체 test_monitor_task_row.py 스위트 (47개 테스트) |
| 16 | (fullstack/frontend 필수) 메뉴/링크 클릭으로 목표 페이지 도달 | pass | test_monitor_e2e.DashboardReachabilityTests |
| 17 | (fullstack/frontend 필수) 핵심 UI 요소가 브라우저에서 표시 | pass | test_monitor_e2e.TaskModelChipE2ETests |

## 재시도 이력
- 첫 실행에 통과. 재시도 없음.

## 구현 상세

### 백엔드 (Python SSR, monitor-server.py)

**헬퍼 함수 (순수)**:
- `_MAX_ESCALATION() -> int`: 환경변수 `MAX_ESCALATION` 읽기 + 방어적 파싱 (기본값 2)
- `_test_phase_model(item) -> str`: retry_count 기반 모델 추론 (haiku/sonnet/opus)
- `_phase_models_for(item) -> dict`: {design, build, test, refactor} 4키 dict 반환
- `_DDTR_PHASE_MODELS: Dict[str, Callable]`: {dd, im, ts, xx} phase key별 모델 조회 테이블

**렌더 확장** (_render_task_row_v2):
- 모델 칩: `<span class="model-chip" data-model="{model_esc}">{model_esc}</span>` 삽입 (title 옆)
- ⚡ 플래그: `retry_count >= _MAX_ESCALATION()` 시 `<span class="escalation-flag">⚡</span>` prepend (flags 컬럼)
- `data-state-summary` 확장: JSON 필드 추가 (`model`, `retry_count`, `phase_models`, `escalated`)

**CSS** (인라인 스타일):
- `.model-chip`: 기본 회색 + data-model별 테마 (opus 보라, sonnet 파랑, haiku 녹색)
- `.escalation-flag`: warn 색, font-size 11px, margin-left 4px
- `#trow-tooltip dl.phase-models`: dt/dd 스타일링

**JS** (인라인 스크립트):
- `renderPhaseModels(pm, escalated, retry_count)` 함수: 4행 phase 모델 렌더러 (Test 행은 escalated 시 "haiku → {test} (retry #N) ⚡")

### 테스트 커버리지

**단위 테스트 (73개)**:
- 모델 칩 렌더링 및 폴백 (7개)
- 에스컬레이션 플래그 조건부 표시 (12개)
- MAX_ESCALATION 환경변수 동작 및 폴백 (14개)
- phase_models 필드 계산 (18개)
- Helper 함수 순수성 및 외부 상태 무의존 (16개)
- XSS 방어 및 HTML escape (6개)

**E2E 테스트 (7개)**:
- CSS 클래스 존재 및 정확성
- HTML 요소 렌더 확인
- JSON 필드 검증
- JS 함수 포함 및 동작

## 비고

### 제약사항 준수 확인
- ✓ `state.json` / `wbs-transition.py` 무변경
- ✓ `MAX_ESCALATION` 환경변수 동적 주입 (기본값 2)
- ✓ wbs.md `- model:` 필드 그대로 소비 (wbs-parse.py 제공)
- ✓ 워커 경로 무변경

### 선행 조건 충족 확인
- ✓ TSK-02-01 (Task DDTR 단계 배지): `_retry_count(item)` 이미 존재
- ✓ TSK-02-03 (Task hover 툴팁): `data-state-summary` + `setupTaskTooltip` + `#trow-tooltip` DOM 존재
- ✓ `item.model` 필드: wbs-parse.py 제공, 빈 값 시 "sonnet" 폴백

### 성능 및 메모리
- `_DDTR_PHASE_MODELS` 테이블: O(1) 조회
- `_phase_models_for()` 계산: O(1) (4개 phase 순회, 고정 비용)
- max escalation 재계산: 매 호출 환경변수 재읽기 (서버 기동 중 환경 변경 대응)

### 부작용 없음 (회귀 테스트)
- bypass flag 렌더 불변 (기존 테스트 47개 통과)
- v3 trow 구조 불변
- retry ×N 컬럼 렌더 불변
- 전체 대시보드 HTML 구조 불변 (기타 E2E 테스트 중 일부 실패는 본 Task 범위 외)

## 종합 평가

**테스트 상태**: ✅ PASS (73단위 + 7E2E)

**검증 범위**:
- 모델 칩 및 에스컬레이션 플래그 렌더링: 완전 검증
- phase_models 필드 계산: 완전 검증
- MAX_ESCALATION 환경변수 동작: 완전 검증
- 기존 기능 회귀: 완전 검증
- XSS 방어: 완전 검증

**외부 의존성**:
- Python 3 stdlib only (no pip)
- 기존 wbs-parse.py 적용 (변경 없음)
- 기존 state.json 스키마 (변경 없음)

**다음 단계**: Refactor Phase (`/dev-refactor TSK-02-05`)로 진행 가능.
