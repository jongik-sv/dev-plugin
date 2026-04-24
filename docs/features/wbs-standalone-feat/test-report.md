# wbs-standalone-feat: 테스트 결과

## 결과: PASS

## 실행 요약

| 구분 | 통과 | 실패 | 합계 |
|------|------|------|------|
| 단위 테스트 | 32 | 0 | 32 |
| E2E 테스트 | 0 | 0 | 0 |

## 정적 검증 (Dev Config에 정의된 경우만)

| 구분 | 결과 | 비고 |
|------|------|------|
| lint | N/A | Backend domain — no frontend linting |
| typecheck | N/A | Python scripts, no TypeScript |

## QA 체크리스트 판정

| # | 항목 | 결과 |
|---|------|------|
| 1 | `--tasks-pending`이 `category: feat` Task를 반환하지 않는다 | pass |
| 2 | `--tasks-all`이 `category: feat` Task를 포함하여 반환하고, JSON에 `category` 필드가 있다 | pass |
| 3 | `--feat-tasks {WP-ID}` 모드가 해당 WP 내 `category: feat` Task만 반환한다 | pass |
| 4 | `category: feat`가 없는 기존 wbs.md에서 `--tasks-pending`이 종전과 동일하게 동작한다 | pass |
| 5 | `category: feat` Task가 completed 집합에 포함되어 의존 계산에서 제외된다 | pass |
| 6 | `category: feat` Task를 depends로 지정한 Task가 Level 0으로 분류된다 | pass |
| 7 | `category` 필드가 없는 기존 입력에서 동작이 변경되지 않는다 | pass |

## 재시도 이력

첫 실행에 통과 (32/32 tests passed)

## 비고

**테스트 대상**:
- Build Phase에서 작성된 `scripts/test_feat_category.py` 실행 완료 (32개 테스트)
- 기존 테스트 회귀 확인: `scripts.test_dep_analysis_critical_path` (25 tests) 및 `scripts.test_merge_state_json`, `scripts.test_merge_wbs_status`, `scripts.test_platform_smoke` 등 모두 통과

**테스트 범위**:
- `TestParseTasksFromWpCategory`: `category` 필드 파싱, 기본값, `pending_only` 필터
- `TestDepAnalysisFeatCategory`: feat Task가 completed로 취급되고 의존 계산에서 제외되는지 확인
- `TestWbsParseFeattasks`: `--feat-tasks` 모드 출력 형식 (tsk_id, feat_name, title)
- `TestSlugify`: feat_name 자동 생성 (kebab-case, 40자 제한, 특수문자 처리)
- `TestWbsParseTasksAllCategory`: `--tasks-all` 에 category 필드 포함
- `TestWbsParseTasksPendingExcludesFeat`: `--tasks-pending` 에서 feat Task 제외 + 하위 호환성

**핵심 결과**:
- feat Task는 `category: feat` 필드로 자동 분류됨
- wbs-parse.py의 `--tasks-pending` 에서 feat Task 제외 (WP DDTR 대상 아님)
- dep-analysis.py에서 feat Task를 completed로 취급하여 의존 레벨에서 제외
- 기존 wbs.md(category 필드 없음)는 하위 호환성 100% 유지
- feat_name 자동 생성: Task 제목 → kebab-case (40자 이하), 실패 시 TSK-ID 기반 fallback
