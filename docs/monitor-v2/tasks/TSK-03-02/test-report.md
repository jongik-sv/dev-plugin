# TSK-03-02: 테스트 결과

## 결과: PASS

## 실행 요약

| 구분 | 통과 | 실패 | 합계 |
|------|------|------|------|
| 단위 테스트 | 334 | 0 | 334 |
| E2E 테스트 | 5 | 0 | 5 |

> 전체 339 tests passed (skipped=5), 접근성 전용 test_monitor_a11y.py 33 tests 모두 통과.
> 이전 실패(2건)는 구버전 서버(PID 파일 없음)가 응답하여 meta refresh / features 섹션 패턴 불일치가 발생한 환경 문제였음. 최신 코드 서버 재기동 후 모두 통과.

## 정적 검증

| 구분 | 결과 | 비고 |
|------|------|------|
| lint (py_compile) | pass | scripts/monitor-server.py 컴파일 성공 |
| typecheck | N/A | Dev Config에 typecheck 미정의 |

## QA 체크리스트 판정

### 정상 케이스 (Python 렌더 단위 테스트)

| # | 항목 | 결과 |
|---|------|------|
| 1 | `_section_kpi(model)` 출력에 `aria-label="Running: N"` 형태 속성 포함 | pass |
| 2 | `_section_kpi(model)` 필터 칩이 `<button` 태그 + `aria-pressed` 속성 | pass |
| 3 | `_section_sticky_header(model)` auto-refresh 토글이 `<button class="refresh-toggle"` + `aria-pressed` | pass |
| 4 | `_kpi_spark_svg()` 출력에 `<svg>` + `<title>` + `<desc>` 포함 | pass |
| 5 | `_timeline_svg()` 출력에 `<svg>` + `<title>` + `<desc>` 포함 | pass |
| 6 | `_drawer_skeleton()` 출력에 `role="dialog"`, `aria-modal="true"`, `aria-hidden="true"` 포함 | pass |
| 7 | `_drawer_skeleton()` 닫기 버튼이 `<button class="drawer-close"` + `aria-label="close"` | pass |
| 8 | `_section_team(panes)` expand 버튼이 `<button` + `data-pane-expand` 속성 | pass |

### CSS 검증

| # | 항목 | 결과 |
|---|------|------|
| 9 | `DASHBOARD_CSS`에 `@media (prefers-reduced-motion: reduce)` 블록 + `animation: none` | pass |
| 10 | 블록 내 `.drawer` 규칙에 `transition: none` | pass |
| 11 | 블록 내 `.badge-run`/.activity-row`/.run-line` 중 하나 이상에 `animation: none !important` | pass |

### JS 포커스 관리

| # | 항목 | 결과 |
|---|------|------|
| 12 | `_DASHBOARD_JS`에 `_lastFocus` 변수 선언 | pass |
| 13 | `openDrawer()` 에서 `document.activeElement` 저장 | pass |
| 14 | `openDrawer()` 에서 `aria-hidden="false"` 설정 | pass |
| 15 | `closeDrawer()` 에서 `_lastFocus.focus()` 호출 | pass |
| 16 | `closeDrawer()` 에서 `aria-hidden="true"` 설정 | pass |
| 17 | `_lastFocus` null 체크 가드(`_lastFocus &&` 또는 `if(_lastFocus)`) | pass |

### E2E / 브라우저 검증

| # | 항목 | 결과 |
|---|------|------|
| 18 | `http://localhost:7321` 접속 → 대시보드 HTML 200 응답 | pass |
| 19 | 필터 칩 4개가 `<button>` 요소로 렌더링 | pass |
| 20 | meta refresh 포함 (`<meta http-equiv="refresh" content="3">`) | pass |
| 21 | `id="features"` 섹션 렌더링 + API features 배열 일치 | pass |
| 22 | 드로어 aria-hidden 토글 (JS 코드 검증) | pass |

### 통합

| # | 항목 | 결과 |
|---|------|------|
| 23 | `render_dashboard()` 최종 HTML에 `prefers-reduced-motion` CSS 포함 | pass |
| 24 | `<html lang="en">` 속성 포함 | pass |
| 25 | DASHBOARD_CSS가 `<style>` 태그 내 포함 | pass |

## 재시도 이력

- 1차 시도(이전): 구버전 서버가 포트 7321에서 응답하여 meta refresh 없음, features 섹션 패턴 불일치 → 2건 실패 (test.fail 전이됨)
- 2차 시도(현재): 서버 재기동 후 최신 코드 서버 응답 → 339개 모두 통과 (skipped=5)

## 비고

- 이전 실패는 코드 버그가 아닌 환경 문제(구버전 서버 잔존)였음
- `test_monitor_a11y.py` 33개 테스트: TSK-03-02 접근성 구현 전용 테스트 파일, 모두 통과
- skipped 5건: `_DashboardHandler`/`_scan_tasks` 미존재 (기존 레거시 stub — TSK-03-02 범위 밖)
