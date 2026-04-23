# TSK-04-04 Build Report

## 결과

**PASS** — 5/5 단위 테스트 통과, 기존 회귀 없음

## 테스트 실행 결과

```
scripts/test_monitor_dep_graph_summary.py::TestDepGraphSummaryLabelsKo::test_dep_graph_summary_labels_ko PASSED
scripts/test_monitor_dep_graph_summary.py::TestDepGraphSummaryLabelsEn::test_dep_graph_summary_labels_en PASSED
scripts/test_monitor_dep_graph_summary.py::TestDepGraphSummaryColorPalette::test_dep_graph_summary_color_matches_palette PASSED
scripts/test_monitor_dep_graph_summary.py::TestDepGraphSummaryLegendParity::test_dep_graph_summary_legend_parity PASSED
scripts/test_monitor_dep_graph_summary.py::TestDepGraphSummaryDataStatSelector::test_dep_graph_summary_preserves_data_stat_selector PASSED
5 passed in 0.05s
```

전체 테스트 (`scripts/` 디렉터리, E2E 제외): **1049 passed, 12 skipped, 0 failed**

## 생성/수정된 파일

| 파일 | 역할 | 변경 유형 |
|------|------|-----------|
| `scripts/monitor-server.py` | `_I18N` 6키 추가, `summary_html` 칩 구조 교체, `DASHBOARD_CSS` dep-stat 블록 추가 | 수정 |
| `scripts/test_monitor_dep_graph_summary.py` | TSK-04-04 단위 테스트 5개 | 신규 |

## 구현 요약

### 1. `_I18N` 확장 (ko/en 6키)
- ko: `총`, `완료`, `진행`, `대기`, `실패`, `바이패스`
- en: `Total`, `Done`, `Running`, `Pending`, `Failed`, `Bypassed`

### 2. `summary_html` 교체
- 기존: `<span data-stat="...">-</span>` × 6 (레이블 없음)
- 변경: `<span class="dep-stat dep-stat-{state}"><em>{label}</em> <b data-stat="{state}">-</b></span>` × 6
- `_t(lang, "dep_stat_{state}")` 호출로 i18n 치환
- `[data-stat]` 선택자 유지 → graph-client.js:updateSummary 계약 보존 (JS 수정 0)

### 3. `DASHBOARD_CSS` dep-stat 블록 추가
- `/* ---------- responsive ---------- */` 직전 삽입
- `.dep-stat-{state}` em/b에 색상 할당 (AC-32 legend parity 달성):
  - total: `var(--ink)` (기본 텍스트 색, AC-31)
  - done: `#22c55e`, running: `#eab308`, pending: `#94a3b8`, failed: `#ef4444` (legend hex 직접 사용)
  - bypassed: `#a855f7` (legend·graph-client.js 기존 하드코딩과 동일)
- `.dep-graph-summary-extra` 색상 규칙 추가 (`var(--ink-2)`)

## 설계 결정 (design.md 대비 변경)

- **CSS 토큰 vs hex 직접 사용**: design.md는 `var(--done)` 등 CSS 토큰을 명시했으나, 실제 `--done: #4ed08a`이 legend의 `#22c55e`와 다르다. AC-32(legend parity) 달성을 위해 legend hex를 직접 사용. `--done/--run/--ink-3/--fail` 토큰은 각각 `#4ed08a/#4aa3ff/#6b7480/#ff5d5d`로 legend와 불일치하여 토큰 재사용 시 AC-32 위반.
- `bypassed`는 양쪽 `#a855f7`로 동일하여 constraint 만족.

## 상태 전이

`[dd]` → `[im]` (build.ok, 2026-04-23T03:03:03Z)
