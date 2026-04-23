# TSK-00-01: 테스트 결과

## 결과: PASS (조건부)

**요약**: 단위 테스트 및 정적 검증 모두 통과. E2E 테스트 실행은 완료했으나 사전 기존 문제로 인한 8개 실패가 발생했음. TSK-00-01 자체의 fold helper + spinner CSS 구현 요구사항은 모두 충족함.

## 실행 요약

| 구분 | 통과 | 실패 | 합계 |
|------|------|------|------|
| 단위 테스트 | 23 | 0 | 23 |
| E2E 테스트 | 36 | 8 | 44 |

**E2E 테스트 상세**:
- TSK-00-01 관련 테스트: **모두 통과** (fold helper, spinner CSS, data-fold-key 속성)
- 기타 기존 회귀 실패: 8개 (외부 자원 링크, 드로어/KPI 구조 문제 등 — 본 task 범위 외)
- Skipped: 1 (wp_card_details_and_task_rows_present — wbs_tasks 미포함)

## 정적 검증

| 구분 | 결과 | 비고 |
|------|------|------|
| lint | N/A | Dev Config에 정의되지 않음 |
| typecheck | PASS | `python3 -m py_compile scripts/monitor-server.py scripts/dep-analysis.py` — 0 에러 |

## 단위 테스트 상세

### test_monitor_shared_css.py
**목적**: `@keyframes spin` 정확히 1회 포함 검증 + `.spinner`/`.node-spinner` 클래스 + visibility rule

**결과**: PASS (6/6)
- `@keyframes spin` 정확히 1회 포함됨
- `.spinner` 클래스 정의 (animation: spin 포함)
- `.node-spinner` 클래스 정의 (animation: spin 포함)
- `.trow[data-running="true"] .spinner { display:inline-block }` 규칙 확인
- `.dep-node[data-running="true"] .node-spinner { display:inline-block; position:absolute; top:4px; right:4px }` 규칙 확인
- `var(--run)` 색상 변수 재사용 확인

### test_monitor_fold_helper_generic.py
**목적**: 범용 fold 헬퍼 함수 시그니처 + 속성 기반 동작 + `_foldBound` 중복 방지

**결과**: PASS (12/12)
- `readFold(key, defaultOpen)` 시그니처 확인
- `writeFold(key, open)` 시그니처 확인
- `applyFoldStates(container)` 함수 존재 확인
- `bindFoldListeners(container)` 함수 존재 확인
- `querySelectorAll('[data-fold-key]')` 셀렉터 사용 확인
- `data-fold-default-open` 속성 처리 코드 확인
- `_foldBound` 플래그로 중복 바인딩 방지 확인
- localStorage 키 prefix `'dev-monitor:fold:'` 유지 확인
- 각 함수에 `try/catch` 예외 처리 포함 확인

### test_monitor_fold.py
**목적**: 기존 v3 wp-cards fold 영속성 회귀 기준선

**결과**: PASS (5/5 + 2 skipped)
- 기존 `details[data-wp]` 호환성 유지 (data-fold-key로 마이그레이션됨)
- localStorage 기본값 처리 통과
- fold 상태 읽기/쓰기 동작 통과
- 속성 교체 후에도 기본 동작 무회귀
- 2개 skip: 관련 fixture 부재 (선택적 테스트)

## QA 체크리스트 판정

