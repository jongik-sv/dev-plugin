# Build Report: monitor-redesign

## 상태

**PASS** — 모든 단위 테스트 통과 (322/322)

## 변경 파일

| 파일 | 변경 내용 |
|------|----------|
| `scripts/monitor-server.py` | DASHBOARD_CSS, _DASHBOARD_CSS_COMPAT, _kpi_spark_svg, _section_kpi, _render_task_row_v2, _section_wp_cards, _section_live_activity, _section_header, _build_dashboard_body, _wp_donut_svg 수정 |
| `scripts/test_monitor_render.py` | 신규 테스트 클래스 6개 추가 (RedesignLayoutTests, RedesignTrowTests, RedesignArowTests, RedesignLangToggleActiveTests, RedesignDonutViewBoxTests) |
| `scripts/test_monitor_kpi.py` | 기존 4개 테스트 redesign 반영 업데이트 + 신규 RedesignKpiHtmlTests 클래스 추가 |

## TDD Red→Green 결과

### 신규 테스트 (40개 추가)

- **Red**: 40개 실패 확인 후 구현 진행
- **Green**: 모든 40개 통과

### 기존 테스트 (282개)

- 4개 테스트 redesign에 맞게 업데이트 (kpi_section_class, kpi_row_class, chip_group_present, css_class_kpi_sparkline)
- 278개 변경 없이 통과 유지

## 구현 세부 사항

### 1. _build_dashboard_body
- `.page` / `.page-col-left` / `.page-col-right` 이중 래퍼 제거
- `.grid > .col` 2열 구조로 단순화
- `sticky-header` 블록 제거 (cmdbar가 대체)

### 2. _section_kpi
- `class="kpi-card {kind} kpi kpi--{suffix}"` → `class="kpi kpi--{suffix}"`
- `class="kpi-row kpi-strip"` → `class="kpi-strip"`
- `class="kpi-section"` → 제거
- `class="chip-group chips"` → `class="chips"`
- `<span class="kpi-label label">` → `<div class="label">`
- `<span class="kpi-num num">` → `<div class="num">`

### 3. _kpi_spark_svg
- `class="kpi-sparkline"` → `class="spark"`

### 4. _render_task_row_v2
- `class="task-row {state}"` → `class="trow"`
- `<div class="run-line">` 제거
- hidden 더미 div 제거

### 5. _section_live_activity
- `class="activity-row"` → `class="arow"`
- `.a-time/.a-id/.a-event/.a-detail/.a-elapsed` → `.t/.tid/.evt/.el`
- `.evt` 내부 `<span class="arrow">→</span><span class="from">…</span><span class="arrow">→</span><span class="to">…</span>` 구조 추가
- hidden 더미 div 제거

### 6. _section_header
- 현재 lang에 맞는 링크에 `aria-current="page" class="active"` 추가

### 7. _wp_donut_svg
- `viewBox="0 0 40 40"` → `viewBox="0 0 36 36"`
- cx/cy: 20 → 18, r: 16 → 15.9
- transform: `rotate(-90 20 20)` → `rotate(-90 18 18)`

### 8. DASHBOARD_CSS
- `.col` CSS 추가: `min-width:0; display:flex; flex-direction:column; gap:0`
- `.lang-toggle a.active` CSS 추가 (amber accent)
- `.spark` CSS 추가 (sparkline)
- `.arow` CSS 추가 (.t/.tid/.evt/.el 자식 포함)

### 9. _DASHBOARD_CSS_COMPAT
- `.page*`, `.page-col-left/right*` 제거
- `.task-row*`, `.run-line*` 제거
- `.activity-row` 제거
- `.kpi-card`, `.kpi-row` 등 backward-compat CSS는 유지 (기존 테스트 보호)

## 라이브 서버 검증

```
http://localhost:7321/?subproject=monitor-v3
HTML length: 84821 bytes
```

- `class="col"`: ✅ present
- `class="page"`: ✅ absent
- `"kpi kpi--run"`: ✅ present
- `class="spark"`: ✅ present
- `class="trow"`: ✅ present
- `class="arow"`: ✅ present
- `class="chips"`: ✅ present
- `aria-current`: ✅ present
- `viewBox="0 0 36 36"`: ✅ present
- `data-section="sticky-header"`: ✅ absent
