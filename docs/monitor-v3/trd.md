# TRD: dev-monitor v3

## 1. 변경 파일

| 파일 | 변경 |
|------|------|
| `scripts/monitor-server.py` | 필터 헬퍼, subproject discovery, /api/state + /api/graph + /static/ 라우팅, 탭 UI, i18n 테이블, URL quote/unquote, CSS 폰트 변수, Graph 섹션 HTML |
| `scripts/dep-analysis.py` | `--graph-stats` 모드 확장: fan-out, critical_path (노드 리스트 + 엣지 리스트) 추가 |
| `skills/dev-monitor/SKILL.md` | 탭/언어/필터/그래프 동작 설명 추가 |
| (신규) `skills/dev-monitor/vendor/cytoscape.min.js` | Cytoscape.js core (오프라인 벤더링) |
| (신규) `skills/dev-monitor/vendor/dagre.min.js` | dagre 레이아웃 엔진 |
| (신규) `skills/dev-monitor/vendor/cytoscape-dagre.min.js` | cytoscape-dagre 어댑터 |
| (신규) `skills/dev-monitor/vendor/graph-client.js` | `/api/graph` 폴링 + diff + 애니메이션 클라이언트 코드 |
| `scripts/test_monitor_render.py` | 탭 UI, i18n, 폰트 변수, Graph 섹션 부트스트랩 회귀 |
| `scripts/test_monitor_pane.py` | URL 인코딩 회귀 |
| `scripts/test_monitor_signal_scan.py` | scope 구조 변경 |
| `scripts/test_monitor_api_state.py` | 프로젝트/서브프로젝트 필터 + 쿼리 파라미터 |
| (신규) `scripts/test_monitor_subproject.py` | `discover_subprojects` 단독 |
| (신규) `scripts/test_monitor_graph_api.py` | `/api/graph` 응답 구조·필터·폴링 idempotency |
| (신규) `scripts/test_dep_analysis_critical_path.py` | `--graph-stats` 의 `critical_path`, `fan_out` 검증 |
| `~/.claude/plugins/cache/dev-tools/dev/1.5.0/` | 위 변경 미러링 |

**변경하지 않을 파일**

- `scripts/monitor-launcher.py` — PID 키는 `$PWD` 그대로 유지 (프로젝트당 1서버).
- `scripts/args-parse.py`, `scripts/wp-setup.py`, `scripts/signal-helper.py` — 이미 서브프로젝트 규약 구현됨. 재사용만.

## 2. 데이터 흐름

```
GET /?subproject=billing&lang=ko
     │
     ▼
┌──────────────────────────────────────────────┐
│ do_GET → _route_root                         │
│   ├─ parse query: subproject, lang           │
│   ├─ discover_subprojects(docs_dir)          │
│   ├─ resolve effective_docs_dir              │
│   │     all   → docs_dir                     │
│   │     <sp>  → docs_dir / sp                │
│   ├─ build filtered scanners (closure):      │
│   │     scan_signals_f = lambda: filter(...) │
│   │     list_panes_f   = lambda: filter(...) │
│   ├─ _build_render_state(root, eff, ...)     │
│   └─ render_dashboard(model, lang, sps, sp)  │
└──────────────────────────────────────────────┘
     │
     ▼
   HTML (ko 기본, ?lang=en 영문)
```

## 3. 컴포넌트 상세

### 3.1 Subproject 탐지

```python
def discover_subprojects(docs_dir: Path) -> List[str]:
    """Return sorted list of subprojects under *docs_dir*.

    Rule identical to args-parse.py:82-92 — a child directory is a subproject
    iff it contains a wbs.md file.
    """
    if not docs_dir.is_dir():
        return []
    subs = []
    for child in sorted(docs_dir.iterdir()):
        if child.is_dir() and (child / "wbs.md").is_file():
            subs.append(child.name)
    return subs
```

`is_multi_mode = len(discover_subprojects(docs_dir)) > 0`.

### 3.2 프로젝트-레벨 필터

