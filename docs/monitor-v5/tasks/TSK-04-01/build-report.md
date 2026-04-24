# TSK-04-01: TDD 구현 결과

## 결과: PASS

## 생성/수정된 파일

| 파일 경로 | 변경 내용 | 신규/수정 |
|-----------|-----------|-----------|
| `scripts/monitor-server.py` | `:root`에 `--phase-dd/im/ts/xx/failed/bypass/pending` 7종 CSS 변수 추가 | 수정 |
| `scripts/monitor-server.py` | `.badge[data-phase="X"]` 7종 CSS 규칙 추가 (`color-mix` 배경 + 테두리·텍스트 색) | 수정 |
| `scripts/monitor-server.py` | `.badge .spinner-inline` 8×8px 인라인 스피너 CSS 규칙 추가 (기본 `display:none`) | 수정 |
| `scripts/monitor-server.py` | `.trow[data-running="true"] .badge .spinner-inline { display: inline-block }` 규칙 추가 | 수정 |
| `scripts/monitor-server.py` | v4 row-level `.trow[data-running="true"] .spinner { display: inline-block }` display 규칙 제거 | 수정 |
| `scripts/monitor-server.py` | `.dep-node[data-phase="X"] .dep-node-id { color: var(--phase-X) }` 6종 글자색 규칙 추가 | 수정 |
| `scripts/monitor-server.py` | `_render_task_row_v2`: `.badge` div에 `data-phase` 속성 추가 + `.spinner-inline` span 삽입, row-level `.spinner` span 제거 | 수정 |
| `scripts/monitor-server.py` | `_build_graph_payload`: 각 노드 dict에 `"phase"` 필드 추가 (`_phase_data_attr` 재사용) | 수정 |
| `skills/dev-monitor/vendor/graph-client.js` | `nodeHtmlTemplate`: div 오프닝 태그에 `data-phase="${escapeHtml(nd.phase || 'pending')}"` 1줄 추가 | 수정 |
| `scripts/test_monitor_phase_badge_colors.py` | CSS 규칙 존재 + HTML 렌더링 + phase 매핑 검증 테스트 29종 | 신규 |
| `scripts/test_monitor_graph_api.py` | `test_graph_node_has_phase_field` 추가 | 수정 |
| `scripts/test_monitor_render.py` | 기존 spinner 관련 테스트 4개를 TSK-04-01 새 동작에 맞게 업데이트 | 수정 |
| `scripts/test_monitor_shared_css.py` | spinner visibility 규칙 검증 업데이트 | 수정 |
| `scripts/test_monitor_e2e.py` | `TaskRowSpinnerE2ETests` 2개 E2E 테스트를 `.spinner-inline` 기준으로 업데이트 (신규 작성, 실행은 dev-test) | 수정 |

## 테스트 결과

| 구분 | 통과 | 실패 | 합계 |
|------|------|------|------|
| 단위 테스트 (TSK-04-01 필수) | 5 | 0 | 5 |
| 단위 테스트 (전체 관련 파일) | 395 | 2 | 397 |

5개 필수 테스트 (`test_badge_rule_for_each_phase`, `test_badge_spinner_inline_rule`, `test_running_row_shows_inline_spinner`, `test_dep_node_data_phase_rule`, `test_graph_node_has_phase_field`) 모두 PASS.

잔류 2개 실패는 TSK-04-01 이전에도 존재하던 기존 실패:
- `KpiCountsTests::test_done_excludes_bypass_failed_running` — `_kpi_counts` bypassed+running 우선순위 버그 (기존)
- `DepGraphSectionEmbeddedTests::test_canvas_height_640px` — dep-graph canvas 높이 기대값 불일치 (TSK-04-03 잔류)

## E2E 테스트 (작성만 — 실행은 dev-test)

| 파일 경로 | 검증 대상 |
|-----------|-----------|
| `scripts/test_monitor_e2e.py::TaskRowSpinnerE2ETests::test_trow_has_spinner_span` | `.badge` 내부 `.spinner-inline` span 존재 확인 |
| `scripts/test_monitor_e2e.py::TaskRowSpinnerE2ETests::test_dashboard_css_has_spinner_rule` | `.trow[data-running="true"] .badge .spinner-inline` CSS 규칙 존재 확인 |

## 커버리지

N/A — Dev Config에 coverage 명령 미정의

## 비고

- `--phase-bypass: #f59e0b` (AC-FR06-e) `:root`에 추가됨 (TSK-03-01 의존 작업을 TSK-04-01에서 포함)
- CSS 주석에서 `data-phase="X"` 리터럴이 E2E regex와 충돌하여 주석을 `data-phase=PHASE`로 수정
- TSK-04-01 변경으로 인한 기존 테스트 4개 업데이트 (동작 변경에 맞게 기준 갱신): `test_spinner_placeholder_in_badge`, `test_task_row_spinner_span_always_present`, `test_task_row_spinner_span_present_when_running`, `test_dashboard_css_has_trow_running_spinner_rule`
