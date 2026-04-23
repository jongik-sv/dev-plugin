# TSK-04-04: Dep-Graph summary 칩 SSR + i18n + CSS - 설계

## 요구사항 확인

- `_section_dep_graph` 함수가 생성하는 SSR `summary_html`을 레이블이 없는 단순 숫자 나열 → 6개 `.dep-stat` 칩(`{레이블} {숫자}`) 형태로 교체한다.
- `_I18N` 테이블에 `dep_stat_total/done/running/pending/failed/bypassed` 6키를 ko/en 추가하고, DASHBOARD_CSS에 `.dep-stat` / `.dep-stat-{state}` 규칙을 추가한다.
- `graph-client.js:updateSummary`가 사용하는 `[data-stat]` 선택자 계약을 유지(JS 변경 0)하고, `test_monitor_dep_graph_summary.py` 신규 파일에 5개 테스트를 작성한다.

## 타겟 앱

- **경로**: N/A (단일 앱)
- **근거**: monitor-server.py는 단일 파이썬 모놀리스, 별도 모노레포 구조 없음

## 구현 방향

1. `scripts/monitor-server.py`의 `_I18N` 딕셔너리(`_I18N["ko"]` / `_I18N["en"]`)에 `dep_stat_*` 6개 키를 추가한다.
2. `_section_dep_graph`의 `summary_html` 리터럴을 교체한다 — `<b data-stat="...">` 유지, 외부에 `.dep-stat dep-stat-{state}` 래퍼 `<span>`, `<em>` 레이블 삽입; `_t(lang, key)` 호출로 i18n 치환.
3. `DASHBOARD_CSS` 문자열에 `.dep-stat` / `.dep-stat-{state}` CSS 블록을 추가한다 — 토큰 재사용(`--done`, `--run`, `--ink`, `--ink-3`, `--fail`, `#a855f7`).
4. `scripts/test_monitor_dep_graph_summary.py`를 신규 생성하고 5개 테스트를 작성한다.

## 파일 계획

**경로 기준:** 프로젝트 루트 기준.

| 파일 경로 | 역할 | 신규/수정 |
|-----------|------|-----------|
| `scripts/monitor-server.py` | `_I18N` 6키 추가, `summary_html` 교체, DASHBOARD_CSS 확장 | 수정 |
| `scripts/test_monitor_dep_graph_summary.py` | TSK-04-04 단위 테스트 5개 | 신규 |

## 진입점 (Entry Points)

- **사용자 진입 경로**: 대시보드 브라우저 접속(`http://localhost:{port}`) → 페이지 하단 "의존성 그래프" 섹션 확인 (섹션이 페이지 내 자동 포함, 별도 메뉴 클릭 불필요)
- **URL / 라우트**: `http://localhost:{port}/` (또는 `?lang=en` 파라미터 추가)
- **수정할 라우터 파일**: 라우팅 변경 없음 — `render_dashboard` 내부 `_section_dep_graph` 호출로 이미 포함됨 (`scripts/monitor-server.py` line ~3959의 `render_dashboard` 참조)
- **수정할 메뉴·네비게이션 파일**: 메뉴 변경 없음 — 기존 dep-graph 섹션이 이미 대시보드에 포함됨
- **연결 확인 방법**: `pytest -q scripts/test_monitor_dep_graph_summary.py` 통과; 브라우저에서 `?lang=ko` / `?lang=en` 전환 후 요약 칩 레이블 표시 확인

## 주요 구조

- **`_I18N` 딕셔너리 확장** (`monitor-server.py`, line ~1004): `"ko"` / `"en"` 서브딕트에 6키 추가. `_t(lang, key)` 함수는 수정 불필요.
- **`_section_dep_graph(lang, subproject)`** (`monitor-server.py`, line ~3088): `summary_html` 지역변수만 교체. `_t(lang, dep_stat_{state})` 호출로 레이블 삽입.
- **`DASHBOARD_CSS`** (`monitor-server.py`, line ~1050): `/* ---------- dep-graph summary chips ---------- */` 블록 추가. 기존 `--done/--run/--ink/--ink-3/--fail` 토큰 재사용, `#a855f7` 하드코딩.
- **`test_monitor_dep_graph_summary.py`** (신규): `_import_server()` 패턴으로 모듈 임포트, 5개 `TestCase` 클래스 작성.