```python
def _filter_panes_by_project(panes, project_root, project_name):
    if panes is None:
        return None
    root = project_root.rstrip(os.sep)
    result = []
    for p in panes:
        cwd = getattr(p, "pane_current_path", "") or ""
        wname = getattr(p, "window_name", "") or ""
        in_root = cwd == root or cwd.startswith(root + os.sep)
        wp_match = wname.startswith("WP-") and f"-{project_name}" in wname
        if in_root or wp_match:
            result.append(p)
    return result

def _filter_signals_by_project(signals, project_name):
    result = []
    for s in signals:
        scope = getattr(s, "scope", "") or ""
        if scope == project_name or scope.startswith(project_name + "-"):
            result.append(s)
    return result
```

### 3.3 Signal scope 구조 변경

현재 `_walk_signal_entries(os.path.join(tmp_root, "claude-signals"), "shared")` 는 전체를 `scope="shared"` 로 평탄화한다. 이걸 subdir-per-scope로 쪼갠다:

```python
def scan_signals() -> List[SignalEntry]:
    tmp_root = tempfile.gettempdir()
    entries: List[SignalEntry] = []
    cs_root = os.path.join(tmp_root, "claude-signals")
    if os.path.isdir(cs_root):
        for sub in sorted(os.listdir(cs_root)):
            sub_path = os.path.join(cs_root, sub)
            if os.path.isdir(sub_path):
                entries.extend(_walk_signal_entries(sub_path, scope=sub))
    # (B) agent-pool unchanged — scope="agent-pool:{timestamp}"
    ...
```

호환: `_classify_signal_scopes` 는 `agent-pool:*` prefix만 특별 처리, 나머지는 shared 버킷에 담는 현재 로직 유지 — 표시 측면에선 불변.

### 3.4 서브프로젝트 필터

```python
def _filter_by_subproject(state: dict, sp: str, project_name: str) -> dict:
    # tasks/features: already scanned from docs/{sp}/ via effective_docs_dir
    filtered_panes = []
    for p in state["tmux_panes"] or []:
        wn = getattr(p, "window_name", "") or ""
        cwd = getattr(p, "pane_current_path", "") or ""
        if wn.endswith(f"-{sp}") or f"-{sp}-" in wn or f"/{sp}/" in cwd:
            filtered_panes.append(p)
    state["tmux_panes"] = filtered_panes if state["tmux_panes"] is not None else None
    prefix = f"{project_name}-{sp}"
    state["shared_signals"] = [
        s for s in state["shared_signals"]
        if s.scope == prefix or s.scope.startswith(prefix + "-")
    ]
    return state
```

### 3.5 pane URL 인코딩 버그 수정

**현재 버그**
- 링크 생성 (`monitor-server.py:2183`): `href="/pane/{pane_id_esc}"` — HTML-escape만, URL-encode 없음. `pane_id="%0"` → `/pane/%0` (유효하지 않은 URL).
- 브라우저가 `%` → `%25`로 자동 재인코딩 → 실제 요청 `/pane/%250`.
- 라우트 핸들러 (`monitor-server.py:3696, 3699`): `pane_id = path[len(prefix):]` — `unquote` 없음. `%250` → 디코드 없이 tmux로.
- `_PANE_ID_RE = ^%\d+$` 는 `%250`도 매치해서 400도 못 냄.

**수정**

출력:
```python
from urllib.parse import quote
href = f'/pane/{quote(pane_id_raw, safe="")}'
```
JS fetch(`monitor-server.py:2944, 3173`)는 이미 `encodeURIComponent` — 서버 쪽만 고치면 됨.

라우터:
```python
from urllib.parse import unquote
pane_id = unquote(path[len(_PANE_PATH_PREFIX):])
```

`_PANE_ID_RE` 는 decode 후 검증. `%250` → `%0` 매치 → 정상. 불량 입력(`%xx` non-digit)은 unquote 결과 비ascii → regex 불일치 → 400.

### 3.6 폰트 변수

CSS 최상단에 추가:
```css
:root {
  --font-body: 14px;
  --font-mono: 14px;
  --font-h2:   17px;
}
```
기존 `font-size: 13px` / `15px` 리터럴을 변수로 치환 (grep으로 정확히 매치되는 지점만). 반응형 미디어 쿼리 없음.

### 3.7 i18n (ko/en, 기본 ko)

**범위**: 섹션 h2 heading만. eyebrow, 테이블 컬럼명, 코드 블록은 건드리지 않음 (스코프 제한).

