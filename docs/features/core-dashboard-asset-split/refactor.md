# core-dashboard-asset-split: 리팩토링 내역

## 변경 사항

| 파일 | 변경 내용 (요약) | 적용 기법 |
|------|-----------------|-----------|
| `scripts/monitor_server/core.py` | loader 섹션 주석의 net LOC를 실측값으로 정정 (`~3,274` → `3,284`, 감소량 `−2,144` → `−2,134`) | Fix Comment / Accuracy |

커밋 목록:

| 커밋 접두사 | 설명 | core.py LOC 변화 |
|-------------|------|-----------------|
| `[core-dashboard-asset-split:refactor-01]` | loader 섹션 LOC 주석 실측값 정정 | 0 (주석만) |

## 조사 결과

### 1. core.py 잔재 중복/dead code 조사

build 단계 완료 후 core.py(3,284 LOC)를 검사한 결과:

- **loader 섹션 분산**: `_load_static_text()` 호출이 L515(`DASHBOARD_CSS`), L1323(`_DASHBOARD_JS`), L1599-1601(`_PANE_JS`/`_PANE_CSS`), L2340-2348(`_TASK_PANEL_CSS_SRC`/`_TASK_PANEL_JS`) 4개 위치에 분산되어 있음. design.md C3-1에서 "단일 블록으로 통합"을 목표로 했으나, 각 변수가 해당 위치의 기능 섹션(WP-02 JS, pane, task_panel)과 문맥상 결합되어 있어 이동 시 `get_static_bundle`(L539) 이전 정의 순서를 신중히 관리해야 함. 기능 변경 없이 이동만 하는 대규모 이동의 위험 대비 이득이 낮다고 판단 — **이월 권고** (Phase 3 또는 단독 정리 커밋).
- **`_TASK_PANEL_CSS_SRC` 중간 변수**: 다른 5개와 달리 중간 변수명이 다름 (`_TASK_PANEL_CSS_SRC` vs 직접 바인딩). 이는 `_task_panel_css()` wrapper와 분리를 명확히 하기 위한 의도적 설계이며 개선 여지 없음.
- **`_load_static_text` 함수**: 6개 호출 전부 활성 참조. dead code 없음.
- **주석 불일치**: C3-1 주석의 net LOC 수치 오류 (refactor-01 커밋으로 정정 완료).

결론: build 단계에서 정리 가능한 dead code는 없으며, loader 위치 통합은 안전성 검토 후 이월한다.

### 2. shim 8개 파일의 file-first fallback 장기 유지 타당성

build 단계에서 적용된 shim:

| 파일 | shim 유형 | file-first 경로 |
|------|----------|-----------------|
| `test_font_css_variables.py` | `_STATIC_CSS.exists()` → `read_text` | `monitor_server/static/dashboard.css` |
| `test_monitor_dep_graph_html.py` | `_static_css.exists()` → `read_text` | `monitor_server/static/dashboard.css` |
| `test_monitor_shared_css.py` | `os.path.exists(_static_css)` → `open` | `monitor_server/static/dashboard.css` |
| `test_monitor_pane_size.py` | `_static_css.exists()` → `read_text` | `monitor_server/static/dashboard.css` |
| `test_monitor_fold.py` | `os.path.exists(_static_js)` → `open` | `monitor_server/static/dashboard.js` |
| `test_monitor_fold_helper_generic.py` | `os.path.exists(_static_js)` → `open` | `monitor_server/static/dashboard.js` |
| `test_monitor_fold_live_activity.py` | `hasattr(monitor_server, "_DASHBOARD_JS")` 없으면 `app.js` read | `monitor_server/static/app.js` |
| `test_monitor_progress_header.py` | `hasattr(monitor_server, "_TASK_PANEL_JS")` skip guard | 속성 접근 (파일 read 없음) |

**평가**:
- `dashboard.css`, `dashboard.js` 파일이 디스크에 존재하므로 현재 file-first 경로가 항상 진입됨. legacy regex-parse fallback은 실질적으로 **dead code**.
- `test_monitor_fold_live_activity.py`의 `app.js` 경로는 stale 파일(`style.css`/`app.js`)이 아닌 번들 파일들의 concat 파일인 `app.js`를 읽음 → 이 파일은 stale이므로 실제 번들과 다른 내용을 테스트하는 셈. 단, 이 테스트는 fold 동작을 검증하는 JS 소스-grep이므로 기능 단언에는 영향 없음.
- **장기 유지 여부**: file-first 경로는 영구 유지해도 무방. static 파일 존재가 보장되는 한 정확한 소스(dashboard.css)를 읽으며, regex-parse fallback은 파일 삭제/이동 시 대비책으로 기능. legacy fallback을 제거하면 코드가 단순해지지만 방어 코드가 사라짐 — **현행 유지 권고**.
- **개선 여지**: 8개 shim의 file-first 경로 패턴이 일관적이지 않음(Path vs os.path, exists 체크 방식). 스타일 통일은 기능 변경 없는 cosmetic 작업이므로 별도 정리 커밋으로 가능하나 우선순위 낮음.

