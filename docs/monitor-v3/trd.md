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
| `scripts/monitor-server.py` | **(WP-04/05)** `_STATIC_WHITELIST`에 `cytoscape-node-html-label.min.js` 추가, `_section_dep_graph` script 로드 순서 갱신, `.dep-node*` CSS inline, fold 영속성 JS 헬퍼 + `patchSection('wp-cards')` 훅 |
| (신규) `skills/dev-monitor/vendor/cytoscape-node-html-label.min.js` | **(WP-04)** HTML 레이블 플러그인 v2.0.1 (~7 KB) |
| `skills/dev-monitor/vendor/graph-client.js` | **(WP-04)** `nodeHtmlTemplate` + `cy.nodeHtmlLabel([...])` 등록, `nodeStyle.label` 제거, `nodeSep 40→60` / `rankSep 80→120`, canvas height 640 |
| (신규) `scripts/merge-preview.py` | **(WP-06)** Task 완료 전 main과의 잠재 충돌 시뮬레이션 |
| (신규) `scripts/init-git-rerere.py` | **(WP-06)** `git config rerere.*` + 머지 드라이버 등록 (idempotent) |
| (신규) `scripts/merge-state-json.py` | **(WP-06)** `state.json` 3-way 머지 드라이버 |
| (신규) `scripts/merge-wbs-status.py` | **(WP-06)** `wbs.md` 상태 라인 머지 드라이버 |
| (신규) `.gitattributes` | **(WP-06)** `union` + `state-json-smart` + `wbs-status-smart` 매핑 |
| `skills/dev-build/SKILL.md` | **(WP-06)** 워커 프롬프트에 "Task `[im]` 진입 전 `merge-preview.py` 실행" 단계 추가 |
| `skills/dev-team/references/merge-procedure.md` | **(WP-06)** rerere/드라이버 순서, 충돌 로그 보존 경로(`docs/merge-log/{WT}-{UTC}.json`) |
| `scripts/monitor-server.py` | **(WP-04/TSK-04-04)** `_section_dep_graph` 요약 HTML을 `<span class="dep-stat dep-stat-{state}"><em>label</em> <b data-stat=...>-</b></span>` 칩 구조로 교체, `_t` 테이블에 `dep_stat_*` i18n 키 6종 추가, `.dep-stat*` CSS 인라인 |
| `skills/dev-monitor/vendor/graph-client.js` | **(WP-04/TSK-04-04)** `updateSummary(stats)` 가 `[data-stat]` 선택자 유지로 태그 변경(`<span>→<b>`)과 무관하게 동작 — JS 수정 0 목표 |
| (신규) `scripts/test_monitor_dep_graph_html.py` | **(WP-04)** 2줄 레이블, 3중 시각 단서, nodeSep/rankSep 회귀 |
| (신규) `scripts/test_monitor_dep_graph_summary.py` | **(WP-04/TSK-04-04)** 요약 칩 레이블(ko/en) + 색상 팔레트 일치 + legend parity |
| (신규) `scripts/test_monitor_fold.py` | **(WP-05)** localStorage 저장/복원 JS 존재 및 서버 계약 검증 |
| (신규) `scripts/test_merge_preview.py` | **(WP-06)** 충돌 탐지 / clean-merge 케이스 |
| (신규) `scripts/test_merge_state_json.py` | **(WP-06)** phase_history union, status 우선순위, bypassed OR |
| (신규) `scripts/test_merge_wbs_status.py` | **(WP-06)** 진행도 높은 status 우선 선택 |
| (신규) `scripts/test_init_git_rerere.py` | **(WP-06)** rerere/드라이버 설정 idempotent |
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

### 3.10 Dep-Graph 노드 HTML 카드 레이블 (WP-04)

#### 3.10.1 목표 및 제약

- 노드에 Task ID + 제목을 2줄 카드로 표시(기존 단일 라인 `title or id` 레이블 교체).
- 상태(done/running/pending/failed/bypassed) 별로 **3중 시각 단서**(좌측 스트립, ID 글자색, 배경 틴트) 동시 적용 — 한 눈에 상태 식별.
- 기존 cytoscape 스택(+ cytoscape-dagre)은 유지, HTML 레이블만 추가 플러그인으로 오버레이.
- 번들 증분 ≤ 10 KB, 기존 pan/zoom / 팝오버 동작 보존.