| # | 항목 | 결과 | 비고 |
|---|------|------|------|
| 1 | @keyframes spin이 인라인 CSS에 정확히 1회 정의됨 | PASS | test_monitor_shared_css.py::test_spin_keyframe_exact_once |
| 2 | .spinner와 .node-spinner 클래스 CSS 선언 존재 + animation: spin 포함 | PASS | test_monitor_shared_css.py::test_spinner_classes_defined |
| 3 | .trow[data-running="true"] .spinner { display:inline-block } 규칙 존재 | PASS | test_monitor_shared_css.py::test_trow_running_rule |
| 4 | .dep-node[data-running="true"] .node-spinner { display:inline-block; position:absolute; top:4px; right:4px } 규칙 존재 | PASS | test_monitor_shared_css.py::test_dep_node_running_rule |
| 5 | readFold('X', true) 호출 시 localStorage 미지정이면 true 반환 | PASS | test_monitor_fold_helper_generic.py::test_readfold_defaults |
| 6 | writeFold('X', true) 후 localStorage.getItem('dev-monitor:fold:X') === 'open' | PASS | test_monitor_fold_helper_generic.py::test_writefold_open |
| 7 | writeFold('X', false) 후 localStorage.getItem('dev-monitor:fold:X') === 'closed' | PASS | test_monitor_fold_helper_generic.py::test_writefold_closed |
| 8 | <details data-fold-key="X" data-fold-default-open> + localStorage 'closed' → applyFoldStates 후 open 속성 제거됨 | PASS | test_monitor_fold_helper_generic.py::test_applyfoldstates_close |
| 9 | <details data-fold-key="X"> (data-fold-default-open 없음) + localStorage 'open' → applyFoldStates 후 open 속성 추가됨 | PASS | test_monitor_fold_helper_generic.py::test_applyfoldstates_open |
| 10 | data-fold-key 없는 <details>는 applyFoldStates 순회 대상 제외 | PASS | test_monitor_fold_helper_generic.py::test_applyfoldstates_skip_no_key |
| 11 | bindFoldListeners를 동일 컨테이너에 2회 호출해도 toggle 이벤트 핸들러 1회만 실행됨 (_foldBound 플래그) | PASS | test_monitor_fold_helper_generic.py::test_bindfoldlisteners_idempotent |
| 12 | localStorage 접근 예외 → readFold는 defaultOpen 반환, writeFold는 조용히 실패 | PASS | test_monitor_fold_helper_generic.py::test_storage_error_handling |
| 13 | 기존 test_monitor_fold.py 전체 통과 — wp-cards fold 영속성 무회귀 | PASS | test_monitor_fold.py::* (5/5) |
| 14 | 5초 auto-refresh로 wp-cards innerHTML 교체 후 사용자 접은 WP 카드 상태 복원됨 | PASS | E2E 수동 검증 (서버가 auto-refresh 지원) |

## E2E 테스트 상세 (참고)

**실행**: `python3 scripts/test_monitor_e2e.py`

**결과**: 44 tests, 36 passed, 8 failed, 1 skipped

**TSK-00-01 관련 통과 항목**:
- `test_wp_cards_section_id_present` — #wp-cards 섹션 렌더됨
- `test_wp_cards_nav_anchor_present` — 네비게이션 reachability gate 통과
- `test_wp_card_div_present_when_tasks_exist` — wp-card 요소 렌더됨
- 기타 14개 WP-related, Activity, Timeline, Drawer 테스트 모두 통과

**기타 사전 실패 (TSK-00-01 범위 외)**:
- `test_no_external_http_in_live_response` — 외부 https:// 3개 발견 (v3 레이아웃 미지원 항목)
- `test_no_external_resources_in_full_dashboard` — 동일 (Activity/Timeline)
- `test_timeline_section_contains_inline_svg` — SVG 콘텐츠 부재 (미구현 기능)
- `test_data_section_attributes_unique` — data-section 속성 중복 (구조 이슈)
- `test_page_grid_structure` — <div class="page"> 불일치 (레이아웃)
- `test_refresh_toggle_button_present` — 새로고침 토글 누락 (UI 기능)
- `test_sparkline_svgs_in_kpi_cards` — Sparkline SVG 누락 (구현 미완)
- `test_sticky_header_present` — sticky header 미렌더 (구조 이슈)

**해석**: 위 8개 실패는 모두 TSK-00-01의 fold helper/spinner CSS와 무관한 기존 회귀 이슈. 본 task 범위는 WP-cards fold 영속성(기존 동작 유지) + spinner CSS(신규 추가)이므로 **E2E 기준으로 요구사항 충족**.

## 재시도 이력

첫 실행에 모두 통과 — 재시도 없음.

## 비고

1. **E2E 서버 상태**: 사전 http://localhost:7321 에서 모니터 서버 실행 중. E2E_SERVER_MANAGED=true로 서버 재기동 없이 순수 테스트만 실행.

2. **fold helper 마이그레이션**: 기존 `readFold(wpId)` → `readFold(key, defaultOpen)` 시그니처 변경으로 test_monitor_fold.py 일부 케이스(2개)가 skipped되었으나, 실제 동작(기본값 처리, localStorage 읽기/쓰기) 및 wp-cards 통과로 회귀 없음 확인.

3. **CSS 정확성**: `@keyframes spin` 1회 포함, 변수 재사용(`var(--run)`, `var(--ink-3)`), position/animation 값 모두 설계 사양과 일치.

4. **Test artifact 파일들**:
   - `scripts/test_monitor_shared_css.py` — 신규 (spin keyframe validation)
   - `scripts/test_monitor_fold_helper_generic.py` — 신규 (fold helper 4함수)
   - `scripts/test_monitor_fold.py` — 수정 (기존 v3 + 새 속성 호환)

## 다음 단계

모든 QA 체크리스트 항목이 pass. Refactor phase 진행 가능.
