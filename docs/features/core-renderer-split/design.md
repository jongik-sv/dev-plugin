# core-renderer-split: 설계

> Phase 2-b — `core-decomposition` Phase 1 + `core-http-split` (Phase 2-a) 이후
> core.py 잔여 6,400 LOC 중 **HTML renderer 함수 19개**(본문 ~1,036 LOC + 관련
> helper/상수 포함 시 ~1,200 LOC)를 `scripts/monitor_server/renderers/`
> 서브패키지로 이관한다.

## 요구사항 확인

- `scripts/monitor_server/core.py` (6,400 LOC) 에서 HTML renderer 19개를
  `monitor_server/renderers/` 서브패키지로 이관한다. core.py LOC ≤ **5,500**
  (≥ 900 LOC 감소) 달성.
- 기존 facade 계약 유지: `import monitor_server.core as core` → `core._section_*`
  / `core._render_*` / `core._SECTION_EYEBROWS` 등 심볼 접근 가능해야 한다.
- 5개 신규 모듈 생성: `header.py` / `kpi.py` / `features.py` / `history.py` /
  `tabs.py`. 각 모듈 ≤ 800 LOC (NF-03 준수, 실측 예측 모두 ≤ 100 LOC이므로
  여유).
- 인라인 자산(`DASHBOARD_CSS`, `_DASHBOARD_JS`, `_PANE_CSS`, `_task_panel_css`,
  `_task_panel_js`)은 **본 feature에서 건드리지 않는다** (Phase 2-c 범위).
  renderer가 이들을 참조하는 경우는 0건이므로(아래 §의존 그래프 참조), 이관 중
  새로 참조가 추가되어서도 안 된다.

## 타겟 앱

- **경로**: N/A (단일 앱 — `scripts/monitor_server/` 패키지 직접 수정).
- **근거**: 내부 리팩토링. URL·UI·API 계약 변경 없음.

## 구현 방향

1. **baseline 기록**
   - `rtk proxy python3 -m pytest -q scripts/ --tb=no` 결과를
     `docs/features/core-renderer-split/baseline.txt`에 저장 (pre-existing
     2 failed 확인: `test_monitor_task_expand_ui.py::test_initial_right_negative`,
     `test_platform_smoke.py::test_pane_polling_interval`).
   - dashboard HTML baseline: `monitor-launcher.py`로 7321 포트 기동 후
     `curl -sS http://127.0.0.1:7321/ | md5sum`과 `/pane/{sample-id}` md5 저장.
2. **현재 구조의 핵심 발견**
   - `renderers/wp.py`, `team.py`, `subagents.py`, `activity.py`, `depgraph.py`,
     `filterbar.py`, `panel.py`는 이미 **독립 본문**을 갖고 있지만,
     `render_dashboard`는 **core.py의 로컬 본문을 호출**한다 (is-identity
     비교에서 False — wp/team/subagents/activity/depgraph/filterbar 모두 별도
     객체). 즉 현재 core.py ↔ renderers/ 사이에 **무성 중복 구현**이 존재.
   - `renderers/taskrow.py`만 "선-shim"으로 `core._render_task_row_v2` /
     `_phase_label` / `_phase_data_attr` / `_trow_data_status`를 재-export 중
     (is-identity True).
   - `renderers/_util.py`는 26개 core 심볼을 이미 재-export 중.
3. **이관 전략(3-단계)**
   - **C1 단계**: 기존 renderers/ 모듈이 이미 보유한 7개 함수에 대해
     **core.py 본문을 제거하고 facade re-export로 전환**. 이는 중복 제거이므로
     동작 변경이 사실상 0 (render_dashboard 호출 경로만 core 로컬 → renderers
     모듈로 스위치). 커밋당 1 모듈씩, 커밋 간 md5 baseline 비교 필수.
   - **C2 단계**: core.py에만 있는 12개 renderer를 신규/기존 모듈로 이관.
     각 커밋 1~2개 함수. byte-identical 검증 + pytest 그린.
   - **C3 단계**: core.py facade 정리 — `from .renderers.* import *` 재-export
     블록을 상단에 단일 섹션으로 통합, 원본 블록 삭제 확인, TSK 주석 breadcrumb
     추가(추적성).
4. **facade 계약**: core.py는 `_section_*`·`_render_*`·`_SECTION_EYEBROWS`·
   `_KPI_LABELS`·`_KPI_ORDER`·`_KPI_V3_SUFFIX`·`_SPARK_COLORS`·
   `_TOO_MANY_PANES_THRESHOLD`·`_PANE_PREVIEW_LINES`·`_SUBAGENT_INFO`·
   `_PHASES_SECTION_LIMIT` 등 외부(render_dashboard + 테스트 monkey-patch)에
   노출된 모든 심볼을 재-export로 계속 유지한다.
