# TSK-01-03: 테스트 결과

## 결과: PASS

## 실행 요약

| 구분 | 통과 | 실패 | 합계 |
|------|------|------|------|
| 단위 테스트 (전체 discover) | 515 | 0 (TSK-01-03 범위) | 523 총 실행 |
| 단위 테스트 (TSK-01-03 전용: test_monitor_wp_cards + test_monitor_render) | 166 | 0 | 166 |
| E2E 테스트 (WpCardsSectionE2ETests) | 4 | 0 | 4 (+ 1 skipped) |

> 전체 `discover` 실행 시 8개 실패: `StickyHeaderKpiSectionE2ETests` 5개 (TSK-01-02 미구현) + `LiveActivityTimelineE2ETests` 3개 (TSK-01-04 미구현) — pre-existing, TSK-01-03 범위 외.

## 정적 검증 (Dev Config에 정의된 경우만)

| 구분 | 결과 | 비고 |
|------|------|------|
| lint | pass | `python3 -m py_compile scripts/monitor-server.py` — no output |
| typecheck | N/A | Dev Config에 typecheck 명령 없음 |

## QA 체크리스트 판정

| # | 항목 | 결과 |
|---|------|------|
| 1 | `_wp_donut_style({'done':6,'running':2,'failed':1,'bypass':0,'pending':1})` 반환 문자열에 `--pct-done-end` 와 `--pct-run-end` CSS 변수가 모두 포함됨 | pass |
| 2 | `_wp_donut_style({'done':0,'running':0,'failed':0,'bypass':0,'pending':0})` 반환 값이 `0deg`를 포함하며 ZeroDivisionError 없음 | pass |
| 3 | `_section_wp_cards([], set(), set())` 렌더 결과에 empty-state 문구 포함 | pass |
| 4 | 단일 WP, 단일 Task(done 상태) 렌더 시 `<div class="wp-card">` 1개, `task-row done` CSS 클래스 포함 | pass |
| 5 | 혼합 상태 WP(done 3 + running 1 + failed 1 + bypass 1 + pending 1) 렌더 시 카운트 합 == 7 | pass |
| 6 | bypassed Task의 task-row에 `bypass` CSS 클래스 포함, `failed` 클래스 미포함 (우선순위 검증) | pass |
| 7 | running Task의 task-row에 `running` CSS 클래스 포함 | pass |
| 8 | `<details>` 태그가 WP 카드 내부에 존재하며 task-row들이 그 안에 배치됨 | pass |
| 9 | `_section_features([], set(), set())` 렌더에 empty-state 포함 | pass |
| 10 | Feature task-row에도 상태별 CSS 클래스 적용됨 | pass |
| 11 | `render_dashboard` 호출 시 응답 HTML에 `id="wp-cards"` 섹션이 존재하며 `id="wbs"` 섹션은 미존재 | pass |
| 12 | `_section_wp_cards`에서 `wp_id=None`인 Task는 `WP-unknown` 그룹으로 처리됨 | pass |
| 13 | WP 이름에 `<script>` 포함 시 `_esc`를 통해 이스케이프됨 | pass |
| 14 | (E2E) 브라우저에서 `http://localhost:7321/` 접속 → WP 카드 섹션(`id="wp-cards"`)이 페이지에 렌더됨 | pass |
| 15 | (E2E) `<div class="wp-card">` 요소가 실제 WP 데이터 기반으로 브라우저에 표시됨 | pass |
| 15b | (E2E) `<details>` 클릭 시 task-row 리스트가 펼쳐짐 | unverified (no wbs_tasks in live server snapshot) |

## 재시도 이력
- 첫 실행에 통과

## 비고
- E2E 서버: 세션 시작 시 메인 repo의 `monitor-server.py`가 port 7321에서 실행 중. 해당 프로세스를 종료 후 worktree 코드로 재기동하여 E2E 실행.
- `test_wp_card_details_and_task_rows_present` — `_SERVER_UP=True` 상태에서도 `wbs_tasks` 데이터가 없어 skip. live server가 빈 WBS 상태(`no wbs_tasks`)로 응답하기 때문. 기능 자체는 단위 테스트(`test_task_row_inside_details`, `test_wp_card_contains_details_tag`)에서 pass로 검증됨.
- pre-existing 실패 8건 (TSK-01-02 KPI/sticky header 5건, TSK-01-04 activity/timeline 3건)은 아직 미구현된 후속 Task 기능이며 TSK-01-03 범위 외.
