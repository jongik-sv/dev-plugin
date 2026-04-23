# TRD: dev-monitor v4

## 1. 변경 파일

| 파일 | 변경 |
|------|------|
| `scripts/monitor-server.py` | `_section_phase_timeline` 제거, `_section_live_activity` `<details>` 래핑, `_render_task_row_v2` 단계 배지/스피너/tooltip 속성/EXPAND 버튼/**모델 칩 + ⚡ 에스컬레이션**, 범용 fold 헬퍼, 슬라이드 패널 DOM + `setupTaskTooltip`/`openTaskPanel` JS, `@keyframes spin` 공통 CSS, `/api/task-detail` 라우트(`logs[]` 필드 포함), `/api/graph` payload 확장(`phase_history_tail`, `last_event`, `last_event_at`, `elapsed_seconds`, `is_running_signal`, **`merge_state`**), **`_section_wp_cards` 머지 뱃지 렌더**, **`_section_filter_bar` 추가**, **`/api/merge-status` 라우트** |
| `skills/dev-monitor/vendor/graph-client.js` | `mouseover`/`mouseout` hover dwell 타이머 (2000ms), nodeHtmlTemplate 에 `.node-spinner` 조건부 삽입, popover `data-source="hover"|"tap"` 플래그, **`applyFilter(predicates)` export** (글로벌 필터 바 훅) |
| `scripts/test_monitor_render.py` | Phase Timeline 제거, Activity `<details>` 기본 닫힘, Task 단계 배지, 스피너 요소 회귀 |
| `scripts/test_monitor_api_state.py` | 기존 그대로(회귀 확인) |
| (신규) `scripts/test_monitor_task_detail_api.py` | `/api/task-detail` 스키마·wbs 섹션 추출·아티팩트 탐지·**logs tail·ANSI strip** |
| (신규) `scripts/test_monitor_task_badge.py` | `[dd]/[im]/[ts]/[xx]/failed/bypass/pending` → 배지 텍스트 매핑 |
| (신규) `scripts/test_monitor_task_spinner.py` | `.running` signal 유무에 따른 `.spinner` / `.node-spinner` 존재 여부 |
| (신규) `scripts/test_monitor_fold_live_activity.py` | Activity `<details data-fold-key="live-activity">` 기본 닫힘 + fold 헬퍼 범용화 회귀 |
| `scripts/test_monitor_graph_api.py` | `/api/graph` 노드에 v4 신규 필드 검증 케이스 추가 |
| (신규) `scripts/test_monitor_e2e_v4.py` | Task tooltip 300ms hover, EXPAND 패널 열림/닫힘, Dep-Graph 2초 dwell, 자동 refresh 중 패널/fold 생존 |
| (신규) `scripts/test_monitor_task_model_chip.py` | 모델 칩 + ⚡ 에스컬레이션 + phase별 모델 툴팁 |
| (신규) `scripts/test_monitor_task_logs_tail.py` | `build-report.md`·`test-report.md` tail 200줄 + ANSI strip |
| (신규) `scripts/merge-preview-scanner.py` | WP 별 Task 의 `merge-preview.json` 집계 → `docs/wp-state/{WP-ID}/merge-status.json` 생성. `state.json`·`wbs.md` 등 auto-merge 드라이버 보유 파일 필터. stdlib only, 5초 이내 완료. |
| (신규) `scripts/test_merge_preview_scanner.py` | auto-merge 필터 / stale 판정 (30분) / WP 집계 로직 |
| (신규) `scripts/test_monitor_merge_badge.py` | WP 카드 뱃지 state 렌더 + 클릭 시 슬라이드 패널 통합 |
| (신규) `scripts/test_monitor_filter_bar.py` | 필터 바 DOM + URL 상태 sync + `patchSection` 후 재적용 |
| `skills/dev-build/references/tdd-prompt-template.md` | `[im]` **완료 후** `merge-preview.py --output docs/tasks/{TSK-ID}/merge-preview.json` 1줄 실행 규약 추가. 결과 해석은 LLM이 하지 않음 (토큰 절약) |
| `~/.claude/plugins/marketplaces/dev-tools/` | 위 변경 미러링 (CLAUDE.md 규약) |

**변경하지 않을 파일**

- `scripts/dep-analysis.py` — 기존 `--graph-stats` 계약 그대로.
- `scripts/args-parse.py`, `scripts/wp-setup.py` — 서브프로젝트 규약 그대로 (v4는 `docs/monitor-v4/` 신설만).
- `scripts/wbs-parse.py` — Task 의 `model` 필드 파싱은 이미 지원 중 (v4 모델 칩은 기존 필드 소비).
- `scripts/monitor-launcher.py` — PID 키 $PWD 유지.
- `scripts/wbs-transition.py` — **state.json 스키마 무변경**. 에스컬레이션은 `retry_count` 기반 추론으로 표시 (모델 필드 추가 금지 → 토큰/마이그레이션 비용 0).
- `scripts/merge-preview.py` — `--output {path}` 플래그 유무 확인 후 **없으면 단일 인자만 추가** (stdout 계약 유지). 해석 로직 무변경.
- `scripts/run-test.py` — **raw log 파일 생성 안 함**. EXPAND 로그 탭은 기존 `build-report.md` / `test-report.md` tail 렌더 (보고서는 이미 DDTR 사이클에서 생성).

## 2. 데이터 흐름

```
GET /?subproject=monitor-v4&lang=ko
     │
     ▼
render_dashboard(model, lang, sps, sp)
     │
     ├─ _section_wp_cards(..)
     │     └─ _render_task_row_v2(task, running_ids, ...)
     │           ├─ badge_text = _phase_label(task.status, lang)   ← v4 NEW
     │           ├─ data-running = task.id in running_ids           ← v4 NEW
     │           ├─ data-state-summary = json.dumps({...})          ← v4 NEW
     │           ├─ <span class="spinner"> (CSS-controlled)         ← v4 NEW
     │           └─ <button class="expand-btn" data-task-id=...>    ← v4 NEW
     │
     ├─ _section_live_activity(..)  → <details data-fold-key="live-activity"> …
     │
     ├─ _section_dep_graph(..)      → (unchanged SSR)
     │
     └─ <aside id="task-panel">     ← v4 NEW: body-level fixed DOM, data-section 밖
```

클라이언트:
```
5초 polling  ──▶ patchSection(name, newHtml)
                   ├─ name=="live-activity" → replace + applyFoldStates + bindFoldListeners
                   ├─ name=="wp-cards"      → replace + applyFoldStates + bindFoldListeners
                   └─ 기본                   → replace
                          (trow-tooltip / task-panel 은 body 직계 → 영향 없음)

이벤트 delegation (document-level):
  mouseenter .trow[data-state-summary]  → 300ms 후 renderTrowTooltip(trow)
  click      .expand-btn                → openTaskPanel(dataset.taskId)

Graph client (2초 폴링):
  mouseover  node  → setTimeout(renderPopover(ele, "hover"), 2000)
  mouseout   node  → clearTimeout
  tap        node  → renderPopover(ele, "tap")  // 기존 경로 유지
```

## 3. 컴포넌트 상세

### 3.0 공유 계약

**`@keyframes spin`** 공통 CSS (인라인, `<style>` 블록 상단):
```css
@keyframes spin { to { transform: rotate(360deg); } }
.spinner, .node-spinner {
  display: none;  /* data-running="true" 컨텍스트에서만 */
  width: 10px; height: 10px;
  border: 2px solid var(--ink-3);
  border-top-color: var(--run);
  border-radius: 50%;
  animation: spin 1s linear infinite;
}
.trow[data-running="true"] .spinner { display: inline-block; }
.dep-node.running .node-spinner,
.dep-node[data-running="true"] .node-spinner { display: inline-block; position: absolute; top: 4px; right: 4px; }
```

**범용 fold 헬퍼** (현재 wp-cards 전용 로직을 일반화):
```javascript
function readFold(key, defaultOpen) {
  var v = localStorage.getItem('dev-monitor:fold:' + key);
  if (v === 'open') return true;
  if (v === 'closed') return false;
  return !!defaultOpen;
}
function writeFold(key, open) {
  localStorage.setItem('dev-monitor:fold:' + key, open ? 'open' : 'closed');
}
function applyFoldStates(container) {
  container.querySelectorAll('[data-fold-key]').forEach(function(el) {
    var key = el.getAttribute('data-fold-key');
    var def = el.hasAttribute('data-fold-default-open');
    if (readFold(key, def)) el.setAttribute('open', '');
    else el.removeAttribute('open');
  });
}
function bindFoldListeners(container) {
  container.querySelectorAll('[data-fold-key]').forEach(function(el) {
    if (el._foldBound) return;
    el._foldBound = true;
    el.addEventListener('toggle', function() {
      writeFold(el.getAttribute('data-fold-key'), el.open);
    });
  });
}
```

`patchSection` 의 `wp-cards` 특례와 `live-activity` 특례 모두 위 헬퍼 재사용.

### 3.1 단계 타임라인 제거

**대상 제거**:
- 함수: `_section_phase_timeline()` (monitor-server.py L3614–L3729)
- 헬퍼: `_timeline_rows()`, 상수 `_PHASE_TO_SEG`
- 호출점: `render_dashboard()` 내부 `_section_phase_timeline(...)` + `data-section="phase-timeline"` 래퍼 (L4191, L4207)
- CSS: `.panel.timeline`, `.tl-row`, `.tl-seg*` 관련 전체 블록
- 테스트: 기존 `test_phase_timeline_*`/`test_timeline_rows_*` 가 있다면 `test_dashboard_has_no_phase_timeline` 로 대체

**확인**:
- `_PHASE_TO_SEG` 가 다른 섹션(특히 dep-graph 색상 매핑)에서 재사용되는지 `grep -n "_PHASE_TO_SEG\|tl_row\|tl-row"` 로 검증 후 제거.
- dep-graph 의 상태→색 매핑은 별도 테이블(`_NODE_COLOR_MAP`)이 있으므로 충돌 없음 — 사전 점검만.

### 3.2 실시간 활동 기본 접힘 + fold 영속

**래핑**:
```python
def _section_live_activity(rows, lang):
    inner = "".join(_render_arow(r) for r in rows)
    return (
      f'<details class="activity-section" data-fold-key="live-activity">'
      f'  <summary><h2>{_t(lang,"live_activity")}</h2></summary>'
      f'  <div class="panel"><div class="activity" aria-live="polite">{inner}</div></div>'
      f'</details>'
    )