#### 3.10.2 벤더링

- 파일: `skills/dev-monitor/vendor/cytoscape-node-html-label.min.js` v2.0.1
- `scripts/monitor-server.py` `_STATIC_WHITELIST`(line 121)에 파일명 추가
- `_section_dep_graph` 의 `<script>` 로드 순서:
  `dagre → cytoscape → cytoscape-node-html-label → cytoscape-dagre → graph-client`

#### 3.10.3 graph-client.js 변경

- `escapeHtml(s)` 헬퍼 추가 (`& < > " '` 이스케이프).
- `nodeHtmlTemplate(data)` — 상태 클래스 + critical/bottleneck 플래그를 계산하여 아래 HTML 반환:

```html
<div class="dep-node status-{st} [critical] [bottleneck]">
  <div class="dep-node-id">{id}</div>
  <div class="dep-node-title">{title or id}</div>
</div>
```

- `nodeStyle()`의 `label` 필드 제거 (HTML 레이어가 담당) — ⚠ 이모지 prefix도 제거.
- cytoscape 초기화 직후 `cy.nodeHtmlLabel([{query:"node", valign:"center", halign:"center", tpl: data => nodeHtmlTemplate(data)}])` 등록.
- cytoscape 노드 스타일: `background-opacity: 0`, `border-width: 0`, `width: 180`, `height: 54`, `shape: roundrectangle` — 자리만 점유.
- 레이아웃: `nodeSep 40→60`, `rankSep 80→120`, rankDir `LR` 유지.

#### 3.10.4 CSS 토큰 (monitor-server.py inline `<style>` 또는 `_section_dep_graph` 내부)

```css
.dep-node {
  width: 180px; min-height: 50px;
  padding: 10px 12px 10px 16px;
  background: var(--bg-2);
  border: 1px solid var(--ink-4);
  border-left: 4px solid var(--ink-4);   /* 단서 1 */
  border-radius: 8px;
  box-shadow: 0 2px 6px rgba(0,0,0,.35);
  font-family: "Space Grotesk", system-ui, sans-serif;
  transition: transform .15s ease, box-shadow .15s ease;
  cursor: pointer;
  background-image: linear-gradient(90deg, var(--_tint, transparent), transparent 45%); /* 단서 3 */
}
.dep-node:hover { transform: translateY(-1px); box-shadow: 0 4px 12px rgba(0,0,0,.45); }
.dep-node-id {
  font-family: "JetBrains Mono", ui-monospace, monospace;
  font-size: 10px; font-weight: 600; color: var(--ink-3);  /* 단서 2 — 상태별 override */
  letter-spacing: .02em; text-transform: uppercase;
  margin-bottom: 3px;
}
.dep-node-title {
  font-size: 12.5px; font-weight: 500; color: var(--ink); /* 제목은 가독성 위해 고정 밝은색 */
  line-height: 1.3;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
  overflow: hidden;
}
.dep-node.status-done     { border-left-color: var(--done); --_tint: color-mix(in srgb, var(--done) 12%, transparent); }
.dep-node.status-done .dep-node-id     { color: var(--done); }
.dep-node.status-running  { border-left-color: var(--run);  --_tint: color-mix(in srgb, var(--run)  12%, transparent); }
.dep-node.status-running .dep-node-id  { color: var(--run); }
.dep-node.status-pending  { border-left-color: var(--ink-3); }
.dep-node.status-pending .dep-node-id  { color: var(--ink-3); }
.dep-node.status-failed   { border-left-color: var(--fail); --_tint: color-mix(in srgb, var(--fail) 12%, transparent); }
.dep-node.status-failed .dep-node-id   { color: var(--fail); }
.dep-node.status-bypassed { border-left-color: #a855f7;     --_tint: color-mix(in srgb, #a855f7    12%, transparent); }
.dep-node.status-bypassed .dep-node-id { color: #a855f7; }
.dep-node.critical   { box-shadow: 0 0 0 1px var(--fail), 0 2px 10px rgba(255,93,93,.25); border-color: var(--fail); }
.dep-node.bottleneck { border-style: dashed; }
```

※ `color-mix()` 미지원 브라우저 대응은 Chromium 111+ / Safari 16.2+ / Firefox 113+ 기준이면 OK. fallback 은 투명 배경(단서 1/2만 유지).

#### 3.10.5 캔버스