## 데이터 흐름

SSR 시점: `render_dashboard(lang, subproject)` → `_section_dep_graph(lang, subproject)` → `_t(lang, "dep_stat_{state}")` → HTML 문자열 반환 → HTTP 응답.  
Live update 시점: `graph-client.js:updateSummary(stats)` → `el.querySelector('[data-stat="total"]')` → `b.textContent = stats.total` (JS 수정 없음).

## 설계 결정 (대안이 있는 경우만)

- **결정**: `<b data-stat="...">` 태그를 유지하고 외부에 `<span class="dep-stat dep-stat-{state}">` + `<em>` 래퍼를 추가
- **대안**: `<span data-stat="...">` 그대로 유지하고 CSS만 추가 (태그 변경 없음)
- **근거**: TRD §3.13.3에서 `<b data-stat>` 구조를 명시하고, `querySelector('[data-stat]')`는 태그명을 구분하지 않으므로 JS 계약에 영향 없이 더 명확한 시맨틱을 부여한다.

- **결정**: CSS를 `DASHBOARD_CSS` 인라인 블록에 추가 (별도 파일 없음)
- **대안**: `_section_dep_graph` 반환 HTML에 `<style>` 태그 인라인 삽입
- **근거**: 기존 모든 CSS가 `DASHBOARD_CSS`에 집중되어 있어 유지보수 일관성 확보; TRD §3.13.5 지침과 일치.

## 선행 조건

- `TSK-03-04` 완료 (dep-graph 섹션 SSR skeleton 및 `_section_dep_graph` 함수 존재) — 현재 worktree에 이미 구현되어 있으므로 선행 조건 충족 상태.

## 리스크

- **MEDIUM**: `DASHBOARD_CSS`가 ~900줄의 단일 문자열이므로 삽입 위치를 잘못 잡으면 `_minify_css`가 인접 선택자와 병합하여 의도치 않은 스타일이 적용될 수 있음. → 삽입 위치를 명확히 특정(activity 섹션 CSS 직전)하고 `pytest -q scripts/test_monitor_render.py`로 기존 테스트 회귀를 확인한다.
- **MEDIUM**: legend 인라인 `style="color:#22c55e"` 해시와 새로 추가되는 CSS 토큰(`var(--done)`)이 실제 동일 hex인지 브라우저 렌더링 레벨에서만 검증 가능 — `test_dep_graph_summary_legend_parity` 테스트가 Python 레벨에서 문자열 패턴 매칭으로 커버. legend 하드코딩 → CSS변수 교체는 이번 범위 밖.
- **LOW**: `_minify_css`가 CSS `em` 선택자를 단순 치환할 가능성 — 실제로는 클래스 이름 일부이므로 영향 없으나, 테스트에서 minified HTML이 아닌 raw CSS 문자열로 검증하여 확인.

## QA 체크리스트