```

- 기본값: `data-fold-default-open` 속성 없음 → `readFold('live-activity', false)` → 닫힘.
- `wp-cards` 는 `data-fold-default-open` 속성을 유지해 기본 열림(기존 동작).
- `<details>` 네이티브 `toggle` 이벤트 → `bindFoldListeners` 가 localStorage 동기화.

**patchSection 특례**:
```javascript
function patchSection(name, newHtml) {
  var cur = document.querySelector('[data-section="'+name+'"]');
  if (!cur) return;
  if (name === 'dep-graph') return;
  if (name === 'hdr') { /* 기존 */ return; }
  if (name === 'wp-cards' || name === 'live-activity') {
    cur.innerHTML = newHtml;
    applyFoldStates(cur);
    bindFoldListeners(cur);
    return;
  }
  if (cur.innerHTML !== newHtml) cur.innerHTML = newHtml;
}
```

### 3.3 Task DDTR 단계 배지

**매핑 테이블** (i18n 반영, `_I18N` 에 neutral phase 키 추가):
```python
_PHASE_LABELS = {
  "[dd]": {"ko": "Design", "en": "Design"},
  "[im]": {"ko": "Build",  "en": "Build"},
  "[ts]": {"ko": "Test",   "en": "Test"},
  "[xx]": {"ko": "Done",   "en": "Done"},
}

