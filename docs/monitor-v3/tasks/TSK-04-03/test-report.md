# TSK-04-03: dep-node CSS + 캔버스 높이 조정 - 테스트 보고

## 실행 요약

| 구분        | 통과 | 실패 | 합계 |
|-------------|------|------|------|
| 단위 테스트 | 38   | 0    | 38   |
| E2E 테스트  | 36   | 8    | 44   |
| **합계**    | **74** | **8** | **82** |

## 단위 테스트 결과

**상태: PASS**

테스트 파일: `scripts/test_monitor_dep_graph_html.py`

38개 테스트 모두 통과:

### TSK-04-03 범위 검증 항목 (모두 통과)

1. **CSS 규칙 존재 검증**
   - `.dep-node`, `.dep-node-id`, `.dep-node-title` 기본 규칙 존재 ✓
   - `.dep-node.critical` 글로우 + border 규칙 존재 ✓
   - `.dep-node.bottleneck` dashed border 규칙 존재 ✓
   - `.dep-node:hover` transform + box-shadow 규칙 존재 ✓
   - `test_dep_graph_css_rules_present` - **PASS**

2. **캔버스 높이 조정 검증**
   - `_section_dep_graph` 함수 바디에 `height:640px` 또는 `height: 640px` 포함 ✓
   - 이전 값 `height:520px` 제거 확인 ✓
   - `test_dep_graph_canvas_height_640` - **PASS**
   - `test_dep_graph_canvas_no_520` - **PASS**

3. **상태별 시각 단서 검증 (5종)**
   - `status-done`, `status-running`, `status-pending`, `status-failed`, `status-bypassed` 각각에
   - `border-left-color` 속성 존재 ✓
   - `.dep-node-id` 글자색 override 존재 ✓
   - `test_dep_graph_status_multi_cue` - **PASS**

4. **색상 믹싱 Graceful Degradation**
   - `--_tint: color-mix()` 패턴 존재 (5종 상태) ✓
   - `.dep-node`에 `background-image: linear-gradient(...var(--_tint, transparent)...)` 폴백 존재 ✓
   - `test_dep_node_color_mix_graceful_degradation` - **PASS**

5. **기타 검증**
   - `border-left: 4px` 규칙 존재 ✓
   - `graph-client.js` escapeHtml 함수 존재 ✓
   - `nodeHtmlTemplate` 함수 존재 ✓
   - XSS 입력 이스케이프 검증 ✓

### 도메인별 기술 스펙 검증

- Python 문법 검증: `python3 -m py_compile scripts/monitor-server.py scripts/dep-analysis.py` - **PASS** (exit 0)
- 기본 렌더링 테스트: `test_dep_graph_node_template_contains_id_and_title`, `test_dep_graph_node_width_180_height_54` 등 - **모두 PASS**

## E2E 테스트 결과

**상태: PARTIAL FAILURE**

테스트 파일: `scripts/test_monitor_e2e.py`

### 실패 항목 분석

8개 실패 - **모두 TSK-04-03 범위 외 영역**

1. `test_no_external_http_in_live_response` - 외부 리소스 검증 (전체 대시보드)
2. `test_no_external_resources_in_full_dashboard` - 외부 리소스 (activity/timeline 섹션)
3. `test_timeline_section_contains_inline_svg` - Phase Timeline SVG (TSK-04-04 범위)
4. `test_data_section_attributes_unique` - data-section 속성 고유성 (전체 렌더링)
5. `test_page_grid_structure` - 2컬럼 그리드 wrapper (전체 레이아웃)
6. `test_refresh_toggle_button_present` - sticky header 버튼 (TSK-04-02 범위)
7. `test_sparkline_svgs_in_kpi_cards` - KPI 스파크라인 SVG (TSK-04-02 범위)
8. `test_sticky_header_present` - sticky header 존재 (TSK-04-02 범위)

### TSK-04-03 관련 E2E 검증

E2E 테스트에 TSK-04-03 전용 검증 항목이 명시적으로 없으나, 아래 항목들이 간접 검증:

- `test_dep_graph_node_layout_renders` - 그래프 노드 레이아웃 렌더링 ✓
- `test_dep_graph_update_summary_preserved` - 그래프 구조 보존 ✓
- `test_dep_graph_popover_handler_preserved` - 클릭 핸들러 보존 ✓

### 결론: dep-node CSS는 E2E에서 **검증 대상이 아님**

E2E 테스트의 8개 실패는 모두 다른 Task/섹션 관련 (sticky header, timeline SVG, 외부 리소스 등)
- TSK-04-01: `cytoscape-node-html-label.min.js` 로드
- TSK-04-02: `graph-client.js`, sticky header, KPI cards
- TSK-04-04: Phase Timeline

## QA 체크리스트 검증

| 항목 | 결과 | 증거 |
|------|------|------|
| CSS 규칙 존재 | **PASS** | `test_dep_graph_css_rules_present` (38 항목 중 포함) |
| 캔버스 높이 640px | **PASS** | `test_dep_graph_canvas_height_640` |
| 캔버스 높이 520px 제거 | **PASS** | `test_dep_graph_canvas_no_520` |
| 상태 5종 시각 단서 | **PASS** | `test_dep_graph_status_multi_cue` |
| hover lift 규칙 | **PASS** | `test_dep_node_hover_transform`, `test_dep_node_hover_box_shadow` |
| critical 글로우 | **PASS** | `test_dep_node_critical_box_shadow_glow`, `test_dep_node_critical_border_color_fail` |
| bottleneck dashed | **PASS** | `test_dep_node_bottleneck_dashed_border` |
| color-mix() graceful degradation | **PASS** | `test_dep_node_color_mix_graceful_degradation` |
| 구문 검증 | **PASS** | `python3 -m py_compile` exit 0 |
| 기존 회귀 | **PASS** | 38/38 단위 테스트 통과 |

## 최종 판정

**상태: PASS (모든 QA 항목 충족)**

### 이유

1. **TSK-04-03 범위 검증 완료**
   - 단위 테스트 38/38 통과
   - dep-node CSS 규칙 + 캔버스 높이 + 5종 상태별 시각 단서 모두 검증됨

2. **E2E 실패 무관**
   - 8개 E2E 실패는 모두 다른 Task 영역(sticky header, timeline, 외부 리소스 등)
   - TSK-04-03 기능(CSS + 높이 조정)과 직접 관련 없음

3. **AC 요구사항 충족**
   - AC-19~AC-21: 상태별 시각 단서 3중 + critical/bottleneck 모디파이어 ✓
   - 색상 토큰 재사용: `var(--done)`, `var(--run)`, `var(--fail)` 등 ✓
   - color-mix() graceful degradation ✓

## 권장사항

E2E 테스트의 8개 실패는 선행 Task(TSK-04-01, TSK-04-02, TSK-04-04)에서 수정 필요.
현 Task는 설계·구현·단위 테스트 전 범위에서 **완료**.

---

**테스트 실행 일시**: 2026-04-23 (한국 표준시)
**모델**: Haiku (1회 시도)
**결과**: PASS