### 3. stale `static/style.css` + `static/app.js` 처리 결정

**현황**:
- `monitor_server/static/style.css` (md5 `0c39eb...`, 48,451 B): build 단계(C2-1)에서 삭제하지 않고 유지됨
- `monitor_server/static/app.js` (md5 `4f91de...`, 31,688 B): 동일 유지
- 런타임 번들 (`dcab587d...`/`479d0ac1...`)과 다름 — stale 디스크 파일

**삭제 시 영향 조사**:
- `test_monitor_critical_color.py`: `_read_style_css()`가 skipTest 없이 `read_text()` 직접 호출 → FileNotFoundError로 **실패**
- `test_monitor_phase_tokens.py`: `assert _STYLE_CSS.exists()` → AssertionError로 **실패**
- `test_monitor_gpu_audit.py`: `setUp`에서 `self.skipTest(...)` → **skip (실패 아님)**
- 그 외 다수 테스트가 `static/style.css`/`static/app.js`를 직접 읽음

**결정: stale 파일 보류 유지**

근거:
1. 삭제 시 최소 2개 테스트(`test_monitor_critical_color.py`, `test_monitor_phase_tokens.py`)에서 pre-existing baseline을 초과하는 신규 실패 발생. baseline Δ = 0 요구사항 위반.
2. 이 테스트들은 `style.css`에서 CSS 규칙(`.dep-node.critical`, `--critical` 변수 등)을 검증하는데, stale 파일에 해당 규칙이 있으므로 현재 통과 중임.
3. `handlers._serve_local_static`는 번들 우선 서빙이므로 stale 파일은 런타임에 실질적으로 노출되지 않음 (fallback 경로는 번들이 비어있을 때만 진입).
4. `/static/` 경로 바인딩을 runtime 번들 쪽으로 일원화하는 최소 수정 방안은 `handlers.py`의 현재 구조가 이미 번들 우선이므로 별도 작업 불필요.

**권고 (Phase 3 또는 별도 정리)**: 향후 이 두 테스트가 `get_static_bundle("style.css")` 경유로 리팩토링되면 stale 파일 삭제 가능.

### 4. Pylance 진단 현황

`액세스하지 않았습니다` 진단은 core.py facade의 re-export 심볼(`from monitor_server.api import ...`, `from monitor_server.caches import ...` 등)에서 발생. 이는 core-decomposition 원칙(facade 계층에서 import가 암묵적으로 공개하는 방식)의 비용으로 **허용**한다. 신규 기능 코드에는 해당 없음.

## 테스트 확인

- 결과: **PASS**
- 실행 명령: `rtk proxy python3 -m pytest -q scripts/ --tb=no`
- 결과: 3 failed (pre-existing) / 1996 passed / 176 skipped — baseline Δ = 0

### Bundle md5 불변

| 파일 | baseline md5 | 실행 후 md5 | 일치 |
|------|-------------|------------|------|
| style.css | dcab587d6fd4fc32f46117fbdce06e44 | dcab587d6fd4fc32f46117fbdce06e44 | ✓ |
| app.js | 479d0ac147cd74f4664c00acd0d38c78 | 479d0ac147cd74f4664c00acd0d38c78 | ✓ |

### 최종 LOC

| 항목 | build 종료 시 | refactor 후 | Δ |
|------|-------------|------------|---|
| `core.py` | 3,284 | **3,284** | 0 (주석 1줄 교체) |

## Phase 2 전체 요약

### Phase 2 sub-feature 별 core.py LOC 감소

| Phase | Feature | 시작 LOC | 종료 LOC | 감소 |
|-------|---------|---------|---------|------|
| Phase 2-a | core-http-split | 6,874 | 6,400 | **−474** |
| Phase 2-b | core-renderer-split | 6,400 | 5,418 | **−982** |
| Phase 2-c | core-dashboard-asset-split | 5,418 | 3,284 | **−2,134** |
| **Phase 2 합산** | | **6,874** | **3,284** | **−3,590** |

### Phase 1+2 누적

| Phase | Feature | 시작 LOC | 종료 LOC | 감소 |
|-------|---------|---------|---------|------|
| Phase 1 | core-decomposition | **7,940** | 6,874 | −1,066 |
| Phase 2 | (3개 sub-feature) | 6,874 | **3,284** | −3,590 |
| **Phase 1+2 합산** | | **7,940** | **3,284** | **−4,656** |