def _phase_label(status_code: str, lang: str, *, failed: bool, bypassed: bool) -> str:
    if failed:   return {"ko":"Failed","en":"Failed"}[lang]
    if bypassed: return {"ko":"Bypass","en":"Bypass"}[lang]
    if not status_code: return {"ko":"Pending","en":"Pending"}[lang]
    return _PHASE_LABELS.get(status_code, {"ko":"Pending","en":"Pending"})[lang]
```

**`_render_task_row_v2()` 수정**:
```python
def _render_task_row_v2(item, running_ids, failed_ids, lang="ko"):
    failed    = item.id in failed_ids or (item.last_event or "").endswith("_failed")
    bypassed  = bool(item.bypassed)
    running   = item.id in running_ids
    badge_txt = _phase_label(item.status, lang, failed=failed, bypassed=bypassed)
    data_status = _trow_data_status(item, running_ids, failed_ids)  # unchanged
    data_phase  = (item.status or "").strip("[]") or "pending"      # v4 NEW
    state_summary = json.dumps({
        "status":       item.status,
        "last_event":   item.last_event,
        "last_event_at":item.last_event_at,
        "elapsed":      item.elapsed_seconds,
        "phase_tail":   item.phase_history_tail[:3],
    }, ensure_ascii=False)
    return (
      f'<div class="trow" data-task-id="{item.id}" data-status="{data_status}" '
      f'     data-phase="{data_phase}" data-running="{str(running).lower()}" '
      f"     data-state-summary='{html_escape(state_summary)}'>"
      f'  <div class="statusbar"></div>'
      f'  <div class="tid id">{item.id}</div>'
      f'  <div class="badge">{badge_txt}<span class="spinner" aria-hidden="true"></span></div>'
      f'  <div class="ttitle title">{html_escape(item.title)}</div>'
      f'  <div class="elapsed">{_fmt_elapsed(item.elapsed_seconds)}</div>'
      f'  <div class="retry">×{item.retry_count}</div>'
      f'  <div class="flags">{_bypass_flag(item)}</div>'
      f'  <button class="expand-btn" data-task-id="{item.id}" aria-label="Expand">↗</button>'
      f'</div>'
    )
```

### 3.4 Task running 스피너 + Dep-Graph 노드 스피너

**Work Packages**: 위 `_render_task_row_v2` 의 `.spinner` + CSS 조건부 표시(§3.0).

**Dep-Graph**:
```javascript
// graph-client.js  nodeHtmlLabel 템플릿
const tpl = nd => `
  <div class="dep-node status-${statusKey(nd)}"
       data-running="${!!nd.is_running_signal}">
    ${nd.is_running_signal ? '<span class="node-spinner"></span>' : ''}
    <div class="id">${escapeHtml(nd.id)}</div>
    <div class="title">${escapeHtml(nd.label)}</div>
  </div>`;
```

- `is_running_signal` 필드는 `/api/graph` payload 에서 제공(§3.8).
- CSS `.dep-node[data-running="true"] .node-spinner { display: inline-block }` — 공용 `spin` keyframe 재사용.

### 3.5 Task hover 툴팁 (Work Packages)

**툴팁 DOM** (body 직계, 한 번만 생성):
```html
<div id="trow-tooltip" role="tooltip" hidden></div>
```
```css
#trow-tooltip {
  position: fixed;
  z-index: 100;
  max-width: 420px;
  background: var(--bg-2);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 10px 12px;
  font: 12px/1.4 var(--font-mono);
  pointer-events: none;
  box-shadow: 0 4px 12px rgba(0,0,0,.3);
}
#trow-tooltip[hidden] { display: none; }
```

**JS** (event delegation + 300ms debounce):
```javascript
(function setupTaskTooltip(){
  var tip = document.getElementById('trow-tooltip');
  var timer = null;
  document.addEventListener('mouseenter', function(e){
    var row = e.target.closest && e.target.closest('.trow[data-state-summary]');
    if (!row) return;
    clearTimeout(timer);
    timer = setTimeout(function(){
      var data;
      try { data = JSON.parse(row.getAttribute('data-state-summary')); } catch(_) { return; }
      tip.innerHTML = renderTooltipHtml(data);
      var r = row.getBoundingClientRect();
      tip.style.top  = (r.top + window.scrollY) + 'px';
      tip.style.left = (r.right + 8) + 'px';
      tip.hidden = false;
    }, 300);
  }, true);
  document.addEventListener('mouseleave', function(e){
    var row = e.target.closest && e.target.closest('.trow[data-state-summary]');
    if (!row) return;
    clearTimeout(timer);
    tip.hidden = true;
  }, true);
  window.addEventListener('scroll', function(){ tip.hidden = true; }, true);
})();
```

`renderTooltipHtml(data)` 는 status / last_event / elapsed / phase_tail[0..2] 을 `<dl>` 로 렌더.

### 3.6 Task EXPAND 슬라이딩 패널

**DOM** (body 직계):
```html
<div id="task-panel-overlay" hidden></div>
<aside id="task-panel" class="slide-panel" hidden aria-labelledby="task-panel-title">
  <header>
    <h3 id="task-panel-title"></h3>
    <button id="task-panel-close" aria-label="Close">×</button>
  </header>
  <div id="task-panel-body"></div>