- [ ] (정상) `lang=ko` 렌더에서 6개 레이블 `총`, `완료`, `진행`, `대기`, `실패`, `바이패스`가 summary HTML에 존재한다 (`test_dep_graph_summary_labels_ko`)
- [ ] (정상) `lang=en` 렌더에서 6개 레이블 `Total`, `Done`, `Running`, `Pending`, `Failed`, `Bypassed`가 summary HTML에 존재한다 (`test_dep_graph_summary_labels_en`)
- [ ] (정상) DASHBOARD_CSS에 5개 상태 칩(`done/running/pending/failed/bypassed`)의 색상이 팔레트 토큰 또는 `#a855f7`로 매핑되어 있고 `total`은 `var(--ink)`이다 (`test_dep_graph_summary_color_matches_palette`)
- [ ] (통합) summary 칩의 상태별 색상값(CSS 토큰)과 `#dep-graph-legend` 인라인 `style="color:..."` 해시값이 state별 1:1 일치한다 (`test_dep_graph_summary_legend_parity`)
- [ ] (정상) SSR HTML에 `[data-stat="total"]`, `[data-stat="done"]`, `[data-stat="running"]`, `[data-stat="pending"]`, `[data-stat="failed"]`, `[data-stat="bypassed"]` 선택자가 매칭되는 요소가 모두 존재한다 (`test_dep_graph_summary_preserves_data_stat_selector`)
- [ ] (회귀) 기존 `test_monitor_render.py`의 dep-graph 관련 테스트(`test_dep_graph_summary_aside_present` 등)가 수정 후에도 통과한다
- [ ] (회귀) `pytest -q scripts/` 전체 실행 시 새로 추가한 테스트를 포함해 모두 통과한다
- [ ] (클릭 경로) 메뉴/사이드바/버튼을 클릭하여 목표 페이지에 도달한다 — 대시보드 접속 시 dep-graph 섹션이 페이지에 포함되어 있고 summary 칩이 표시된다 (URL 직접 입력 금지)
- [ ] (화면 렌더링) 핵심 UI 요소가 브라우저에서 실제 표시되고 기본 상호작용이 동작한다 — `lang=ko`/`lang=en` 전환 시 summary 칩 레이블이 변경되며, 2초 폴링 후 숫자가 업데이트된다

---

## 구현 세부 사항 (dev-build 참조용)

### 1. `_I18N` 딕셔너리 변경 위치

`scripts/monitor-server.py` line ~1004의 `_I18N` 딕셔너리:

```python
_I18N: dict[str, dict[str, str]] = {
    "ko": {
        # 기존 키 유지 ...
        "dep_graph": "의존성 그래프",
        # 추가
        "dep_stat_total":    "총",
        "dep_stat_done":     "완료",
        "dep_stat_running":  "진행",
        "dep_stat_pending":  "대기",
        "dep_stat_failed":   "실패",
        "dep_stat_bypassed": "바이패스",
    },
    "en": {
        # 기존 키 유지 ...
        "dep_graph": "Dependency Graph",
        # 추가
        "dep_stat_total":    "Total",
        "dep_stat_done":     "Done",
        "dep_stat_running":  "Running",
        "dep_stat_pending":  "Pending",
        "dep_stat_failed":   "Failed",
        "dep_stat_bypassed": "Bypassed",
    },
}
```

### 2. `summary_html` 교체 (line ~3104)

현재:
```python
summary_html = (
    '<aside id="dep-graph-summary" class="dep-graph-summary">'
    '<span data-stat="total">-</span> · '
    ...
    '</aside>'
)
```

교체 후:
```python
summary_html = (
    '<aside id="dep-graph-summary" class="dep-graph-summary">'
    + '<span class="dep-stat dep-stat-total">'
    + f'<em>{html.escape(_t(lang, "dep_stat_total"))}</em>'
    + ' <b data-stat="total">-</b></span>'
    + ' <span class="dep-stat dep-stat-done">'
    + f'<em>{html.escape(_t(lang, "dep_stat_done"))}</em>'
    + ' <b data-stat="done">-</b></span>'
    + ' <span class="dep-stat dep-stat-running">'
    + f'<em>{html.escape(_t(lang, "dep_stat_running"))}</em>'
    + ' <b data-stat="running">-</b></span>'
    + ' <span class="dep-stat dep-stat-pending">'
    + f'<em>{html.escape(_t(lang, "dep_stat_pending"))}</em>'
    + ' <b data-stat="pending">-</b></span>'
    + ' <span class="dep-stat dep-stat-failed">'
    + f'<em>{html.escape(_t(lang, "dep_stat_failed"))}</em>'
    + ' <b data-stat="failed">-</b></span>'
    + ' <span class="dep-stat dep-stat-bypassed">'
    + f'<em>{html.escape(_t(lang, "dep_stat_bypassed"))}</em>'
    + ' <b data-stat="bypassed">-</b></span>'
    + '</aside>'
)
```