### 신규 모듈/파일 목록

**Phase 1 (core-decomposition)** — `scripts/monitor_server/`:
- `api.py` — 8개 API 함수 (state/graph/task-detail/merge-status)
- `caches.py` — `_TTLCache`, `_SIGNALS_CACHE`, `_GRAPH_CACHE`, etag 캐시
- `signals.py` — `scan_signals`, `scan_signals_cached`
- `panes.py` — `list_tmux_panes`, `_parse_pane_line`
- `workitems.py` — `WorkItem`, `PhaseEntry`, `scan_work_items`
- `etag_cache.py` — `_compute_etag`, `_check_if_none_match`

**Phase 2-a (core-http-split)** — `scripts/monitor_server/`:
- `handlers.py` — `Handler` 클래스 (라우팅 dispatcher)
- `handlers_pane.py` — `_handle_pane_html`, `_handle_pane_api`
- `handlers_graph.py` — `_handle_graph_api`
- `handlers_state.py` — `_handle_api_state`, `_handle_api_task_detail`

**Phase 2-b (core-renderer-split)** — `scripts/monitor_server/renderers/`:
- `__init__.py` — 패키지 re-export
- `_util.py` — `_phase_label`, `_phase_data_attr`, `_fmt_hms`, 공용 유틸
- `activity.py` — `_section_activity`, `_render_activity_row` 등
- `depgraph.py` — `_section_dep_graph`, `render_legend`
- `features.py` — `_section_features`
- `filterbar.py` — `_section_filter_bar`
- `header.py` — `_section_header`, `_section_sticky_header`
- `history.py` — `_section_phase_history`
- `kpi.py` — `_section_kpi`, `_kpi_counts`, `_kpi_spark_svg` 등
- `panel.py` — `_render_pane_html`, `_render_pane_json`, `_render_pane_html` (pane HTML)
- `subagents.py` — `_section_subagents`, `_render_subagent_row`
- `tabs.py` — `_section_subproject_tabs`
- `taskrow.py` — `_render_task_row_v2`, `_trow_data_status`
- `team.py` — `_section_team`, `_render_pane_row`
- `wp.py` — `_section_wp_cards`

**Phase 2-c (core-dashboard-asset-split)** — `scripts/monitor_server/static/`:
- `dashboard.css` (42.4 KB) — DASHBOARD_CSS 인라인 상수 외부화 (1,210 LOC)
- `dashboard.js` (21.4 KB) — `_DASHBOARD_JS` 인라인 상수 외부화 (545 LOC)
- `pane.css` (1.0 KB) — `_PANE_CSS` 외부화 (24 LOC)
- `pane.js` (619 B) — `_PANE_JS` 외부화 (18 LOC)
- `task_panel.css` (6.4 KB) — `_task_panel_css()` 외부화 (103 LOC)
- `task_panel.js` (12.2 KB) — `_TASK_PANEL_JS` 외부화 (277 LOC)

(기존 `style.css`/`app.js` — stale 보류 유지, 본 문서 §3 참조)

### 차기 권고

**core-decomposition 완전 종결 선언**: Phase 1+2 완료로 `core.py` 7,940 → 3,284 LOC (−58.6%).
NF-03(≤ 800 LOC) 기준 대비 여전히 4배 초과이지만, 모놀리스의 핵심 문제였던
"충돌 자석 + 시각 회귀 자석" 는 각각 renderers/ 분리 + static/ 외부화로 해소됨.

Phase 3 진행 가능하나 필수는 아님. 진행 시 권고 대상:
- `core.py` 내 `_load_static_text()` 호출 단일 블록 통합 (현재 4개 위치 분산)
- `test_monitor_critical_color.py`/`test_monitor_phase_tokens.py`를 `get_static_bundle()` 경유로 전환 → stale `style.css`/`app.js` 삭제 가능
- 테스트 shim 8개의 legacy regex-parse fallback 코드 제거 (현재 dead code)
- `handlers.py::_STATIC_ASSET_WHITELIST`를 `{"style.css", "app.js"}` → 번들 명칭 기반으로 정비

## 비고

- 케이스 분류 (SKILL.md 단계 3 참조): **A (리팩토링 성공)**
- refactor 단계 실질 정리 커밋은 1건 (LOC 주석 정정). build 단계에서 code quality가 이미 충분히 정돈됨.
- stale 파일 삭제를 보류한 이유는 테스트 영향도 분석에 따른 의도적 결정이며, 향후 테스트 리팩토링 후 삭제 가능.
- Pylance `액세스하지 않았습니다` 진단은 core-decomposition facade 비용으로 허용 (core-decomposition:refactor-05 phase2-decision.md 참조).