</aside>
```
```css
.slide-panel {
  position: fixed; top: 0; right: -560px; bottom: 0;
  width: 560px; background: var(--bg-2); border-left: 1px solid var(--border);
  overflow-y: auto; z-index: 90;
  transition: right 0.22s cubic-bezier(.4,0,.2,1);
}
.slide-panel.open { right: 0; }
.slide-panel[hidden] { display: block; }  /* transition용 — open 클래스로 제어 */
#task-panel-overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,.3);
  z-index: 80;
}
```

**JS**:
```javascript
async function openTaskPanel(taskId){
  var sp = new URLSearchParams(window.location.search).get('subproject') || 'all';
  var r = await fetch('/api/task-detail?task='+encodeURIComponent(taskId)+'&subproject='+encodeURIComponent(sp));
  if (!r.ok) { /* show error banner */ return; }
  var d = await r.json();
  document.getElementById('task-panel-title').textContent = d.task_id + ' — ' + d.title;
  document.getElementById('task-panel-body').innerHTML =
      renderWbsSection(d.wbs_section_md)
    + renderStateJson(d.state)
    + renderArtifacts(d.artifacts);
  document.getElementById('task-panel').classList.add('open');
  document.getElementById('task-panel-overlay').hidden = false;
}
function closeTaskPanel(){ /* reverse */ }
document.addEventListener('click', function(e){
  var btn = e.target.closest && e.target.closest('.expand-btn');
  if (btn) { e.preventDefault(); openTaskPanel(btn.getAttribute('data-task-id')); return; }
  if (e.target.id === 'task-panel-close' || e.target.id === 'task-panel-overlay') closeTaskPanel();
});
document.addEventListener('keydown', function(e){ if (e.key === 'Escape') closeTaskPanel(); });
```

`renderWbsSection(md)` 는 경량 마크다운 변환(`^##?#?\s`, `^\s*- `, ```` ``` ```` 블록) — 외부 라이브러리 없음. 위험 HTML은 escape 후 재구성.

### 3.7 Dep-Graph 2초 hover 툴팁

**변경 대상**: `skills/dev-monitor/vendor/graph-client.js` (기존 tap 경로 L321 주변).

```javascript
let hoverTimer = null;
cy.on("mouseover", "node", evt => {
  const ele = evt.target;
  clearTimeout(hoverTimer);
  hoverTimer = setTimeout(() => {
    popoverNodeId = ele.id();
    renderPopover(ele, "hover");
  }, 2000);
});
cy.on("mouseout", "node", () => {
  clearTimeout(hoverTimer);
  if (popoverSource === "hover") hidePopover();
});
cy.on("tap", "node", evt => {
  clearTimeout(hoverTimer);
  popoverNodeId = evt.target.id();
  renderPopover(evt.target, "tap");
});
```

`renderPopover(ele, source)` 에 `source` 인자 추가 → 팝오버 DOM 에 `data-source` 속성 저장. `hidePopover()` 는 tap 소스는 외부 클릭/ESC 까지 유지, hover 소스는 `mouseout` 시 즉시 숨김.

payload 확장(§3.8) 덕분에 `renderPopover` 내 기존 `phase_history` 렌더 라인이 실데이터를 표시.

### 3.8 `/api/graph` payload 확장

노드 dict 생성부에 다음 필드 추가:

```python
node = {
    # existing
    "id": task.id, "label": task.title, "status": node_status,
    "is_critical": ..., "is_bottleneck": ..., "fan_in": ..., "fan_out": ...,
    "bypassed": task.bypassed, "wp_id": task.wp_id, "depends": list(task.depends),
    # v4 NEW
    "phase_history_tail": [_phase_entry_dict(e) for e in task.phase_history_tail[:3]],
    "last_event":         task.last_event,
    "last_event_at":      task.last_event_at,
    "elapsed_seconds":    task.elapsed_seconds,
    "is_running_signal":  task.id in running_ids,
}
```

`running_ids` 는 현재 `/api/state` 구축 시 계산하는 set 재사용.

### 3.9 `/api/task-detail` 신규 라우트

**계약**:
- `GET /api/task-detail?task={TSK-ID}&subproject={sp}`
- 404 if task not found in effective docs_dir
- 200 with:
  ```json
  {
    "task_id": "TSK-02-04",
    "title": "Task EXPAND 슬라이딩 패널",
    "wp_id": "WP-02",
    "source": "wbs",
    "wbs_section_md": "...raw markdown from '### TSK-02-04:' up to next '### ' or '## '...",
    "state": { "status": "[im]", "last": {...}, "phase_history": [...], "elapsed_seconds": 123, "bypassed": false },
    "artifacts": [
      {"name": "design.md",      "path": "docs/monitor-v4/tasks/TSK-02-04/design.md",      "exists": true,  "size": 4210},
      {"name": "test-report.md", "path": "docs/monitor-v4/tasks/TSK-02-04/test-report.md", "exists": false, "size": 0},
      {"name": "refactor.md",    "path": "docs/monitor-v4/tasks/TSK-02-04/refactor.md",    "exists": false, "size": 0}
    ]
  }
  ```

**구현**:
```python
_WBS_SECTION_RE = re.compile(r"^### (?P<id>TSK-\S+):", re.MULTILINE)

def _extract_wbs_section(wbs_md: str, task_id: str) -> str:
    lines = wbs_md.splitlines()
    start = None
    for i, ln in enumerate(lines):
        if ln.startswith(f"### {task_id}:"):
            start = i; break
    if start is None:
        return ""
    end = len(lines)
    for j in range(start+1, len(lines)):
        if lines[j].startswith("### ") or lines[j].startswith("## "):
            end = j; break
    return "\n".join(lines[start:end]).strip()
```

Feature 모드면 `state["features"]` 에서 검색, `wbs_section_md` 대신 `feat_spec_md` (또는 동일 키로 `spec.md` 본문) 반환 — source 필드로 구분.

**아티팩트 탐지**:
```python
ART_NAMES = ("design.md", "test-report.md", "refactor.md")
def _collect_artifacts(task_dir: Path) -> list[dict]:
    return [
      {"name": n, "path": str(task_dir/n), "exists": (task_dir/n).exists(),
       "size": (task_dir/n).stat().st_size if (task_dir/n).exists() else 0}
      for n in ART_NAMES
    ]
```