- `_section_dep_graph` 내부 `<div id="dep-graph-canvas" style="height:520px;">` → `640px`.

### 3.11 WP 카드 Fold 상태 영속성 (WP-05)

#### 3.11.1 문제

- `<details class="wp wp-tasks" data-wp="{WP-ID}" open>` 는 서버가 항상 `open` 렌더(monitor-server.py line 2730 근방).
- 5초 `fetchAndPatch`가 `patchSection` 로 `innerHTML` 전체 교체 → 사용자 fold 상태 리셋.
- 유사 문제를 `hdr` 섹션 chip/refresh-toggle 은 snapshot/restore 패턴으로 해결(line 3668-3689) — 동일 패턴 확장.

#### 3.11.2 저장 계약

- 저장소: `localStorage`
- 키 스키마: `dev-monitor:fold:{WP-ID}`, 값 `"open"|"closed"` (그 외 값은 무시, 서버 기본 따름)
- quota/disabled 대응: 모든 read/write try/catch silent skip
- 다중 탭 sync(`storage` 이벤트)는 범위 밖(비대상)

#### 3.11.3 클라이언트 JS 헬퍼 (monitor-server.py inline script)

```js
var FOLD_KEY_PREFIX = 'dev-monitor:fold:';
function readFold(wpId){ try{return localStorage.getItem(FOLD_KEY_PREFIX+wpId);}catch(e){return null;} }
function writeFold(wpId,open){ try{localStorage.setItem(FOLD_KEY_PREFIX+wpId, open?'open':'closed');}catch(e){} }
function applyFoldStates(root){
  (root||document).querySelectorAll('details[data-wp]').forEach(function(el){
    var s=readFold(el.getAttribute('data-wp'));
    if(s==='closed') el.removeAttribute('open');
    else if(s==='open') el.setAttribute('open','');
  });
}
function bindFoldListeners(root){
  (root||document).querySelectorAll('details[data-wp]').forEach(function(el){
    if(el.__foldBound) return;
    el.__foldBound=true;
    el.addEventListener('toggle', function(){
      writeFold(el.getAttribute('data-wp'), el.open);
    });
  });
}
```

#### 3.11.4 통합 지점

- **초기 로드**: `startMainPoll()` 호출 직전에 `applyFoldStates(); bindFoldListeners();`
- **patchSection 후**: `name === 'wp-cards'` 분기에서 교체 뒤 `applyFoldStates(current); bindFoldListeners(current);`

#### 3.11.5 서버 계약

- 서버는 `<details ... open>` 하드코딩 유지. JS 비활성화/첫 방문자 호환.
- 클라이언트 JS가 localStorage 기반으로 덮어씀.

### 3.12 워크트리 머지 충돌 저감 MVP (WP-06)

#### 3.12.1 목표

- `/dev-team` 머지 단계의 충돌 빈도와 해결 토큰비용 저감.
- Layer 2 (조기 탐지) + Layer 3 (자동 해결) + Layer 4 (주기 동기화) 조합을 MVP 로 구현.
- Layer 1 (파일 오너십 사전 선언), Layer 5 (충돌 예측 대시보드 카드) 는 범위 밖(후속 릴리스).

#### 3.12.2 merge-preview.py (Layer 2)

- 위치: `scripts/merge-preview.py` (신규). Python stdlib subprocess. zero-LLM.
- CLI: `python3 scripts/merge-preview.py [--remote origin] [--target main]`
- 동작:
  1. `git fetch {remote} {target}` (조용히)
  2. `git merge --no-commit --no-ff {remote}/{target}` 시뮬레이션
  3. 충돌 시 파일/hunk 목록 수집 → 즉시 `git merge --abort` (부작용 0)
  4. JSON stdout: `{"clean": bool, "conflicts": [{"file": str, "hunks": [...]}], "base_sha": str}`
- 실패 모드: 깨끗한 git 상태가 아니면 exit 2 + stderr 경고 ("uncommitted changes prevent preview").
- 워커 통합 (`skills/dev-build/SKILL.md` 프롬프트에 1줄 추가):
  > "Task `[im]` 단계 진입 전 `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/merge-preview.py` 를 실행하고, 출력 `clean`이 `false` 이면 `conflicts[*].file` 들을 현재 컨텍스트에서 `git rebase origin/main` 로 해결한 뒤 `[im]` 진행."