**스토어**: JS 없이 SSR + `?lang=ko|en` 쿼리 파라미터. 쿠키/localStorage 안 씀.

**변환 테이블** (모듈 상단 상수):
```python
_I18N = {
    "ko": {
        "work_packages": "작업 패키지",
        "features": "기능",
        "team_agents": "팀 에이전트 (tmux)",
        "subagents": "서브 에이전트 (agent-pool)",
        "live_activity": "실시간 활동",
        "phase_timeline": "단계 타임라인",
    },
    "en": {
        "work_packages": "Work Packages",
        "features": "Features",
        "team_agents": "Team Agents (tmux)",
        "subagents": "Subagents (agent-pool)",
        "live_activity": "Live Activity",
        "phase_timeline": "Phase Timeline",
    },
}

def _t(lang: str, key: str) -> str:
    return _I18N.get(lang, _I18N["ko"]).get(key, key)
```

`_section_*` 함수의 heading 인자를 `_t(lang, ...)` 결과로 교체. `lang` 은 `render_dashboard(model, lang="ko")` 에서 받아 internally 전달. 기본 `ko`.

헤더 우측 토글 (SSR):
```html
<nav class="lang-toggle">
  <a href="?lang=ko&subproject={sp}">한</a>
  <a href="?lang=en&subproject={sp}">EN</a>
</nav>
```

### 3.8 /api/state 변경

**쿼리 파라미터**
- `subproject` (str, optional) — `all` 또는 `<subproject>`. 기본 `all`.
- `lang` (str, optional) — API 응답에는 영향 없음 (HTML 렌더 전용).
- `include_pool` (0/1, optional) — agent-pool signals 포함 여부. 기본 0.

**응답 추가 필드**
```json
{
  "subproject": "billing",
  "available_subprojects": ["billing", "reporting"],
  "is_multi_mode": true,
  "project_name": "project-α",
  "generated_at": "2026-04-22T13:00:00Z",
  "project_root": "/Users/jji/project/project-α",
  "docs_dir": "docs/billing",
  "wbs_tasks": [...],
  "features": [...],
  "shared_signals": [...],
  "agent_pool_signals": [],
  "tmux_panes": [...]
}
```

### 3.9 Dependency Graph — 실시간 인터랙티브 뷰

#### 3.9.1 아키텍처

```
┌─────────────────────────────────────────────────┐
│ Browser                                         │
│  ┌──────────────────────────────────────────┐   │
│  │ Graph section (HTML placeholder)         │   │
│  │   #dep-graph-canvas (cytoscape container)│   │
│  │   #dep-graph-summary (counters)          │   │
│  └──────────────────────────────────────────┘   │
│  graph-client.js: 2s polling → fetch JSON →     │
│    diff nodes/edges → apply state delta with    │
│    CSS transition                               │
└─────────────────────────────────────────────────┘
              │ GET /api/graph?subproject=X
              ▼
┌─────────────────────────────────────────────────┐
│ monitor-server.py                               │
│   _handle_graph_api:                            │
│     ├─ scan_tasks(effective_docs_dir)           │
│     ├─ dep_analysis_graph_stats(tasks)          │
│     └─ build {nodes, edges, stats} payload      │
└─────────────────────────────────────────────────┘
              │ 상태는 state.json (Task별 sidecar)
              ▼
         Signals + state.json 을 직접 읽어 항상 최신
```

#### 3.9.2 `/api/graph` 엔드포인트

**요청**: `GET /api/graph?subproject=<sp>` (기본 `all` = 루트 docs_dir)

**응답 스키마**:

```json
{
  "subproject": "billing",
  "docs_dir": "docs/billing",
  "generated_at": "2026-04-22T13:00:00Z",
  "stats": {
    "total": 12,
    "done": 3,
    "running": 2,
    "pending": 6,
    "failed": 0,
    "bypassed": 1,
    "max_chain_depth": 4,
    "critical_path_length": 4,
    "bottleneck_count": 2
  },
  "critical_path": {
    "nodes": ["TSK-00-01", "TSK-01-02", "TSK-02-01", "TSK-03-01"],
    "edges": [
      {"source": "TSK-00-01", "target": "TSK-01-02"},
      {"source": "TSK-01-02", "target": "TSK-02-01"},
      {"source": "TSK-02-01", "target": "TSK-03-01"}
    ]
  },
  "nodes": [
    {
      "id": "TSK-00-01",
      "label": "Bootstrap",
      "wp_id": "WP-00",
      "status": "done",
      "is_critical": true,
      "is_bottleneck": false,
      "fan_in": 0,
      "fan_out": 4,
      "bypassed": false
    },
    ...
  ],
  "edges": [
    {
      "source": "TSK-00-01",
      "target": "TSK-01-01",
      "is_critical": false
    },
    ...
  ]
}
```

**`status` 값** (노드 색상 매핑):
- `done` — state.json.status == `[xx]`
- `running` — `.running` 시그널 존재 또는 state.json.status in {`[dd]`, `[im]`, `[ts]`}
- `pending` — 기타
- `failed` — `.failed` 시그널 존재 또는 state.json.last.event == `fail`
- `bypassed` — state.json.bypassed == true

판정은 `monitor-server.py`에 `_derive_node_status(task, signals)` 헬퍼로 격리.

#### 3.9.3 dep-analysis.py 확장

현재 `--graph-stats` 는 `max_chain_depth`, `fan_in_top`, `diamond_patterns` 를 반환. 추가:

- `fan_out` per-task (기존 fan_in과 대칭)
- `critical_path`: 루트(fan_in==0)부터 리프까지의 longest path (엣지 가중치 1 가정). 반환 형식 `{"nodes": [...], "edges": [...]}`.
- `bottleneck_ids`: `fan_in >= 3 or fan_out >= 3` 인 Task ID 목록.

알고리즘:
- Topological sort → DP로 각 노드의 "가장 긴 distance from source" 계산
- max distance 노드를 리프로 선택 → parent 추적하여 경로 복원
- 동점이면 task_id alphabetical 작은 것 우선 (결정론적)

#### 3.9.4 클라이언트 폴링 + 애니메이션

`graph-client.js` (≤300 LOC):

```javascript
const POLL_MS = 2000;
const SP = new URLSearchParams(location.search).get('subproject') || 'all';

const cy = cytoscape({
  container: document.getElementById('dep-graph-canvas'),
  elements: [],
  style: [
    {selector: 'node', style: {
      'background-color': 'data(color)',
      'label': 'data(label)',
      'border-width': 'data(borderWidth)',
      'border-color': 'data(borderColor)',
      'transition-property': 'background-color, border-color, border-width',
      'transition-duration': '400ms'
    }},
    {selector: 'edge', style: {
      'width': 'data(width)',
      'line-color': 'data(color)',
      'target-arrow-color': 'data(color)',
      'target-arrow-shape': 'triangle',
      'curve-style': 'bezier',
      'transition-property': 'line-color, width',
      'transition-duration': '400ms'
    }},
    {selector: 'node.bottleneck', style: {
      'content': '⚠ ' + 'data(label)'
    }}
  ],
  layout: {name: 'dagre', rankDir: 'LR', nodeSep: 40, rankSep: 80}
});

let lastSignature = '';

async function tick() {
  const res = await fetch(`/api/graph?subproject=${encodeURIComponent(SP)}`, {cache: 'no-store'});
  if (!res.ok) return;
  const data = await res.json();
  const sig = data.generated_at;  // 전체 재빌드 방지 — 실제로는 nodes 변경 해시 권장
  if (sig === lastSignature) return;
  applyDelta(cy, data);
  updateSummary(data.stats);
  lastSignature = sig;
}

setInterval(tick, POLL_MS);
tick();
```

**Delta 적용 전략**:
- 첫 로드: `cy.add()` 로 전체 구성 + `cy.layout({name:'dagre'}).run()`
- 이후: 기존 노드는 `node.data('color', newColor)` 로 속성만 갱신 → CSS transition이 fade-in. 신규 노드/엣지는 `cy.add()`, 삭제는 `cy.remove()`. 레이아웃은 **토폴로지 변경 시에만** 재실행 (노드/엣지 추가·삭제 감지).
- `is_critical` 변화 시 엣지의 color/width 속성만 업데이트 → 부드러운 하이라이트 전환.