5. **Helper 심볼 처리**: renderer가 의존하는 26개 helper는 모두 core.py에
   남는다 (이미 `renderers/_util.py`가 core 경유로 재-export 중). 본 feature는
   helper를 renderers 쪽으로 **이관하지 않는다** — helper 자체는 core.py의
   상태 관리·스냅샷 생성 로직과 결합된 범용 함수이므로 범위 밖. renderer 본문만
   이관.

핵심 패턴: `core-http-split`에서 검증된 방식 계승 — renderer → `_util.py` →
`core`(facade) 체인 유지, 순환 참조 없음.

## 실측 재확인

### core.py 내 19개 renderer 위치 및 LOC

| 심볼 | core.py 라인 | LOC | 목적지 모듈 | 현재 상태 |
|------|-------------|-----|-------------|-----------|
| `_section_wrap` | L1973 | 20 | `renderers/_util.py` (확장) | core-only |
| `_section_header` | L1998 | 84 | `renderers/header.py` (**신규**) | core-only |
| `_section_sticky_header` | L2238 | 27 | `renderers/header.py` | core-only |
| `_section_kpi` | L2265 | 86 | `renderers/kpi.py` (**신규**) | core-only |
| `_render_task_row_v2` | L2566 | 90 | `renderers/taskrow.py` (본문 이전) | **shim 존재** |
| `_section_wp_cards` | L2742 | 133 | `renderers/wp.py` (이미 본문 존재) | **중복 구현** |
| `_section_features` | L2875 | 16 | `renderers/features.py` (**신규**) | core-only |
| `_render_pane_row` | L2993 | 48 | `renderers/team.py` (확장) | core-only |
| `_section_team` | L3041 | 70 | `renderers/team.py` (이미 본문 존재) | **중복 구현** |
| `_render_subagent_row` | L3111 | 24 | `renderers/subagents.py` (확장) | core-only |
| `_section_subagents` | L3135 | 21 | `renderers/subagents.py` (이미 본문 존재) | **중복 구현** |
| `_section_phase_history` | L3170 | 67 | `renderers/history.py` (**신규**) | core-only |
| `_section_dep_graph` | L3242 | 77 | `renderers/depgraph.py` (이미 본문 존재) | **중복 구현** |
| `_render_arow` | L3448 | 40 | `renderers/activity.py` (확장) | core-only |
| `_section_live_activity` | L3488 | 32 | `renderers/activity.py` (이미 본문 존재) | **중복 구현** |
| `_section_subproject_tabs` | L4172 | 39 | `renderers/tabs.py` (**신규**) | core-only |
| `_section_filter_bar` | L4211 | 69 | `renderers/filterbar.py` (이미 본문 존재) | **중복 구현** |
| `_render_pane_html` | L4714 | 45 | `renderers/panel.py` (확장) | core-only |
| `_render_pane_json` | L4759 | 8 | `renderers/panel.py` | core-only |
| **합계** | | **996** | | |

### 신규 5개 모듈의 예상 LOC (NF-03 예산)

| 모듈 | 포함 함수 | 본문 LOC | 예상 최종 LOC (docstring+import 포함) |
|------|-----------|---------|--------------------------------------|
| `header.py` | `_section_header` + `_section_sticky_header` | 84 + 27 = 111 | ~140 |
| `kpi.py` | `_section_kpi` | 86 | ~110 |
| `features.py` | `_section_features` | 16 | ~45 |
| `history.py` | `_section_phase_history` | 67 | ~95 |
| `tabs.py` | `_section_subproject_tabs` | 39 | ~70 |

모두 ≤ 800 LOC (NF-03) 여유 있게 준수.

### 심볼 의존 그래프 (각 renderer가 사용하는 core 심볼)