### 3.10 Task 모델/에스컬레이션 배지

**DDTR 고정 규칙** (`_DDTR_PHASE_MODELS`):
```python
_DDTR_PHASE_MODELS = {
    "dd": lambda task: task.model or "sonnet",   # wbs.md - model: 필드
    "im": lambda task: "sonnet",                  # 고정
    "ts": lambda task: _test_phase_model(task),   # retry_count 기반
    "xx": lambda task: "sonnet",                  # refactor 고정
}
def _test_phase_model(task) -> str:
    # MAX_ESCALATION=2 규칙: retry_count 0 → haiku, 1 → sonnet, ≥2 → opus
    rc = task.retry_count
    if rc >= 2: return "opus"
    if rc >= 1: return "sonnet"
    return "haiku"
```

**`_render_task_row_v2` 확장**:
```python
# item.model 은 wbs-parse.py 에서 이미 제공
model_chip = f'<span class="model-chip" data-model="{item.model or "sonnet"}">{item.model or "sonnet"}</span>'
escalation_flag = '<span class="escalation-flag" aria-label="escalated">⚡</span>' if item.retry_count >= 2 else ''
# state_summary JSON 에 phase_models dict 추가 (툴팁용)
state_summary = json.dumps({
    ...,
    "model":        item.model or "sonnet",
    "retry_count":  item.retry_count,
    "phase_models": {
        "design":   item.model or "sonnet",
        "build":    "sonnet",
        "test":     _test_phase_model(item),
        "refactor": "sonnet",
    },
    "escalated":    item.retry_count >= 2,
}, ensure_ascii=False)
```

**CSS**:
```css
.model-chip {
  display: inline-block; padding: 1px 6px; margin-left: 6px;
  font: 10px/1.4 var(--font-mono); border-radius: 3px;
  background: var(--bg-3); color: var(--ink-2);
  border: 1px solid var(--border);
}
.model-chip[data-model="opus"]   { background: #3b2f4a; color: #e8d8ff; }
.model-chip[data-model="sonnet"] { background: #2a3a4a; color: #cce0f0; }
.model-chip[data-model="haiku"]  { background: #2a3f30; color: #c8e6c9; }
.escalation-flag { margin-left: 4px; color: var(--warn); font-size: 11px; }
```

**툴팁 렌더 확장** (`renderTooltipHtml`):
```javascript
function renderPhaseModels(pm, escalated) {
  var testLine = escalated
    ? 'haiku → ' + pm.test + ' (retry #' + data.retry_count + ') ⚡'
    : pm.test;
  return '<dl class="phase-models">'
    + '<dt>Design</dt><dd>' + pm.design + '</dd>'
    + '<dt>Build</dt><dd>'  + pm.build  + '</dd>'
    + '<dt>Test</dt><dd>'   + testLine  + '</dd>'
    + '<dt>Refactor</dt><dd>' + pm.refactor + '</dd>'
    + '</dl>';
}
```

**사용 토큰 영향**: 워커 경로 0 (wbs.md · state.json 무변경). 대시보드 payload 증가 ~100B/Task (phase_models dict).

### 3.11 EXPAND 패널 § 로그 섹션

**`/api/task-detail` 응답 확장**:
```python
LOG_NAMES = ("build-report.md", "test-report.md")
_ANSI_RE = re.compile(r"\x1b\[[\d;]*[A-Za-z]")

def _tail_report(path: Path, max_lines: int = 200) -> dict:
    if not path.exists():
        return {"name": path.name, "tail": "", "truncated": False,
                "lines_total": 0, "exists": False}
    text = path.read_text(encoding="utf-8", errors="replace")
    stripped = _ANSI_RE.sub("", text)
    lines = stripped.splitlines()
    total = len(lines)
    tail_lines = lines[-max_lines:] if total > max_lines else lines
    return {
        "name":        path.name,
        "tail":        "\n".join(tail_lines),
        "truncated":   total > max_lines,
        "lines_total": total,
        "exists":      True,
    }

def _collect_logs(task_dir: Path) -> list[dict]:
    return [_tail_report(task_dir / n) for n in LOG_NAMES]
```

**응답 스키마 추가 필드**:
```json
"logs": [
  {"name": "build-report.md", "tail": "...", "truncated": true,  "lines_total": 342, "exists": true},
  {"name": "test-report.md",  "tail": "...", "truncated": false, "lines_total":  87, "exists": true}
]
```

**클라이언트 렌더** (`openTaskPanel` 내 body 구성에 `renderLogs(d.logs)` 추가):
```javascript
function renderLogs(logs) {
  if (!logs || !logs.length) return '';
  var parts = ['<section class="panel-logs"><h4>§ 로그</h4>'];
  logs.forEach(function(log) {
    if (!log.exists) {
      parts.push('<div class="log-empty">' + log.name + ' — 보고서 없음</div>');
      return;
    }
    var hdr = log.name + (log.truncated ? ' (마지막 200줄 / 전체 ' + log.lines_total + '줄)' : '');
    parts.push('<details class="log-entry" open><summary>' + hdr + '</summary>');
    parts.push('<pre class="log-tail">' + escapeHtml(log.tail) + '</pre>');
    parts.push('</details>');
  });
  parts.push('</section>');
  return parts.join('');
}
```

**CSS**:
```css
.panel-logs pre.log-tail {
  max-height: 300px; overflow: auto;
  background: var(--bg-1); border: 1px solid var(--border);
  padding: 8px 10px; font: 11px/1.3 var(--font-mono);
  white-space: pre-wrap; word-break: break-all;
}
.log-empty { color: var(--ink-3); font-style: italic; padding: 6px 0; }
```

**사용 토큰 영향**: 워커 경로 0. `/api/task-detail` 응답 증가는 drill-down 시만 (워커/Claude 조회 없음 시 0). Claude 가 debug 목적으로 호출 시 +~5-10KB per call.