#### 3.12.3 git rerere + 머지 드라이버 등록 (Layer 3)

- 위치: `scripts/init-git-rerere.py` (신규). Idempotent.
- 수행하는 `git config` 셋:

```
git config rerere.enabled true
git config rerere.autoupdate true
git config merge.state-json-smart.driver  "python3 {PLUGIN}/scripts/merge-state-json.py %O %A %B %L"
git config merge.state-json-smart.name    "Smart state.json merger (phase_history union + status priority)"
git config merge.wbs-status-smart.driver  "python3 {PLUGIN}/scripts/merge-wbs-status.py %O %A %B %L"
git config merge.wbs-status-smart.name    "Smart wbs.md status-line merger"
```

- 호출 시점: `/dev-team` 팀리더가 각 WP 워크트리 생성 직후 1회 — `scripts/wp-setup.py` 또는 dev-team 리더 스폰 지점에 후크 추가.
- Idempotence: 이미 설정된 값과 동일하면 no-op.

#### 3.12.4 .gitattributes (신규, 프로젝트 루트)

```
docs/todo.md                    merge=union
docs/**/state.json              merge=state-json-smart
docs/**/tasks/**/state.json     merge=state-json-smart
docs/**/wbs.md                  merge=wbs-status-smart
```

`union`은 git 내장 드라이버 (양쪽 줄 단순 합치기). 실패해도 일반 충돌로 폴백.

#### 3.12.5 merge-state-json.py (Layer 3 드라이버)

- 서명: `%O %A %B %L` (base / ours / theirs / conflict_marker_size).
- 알고리즘:
  1. 세 파일을 JSON 로드. 파싱 실패 시 exit 1 (일반 3-way 충돌로 폴백).
  2. `phase_history` union: `(event, at)` 기준 dedup, `at` 오름차순 정렬.
  3. `status` 우선순위: `[xx] > [ts] > [im] > [dd] > [ ]`. 동률이면 ours 우선.
  4. `bypassed`: ours OR theirs.
  5. `completed_at`, `elapsed_seconds`: 둘 중 non-null 이면서 더 최신(`updated` 비교)인 쪽.
  6. `updated`: max(ours.updated, theirs.updated).
  7. 결과를 `%A` 경로에 원자적으로 기록 (tmp → rename). exit 0.

#### 3.12.6 merge-wbs-status.py (Layer 3 드라이버)

- 서명: `%O %A %B %L`.
- 알고리즘:
  1. `- status: [xxx]` 라인만 따로 파싱(task_id 키 매칭).
  2. 각 task 의 status 는 `[xx] > [ts] > [im] > [dd] > [ ]` 우선 선택.
  3. 비-status 라인은 git 표준 3-way 시도 (Python `difflib` 기반 merge3), 실패 시 conflict marker 유지 (exit 1).
  4. status-only 충돌만 있는 경우 자동 해결(exit 0), 그 외는 exit 1.

#### 3.12.7 merge-procedure.md 개정

- `skills/dev-team/references/merge-procedure.md` 에 다음 순서 명시:
  1. early-merge 시도.
  2. 충돌 발생 시: rerere 자동 해결 확인 → 해결 안 된 파일은 등록된 머지 드라이버 시도 → 여전히 잔존하면 `docs/merge-log/{WT_NAME}-{UTC}.json` 저장 후 `--abort`.
  3. abort 시 기존 auto-preserve 워크트리 동작 유지 (수동 복구 가능).
- 충돌 로그 JSON 스키마: `{wt_name, utc, conflicts: [{file, hunks[], lines_added, lines_removed}], base_sha, result: "aborted"|"resolved"}`.

#### 3.12.8 WP-06 내부 재귀 주의

- WP-06 이 merge-preview / rerere 자기 자신을 구현하므로, WP-06 Task 진행 중에는 **해당 기능 없이** 진행. TSK-06-01 완료 전 워커 프롬프트 훅 비활성, TSK-06-02 완료 전 rerere 비활성.
- 팀리더 프롬프트는 WP-06 머지 시 특별히 "드라이버 미설정 상태에서 수동 3-way 충돌 해결 가능" 주의사항 포함.

### 3.13 Dep-Graph 요약 카드 범례화 + 상태별 색상 (WP-04 / TSK-04-04)

#### 3.13.1 현재 상태와 문제

