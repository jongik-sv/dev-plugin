# TSK-04-03: TDD 구현 결과

## 결과: PASS

## 생성/수정된 파일

| 파일 경로 | 변경 내용 | 신규/수정 |
|-----------|-----------|-----------|
| `scripts/monitor-server.py` | `_merge_badge(ws, lang)` 헬퍼 추가, `_load_wp_merge_states(docs_dir)` 추가, `_section_wp_cards()` 에 `wp_merge_state` 인자 추가 + row1 div에 뱃지 삽입, `_task_panel_css()` 에 merge-badge/merge-stale-banner/merge-ready-banner/merge-conflict-file/merge-hunk-preview CSS 추가, `_TASK_PANEL_JS` 에 `openMergePanel`/`renderMergePreview`/`closeMergePanel` JS 추가 + `.merge-badge` click delegation 분기 추가 + `openTaskPanel` 내 `panelMode='task'` 명시 설정, `render_dashboard` 에서 `_load_wp_merge_states` 호출 후 `_section_wp_cards` 에 전달 | 수정 |
| `scripts/test_monitor_merge_badge.py` | `_merge_badge` 4개 state HTML 렌더 단위 테스트 (47개), `_section_wp_cards` wp_merge_state 인자 테스트, `_TASK_PANEL_JS` openMergePanel/renderMergePreview/delegation 포함 테스트, CSS 포함 테스트, `_load_wp_merge_states` 파일 읽기+graceful degradation 테스트 | 신규 |
| `scripts/test_monitor_merge_badge_e2e.py` | E2E `test_merge_badge_e2e` — 실 서버 HTTP 클라이언트 검증 (16개) + SSR 구조 검증 (6개). 서버 미기동 시 자동 skipUnless | 신규 (build 작성, 실행은 dev-test) |
| `scripts/test_monitor_wp_cards.py` | `data-wp` 개수 assertion을 `<details class="wp"` 개수로 수정 (TSK-04-03 merge-badge 추가로 data-wp 속성이 2개가 되어 기존 assertion 정밀도 개선) | 수정 |

## 테스트 결과

| 구분 | 통과 | 실패 | 합계 |
|------|------|------|------|
| 단위 테스트 (TSK-04-03 신규) | 47 | 0 | 47 |
| 기존 단위 테스트 전체 (회귀 포함) | 1541 | 0 | 1541 (+9 skipped) |

- pre-existing failures (TSK-04-03 이전부터 실패하던 테스트): 47개 (filter_bar TSK-05-01 미구현 + E2E 서버 미기동)
- 우리 변경으로 도입된 회귀: 0개

## E2E 테스트 (작성만 — 실행은 dev-test)

| 파일 경로 | 검증 대상 |
|-----------|-----------|
| `scripts/test_monitor_merge_badge_e2e.py::MergeBadgeE2ETests` | 실 서버 GET / 응답에 merge-badge, openMergePanel, renderMergePreview, CSS, panelMode 코드 포함 확인 (16개 테스트, 서버 미기동 시 skipUnless) |
| `scripts/test_monitor_merge_badge_e2e.py::MergeBadgeSSRStructureTests` | render_dashboard() SSR 출력에 merge-badge/JS/CSS 포함 확인 (6개 테스트, 항상 실행) |

## 커버리지 (Dev Config에 coverage 정의 시)
- Dev Config에 `quality_commands.coverage` 미정의 → N/A

## 비고
- 기존 `test_monitor_wp_cards.py`의 `data-wp="WP-01"` 개수 assertion 3개가 실패 — merge-badge에도 `data-wp` 속성이 추가되어 카드당 2개가 됨. 기존 테스트의 의도("WP 카드 1개")를 보존하여 `<details class="wp"` 개수 카운트 방식으로 정밀도 개선 후 수정.
- `_load_wp_merge_states`: `docs/wp-state/{WP-ID}/merge-status.json` 파일 미존재 시 `{}` 반환 (graceful degradation). TSK-04-02 스캐너 실행 전에도 대시보드 크래시 없음.
- render_dashboard에서 `docs_dir`은 `model.get("docs_dir")` 또는 `model.get("subproject")`에서 추출. 비어있으면 `_load_wp_merge_states` 호출 생략.
- merge-preview.py: 미커밋 변경으로 skip (exit 2) — 회귀 없음.
