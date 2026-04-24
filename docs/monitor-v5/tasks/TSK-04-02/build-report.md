# TSK-04-02: TDD 구현 결과

## 결과: PASS

## 생성/수정된 파일

| 파일 경로 | 변경 내용 | 신규/수정 |
|-----------|-----------|-----------|
| `scripts/monitor-server.py` | CSS: `#trow-tooltip` 전량 삭제 + `.info-btn`/`.info-popover`/꼬리 pseudo-element/`data-placement` 폴백 규칙 신설. Python: `_trow_tooltip_skeleton()` → `_trow_info_popover_skeleton()`(싱글톤 dialog DOM). `_render_task_row_v2()`에 `info-btn` 버튼 삽입(`.flags` 뒤, `.expand-btn` 앞). `render_dashboard()` 조립: `_trow_info_popover_skeleton()` 호출로 교체. JS: `setupTaskTooltip` IIFE 전량 삭제 → `setupInfoPopover` IIFE 신설(`positionPopover`, `renderInfoPopoverHtml`, `close`, 클릭 위임, ESC/스크롤/리사이즈 핸들러). | 수정 |
| `scripts/test_monitor_info_popover.py` | 단위 테스트 신규 — `.info-btn` DOM/ARIA, 싱글톤 팝오버 DOM, CSS 규칙, JS IIFE, 회귀 검증 (25개 케이스) | 신규 |
| `scripts/test_monitor_e2e.py` | hover 기반 E2E(`test_task_tooltip_dom_body_direct`, `test_task_tooltip_second_render_keeps_dom`, `test_task_tooltip_setupTaskTooltip_in_script`) → click 기반 마이그레이션(`test_task_popover_dom_body_direct`, `test_task_popover_second_render_keeps_dom`, `test_task_popover_setupInfoPopover_in_script`, `test_task_popover_click`, `test_task_popover_no_hover_trigger` 추가). `test_task_tooltip_trow_has_data_state_summary` 유지(data-state-summary는 팝오버 콘텐츠 재사용). | 수정 |

## 테스트 결과

| 구분 | 통과 | 실패 | 합계 |
|------|------|------|------|
| 단위 테스트 (test_monitor_info_popover.py) | 25 | 0 | 25 |
| 기존 단위 테스트 (test_monitor_task_row.py) | 47 | 0 | 47 |
| 기존 단위 테스트 (test_monitor_static.py) | 48 | 0 | 48 |
| 기존 단위 테스트 (test_render_dashboard_tsk0106.py) | 40 | 0 | 40 |
| 기존 단위 테스트 (test_monitor_api_state.py) | 68 | 0 | 68 |
| 기존 단위 테스트 (test_monitor_task_detail_api.py) | 63 | 0 | 63 |
| 기존 단위 테스트 (test_dashboard_css_tsk0101.py) | 27 | 0 | 27 |
| 기존 단위 테스트 (test_monitor_wp_cards.py) | 68 | 0 | 68 |
| 기존 단위 테스트 (test_monitor_task_spinner.py) | 21 | 0 | 21 |
| 기존 단위 테스트 (test_monitor_filter_bar.py) | 55 | 0 | 55 |
| 기존 단위 테스트 (test_font_css_variables.py) | 11 | 0 | 11 |

- 전체 scripts/ pytest: 1784 passed, 61 failed, 36 skipped — 61개 실패는 모두 pre-existing (git stash 후에도 동일 실패 확인됨), TSK-04-02 범위 외.

## E2E 테스트 (작성만 — 실행은 dev-test)

| 파일 경도 | 검증 대상 |
|-----------|-----------|
| `scripts/test_monitor_e2e.py::test_task_popover_click` | AC-FR01-a: .info-btn 버튼 + aria-expanded="false" + aria-controls 존재 / AC-FR01-b: #trow-info-popover[hidden] 초기 상태 |
| `scripts/test_monitor_e2e.py::test_task_popover_dom_body_direct` | 싱글톤 팝오버 DOM 1회 존재 (5초 폴링 격리) |
| `scripts/test_monitor_e2e.py::test_task_popover_second_render_keeps_dom` | 2회 GET 응답 모두 팝오버 DOM 유지 |
| `scripts/test_monitor_e2e.py::test_task_popover_setupInfoPopover_in_script` | AC-FR01-f: setupInfoPopover 존재 + setupTaskTooltip 부재 |
| `scripts/test_monitor_e2e.py::test_task_popover_no_hover_trigger` | AC-FR01-b: setupTaskTooltip(hover 기반) 없음 — 회귀 방지 |
| `scripts/test_monitor_info_popover.py` (전체) | DOM/CSS/JS 정적 분석 (서버 기동 불필요) |

## 커버리지

N/A — Dev Config에 coverage 명령 미정의

## 비고

- TSK-01-03(app.js 분리), TSK-02-01(renderers 패키지 분리)이 미완료 상태여서 design.md의 fallback 경로(monitor-server.py 직접 편집)를 사용했다. 모든 acceptance criteria를 동일하게 충족한다.
- `_trow_tooltip_skeleton()` 함수는 코드베이스에서 완전 삭제하고 `_trow_info_popover_skeleton()`으로 대체했다. `render_dashboard()` 호출부도 새 함수를 참조한다.
- design.md 리스크 LOW(ESC focus 복원 순서)는 `var btn=openBtn; close(); btn&&btn.focus();` 패턴으로 해소했다.
- design.md 리스크 MEDIUM(detached openBtn 5초 폴링) 완화: `close()` 진입부 `document.contains(openBtn)` 가드 추가.
- 단위 테스트에서 `test_old_tooltip_skeleton_removed`가 `_trow_tooltip_skeleton` 함수 부재(삭제됨)로 pass된다.