### 3.12 WP 머지 준비도 뱃지

**아키텍처 — LLM 해석 금지 원칙**:

```
워커 ([im] 완료 후)                 scanner (데몬 or on-demand)      대시보드
───────────────────                ─────────────────────────      ───────────
merge-preview.py                   merge-preview-scanner.py       _section_wp_cards
  --output docs/tasks/              (2분 주기 cron or 버튼)          _merge_badge()
  {TSK-ID}/merge-preview.json        │                             │
     │                               │                             ▼
     │                               ▼                             GET /api/merge-status?wp=WP-02
     └─ 파일 저장 (zero LLM)         docs/wp-state/                    │
                                     {WP-ID}/merge-status.json         ▼
                                     (집계 + auto-merge 필터)       JSON 응답 (WP 별)
```

**`scripts/merge-preview-scanner.py`** (신규, stdlib only):
```python
# 사용법: python3 merge-preview-scanner.py [--docs docs/monitor-v4] [--force]
# 동작: docs/monitor-v4/tasks/TSK-*/merge-preview.json 스캔 →
#       WP 별 집계 → docs/wp-state/WP-XX/merge-status.json 생성

AUTO_MERGE_FILES = {"state.json", "wbs.md", "wbs-merge-log.md"}  # 드라이버 보유

def _classify_wp(wp_id: str, task_previews: list[dict]) -> dict:
    """Aggregate per-WP merge state. Returns dict with state + conflicts."""
    all_conflicts = []
    stale = False
    now = time.time()
    for tp in task_previews:
        mtime = tp.get("_mtime", 0)
        if now - mtime > 1800:  # 30 min
            stale = True
        for c in tp.get("conflicts", []):
            fname = Path(c["file"]).name
            if fname in AUTO_MERGE_FILES: continue
            all_conflicts.append(c)
    incomplete = sum(1 for tp in task_previews if tp.get("_status") != "[xx]")
    if incomplete > 0:
        return {"state": "waiting", "pending_count": incomplete, "stale": stale, "conflicts": []}
    if all_conflicts:
        return {"state": "conflict", "conflict_count": len(all_conflicts),
                "stale": stale, "conflicts": all_conflicts}
    return {"state": "ready", "stale": stale, "conflicts": []}
```

**뱃지 HTML 렌더** (`_merge_badge(wp_status: dict, lang: str) -> str`):
```python
def _merge_badge(ws: dict, lang: str) -> str:
    state = ws.get("state", "waiting")
    stale = ws.get("stale", False)
    label_map = {
        "ready":    ("🟢", {"ko": "머지 가능",   "en": "Ready"}),
        "waiting":  ("🟡", {"ko": f"{ws.get('pending_count', 0)} Task 대기",
                            "en": f"{ws.get('pending_count', 0)} pending"}),
        "conflict": ("🔴", {"ko": f"{ws.get('conflict_count', 0)} 파일 충돌 예상",
                            "en": f"{ws.get('conflict_count', 0)} conflicts"}),
    }
    emoji, labels = label_map.get(state, label_map["waiting"])
    stale_mark = ' <span class="stale">⚠ stale</span>' if stale else ''
    return (f'<button class="merge-badge" data-state="{state}" data-wp="{ws["wp_id"]}" '
            f'aria-label="merge {state}">{emoji} {labels[lang]}{stale_mark}</button>')
```

**`/api/merge-status` 라우트** (GET):
- `/api/merge-status?subproject={sp}` → 전체 WP 상태 JSON
- `/api/merge-status?subproject={sp}&wp={WP-ID}` → 단일 WP 상세 (패널용)
- 응답: `docs/wp-state/{WP-ID}/merge-status.json` 읽기(mtime 캐시) 또는 on-demand scanner 호출.

**슬라이드 패널 통합**:
- 기존 `task-panel` DOM 재사용. `openMergePanel(wpId)` 함수가 `/api/merge-status?wp=X` fetch → 별도 섹션으로 렌더.
- DOM delegation: `.merge-badge` 클릭 → `openMergePanel(dataset.wp)`.
- 패널 본문: `§ 머지 프리뷰` — 충돌 파일 목록(각 hunk 3-5줄 preview), stale 시 경고 배너.

**워커 프롬프트 증분** (`skills/dev-build/references/tdd-prompt-template.md`):
```markdown
## [im] 완료 후 (토큰 최소화 경로)

`[im]` 상태가 완료되면 다음 한 줄을 실행한다. **결과 해석은 하지 말고 즉시 다음 phase(ts)로 진행**:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/merge-preview.py \
  --remote origin --target main \
  --output {DOCS_DIR}/tasks/{TSK-ID}/merge-preview.json
```

이 파일은 대시보드 scanner(`merge-preview-scanner.py`)가 집계하여 WP 뱃지를 갱신한다. 충돌 판정은 scanner와 사람(뱃지 클릭)이 수행하므로 워커는 파일 기록만 담당한다.
```

**사용 토큰 영향**: 워커 증가 = 위 1줄 규약 + 실행 + stdout 무시 ≈ **50-80 토큰/Task**. LLM 해석 없으므로 conflict 재시도 증폭 없음.

### 3.13 글로벌 필터 바 (클라이언트 전용)

**DOM** (`_section_filter_bar` 렌더, `<header>` 아래 sticky):
```html
<div class="filter-bar" data-section="filter-bar" role="search">
  <input type="search" id="fb-q" placeholder="🔍 검색 (ID / 제목)" />
  <select id="fb-status">
    <option value="">상태</option>
    <option value="running">Running</option>
    <option value="done">Done</option>
    <option value="failed">Failed</option>
    <option value="bypass">Bypass</option>
    <option value="pending">Pending</option>
  </select>
  <select id="fb-domain">
    <option value="">도메인</option>
    <!-- dynamically populated from /api/state.distinct.domains -->
  </select>
  <select id="fb-model">
    <option value="">모델</option>
    <option value="opus">opus</option>
    <option value="sonnet">sonnet</option>
    <option value="haiku">haiku</option>
  </select>
  <button id="fb-reset" aria-label="Reset">✕</button>