`monitor-server.py:_section_dep_graph` (line ~3079) 가 생성하는 현재 요약 HTML:

```html
<aside id="dep-graph-summary" class="dep-graph-summary">
  <span data-stat="total">-</span> ·
  <span data-stat="done">-</span> ·
  <span data-stat="running">-</span> ·
  <span data-stat="pending">-</span> ·
  <span data-stat="failed">-</span> ·
  <span data-stat="bypassed">-</span>
</aside>
```

- 사용자 눈에는 `4 · 2 · 1 · 1 · 0 · 0` 처럼 **레이블 없는 숫자 나열**만 보임 — 어느 숫자가 무엇인지 추측해야 함.
- 노드·legend는 이미 상태별 색상 팔레트를 쓰지만, 요약 숫자는 단색(inherit) — 색상 언어 단절.
- `#dep-graph-legend` (canvas 아래) 는 존재하지만 사용자의 시선이 노드·숫자·legend 세 곳에 분산되어, **요약 카드 자체만으로 상태를 읽을 수 없음**.

#### 3.13.2 목표 및 제약

- 요약 카드 각 숫자를 **`{레이블} {숫자}` 칩 형태**로 치환하고, 레이블·숫자 글자색을 해당 상태 색으로 칠한다.
- 레이블은 i18n(`ko`/`en`) 대응 — 기존 `_t(lang, key)` 프레임워크 재사용.
- 기존 `graph-client.js:updateSummary` 는 `span[data-stat="..."]` 를 찾아 `textContent` 만 갱신하므로 **JS 계약 변경 없이 SSR HTML만 재구성** — 회귀 위험 최소.
- 크리티컬 패스 깊이/병목 수는 현 구조(`.dep-graph-summary-extra`) 유지.

#### 3.13.3 변경 HTML (SSR)

`_section_dep_graph` 의 `summary_html` 을 다음으로 교체:

```html
<aside id="dep-graph-summary" class="dep-graph-summary">
  <span class="dep-stat dep-stat-total">
    <em>{dep_stat_total}</em> <b data-stat="total">-</b>
  </span>
  <span class="dep-stat dep-stat-done">
    <em>{dep_stat_done}</em> <b data-stat="done">-</b>
  </span>
  <span class="dep-stat dep-stat-running">
    <em>{dep_stat_running}</em> <b data-stat="running">-</b>
  </span>
  <span class="dep-stat dep-stat-pending">
    <em>{dep_stat_pending}</em> <b data-stat="pending">-</b>
  </span>
  <span class="dep-stat dep-stat-failed">
    <em>{dep_stat_failed}</em> <b data-stat="failed">-</b>
  </span>
  <span class="dep-stat dep-stat-bypassed">
    <em>{dep_stat_bypassed}</em> <b data-stat="bypassed">-</b>
  </span>
</aside>
```

- `<b data-stat="...">` 는 **기존 계약 보존** — `graph-client.js:updateSummary` 의 `el.querySelector('[data-stat="...")')` 가 그대로 동작.
- `<em>` 은 레이블(i18n 치환), 기본 `font-style: normal`.
- 각 `.dep-stat-{state}` 래퍼가 색상 규칙을 담당.

#### 3.13.4 i18n 키 추가

`_t` 테이블(line ~980, `"dep_graph"` 항목 근처)에 6키 추가:

```python
"dep_stat_total":    {"ko": "총",       "en": "Total"},
"dep_stat_done":     {"ko": "완료",     "en": "Done"},
"dep_stat_running":  {"ko": "진행",     "en": "Running"},
"dep_stat_pending":  {"ko": "대기",     "en": "Pending"},
"dep_stat_failed":   {"ko": "실패",     "en": "Failed"},
"dep_stat_bypassed": {"ko": "바이패스", "en": "Bypassed"},
```

> 표시 순서는 `total · done · running · pending · failed · bypassed` 로 기존 순서 유지 — 사용자 습관 보호.

#### 3.13.5 CSS (monitor-server.py inline `<style>` 또는 섹션 head)