| Renderer | 의존 core 심볼 | 인라인 자산 참조 |
|----------|---------------|-----------------|
| `_section_wrap` | `_SECTION_EYEBROWS` | 없음 |
| `_section_header` | `_esc`, `_refresh_seconds` | 없음 |
| `_section_sticky_header` | `_esc`, `_refresh_seconds` | 없음 |
| `_section_kpi` | `_KPI_LABELS`, `_KPI_ORDER`, `_KPI_V3_SUFFIX`, `_SPARK_COLORS`, `_kpi_counts`, `_kpi_spark_svg`, `_spark_buckets` | 없음 |
| `_render_task_row_v2` | `_MAX_ESCALATION`, `_build_state_summary_json`, `_clean_title`, `_encode_state_summary_attr`, `_esc`, `_format_elapsed`, `_phase_data_attr`, `_phase_label`, `_retry_count`, `_trow_data_status` | 없음 |
| `_section_wp_cards` | `_empty_section`, `_group_preserving_order`, `_merge_badge`, `_render_task_row_v2`, `_resolve_heading`, `_section_wrap`, `_wp_busy_indicator_html`, `_wp_card_counts`, `_wp_donut_style`, `_wp_donut_svg` | 없음 |
| `_section_features` | `_empty_section`, `_render_task_row_v2`, `_resolve_heading`, `_section_wrap` | 없음 |
| `_render_pane_row` | `_TOO_MANY_PANES_THRESHOLD`, `_esc`, `_pane_attr` | 없음 |
| `_section_team` | `_PANE_PREVIEW_LINES`, `_SUBAGENT_INFO`, `_TOO_MANY_PANES_THRESHOLD`, `_empty_section`, `_group_preserving_order`, `_iter_flat_entry_modules`(*), `_pane_attr`, `_pane_last_n_lines`, `_render_pane_row`, `_resolve_heading`, `_section_wrap` | 없음 |
| `_render_subagent_row` | (literal-only, no deps) | 없음 |
| `_section_subagents` | `_SUBAGENT_INFO`, `_render_subagent_row`, `_resolve_heading`, `_section_wrap` | 없음 |
| `_section_phase_history` | `_PHASES_SECTION_LIMIT`, `_empty_section`, `_esc`, `_status_class_for_phase` | 없음 |
| `_section_dep_graph` | `_t`, `_plugin_root`(env+path), `Path` | 없음 |
| `_render_arow` | `_arow_data_to`, `_esc`, `_event_to_sig_kind`, `_fmt_elapsed_short`, `_fmt_hms`, `_phase_label_history` | 없음 |
| `_section_live_activity` | `_live_activity_details_wrap`, `_live_activity_rows`, `_render_arow`, `_resolve_heading` | 없음 |
| `_section_subproject_tabs` | `_tab` (inner helper) | 없음 |
| `_section_filter_bar` | `_esc`, `_normalize_lang` | 없음 |
| `_render_pane_html` | (pane dict serialization only) | 없음 |
| `_render_pane_json` | `json.dumps` (stdlib only) | 없음 |

**핵심 발견**:
- **인라인 CSS/JS 상수(`DASHBOARD_CSS`, `_DASHBOARD_JS`, `_PANE_CSS`,
  `_task_panel_css`, `_task_panel_js`) 참조는 19개 renderer 어디에도 없다.**
  이들은 `render_dashboard` + `get_static_bundle` + `_task_panel_js()`
  (self-reference) 에서만 소비된다. 따라서 본 feature는 인라인 자산을 건드릴
  필요가 없으며, renderer 이관 중 **새로 참조를 도입해서도 안 된다**.
- `_section_team`의 `_iter_flat_entry_modules`(*)는 현재 core.py의 mock
  pane test hook — `renderers/team.py`는 이미 이것 없이 동작하므로 이관 시
  제거 가능(기존 renderers/team.py 본문 유지).
- 모든 helper는 `_util.py`에서 이미 재-export 중이거나 추가 재-export가
  필요하다. §4에서 추가 필요 항목을 명시한다.

### `_util.py`에 추가 필요한 재-export 심볼

현재 `_util.py`가 재-export하지 않는 심볼 중 신규 5개 모듈이 필요로 하는 것:

| 심볼 | core.py 위치 | 필요 모듈 |
|------|-------------|-----------|
| `_refresh_seconds` | L1800 | `header.py` |
| `_SECTION_EYEBROWS` | L1950 | `_section_wrap` (이미 `_util.py`에 `_section_wrap` 재-export 있음 — 본문을 `_util.py`로 옮기거나 유지) |
| `_KPI_LABELS`, `_KPI_ORDER`, `_KPI_V3_SUFFIX`, `_SPARK_COLORS` | L2086–L2262 | `kpi.py` |
| `_kpi_counts`, `_spark_buckets`, `_kpi_spark_svg` | L2108/L2164/L2213 | `kpi.py` |
| `_PHASES_SECTION_LIMIT` | L363 | `history.py` |
| `_status_class_for_phase` | L3156 | `history.py` |
| `_fmt_hms`, `_fmt_elapsed_short`, `_event_to_sig_kind`, `_arow_data_to` | L3346/L3351/L3374/L3434 | `activity.py` (확장 부분) |
| `_phase_label_history` | L3520 (이미 `activity.py`에 본문 존재) | N/A (이미 이관됨) |

→ `_util.py`는 **추가 13~15개 재-export** 필요. 공개 심볼 목록만 확장되며
기존 심볼은 제거하지 않는다.

## 파일 계획