### 3. DASHBOARD_CSS 추가 블록

`/* ---------- responsive ---------- */` 블록 직전에 삽입:

```css
/* ---------- dep-graph summary chips ---------- */
#dep-graph-summary {
  display: flex; gap: 14px; align-items: baseline;
  font-size: 12.5px; font-variant-numeric: tabular-nums;
}
.dep-stat { display: inline-flex; gap: 5px; align-items: baseline; }
.dep-stat em { font-style: normal; font-weight: 500; opacity: .85; letter-spacing: .02em; }
.dep-stat b  { font-weight: 700; }
.dep-stat-total    em,
.dep-stat-total    b { color: var(--ink); }
.dep-stat-done     em,
.dep-stat-done     b { color: var(--done); }
.dep-stat-running  em,
.dep-stat-running  b { color: var(--run); }
.dep-stat-pending  em,
.dep-stat-pending  b { color: var(--ink-3); }
.dep-stat-failed   em,
.dep-stat-failed   b { color: var(--fail); }
.dep-stat-bypassed em,
.dep-stat-bypassed b { color: #a855f7; }
.dep-graph-summary-extra { color: var(--ink-2); margin-left: 10px; }
```

### 4. `test_monitor_dep_graph_summary.py` 구조

```
class TestDepGraphSummaryLabelsKo:      # test_dep_graph_summary_labels_ko
class TestDepGraphSummaryLabelsEn:      # test_dep_graph_summary_labels_en
class TestDepGraphSummaryColorPalette:  # test_dep_graph_summary_color_matches_palette
class TestDepGraphSummaryLegendParity:  # test_dep_graph_summary_legend_parity
class TestDepGraphSummaryDataStatSelector:  # test_dep_graph_summary_preserves_data_stat_selector
```

각 클래스는 `_import_server()` 헬퍼(기존 `test_monitor_render_tsk04.py` 패턴 참고)로 `monitor-server` 모듈을 임포트하고, `_section_dep_graph(lang=...)` 반환 HTML 또는 `DASHBOARD_CSS` 문자열을 파싱하여 assert.

- `test_dep_graph_summary_labels_ko`: `_section_dep_graph(lang="ko")` HTML에 `총`, `완료`, `진행`, `대기`, `실패`, `바이패스` 6개 레이블이 모두 포함됨.
- `test_dep_graph_summary_labels_en`: `_section_dep_graph(lang="en")` HTML에 `Total`, `Done`, `Running`, `Pending`, `Failed`, `Bypassed` 6개 포함됨.
- `test_dep_graph_summary_color_matches_palette`: `DASHBOARD_CSS`에 `.dep-stat-done` → `var(--done)`, `.dep-stat-running` → `var(--run)`, `.dep-stat-pending` → `var(--ink-3)`, `.dep-stat-failed` → `var(--fail)`, `.dep-stat-bypassed` → `#a855f7`, `.dep-stat-total` → `var(--ink)` 패턴이 존재함.
- `test_dep_graph_summary_legend_parity`: legend HTML(`#dep-graph-legend`)의 state별 `style="color:..."` 값과 summary CSS 색상이 일치함. (done: `#22c55e` vs `--done`, running: `#eab308` vs `--run`, pending: `#94a3b8` vs `--ink-3`, failed: `#ef4444` vs `--fail`, bypassed: `#a855f7` vs `#a855f7`). CSS 변수 색상은 `DASHBOARD_CSS`의 `:root` 블록에서 hex 값을 추출하여 비교.
- `test_dep_graph_summary_preserves_data_stat_selector`: `_section_dep_graph(lang="ko")` HTML에 `data-stat="total"`, `data-stat="done"`, `data-stat="running"`, `data-stat="pending"`, `data-stat="failed"`, `data-stat="bypassed"` 6종 모두 존재함.
