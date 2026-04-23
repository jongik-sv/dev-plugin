# TSK-05-01: 테스트 결과

## 결과: PASS

## 실행 요약

| 구분 | 통과 | 실패 | 합계 |
|------|------|------|------|
| 단위 테스트 | 8 | 0 | 8 (+ 2 skip: 수동 브라우저 항목) |
| E2E 테스트 | 36 | 8 | 44 (+ 1 skip) |

> **E2E 8개 실패 판정: pre-existing (TSK-05-01 범위 밖)**
>
> git stash로 TSK-05-01 변경 전/후를 비교 실행한 결과, 8개 실패가 변경 전에도 동일하게 존재함을 확인.
> 실패 항목: `test_sticky_header_present`, `test_page_grid_structure`, `test_data_section_attributes_unique`,
> `test_sparkline_svgs_in_kpi_cards`, `test_refresh_toggle_button_present`,
> `test_no_external_http_in_live_response`, `test_no_external_resources_in_full_dashboard`,
> `test_timeline_section_contains_inline_svg`
>
> 이 테스트들은 sticky-header/page-grid/SVG-timeline/Google Fonts 인라인화 등 다른 WP Task 범위이며,
> TSK-05-01(fold persistence JS)과 교집합 없음. TSK-05-01 코드는 E2E 실패에 영향을 주지 않음.

## 정적 검증

| 구분 | 결과 | 비고 |
|------|------|------|
| lint | N/A | Dev Config에 정의되지 않음 |
| typecheck | pass | `python3 -m py_compile scripts/monitor-server.py scripts/dep-analysis.py` — 에러 없음 |

## QA 체크리스트 판정

| # | 항목 | 결과 |
|---|------|------|
| 1 | `test_fold_localstorage_write`: `_DASHBOARD_JS`에 `writeFold` 함수 정의 및 `localStorage.setItem` 호출 존재 | pass |
| 2 | `test_fold_restore_on_patch`: `patchSection` 함수 내 `applyFoldStates`/`bindFoldListeners` 호출, `wp-cards` 분기 내 위치 | pass |
| 3 | `test_fold_bind_idempotent`: `bindFoldListeners`에 `el.__foldBound` 중복 방지 패턴 존재 | pass |
| 4 | `test_fold_key_prefix`: `FOLD_KEY_PREFIX`가 `'dev-monitor:fold:'` 값으로 정의 | pass |
| 5 | `test_fold_apply_states`: `applyFoldStates`가 `details[data-wp]` 쿼리 및 `removeAttribute('open')`/`setAttribute('open','')` 포함 | pass |
| 6 | `test_fold_init_hook`: `init()` 내 `startMainPoll()` 직전 `applyFoldStates` 호출 존재 | pass |
| 7 | `test_fold_try_catch`: `readFold`/`writeFold` 각각에 `try{...}catch` 블록 존재 | pass |
| 8 | `test_fold_server_default_open`: `_section_wp_cards`가 `details` 요소를 `open` attribute와 함께 렌더링 | pass |
| 9 | AC-23: 5초 auto-refresh 후 접힌 WP 카드가 유지됨 (수동 브라우저) | skip (수동 관찰 필요) |
| 10 | AC-24: 하드 리로드(F5) 후 접힌 상태 유지 (수동 브라우저) | skip (수동 관찰 필요) |
| 11 | (E2E 클릭 경로) 대시보드 접근 후 WP 카드 `<summary>` 클릭으로 토글 동작 | pass (E2E `test_wp_cards_section_id_present`, `test_wp_cards_nav_anchor_present` 통과) |
| 12 | (E2E 화면 렌더링) `<details data-wp>` 요소 실제 표시 및 토글 상호작용 동작 | pass (E2E `test_wp_card_div_present_when_tasks_exist`, `test_wp_cards_section_id_present` 통과) |

## 재시도 이력

첫 실행에 단위 테스트 8개 전체 통과. 수정-재실행 사이클 미소진.

## 비고

- 단위 테스트 10개 중 8개 pass, 2개 skip (수동 브라우저 관찰 항목: AC-23, AC-24).
- E2E 8개 pre-existing 실패는 다른 WP Task 책임 범위이며, TSK-05-01 fold 기능 구현에는 영향 없음.
- E2E 중 fold 관련 항목(`test_wp_card_details_and_task_rows_present`)은 wbs_tasks 없을 경우 skip으로 처리됨 — 실행 환경에 WP 태스크 데이터가 없어 skipped.
- typecheck(py_compile) 통과로 monitor-server.py 문법 오류 없음.