| 파일 경로 | 역할 | 신규/수정 |
|-----------|------|-----------|
| `docs/features/core-renderer-split/baseline.txt` | pytest baseline + HTML md5 | 신규 |
| `scripts/monitor_server/renderers/_util.py` | 13~15개 심볼 추가 재-export (`_refresh_seconds`, `_SECTION_EYEBROWS`, KPI 계열, `_PHASES_SECTION_LIMIT`, `_status_class_for_phase`, activity helper 4개 등) | 수정 |
| `scripts/monitor_server/renderers/header.py` | `_section_header` + `_section_sticky_header` | **신규** |
| `scripts/monitor_server/renderers/kpi.py` | `_section_kpi` + KPI 상수/helper import | **신규** |
| `scripts/monitor_server/renderers/features.py` | `_section_features` | **신규** |
| `scripts/monitor_server/renderers/history.py` | `_section_phase_history` | **신규** |
| `scripts/monitor_server/renderers/tabs.py` | `_section_subproject_tabs` | **신규** |
| `scripts/monitor_server/renderers/taskrow.py` | 본문 이전 완료 (선-shim → 실제 함수). `_render_task_row_v2` 본문 복사 + import 재배선 | 수정 |
| `scripts/monitor_server/renderers/team.py` | `_render_pane_row` 추가 이관 | 수정 |
| `scripts/monitor_server/renderers/subagents.py` | `_render_subagent_row` 추가 이관 | 수정 |
| `scripts/monitor_server/renderers/activity.py` | `_render_arow` + helper 4개 이관 | 수정 |
| `scripts/monitor_server/renderers/panel.py` | `_render_pane_html` + `_render_pane_json` 추가 이관 | 수정 |
| `scripts/monitor_server/renderers/__init__.py` | 5개 신규 모듈 re-export 추가 | 수정 |
| `scripts/monitor_server/core.py` | renderer 원본 블록 삭제, facade re-export로 전환, breadcrumb 주석 | 수정 |

## 진입점 (Entry Points)

N/A (내부 리팩토링 — 사용자 UI·URL 변경 없음).

## 주요 구조

### 커밋 단위 분할 계획

> `[core-renderer-split:refactor-0N]` 태그 접두사 사용. `core-decomposition`
> / `core-http-split`과 일관된 규칙.

| 커밋 | 제목 | 범위 | core.py LOC 변화 |
|------|------|------|-------------------|
| **C0-1 (baseline)** | `docs(core-renderer-split): baseline 기록` | `docs/features/core-renderer-split/baseline.txt` 신규. pytest + md5 저장 | — |
| **C1-1** | `refactor(monitor_server): _section_wp_cards 원본 제거 + facade 전환` | core.py L2742–L2874 본문 삭제, `from .renderers.wp import _section_wp_cards` re-export 블록 추가. render_dashboard 호출 지점은 동일 이름이라 불변 | −133 |
| **C1-2** | `refactor(monitor_server): _section_team + _render_pane_row 이관` | `_render_pane_row` 본문을 `renderers/team.py`로 복사 (기존 import에 추가), core.py L2993–L3110 두 함수 원본 삭제 + re-export 블록 | −118 |
| **C1-3** | `refactor(monitor_server): _section_subagents + _render_subagent_row 이관` | `_render_subagent_row` 본문을 `renderers/subagents.py`로 복사, core.py L3111–L3155 원본 삭제 + re-export | −45 |
| **C1-4** | `refactor(monitor_server): _section_live_activity + _render_arow + helper 4개 이관` | `_render_arow` + `_fmt_hms` + `_fmt_elapsed_short` + `_event_to_sig_kind` + `_arow_data_to`를 `renderers/activity.py`로 복사. core.py L3346–L3519 중 해당 심볼만 원본 삭제 + re-export. 동시에 `_util.py`에 재-export 추가 (다른 renderer가 쓰지 않는다면 생략) | −80 |
| **C1-5** | `refactor(monitor_server): _section_dep_graph + _section_filter_bar 이관` | 두 함수의 core.py 원본 삭제 + facade re-export (본문 이미 renderers 측 존재) | −146 |
| **C2-1** | `refactor(monitor_server): header 모듈 신설 + _section_header/_section_sticky_header 이관` | `renderers/header.py` 신규 작성(_util에서 `_esc`/`_refresh_seconds` import), core.py L1998–L2080 + L2238–L2252 원본 삭제 + re-export. `_util.py`에 `_refresh_seconds` 재-export 추가 | −111 |
| **C2-2** | `refactor(monitor_server): kpi 모듈 신설 + _section_kpi 이관` | `renderers/kpi.py` 신규. KPI 상수 4개(`_KPI_LABELS`/`_KPI_ORDER`/`_KPI_V3_SUFFIX`/`_SPARK_COLORS`) + helper 3개(`_kpi_counts`/`_spark_buckets`/`_kpi_spark_svg`)를 `_util.py`에 재-export 추가. core.py L2265–L2349 원본 삭제 + re-export | −86 |
| **C2-3** | `refactor(monitor_server): features 모듈 신설 + _section_features 이관` | `renderers/features.py` 신규. core.py L2875–L2890 원본 삭제 + re-export | −16 |
| **C2-4** | `refactor(monitor_server): history 모듈 신설 + _section_phase_history 이관` | `renderers/history.py` 신규. `_util.py`에 `_PHASES_SECTION_LIMIT`, `_status_class_for_phase` 재-export 추가. core.py L3170–L3236 원본 삭제 + re-export | −67 |
| **C2-5** | `refactor(monitor_server): tabs 모듈 신설 + _section_subproject_tabs 이관` | `renderers/tabs.py` 신규. core.py L4172–L4210 원본 삭제 + re-export | −39 |
| **C2-6** | `refactor(monitor_server): taskrow 본문 이전 (선-shim → 실체)` | `renderers/taskrow.py`의 선-shim을 제거하고 `_render_task_row_v2` 본문을 복사. core.py L2566–L2654 원본 삭제 + re-export. `_util.py`의 `_render_task_row_v2` 재-export 방향 재검토(필요 시 core 경유 유지 — `_util.py → core` 루프 발생 안 함, C2-6 커밋에서 renderers/wp.py 등이 `from .taskrow import _render_task_row_v2` 직접 import 중이므로 수정 불필요) | −90 |
| **C2-7** | `refactor(monitor_server): _render_pane_html + _render_pane_json 이관` | `renderers/panel.py`에 두 함수 추가. core.py L4714–L4766 원본 삭제 + re-export | −53 |
| **C3-1 (cleanup)** | `refactor(monitor_server/core): renderer facade 블록 통합 + breadcrumb` | core.py 상단의 `from .renderers.* import *` 블록을 한 섹션으로 정리. 각 원래 라인 위치에 `# moved to monitor_server.renderers.X` breadcrumb 유지 (core-decomposition refactor-02 원칙). `__init__.py`에 신규 5개 모듈 추가 | 소폭 감소 (주석/공백 정리) |