**색상 팔레트** (다크 배경 기준, 기존 대시보드 톤):
- done `#22c55e`, running `#eab308`, pending `#94a3b8`, failed `#ef4444`, bypassed `#a855f7`
- 크리티컬 엣지 `#ef4444`, 기본 엣지 `#475569`
- 크리티컬 노드 border `#ef4444` 2px

#### 3.9.5 대시보드 섹션 HTML (SSR 뼈대)

`_section_dep_graph(lang: str, subproject: str) -> str`:

```html
<section id="dep-graph" class="section">
  <div class="section-head">
    <div><div class="eyebrow">graph</div><h2>{_t(lang, "dep_graph")}</h2></div>
    <aside class="summary" id="dep-graph-summary">
      <span>loading…</span>
    </aside>
  </div>
  <div class="dep-graph-wrap">
    <div id="dep-graph-canvas" style="height:520px;"></div>
    <div id="dep-graph-legend">
      <!-- 색상 범례 정적 -->
    </div>
  </div>
  <script src="/static/dagre.min.js"></script>
  <script src="/static/cytoscape.min.js"></script>
  <script src="/static/cytoscape-dagre.min.js"></script>
  <script src="/static/graph-client.js"></script>
</section>
```

i18n 키 추가:
```python
"dep_graph": {"ko": "의존성 그래프", "en": "Dependency Graph"}
```

#### 3.9.6 `/static/` 라우팅

새 `_is_static_path(path)` 분기 + `_handle_static(handler, path)`:

- base = `{CLAUDE_PLUGIN_ROOT}/skills/dev-monitor/vendor/`
- 허용 파일만 서빙 (화이트리스트: `cytoscape.min.js`, `dagre.min.js`, `cytoscape-dagre.min.js`, `graph-client.js`). 디렉터리 traversal 방지 — `..` 포함 경로는 404.
- MIME: `.js` → `application/javascript; charset=utf-8`
- Cache-Control: `public, max-age=3600` (벤더 파일은 빌드 해시 불변)

#### 3.9.7 성능 · 한계

- 폴링 주기 2초. `/api/graph` 는 O(N+E) 재계산. N ≈ 수백 수준까지 단일 요청 <50ms 예상.
- 토폴로지 변경(Task 추가/삭제) 없으면 레이아웃 재실행 안 함 → 지터 없음.
- `refresh_seconds` 와 별개 주기 (대시보드 나머지 섹션은 기존 refresh 유지). 추후 통일 고려.
- WebSocket/SSE 미채택 사유: 상태 머신이 이미 파일 기반(.done 시그널 + state.json)이라 폴링이 push 없이도 지연 2초 이내로 수렴. 복잡도 대비 이득 없음.

## 4. 테스트 전략

### 단위 테스트 (pytest + Python stdlib만)