</div>
```

**CSS** — sticky top, z-index 하드 고정:
```css
.filter-bar {
  position: sticky; top: 0; z-index: 70;
  display: flex; gap: 8px; padding: 8px 12px;
  background: var(--bg-1); border-bottom: 1px solid var(--border);
}
.filter-bar input, .filter-bar select, .filter-bar button {
  font: 12px var(--font-body); padding: 4px 8px;
  background: var(--bg-2); color: var(--ink-1);
  border: 1px solid var(--border); border-radius: 3px;
}
```

**JS — 단일 `applyFilters()` 함수 + URL sync**:
```javascript
function currentFilters() {
  return {
    q:      document.getElementById('fb-q').value.trim().toLowerCase(),
    status: document.getElementById('fb-status').value,
    domain: document.getElementById('fb-domain').value,
    model:  document.getElementById('fb-model').value,
  };
}
function matchesRow(trow, f) {
  if (f.q) {
    var hay = (trow.dataset.taskId + ' ' + trow.querySelector('.ttitle').textContent).toLowerCase();
    if (hay.indexOf(f.q) === -1) return false;
  }
  if (f.status && trow.dataset.status !== f.status && trow.dataset.phase !== f.status) return false;
  if (f.domain && trow.dataset.domain !== f.domain) return false;
  if (f.model && trow.querySelector('.model-chip')?.dataset.model !== f.model) return false;
  return true;
}
function applyFilters() {
  var f = currentFilters();
  document.querySelectorAll('.trow').forEach(function(r) {
    r.style.display = matchesRow(r, f) ? '' : 'none';
  });
  // Dep-Graph via graph-client.js hook
  if (window.depGraph && window.depGraph.applyFilter) {
    window.depGraph.applyFilter(function(node) {
      if (f.status && node.data('status') !== f.status) return false;
      if (f.domain && node.data('domain') !== f.domain) return false;
      if (f.model  && node.data('model')  !== f.model)  return false;
      if (f.q) {
        var hay = (node.id() + ' ' + (node.data('label') || '')).toLowerCase();
        if (hay.indexOf(f.q) === -1) return false;
      }
      return true;
    });
  }
  syncUrl(f);
}
function syncUrl(f) {
  var url = new URL(location.href);
  ['q', 'status', 'domain', 'model'].forEach(function(k) {
    if (f[k]) url.searchParams.set(k, f[k]);
    else url.searchParams.delete(k);
  });
  history.replaceState(null, '', url);
}
function loadFiltersFromUrl() {
  var p = new URLSearchParams(location.search);
  document.getElementById('fb-q').value      = p.get('q') || '';
  document.getElementById('fb-status').value = p.get('status') || '';
  document.getElementById('fb-domain').value = p.get('domain') || '';
  document.getElementById('fb-model').value  = p.get('model')  || '';
}
// 이벤트
['fb-q', 'fb-status', 'fb-domain', 'fb-model'].forEach(function(id) {
  document.getElementById(id).addEventListener('input', applyFilters);
  document.getElementById(id).addEventListener('change', applyFilters);
});
document.getElementById('fb-reset').addEventListener('click', function() {
  ['fb-q', 'fb-status', 'fb-domain', 'fb-model'].forEach(function(id) {
    document.getElementById(id).value = '';
  });
  applyFilters();
});
// patchSection 후 자동 재적용 — wp-cards / live-activity 교체에 필터 복원
var _origPatch = window.patchSection;
window.patchSection = function(name, html) {
  _origPatch.call(this, name, html);
  if (name === 'wp-cards' || name === 'live-activity') applyFilters();
};
// 초기 로드
loadFiltersFromUrl();
applyFilters();
```

**`graph-client.js` `applyFilter(predicate)` 훅** (신규 export):
```javascript
// graph-client.js 모듈 스코프
let _filterPredicate = null;
export function applyFilter(predicate) {
  _filterPredicate = predicate;
  cy.nodes().forEach(function(node) {
    var match = predicate ? predicate(node) : true;
    node.style('opacity', match ? 1.0 : 0.3);
  });
  cy.edges().forEach(function(edge) {
    var src = edge.source(), dst = edge.target();
    var match = !predicate || (predicate(src) && predicate(dst));
    edge.style('line-color', match ? '' : 'var(--ink-3)');
    edge.style('opacity', match ? 1.0 : 0.3);
  });
}
// window.depGraph = { applyFilter, ... }
```

**필수 `data-*` 추가** (`_render_task_row_v2` 보강):
- `data-domain="{domain}"` — 필터 바 도메인 매치용
- (이미 `data-status`, `data-phase` 는 존재)
- `/api/graph` payload 노드에 `domain`, `model` 필드 추가

**사용 토큰 영향**: 서버 payload 증가 ~30B/Task (domain + model 필드), 워커 증가 0.

## 4. 성능/호환

- `/api/graph` payload: 노드당 +~400B (phase tail 3엔트리 + is_running_signal + merge_state + domain + model). 50 노드 기준 +20KB, 2초 폴링에서 허용.
- `/api/task-detail`: on-demand (Expand 클릭 시만). wbs.md 는 서버 시작 시 1회 로드 + 수정 mtime 기반 재로드(기존 패턴). `logs[]` 필드는 `build-report.md`·`test-report.md` 각 tail 200줄 — 최악 ~40KB/응답.
- `/api/merge-status`: on-demand (뱃지 클릭 시) 또는 `/api/state` 번들 응답에 WP 요약만 포함. 상세 conflicts 배열은 on-demand.
- localStorage 키: 기존 `dev-monitor:fold:{WP-ID}` 외에 `dev-monitor:fold:live-activity` 1건 추가.
- `@keyframes spin` + `.spinner`: GPU accel(`transform`) 사용, DOM 10+ 동시 회전 시에도 1% 미만 CPU (macOS Chrome 기준 추정).
- 서버 측 `_WBS_SECTION_RE` 는 정규식 1회 스캔 — O(n) over wbs.md.
- `merge-preview-scanner.py`: 기본 on-demand (`/api/merge-status` 호출 시 staleness 확인 후 필요하면 재실행). 주기 스캔 데몬은 옵션 — `python3 scripts/merge-preview-scanner.py --daemon 120`. 50 Task 기준 5초 이내 완료(zero LLM).
- 필터 바: 클라이언트 전용 DOM traversal — 50 Task 기준 `applyFilters()` 5ms 이하.
- 기존 i18n/필터/탭 UI 모두 호환, 계약 변경 없음.
- **사용 토큰 예산** (v4 add-on 4종 전체):
  - 워커 증가: `merge-preview.py --output` 실행 규약 1줄 = Task당 **~50-80 토큰** (대부분 #4).
  - Claude 조회 증가: `/api/state` payload +~1KB (WP별 merge_state), `/api/task-detail` +~10-40KB (logs tail) — on-demand.
  - N=20 Task 프로젝트 1회 DDTR 사이클 누적: **~1-2k 토큰** (워커 기준, #4가 지배적).

## 5. 위험·완화

| # | 위험 | 완화 |
|---|------|------|
| R1 | `_PHASE_TO_SEG` 또는 `_timeline_rows` 가 다른 섹션에서 참조되고 있을 가능성 | 제거 전 `grep -rn "_PHASE_TO_SEG\|_timeline_rows\|tl-row"` 로 확인. 참조 없음 확인 후 제거. 테스트 회귀로 2차 검증. |
| R2 | wbs.md 섹션 추출이 `####` (h4) 을 다음 Task 로 오인식 | `_WBS_SECTION_RE` 는 `### {TSK-ID}:` 앵커로만 매치. 종료 조건도 `### ` / `## ` 라인에만 매치 — `#### PRD 요구사항` 등 h4 는 섹션 내부로 포함됨. monitor-v3 WBS 에서 실제 샘플 추출 검증. |
| R3 | localStorage 마이그레이션 — 기존 사용자가 v3 에서 live-activity fold 키가 없어 v4 첫 접속 시 기본값(닫힘)만 적용 | 정책: 첫 접속에서 무조건 닫힘이 기본이므로 마이그레이션 불필요. 사용자 1회 클릭으로 상태 생성. |
| R4 | Task tooltip JSON 인젝션 — state.json 값에 quote/HTML 주입 가능성 | `json.dumps(..., ensure_ascii=False)` 후 `html.escape(s, quote=True)` 적용. `data-state-summary` 는 single-quote 로 감싸고 내부 single-quote 은 `&#39;` 치환. |
| R5 | EXPAND 패널이 refresh 중 `task-panel-body` 내용을 덮어쓸 우려 | 패널은 `data-section` 밖 body 직계 → patchSection 영향 없음. 열림 상태도 클래스 기반이라 생존. |
| R6 | Dep-Graph hover 타이머가 pan/zoom 중에도 살아남아 오작동 | 기존 코드의 `cy.on("pan zoom", ...)` 핸들러에 `clearTimeout(hoverTimer)` 추가. |
| R7 | `.running` signal 판정이 과거 시그널을 포함(cleanup 누락) 시 스피너가 잘못 표시 | 기존 `running_ids` 스캐너의 mtime 필터(`_RUNNING_STALE_SEC`, 기본 2분) 그대로 재사용 — 추가 작업 없음. |
| R8 | `retry_count` 기반 에스컬레이션 추론이 MAX_ESCALATION 변경 시 오작동 | `_test_phase_model()` 이 환경변수 `MAX_ESCALATION` (기본 2) 을 읽어 동적 적용. 테스트에서 2/3/4 값 모두 검증. 향후 상수 변경 시 한 곳만 업데이트. |
| R9 | `build-report.md` 가 아직 생성되지 않은 상태([im] 진행 중)에서 로그 탭 호출 시 빈 응답 | `_tail_report()` 가 `exists: false` 필드로 구분. 클라이언트는 "보고서 없음" placeholder 표시. 에러 대신 정상 응답. |
| R10 | `merge-preview.py --output` 옵션이 없는 레거시 버전과 충돌 | v4 구현 시 `merge-preview.py` 에 `--output` 플래그 선행 추가(하위 호환 stdout 유지). 미존재 시 워커는 stdout 을 shell 리다이렉션(`> path`)으로 저장 — 차선책 명시. |
| R11 | merge-preview scanner 가 동시 실행되어 `merge-status.json` 레이스 | scanner 는 write 전에 임시 파일 → `rename` 원자 교체. 기존 signal-helper 패턴 재사용. |
| R12 | 필터 바 URL 쿼리가 subproject 탭 전환 등 기존 쿼리와 충돌 | 예약 파라미터(`q`, `status`, `domain`, `model`) 만 필터용 — 기존 `subproject`, `lang` 은 그대로. `URLSearchParams` get/set 으로 안전 병합. |
| R13 | `applyFilters()` 가 `patchSection` 이후 매번 전체 `.trow` 순회 → 50+ Task 에서 지연 | wp-cards 전체는 1개 섹션이고 매 2-5초 갱신이므로 50 Task × O(1) filter = 최악 0.5ms. hot path 아님. |
| R14 | 머지 뱃지에서 `state.json`/`wbs.md` 필터가 과도 — 사용자가 실제 로직 충돌을 놓칠 가능성 | `AUTO_MERGE_FILES` 세트를 상수로 분리. 뱃지는 필터 적용, 슬라이드 패널 상세는 **모든** conflict 를 표시하되 auto-merge 파일은 회색 disabled 로 구분. |