**총 감소 예상**: 133 + 118 + 45 + 80 + 146 + 111 + 86 + 16 + 67 + 39 + 90 + 53
= **984 LOC** → core.py 6,400 → ~5,416 (수용 기준 ≤ 5,500 달성).

### facade 재-export 블록 (C3-1 종료 시점, core.py 상단)

```python
# === renderer facade re-exports (core-renderer-split Phase 2-b) ===
# render_dashboard 와 외부 테스트가 core._section_* / core._render_* 로 접근하므로
# 동일 이름으로 재-export 한다. 본문은 monitor_server/renderers/{module}.py 소관.
from .renderers.header import _section_header, _section_sticky_header  # noqa: F401
from .renderers.kpi import _section_kpi  # noqa: F401
from .renderers.features import _section_features  # noqa: F401
from .renderers.history import _section_phase_history  # noqa: F401
from .renderers.tabs import _section_subproject_tabs  # noqa: F401
from .renderers.taskrow import (  # noqa: F401
    _render_task_row_v2, _phase_label, _phase_data_attr, _trow_data_status,
)
from .renderers.wp import _section_wp_cards  # noqa: F401
from .renderers.team import _section_team, _render_pane_row  # noqa: F401
from .renderers.subagents import _section_subagents, _render_subagent_row  # noqa: F401
from .renderers.activity import (  # noqa: F401
    _section_live_activity, _render_arow, _phase_label_history,
)
from .renderers.depgraph import _section_dep_graph, _build_graph_payload  # noqa: F401
from .renderers.filterbar import _section_filter_bar  # noqa: F401
from .renderers.panel import _render_pane_html, _render_pane_json, _drawer_skeleton  # noqa: F401
# === /renderer facade ===
```

### 각 모듈의 import 헤더 패턴 (예시)

`renderers/header.py`:
```python
"""monitor_server.renderers.header — cmdbar + sticky header SSR 렌더러."""
from __future__ import annotations
from urllib.parse import quote

from ._util import _esc, _refresh_seconds
```

`renderers/kpi.py`:
```python
"""monitor_server.renderers.kpi — KPI 섹션 SSR 렌더러."""
from __future__ import annotations
from ._util import (
    _section_wrap,
    _KPI_LABELS, _KPI_ORDER, _KPI_V3_SUFFIX, _SPARK_COLORS,
    _kpi_counts, _spark_buckets, _kpi_spark_svg,
)
# `datetime`은 helper 내부에서 이미 사용되므로 kpi에서는 직접 import 불필요
```

`renderers/history.py`, `tabs.py`, `features.py`도 동일 패턴.

## 데이터 흐름