| 테스트 | 대상 |
|-------|------|
| `test_discover_subprojects_multi` | `docs/p1/wbs.md`, `docs/p2/wbs.md` → `["p1", "p2"]` |
| `test_discover_subprojects_legacy` | `docs/wbs.md` 만 → `[]` |
| `test_discover_subprojects_ignores_dirs_without_wbs` | `docs/tasks/`, `docs/features/` 같은 디렉터리는 제외 |
| `test_scan_signals_scope_is_subdir` | `/tmp/claude-signals/proj-a/X.done` → scope="proj-a" |
| `test_filter_panes_by_project_root_startswith` | cwd가 root 하위인 pane만 통과 |
| `test_filter_panes_by_project_window_name_match` | cwd는 밖이어도 `WP-01-proj-a` 면 통과 |
| `test_filter_signals_by_project` | `proj-a-billing`은 통과, `other-proj`는 제외 |
| `test_filter_by_subproject_signals` | `proj-a-billing` 통과, `proj-a-reporting` 제외 |
| `test_filter_by_subproject_panes_by_window` | `WP-01-billing` 통과 |
| `test_api_state_subproject_query` | `?subproject=billing` 응답에 `"subproject":"billing"` + 필터된 리스트 |
| `test_api_state_include_pool_default_excluded` | agent-pool signals 기본 제외 |
| `test_api_state_include_pool_flag` | `?include_pool=1` 시 포함 |
| `test_pane_route_decodes_percent_encoded` | `GET /pane/%250` → `capture_pane` 에 `%0` 전달 |
| `test_pane_link_quotes_pane_id` | render 결과 href 에 `%25` 포함 |
| `test_section_titles_korean_default` | lang 미지정 시 "작업 패키지" 포함 |
| `test_section_titles_english_with_lang_en` | `?lang=en` 시 "Work Packages" 포함 |
| `test_dashboard_shows_tabs_in_multi_mode` | `[ all | p1 | p2 ]` 탭 마크업 |
| `test_dashboard_hides_tabs_in_legacy` | 탭 마크업 없음 |
| `test_font_css_variables_present` | `:root { --font-body:` 선언 존재 |
| `test_api_graph_returns_nodes_and_edges` | `/api/graph` 응답에 nodes/edges 존재 + 스키마 검증 |
| `test_api_graph_derives_status_done_running_pending_failed_bypassed` | 각 상태에 대해 올바른 노드 `status` 값 |
| `test_api_graph_respects_subproject_filter` | `?subproject=p1` 시 `docs/p1/` Task만 |
| `test_dep_analysis_critical_path_linear` | TSK-A→B→C→D 체인 → critical_path = [A,B,C,D] |
| `test_dep_analysis_critical_path_diamond` | 다이아몬드 그래프 → 긴 쪽 선택 + 결정론 |
| `test_dep_analysis_fan_out` | fan_in 대칭으로 fan_out 계산 |
| `test_dep_analysis_bottleneck_ids` | fan_in≥3 또는 fan_out≥3 만 반환 |
| `test_static_route_whitelist_allows_vendor_js` | `GET /static/cytoscape.min.js` → 200 |
| `test_static_route_rejects_traversal` | `GET /static/../secrets` → 404 |
| `test_graph_section_embedded_in_dashboard` | `_section_dep_graph` 가 `<div id="dep-graph-canvas">` 포함 |

### 수동 E2E

1. `/tmp/mp-demo/` 에 `docs/p1/wbs.md`, `docs/p2/wbs.md` 조립 → 탭 동작 확인
2. 실제 `/Users/jji/project/dev-plugin` 에서 레거시 동작 유지 확인
3. 다른 프로젝트 tmux pane 생성 후 필터 확인
4. pane `%0`, `%1`, `%99` 클릭 → 모두 상세 페이지 정상
5. **그래프 실시간성**: dev-plugin 자체를 타겟으로 `/dev TSK-ID` 실행 → 브라우저에서 Dependency Graph 섹션을 열어둔 상태에서 Task가 `[xx]`로 완료되면 2~3초 이내 노드가 초록으로 전환되는지 관찰. 리로드 없이.
6. **크리티컬 패스 갱신**: Task 완료 후 크리티컬 패스가 다음 체인으로 이동하는지 확인.
7. **인터랙션**: 마우스 휠 pan/zoom, 노드 클릭 → 팝오버 Task 상세. 대용량 WBS(~100 Task)에서 프레임 끊김 없는지.
8. **오프라인**: Wi-Fi 끈 상태에서 모니터 재기동 → 그래프 정상 로드 (벤더 JS 서빙 확인).

## 5. 롤백

- `scripts/monitor-server.py` 를 이전 커밋으로 되돌리면 즉시 복구. 외부 API 소비자 없음.
- signal scope 값 변경(`"shared"` → subdir name)이 유일한 breaking change지만, 소비자는 동일 프로세스 내 `_classify_signal_scopes` 하나 — 함께 변경되므로 격리 영향.

## 6. 의존성 · 리스크

- agent-pool signals의 프로젝트 귀속 불가 → 기본 제외 선택. `?include_pool=1` opt-in. 제외로 인한 정보 손실은 헤더 카운트로 보완.
- tmux pane의 `pane_current_path`는 셸 cd 상태에 의존 — 사용자가 pane 안에서 다른 프로젝트로 cd하면 필터가 어긋날 수 있음. 알려진 한계로 `window_name` fallback으로 일부 완화.
- `?lang=` stateless — 새 탭마다 ko 기본. 후속 릴리스에서 localStorage 고려.