```css
#dep-graph-summary {
  display: flex; gap: 14px; align-items: baseline;
  font-size: 12.5px; font-variant-numeric: tabular-nums;
}
.dep-stat { display: inline-flex; gap: 5px; align-items: baseline; }
.dep-stat em   { font-style: normal; font-weight: 500; opacity: .85; letter-spacing: .02em; }
.dep-stat b    { font-weight: 700; }
.dep-stat-total    em,
.dep-stat-total    b { color: var(--ink); }                /* 총계는 기본 텍스트 */
.dep-stat-done     em,
.dep-stat-done     b { color: var(--done); }               /* #22c55e */
.dep-stat-running  em,
.dep-stat-running  b { color: var(--run); }                /* #eab308 */
.dep-stat-pending  em,
.dep-stat-pending  b { color: var(--ink-3); }              /* 대기 — pending 톤 */
.dep-stat-failed   em,
.dep-stat-failed   b { color: var(--fail); }               /* #ef4444 */
.dep-stat-bypassed em,
.dep-stat-bypassed b { color: #a855f7; }                   /* bypassed 보라 */
.dep-graph-summary-extra { color: var(--ink-2); margin-left: 10px; }
```

- 기존 토큰(`--done`, `--run`, `--ink`, `--ink-3`, `--fail`) 재사용. 새 토큰 도입 없음.
- `#a855f7` 는 기존 graph-client.js `COLOR.bypassed` / legend 하드코딩과 동일값 — 별도 변수 없이 일치.
- legend(line ~3090) 색상 해시(`#22c55e`/`#eab308`/`#94a3b8`/`#ef4444`/`#a855f7`) 는 이번 WP 범위에서 `var(--done)` 등으로 치환 검토 가능하나, **선택 사항** — 선(先) 요약 칩만 확정하고 legend 치환은 후속 리팩토링(회귀 최소화).

#### 3.13.6 graph-client.js 영향

- `updateSummary(stats)` 의 `el.querySelector('[data-stat="..."]')` → `<b data-stat="...">` 로 타겟 맞춤 (태그만 변경, 선택자 유지).
- `.dep-graph-summary-extra` 로직 기존 그대로.
- **JS 변경 없음** 시나리오: `<b>` / `<span>` 차이는 `querySelector` 가 구분하지 않으므로 선택자 `[data-stat]` 만 유지하면 JS 수정 0. 다만 TSK 분리를 위해 `test_monitor_dep_graph_summary.py` 에서 `<b data-stat>` 또는 `<span data-stat>` 양쪽 허용.

#### 3.13.7 legend parity

- `.dep-stat-{state}` 색상 토큰과 `#dep-graph-legend .leg-item` 의 inline `style="color:..."` 해시가 일치해야 함.
- 테스트: `test_dep_graph_summary_legend_parity` — 양쪽 HTML에서 state별 색상값 추출해 동일성 assert.

#### 3.13.8 접근성 · 성능

- 색만으로 상태를 구분하지 않음 — **레이블이 1차 단서**, 색은 보조. 색맹 대응 OK.
- SSR HTML 크기 증분 ~400 bytes (6 칩 × 약 60 bytes). 무시 가능.
- 폴링 주기 갱신 시 DOM 조작은 기존과 동일(`<b>` 의 `textContent` 만 교체).

#### 3.13.9 비목표 재확인

- 숫자 클릭 → 해당 상태 필터링(인터랙션) 비대상.
- 완료율 %·ETA 등 추가 메트릭 비대상.
- `#dep-graph-legend` 자체 색상 토큰 리팩토링(하드코딩 해시 → CSS 변수) 비대상 — 후속 정리 트랙.

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
| `test_dep_graph_summary_labels_ko` | `lang=ko` 렌더에 `<em>총</em>`, `<em>완료</em>`, `<em>진행</em>`, `<em>대기</em>`, `<em>실패</em>`, `<em>바이패스</em>` 6종 존재 |
| `test_dep_graph_summary_labels_en` | `?lang=en` 시 `Total/Done/Running/Pending/Failed/Bypassed` 치환 |
| `test_dep_graph_summary_color_matches_palette` | `.dep-stat-done` 규칙이 `var(--done)` 적용, `.dep-stat-bypassed` 는 `#a855f7`, `.dep-stat-total` 은 `var(--ink)` |
| `test_dep_graph_summary_legend_parity` | `.dep-stat-{state}` 색상과 `#dep-graph-legend` 의 동일 state 색상 1:1 일치 |
| `test_dep_graph_summary_preserves_data_stat_selector` | `[data-stat="total\|done\|running\|pending\|failed\|bypassed"]` 6개 모두 존재 (graph-client.js 계약 보존) |

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