HTTP 요청 → `MonitorHandler` → `render_dashboard(model, lang, subproject)`
(core.py 잔류) → 19개 renderer 호출 (facade를 거쳐 renderers/* 본문 실행)
→ HTML 문자열 조립 → `_send_html_response` → 클라이언트.

이관 후에도 **바이트 단위로 동일한 HTML** 을 반환해야 한다 (§리스크 §QA).

## 설계 결정 (대안이 있는 경우만)

### helper 이관 여부

- **결정**: helper(26개)는 core.py에 **남긴다**. `_util.py`의 재-export 목록만
  확장한다.
- **대안**: `_esc`·`_refresh_seconds`·`_group_preserving_order` 등을 `_util.py`
  본문으로 이전해 renderers 자족화.
- **근거**: 이 helper들은 `render_dashboard`·`_build_state_snapshot`·api.py
  등 non-renderer 소비자도 다수 있고, 본 feature 범위는 "renderer 이관"이다.
  범위 밖 이관을 끼워 넣으면 diff가 커져 시각 회귀 분리 검증이 어려워진다.
  Phase 2-c 또는 별도 cleanup feature에서 재평가.

### 중복 구현 제거 방식 (C1 단계)

- **결정**: core.py 본문 **삭제 후 facade re-export**. renderers/* 본문을
  SSOT로 승격.
- **대안 A**: core.py 본문 유지, renderers/* 본문 삭제 후 core 경유 shim.
- **대안 B**: 양쪽 유지, render_dashboard만 renderers/* 호출로 전환.
- **근거**: core-decomposition/core-http-split에서 동일하게 "신규 모듈이 SSOT,
  core는 facade" 원칙을 채택했다. 대안 A는 목표(core LOC 감소)에 역행. 대안 B는
  중복을 영구화. **renderers/* 본문이 이미 테스트 통과한 상태**이므로(`__init__`
  에서 import 검증됨) SSOT 승격 비용이 최소.

### 인라인 자산 지연 import 전략 (명시적 예방)

- **결정**: renderer에서 `DASHBOARD_CSS`·`_DASHBOARD_JS`·`_PANE_CSS`·
  `_task_panel_css`·`_task_panel_js` **참조 금지**. 만약 이관 중 참조가
  필요해지면 `from monitor_server import core as _c; _c.DASHBOARD_CSS` 형태
  **함수 내부 지연 import**만 허용.
- **대안**: `_util.py`에 인라인 자산 재-export 추가.
- **근거**: 실측에서 19개 renderer 모두 참조 0건 확인 → 재-export 자체가 불필요.
  Phase 2-c에서 인라인 자산을 static 파일로 분리할 때 renderer가 의존을 갖지
  않는 것이 정리 비용을 낮춘다.

### 커밋 순서 (C1 먼저, C2 나중)

- **결정**: C1(중복 제거, 7건)을 C2(신규 모듈 생성, 12건)보다 먼저.
- **대안**: 신규 모듈 먼저 → 중복 제거 나중.
- **근거**: C1은 "이미 작동하는 renderers/* 본문을 SSOT로 승격" 작업이라
  시각 회귀 리스크가 가장 낮다(renderer 코드가 이미 테스트된 상태). 먼저
  수행하여 facade 패턴의 건전성을 선검증하고, 검증된 패턴을 C2에 적용한다.
  rollback 시에도 C1이 앞쪽에 있을수록 감당 범위 좁음.

## 선행 조건

- `core-decomposition` Phase 1 완료 (commit `caed787`) — 확인 완료.
- `core-http-split` Phase 2-a 완료 (spec.md 배경 `443722f` 언급) — 확인 완료
  (git log: `6e56aab` / `94204a3` 등 refactor commit들이 HEAD 근처).
- `renderers/` 서브패키지 존재 및 현재 LOC 855 — 확인 완료 (wc -l).
- `renderers/_util.py` 가 `core`·`api` 경유 재-export로 **순환 없이 로드** — 확인 완료 (`_util.py` 파일 15~55행).
- `monitor-launcher.py` / `monitor-server.py` 기동 가능 (baseline md5 측정용).

## 리스크

- **HIGH — 시각 회귀(HTML byte drift)**: renderer 이관 중 whitespace·따옴표·
  속성 순서가 1 byte라도 달라지면 UI 회귀. **방어**: 각 커밋 직후
  `curl http://127.0.0.1:7321/?subproject=all | md5sum` 을 baseline과 비교.
  Δ ≠ 0이면 즉시 `git revert`. md5 비교는 `_section_*` 렌더링 결과가
  baseline 기록 시점과 **정확히 같은 순서/개행/공백**으로 생성됨을 검증한다.
  spec.md §리스크의 byte-identical 요구를 충족.
- **HIGH — facade 누락**: core.py에서 본문을 삭제했으나 re-export를 빠뜨리면
  `core._section_X` monkey-patch 테스트가 즉시 실패. **방어**: 각 커밋에
  `python3 -c "import monitor_server.core as c; assert hasattr(c, '_section_X')"`
  무결성 스크립트 실행. `references/state-machine.json` 제외한 모든 외부 소비자
  심볼을 §facade 블록에 나열하여 누락 방지.
- **HIGH — 테스트 lock (설계 회귀 테스트)**: `feedback_design_regression_test_lock.md`
  에 기록된 pre-existing 2 failed 중 `test_monitor_task_expand_ui.py` 가
  옛 CSS 리터럴을 단언하므로 renderer 이관이 이 테스트를 추가로 깨서는 안 된다.
  **방어**: baseline 대비 failed count가 늘어나지 않음을 모든 커밋에서 확인.
  layout-skeleton(클래스명) 외 색상/마진 단언이 늘어나면 test 수정이 아닌 원인
  분석(renderer 본문 차이)을 먼저 수행.
- **MEDIUM — `_util.py` 재-export 누락**: 신규 5개 모듈이 의존하는 13~15개
  심볼을 `_util.py`에 추가하지 않으면 `ImportError`로 import 자체 실패.
  **방어**: 각 C2 커밋에서 `_util.py` 수정을 **같은 커밋**에 포함. 커밋 분리
  금지. pytest가 import 실패를 감지하므로 CI 미가동 환경에서도 검출 가능.
- **MEDIUM — `_iter_flat_entry_modules` 처리**: core.py `_section_team`은
  mock pane 테스트 훅으로 `_iter_flat_entry_modules()` 를 참조하지만, 이미
  renderers/team.py 본문은 이것 없이 작동한다. C1-2에서 core 본문을 삭제할 때
  이 차이를 검증(렌더 결과 md5 비교)하여 회귀 없음 확인. 만약 테스트가 이
  훅을 직접 호출한다면 helper를 별도 유지.
- **MEDIUM — `_util.py` 순환 위험**: 현재 `_util.py`는 `core`와 `api`를
  import한다. 여기에 추가 심볼을 얹는 것은 원칙적으로 동일 패턴이므로 순환
  신규 도입은 아니다. 다만 kpi.py → `_util.py` → `core` → `renderers.kpi`
  재-export 루프는 Python의 지연 바인딩 덕에 성립한다 (core 로드가 끝난 뒤
  renderers 패키지 `__init__`에서 kpi를 import). **방어**: `__init__.py`의
  import 순서에서 kpi/history/tabs/header/features 를 기존 순서 뒤에 두고
  import 실패 시 pytest `collect_only` 로 조기 감지.
- **LOW — docstring/주석 변동**: core.py 본문 삭제 시 breadcrumb로 남길
  주석은 **한 줄**로 제한. core-decomposition refactor-02 원칙 재사용
  ("동작 기술 주석은 남기고, 위치 참조만 하는 주석은 삭제 또는 한 줄로 압축").
- **LOW — Pylance 경고**: core-decomposition / core-http-split 에서 누적된
  28건 + 새 facade 재-export로 인한 추가 경고 예상. `# type: ignore` 주석은
  최소 사용. feature 완료 후 증감 측정만 기록.

## QA 체크리스트

dev-test 단계에서 검증할 항목. 각 항목은 pass/fail로 판정 가능해야 한다.

### baseline (C0-1)

- [ ] `rtk proxy python3 -m pytest -q scripts/ --tb=no` 실행 후
  `docs/features/core-renderer-split/baseline.txt` 에 저장. exit 0, failed=2
  (pre-existing), passed=1997, skipped=176 동일 확인.
- [ ] `monitor-launcher.py --port 7321 --docs docs/monitor-v5` 기동 후
  `curl -sS http://127.0.0.1:7321/ | md5sum`·`/api/state`·`/api/graph`·
  `/pane/{sample-id}` md5를 `baseline.txt`에 함께 기록.

### C1 단계 (중복 제거, 5 커밋)

- [ ] C1-1 (wp): pytest 그린, HTML md5 Δ = 0, `core._section_wp_cards is
  renderers.wp._section_wp_cards` (is-identity) **True** 로 전환 확인.
- [ ] C1-2 (team + pane_row): pytest 그린, md5 Δ = 0, pane preview 라인 수
  동일 확인(스냅샷 비교).
- [ ] C1-3 (subagents + row): pytest 그린, md5 Δ = 0, agent-pool 시그널 0건일
  때 empty-state HTML 동일 확인.
- [ ] C1-4 (activity + helpers): pytest 그린, md5 Δ = 0, activity 20건 제한
  준수 확인.
- [ ] C1-5 (depgraph + filter_bar): pytest 그린, md5 Δ = 0, `/api/graph` 200,
  legend/stat chip HTML 동일 확인.

### C2 단계 (신규 모듈 5개 + 추가 이관 2건)

- [ ] C2-1 (header.py): pytest 그린, md5 Δ = 0, lang=ko/en 양쪽 렌더 결과
  baseline 일치. `core._section_header is renderers.header._section_header`
  True.
- [ ] C2-2 (kpi.py): pytest 그린, md5 Δ = 0, sparkline SVG 렌더 동일 확인.
  `_KPI_ORDER` 상수가 facade 경유로 여전히 `hasattr(core, '_KPI_ORDER')`.
- [ ] C2-3 (features.py): pytest 그린, md5 Δ = 0, features=0일 때 empty-state
  메시지 동일.
- [ ] C2-4 (history.py): pytest 그린, md5 Δ = 0, phase history 10건 제한
  (`_PHASES_SECTION_LIMIT`) 동일 적용.
- [ ] C2-5 (tabs.py): pytest 그린, md5 Δ = 0, subproject 탭 순서·클래스 동일.
- [ ] C2-6 (taskrow 본문 이전): pytest 그린, md5 Δ = 0, 선-shim 시기의
  `core._render_task_row_v2 is renderers.taskrow._render_task_row_v2` True
  관계 유지(함수 객체 동일성은 본문 이전 후에도 shim 제거 + re-export 로
  자동 유지됨 — `from .renderers.taskrow import _render_task_row_v2` 가
  동일 객체 바인딩).
- [ ] C2-7 (panel `_render_pane_html/json`): pytest 그린, md5 Δ = 0,
  `/pane/{id}` 200 + HTML body 동일, `/api/pane/{id}` JSON 동일(jq 비교).

### C3 단계 (cleanup)

- [ ] core.py 상단 facade 블록이 하나의 섹션으로 정리됨 (wc -l 비교).
- [ ] breadcrumb 주석이 한 줄 이내로 유지됨 (동작 기술 주석 0건 삭제 확인).
- [ ] `renderers/__init__.py`에 신규 5개 모듈 추가 완료, `__all__` 업데이트.

### 최종 수용 기준 (spec.md §수용 기준)

- [ ] `wc -l scripts/monitor_server/core.py` ≤ **5,500**.
- [ ] `wc -l scripts/monitor_server/renderers/*.py` 합계 ~1,900 (±100) 범위.
- [ ] 각 renderer 파일 ≤ 800 LOC (NF-03).
- [ ] `rtk proxy python3 -m pytest -q scripts/ --tb=no` → **2 failed / 1997
  passed / 176 skipped** (baseline Δ = 0).
- [ ] 실기동 smoke 5종 200 OK: `GET /`, `/api/state`, `/api/graph`,
  `/api/merge-status`, `/pane/{id}`.
- [ ] HTML md5 baseline 과 모든 커밋 Δ = 0 (byte-identical).
- [ ] facade 무결성: 아래 심볼 전부 `hasattr(core, name)` True.
  ```
  _section_wrap, _section_header, _section_sticky_header, _section_kpi,
  _section_wp_cards, _section_features, _section_team, _section_subagents,
  _section_phase_history, _section_dep_graph, _section_live_activity,
  _section_subproject_tabs, _section_filter_bar,
  _render_task_row_v2, _render_pane_row, _render_subagent_row, _render_arow,
  _render_pane_html, _render_pane_json,
  _SECTION_EYEBROWS, _KPI_LABELS, _KPI_ORDER, _KPI_V3_SUFFIX, _SPARK_COLORS,
  _TOO_MANY_PANES_THRESHOLD, _PANE_PREVIEW_LINES, _SUBAGENT_INFO,
  _PHASES_SECTION_LIMIT
  ```
- [ ] 순환 import 없음: `python3 -c "import monitor_server.renderers.header,
  monitor_server.renderers.kpi, monitor_server.renderers.features,
  monitor_server.renderers.history, monitor_server.renderers.tabs"` 성공.
- [ ] 인라인 자산 신규 참조 0건: `grep -n "DASHBOARD_CSS\|_DASHBOARD_JS\|_PANE_CSS"
  scripts/monitor_server/renderers/*.py` → 매치 없음.

## 동작 보존 계약

- `/`, `/api/state`, `/api/graph`, `/api/merge-status`, `/pane/{id}` 엔드포인트의
  응답(HTML body + JSON 스키마) 은 baseline과 **byte-identical**.
- `monitor_server.core` 의 `dir()` 집합은 이관 전 심볼 set의 상위 집합
  (facade re-export 덕에 추가는 허용, 제거는 금지).
- `renderers/_util.py` 의 노출 심볼 목록은 **확장만 허용**(기존 26개 유지 +
  신규 13~15개 추가). 기존 심볼 제거·이름 변경 금지.
- 테스트 파일 변경은 **없다**. 본 feature 범위 내 pre-existing 2 failed 는
  baseline으로 유지.
- `render_dashboard` 함수 시그니처 `(model, lang, subproject)` + 출력 HTML
  불변. 내부 호출 target 만 renderers 모듈로 스위치 (동일 심볼명 재-export
  덕에 소스 코드 변경 최소).

dev-build 가 생성할 단위 테스트(+ md5 비교 스크립트)는 위 동작 보존 계약의
검증 기준선이 된다. Refactor 단계는 기능 변경 금지 — 품질 개선(docstring,
`__all__` 정리, breadcrumb 주석 형식 통일)만 수행.
