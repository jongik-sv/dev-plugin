# core-dashboard-asset-split: 설계

> Phase 2-c — `core-decomposition` Phase 1 + `core-http-split` (Phase 2-a) +
> `core-renderer-split` (Phase 2-b) 이후 core.py 잔여 5,418 LOC 중 **인라인
> CSS/JS 자산 상수 5개**(실측 2,177 LOC)를 `scripts/monitor_server/static/`
> 외부 파일로 분리한다. 본 feature는 Phase 2 시리즈의 세 번째이자 마지막,
> 그리고 **최상위 리스크** (시각 회귀 자석 + 테스트 regex-parse lock 이중
> 위험)이다.

---

## 0. SSOT 조사 결과 (Design time facts, 필수 선행 조사)

### 0.1 동작 검증 — `get_static_bundle` vs on-disk static/

실측:
```
$ python3 -c "...md5 및 len 비교..."
style.css bundle md5: dcab587d6fd4fc32f46117fbdce06e44  len: 51028
style.css disk   md5: 0c39eb444e20f1ace7f03c2ba3b22ae5  len: 48451
app.js   bundle md5: 479d0ac147cd74f4664c00acd0d38c78  len: 35079
app.js   disk   md5: 4f91deae50f36be89aa517c4cb2f3e65  len: 31688

CSS identical: False
JS identical: False
```

- `get_static_bundle(name)` (core.py L1721) 는 인라인 상수 6개
  (`DASHBOARD_CSS`, `_task_panel_css()`, `_PANE_CSS` / `_DASHBOARD_JS`,
  `_task_panel_js()`, `_PANE_JS`) 를 **메모리 내에서 concat** 하여 반환한다.
- `scripts/monitor_server/static/style.css` (48,451 B) 와
  `.../static/app.js` (31,688 B) 는 인라인 번들 (51,028 B / 35,079 B) 과
  **md5/length 모두 불일치**. 즉 디스크 파일은 **stale 스냅샷**이며 현재
  런타임에는 서빙되지 않는다.

### 0.2 서빙 경로 확정

- `handlers.py::Handler._serve_local_static` (L226–L270):
  - **Primary**: `core.get_static_bundle(filename)` 호출 → 인라인 번들 반환
    (source of truth).
  - **Fallback**: `monitor_server/static/{filename}` 디스크 파일 (번들이
    빈 바이트일 때만).
  - Content-Type: CSS `text/css`, JS `application/javascript`,
    Cache-Control `public, max-age=300`.
- `handlers.py::Handler._serve_vendor_js` (L196–L224):
  - cytoscape/dagre 등 5개 vendor JS만 `skills/dev-monitor/vendor/` 에서
    서빙. CSS/JS 번들과 무관.
- `core.py::_handle_static` (L3427) 은 facade 유지용 레거시 구현. 현 런타임
  핸들러는 `handlers.Handler` 쪽이며 (monitor-server.py 진입점 확인 완료),
  `_handle_static` 은 `_VENDOR_WHITELIST` 만 처리한다 (CSS/JS 경로 없음).

### 0.3 HTML 임베딩 방식

- **Dashboard** (`render_dashboard`, core.py L3288–L3310):
  `<link rel="stylesheet" href="/static/style.css?v={css_ver}">` +
  `<script src="/static/app.js?v={js_ver}" defer></script>`
  — **외부 로드**. HTML body 자체에는 CSS/JS 리터럴 없음.
  `css_ver`/`js_ver` 는 `get_static_version(name)` → `get_static_bundle(name)`
  의 md5 앞 8자로 캐시버스팅.
- **Pane HTML** (`renderers/panel.py::_render_pane_html`, L19–L61):
  동일 외부 로드 패턴 (`<link href="/static/style.css?v=...">`).

**결론**: HTML output 은 이미 **byte-level 에서 CSS/JS 원문을 포함하지 않는다**.
즉 spec.md §리스크 "시각 회귀 자석" 의 대상은 "GET / md5 불변" 이 아니라
**"GET /static/style.css md5 불변"** 으로 재정의되어야 한다. 자산 파일을
파일 시스템에서 읽도록 전환하더라도, 핵심 검증 대상은
`curl /static/style.css | md5sum` 값이다.

### 0.4 테스트 접근 패턴 분류 (22개 테스트 파일, 5개 심볼 참조)

`grep -l "DASHBOARD_CSS\|_DASHBOARD_JS\|_PANE_CSS\|_task_panel_css\|_task_panel_js\|_TASK_PANEL_JS"
scripts/test_*.py` → 22개 파일.

| 접근 패턴 | 대표 파일 | 영향 |
|-----------|-----------|------|
| **Attribute 접근** (`mod.DASHBOARD_CSS`) | `test_monitor_kpi.py`, `test_monitor_phase_badge_colors.py`, `test_monitor_task_row.py`, `test_monitor_team_preview.py`, `test_monitor_filter_bar.py`, `test_monitor_info_popover.py`, `test_dashboard_css_tsk0101.py` | **영향 없음** — core가 `DASHBOARD_CSS = <file_content_str>` 를 그대로 노출하면 통과 |
| **Regex source-parse** (`re.search(r'DASHBOARD_CSS\s*=\s*"""(.*?)"""', src)`) | `test_font_css_variables.py`, `test_monitor_dep_graph_html.py`, `test_monitor_shared_css.py`, `test_monitor_fold.py`, `test_monitor_fold_helper_generic.py`, `test_monitor_dep_graph_summary.py`, `test_monitor_pane_size.py` | **BREAK** — 인라인 삼중따옴표 블록 제거 시 `_CSS_MATCH` 가 None → 전 테스트 실패 |
| **Fallback 설계 (이미 대비됨)** | `test_monitor_render.py`, `test_monitor_fold_live_activity.py`, `test_render_dashboard_tsk0106.py`, `test_monitor_task_detail_api.py`, `test_monitor_task_expand_ui.py` | **이미 외부 파일 경로 허용** — `app.js` / `style.css` 디스크 파일을 폴백으로 읽음 |
| **함수 호출** (`monitor_server._task_panel_js()`) | `test_monitor_merge_badge.py`, `test_monitor_progress_header.py`, `test_monitor_e2e.py` | 함수 시그니처 유지 시 영향 없음 |

**핵심 제약**: "Regex source-parse" 그룹 7개 테스트가 본 feature 의 가장 큰
장벽이다. spec.md 의 "pre-existing 2 failed + 1 flaky 허용, 나머지 green"
기준을 지키려면 이 7개 테스트를 깨뜨리지 않는 방식이 필요.

### 0.5 `_minify_css` 의미 재확인

- core.py L1699–L1704:
  ```python
  def _minify_css(css: str) -> str:
      return re.sub(r"\n\s*", " ", css).strip()
  DASHBOARD_CSS = _minify_css(DASHBOARD_CSS)
  ```
- **rebinds** `DASHBOARD_CSS` 글로벌 변수를 minified 버전으로 교체 (in-place).
- 즉 런타임에서 `mod.DASHBOARD_CSS` 속성값은 이미 minified 상태.
- `_task_panel_css()` / `_PANE_CSS` 에는 minify 미적용 (이미 함수형/압축된
  정적 문자열로 작성됨).
- **이관 전략에 미치는 영향**: 외부 `dashboard.css` 파일을 만들 때, **원본
  (non-minified) 문자열** 을 저장하고 모듈 import 시 `_minify_css()` 적용
  후 `DASHBOARD_CSS` 속성에 바인딩. 기존 어트리뷰트-접근 테스트는 minified
  값을 받으므로 동작 보존.

### 0.6 측정 재확인 (spec.md 예상치 vs 실측)

| 심볼 | spec 추정 LOC | 실측 LOC | 비고 |
|------|-------------|---------|------|
| `DASHBOARD_CSS` (L488–L1697 raw string) | ~1,200 | **1,210** | 일치 |
| `_DASHBOARD_JS` (L2504–L3048) | ~800 | **545** | spec 과대 추정 |
| `_PANE_JS` (L3323–L3340, 누락됨) | — | **18** | spec 에 미기재 |
| `_PANE_CSS` (L3342–L3365) | ~100 | **24** | spec 과대 추정 |
| `_task_panel_css` def (L4104–L4206) | ~500 | **103** | spec 과대 추정 |
| `_TASK_PANEL_JS` raw string (L4209–L4482) | — | **274** | spec 에 `_task_panel_js()` 로만 기재 |
| `_task_panel_js` def (L4485–L4487) | (포함) | 3 | thin wrapper |
| **Σ (이관 대상)** | ~3,000 | **2,177** | spec 대비 −823 LOC |

**예상 core.py 감소량 재추정**: 5,418 → **~3,300 LOC** (≥ 2,100 감소).
spec.md 수용 기준 ≤ 3,000 에는 미달할 수 있음 — §작업량 재평가 참조.

### 0.7 확정 시나리오 — 하이브리드 Scenario A + C

spec.md §분리 전략의 3가지 후보 중:

- **Scenario A (static/ 구버전, core.py SSOT)** — 사실 관계 부합: 번들이
  정확하고 디스크가 stale.
- **Scenario B (이미 외부화 완료)** — **기각**: 디스크 파일이 있으나 런타임
  서빙에 쓰이지 않고, 인라인 상수가 여전히 번들 SSOT.
- **Scenario C (인라인 `<style>` 용도 병존)** — 기각: HTML 에서 `<style>`
  태그 없음. 모두 `<link href="/static/...">` 외부 로드.

**확정 시나리오**: **Scenario A (인라인→외부 이관)** + 일부 **Scenario A'**
(기존 stale 디스크 파일 *교체* 이관). 신규 파일을 만드는 대신 기존
`monitor_server/static/style.css` / `app.js` 를 번들 바이트로 **덮어쓰기**
(`dashboard.css` / `pane.css` / `task_panel.css` / `dashboard.js` /
`task_panel.js` / `pane.js` 로 섹션별 분리할지, 아니면 기존 이름 유지할지는
§3 설계 결정 참조).

---

## 1. 요구사항 확인

- `scripts/monitor_server/core.py` (5,418 LOC) 에서 5개 인라인 자산 상수를
  외부 파일로 분리. 실측 이관 LOC = 2,177.
- 모든 테스트 (22개 자산 참조 + 전체 pytest 집합) 가 baseline ( Δ = 0)
  유지. pre-existing 3 failed (2 UI lock + 1 flaky) 외 신규 회귀 0건.
- `get_static_bundle(name)` 의 반환값이 이관 **전후 byte-identical**.
- `curl /static/style.css | md5sum` · `curl /static/app.js | md5sum` 이
  이관 전후 baseline 과 일치.
- facade 계약 유지: `monitor_server.core.DASHBOARD_CSS`,
  `monitor_server.core._DASHBOARD_JS`, `monitor_server.core._PANE_CSS`,
  `monitor_server.core._task_panel_css()`, `monitor_server.core._task_panel_js()`
  모두 `hasattr` True, 반환값 동일.
- **테스트 regex-parse 그룹 (7개 파일) 호환 방식 동시 적용**: design.md
  §2.3 의 "어댑터 loader 패턴" 또는 "테스트 유틸 공유 수정" 중 채택안.

## 2. 타겟 앱

- **경로**: N/A (단일 앱 — `scripts/monitor_server/` 패키지 + `static/`
  서브디렉토리 직접 수정).
- **근거**: 내부 리팩토링. URL/UI/API 계약 불변.

## 3. 구현 방향

### 3.1 이관 대상 파일 매핑 (최종)

| 심볼 (core.py) | core.py 위치 | 목적지 파일 | 변환 | LOC |
|----------------|-------------|-------------|------|-----|
| `DASHBOARD_CSS` | L488–L1697 (raw string, pre-minify) | `scripts/monitor_server/static/dashboard.css` (신규) | 원본 그대로 저장 (minify 는 import 시 적용) | 1,210 |
| `_DASHBOARD_JS` | L2504–L3048 | `scripts/monitor_server/static/dashboard.js` (신규) | 원본 그대로 | 545 |
| `_PANE_JS` | L3323–L3340 | `scripts/monitor_server/static/pane.js` (신규) | 원본 그대로 | 18 |
| `_PANE_CSS` | L3342–L3365 | `scripts/monitor_server/static/pane.css` (신규) | 원본 그대로 | 24 |
| `_task_panel_css` def + body | L4104–L4206 | `scripts/monitor_server/static/task_panel.css` (신규) | 함수→상수 변환 (return 값을 파일화) | 103 |
| `_TASK_PANEL_JS` + `_task_panel_js` wrapper | L4209–L4487 | `scripts/monitor_server/static/task_panel.js` (신규) | 이미 raw string → 그대로 저장 | 277 |
| **Σ** | | | | **2,177** |

**기존 `monitor_server/static/style.css` / `app.js` 처리**: 번들 생성 로직에
더 이상 필요 없으므로 제거한다. 단 `handlers.py::_serve_local_static` 의
디스크 폴백은 유지 (번들이 비어있을 때만 쓰임 — 신규 6개 개별 파일과 무관).
**최종적으로 `static/` 디렉터리에는 새 6개 파일만 남고, 기존 `style.css`/`app.js` 는
삭제**한다.

### 3.2 모듈 로드 패턴 (core.py 개편)

core.py 상단에 새 loader 섹션 추가 (L1700 부근, `_minify_css` 직전):

```python
# ---------------------------------------------------------------------------
# [core-dashboard-asset-split] 인라인 자산 외부화 loader
# ---------------------------------------------------------------------------
# 원본 CSS/JS 블록은 monitor_server/static/*.css|.js 로 이관되었다.
# 본 모듈 import 시 파일을 읽어 기존 동일 이름 속성으로 재바인딩한다.
# 파일 IO 실패(누락/권한) → 빈 문자열 fallback + sys.stderr 경고.

_STATIC_ROOT = Path(__file__).parent / "static"

def _load_static_text(filename: str) -> str:
    try:
        return (_STATIC_ROOT / filename).read_text(encoding="utf-8")
    except OSError as e:
        sys.stderr.write(f"[core-dashboard-asset-split] failed to load "
                         f"{filename}: {e!r}\n")
        return ""

DASHBOARD_CSS = _load_static_text("dashboard.css")       # pre-minify 원본
_DASHBOARD_JS = _load_static_text("dashboard.js")
_PANE_CSS     = _load_static_text("pane.css")
_PANE_JS      = _load_static_text("pane.js")
_TASK_PANEL_JS = _load_static_text("task_panel.js")
_TASK_PANEL_CSS_SRC = _load_static_text("task_panel.css")

def _task_panel_css() -> str:
    """CSS for task slide panel (TSK-02-04). 외부 파일 경유."""
    return _TASK_PANEL_CSS_SRC

def _task_panel_js() -> str:
    """JS for task slide panel. Document-level delegation survives auto-refresh."""
    return _TASK_PANEL_JS
```

그리고 기존 `_minify_css` 호출은 유지:

```python
DASHBOARD_CSS = _minify_css(DASHBOARD_CSS)  # L1704 변경 없음
```

### 3.3 테스트 regex-parse 그룹 호환 전략 (선택된 방안)

**방안 A (채택)**: regex-parse 7개 테스트를 **외부 파일 경로 우선, core.py
fallback** 로 전환.

패턴 (샘플: `test_font_css_variables.py`):
```python
# Before:
_SOURCE_TEXT = _MONITOR_PATH.read_text() + "\n" + _CORE_PATH.read_text()
_CSS_MATCH = re.search(r'DASHBOARD_CSS\s*=\s*"""(.*?)"""', _SOURCE_TEXT, re.DOTALL)
DASHBOARD_CSS = _CSS_MATCH.group(1) if _CSS_MATCH else ""

# After:
_STATIC_CSS = _THIS_DIR / "monitor_server" / "static" / "dashboard.css"
if _STATIC_CSS.exists():
    DASHBOARD_CSS = _STATIC_CSS.read_text(encoding="utf-8")
else:
    # Legacy fallback (본 feature 완료 후 제거 대상, 단 Phase 2 히스토리 참조용 유지)
    _SOURCE_TEXT = _MONITOR_PATH.read_text() + "\n" + _CORE_PATH.read_text()
    _CSS_MATCH = re.search(r'DASHBOARD_CSS\s*=\s*"""(.*?)"""', _SOURCE_TEXT, re.DOTALL)
    DASHBOARD_CSS = _CSS_MATCH.group(1) if _CSS_MATCH else ""
```

- 정규식 파서 호환 유지 (디스크 파일 우선, 삼중따옴표 fallback 유지).
- `core-decomposition` refactor.md §"유지 이유" 패턴과 동일 접근 — "테스트
  가 소스 구조를 단언하면 그 소스를 파일로 이동했다고 단언 대상도 함께
  이동".
- 7개 대상 파일에 동일 shim 적용. Build 단계 TDD 테스트 작성 후 Refactor
  에서 legacy fallback 제거 판단.

**방안 B (기각)**: core.py 에 "fake 삼중따옴표 literal" 주석 블록을 남겨
정규식이 매치되게 하는 꼼수. **기각 근거**: 정적 주석은 로더가 파일을
바꿀 때 자동 동기화되지 않아 드리프트 자석이 된다. 본 feature 의 핵심 목적
(시각 회귀 자석 제거) 을 역행.

**방안 C (기각)**: 로더를 `exec()` 기반으로 작성해 원본 literal 을 유지
(파일에서 read 한 텍스트를 `f'DASHBOARD_CSS = """{payload}"""'` 로 재구성
후 exec). **기각 근거**: 테스트가 literally 찾는 것은 **소스 파일 텍스트**
이지 런타임 모듈 속성이 아니므로 exec 변수는 도움이 되지 않는다. 또한
복잡도 추가 + 인용부호 escape 문제.

### 3.4 `get_static_bundle` 의 byte-identical 보장

현재 구현 (L1727–L1740):
```python
if name == "style.css":
    body = "\n".join([DASHBOARD_CSS, _task_panel_css(), _PANE_CSS])
    return body.encode("utf-8")
if name == "app.js":
    body = "\n".join([_DASHBOARD_JS, _task_panel_js(), _PANE_JS])
    return body.encode("utf-8")
```

- 외부 파일 이관 후에도 **같은 concat 로직**을 유지. 문자열은 동일 순서
  (Dashboard → Task Panel → Pane) 로 합성.
- 합성 결과 bytes 가 이관 전 baseline md5 (`dcab587d6fd4fc32f46117fbdce06e44`
  / `479d0ac147cd74f4664c00acd0d38c78`) 와 일치해야 한다. 이는 각 개별 파일
  내용이 원본 리터럴의 **정확한 복사본** 일 때만 성립.
- 저장 시 주의 사항:
  - CSS: `_minify_css` 는 `DASHBOARD_CSS` 에만 적용되며, 이는 `get_static_bundle`
    의 `"\n".join([DASHBOARD_CSS, ...])` 경유로 bundle 에 반영됨. 디스크
    `dashboard.css` 는 **pre-minify 원본** 으로 저장해야 현 로더 패턴이
    동작 보존 성립.
  - line ending: LF (`\n`) 만 사용. `open(..., newline="\n")` 로 저장 —
    Windows 에서 CRLF 변환 방지 (CLAUDE.md §Windows 네이티브 지원 원칙).
  - 인코딩: UTF-8 (BOM 없음).
  - Trailing newline: 원본 raw-string 이 `"""` 닫기 전에 개행 없음 / 있음
    인지 byte-level 로 보존. 예) `_PANE_CSS` 는 `.footer { ... }"""` 로
    개행 없이 끝남 → 디스크 파일도 마지막 바이트가 `}` 가 되도록 저장.

### 3.5 커밋 단위 분할

> `[core-dashboard-asset-split:C{N}-{M}]` 태그 접두사. 각 커밋 직후 §5
> 검증 필수.

| 커밋 | 제목 | 범위 | core.py LOC 변화 |
|------|------|------|------------------|
| **C0-1 (baseline)** | `docs(core-dashboard-asset-split): baseline 기록 + md5 pinning` | `docs/features/core-dashboard-asset-split/baseline.txt` 신규. pytest 결과 + `/static/style.css` / `/static/app.js` 의 md5 (현재 버전 + 번들 결과) + 5개 심볼 `md5(bytes)` 개별 pinning | — |
| **C1-1 (DASHBOARD_CSS)** | `refactor(monitor_server): DASHBOARD_CSS → static/dashboard.css 이관` | ① `static/dashboard.css` 신규 (L488–L1697 raw string 그대로). ② core.py L488–L1697 삭제, `DASHBOARD_CSS = _load_static_text("dashboard.css")` 대체. ③ `_load_static_text` / `_STATIC_ROOT` 정의 추가. ④ 테스트 regex-parse 7개 파일 중 `DASHBOARD_CSS` 참조 6개 shim 적용 (`test_font_css_variables.py`, `test_monitor_dep_graph_html.py`, `test_monitor_shared_css.py`, `test_monitor_dep_graph_summary.py`, `test_monitor_pane_size.py`, `test_dashboard_css_tsk0101.py`). ⑤ 검증: `md5(get_static_bundle("style.css"))` 불변. | −1,210 |
| **C1-2 (_DASHBOARD_JS)** | `refactor(monitor_server): _DASHBOARD_JS → static/dashboard.js 이관` | ① `static/dashboard.js` 신규. ② core.py L2504–L3048 삭제, `_DASHBOARD_JS = _load_static_text("dashboard.js")`. ③ 테스트 shim 3개 추가: `test_monitor_fold.py`, `test_monitor_fold_helper_generic.py`, `test_monitor_fold_live_activity.py` (`_DASHBOARD_JS` regex-parse 및 fallback 추가). ④ 검증: `md5(get_static_bundle("app.js"))` 불변. | −545 |
| **C1-3 (_PANE_CSS + _PANE_JS)** | `refactor(monitor_server): _PANE_CSS + _PANE_JS → static/pane.{css,js} 이관` | ① `static/pane.css` + `static/pane.js` 신규. ② core.py L3323–L3340 + L3342–L3365 삭제, 두 속성 `_load_static_text`. ③ 테스트 shim: 필요 없음 (`_PANE_CSS`/`_PANE_JS` 는 attribute 접근만). ④ 검증: pane HTML smoke `GET /pane/%1` md5 불변. | −42 |
| **C1-4 (_task_panel_css)** | `refactor(monitor_server): _task_panel_css → static/task_panel.css 이관` | ① `static/task_panel.css` 신규 (L4106–L4206 return (...) 의 concat 결과를 byte-level 그대로). ② core.py L4104–L4206 삭제, `_TASK_PANEL_CSS_SRC = _load_static_text(...)` + `_task_panel_css()` wrapper. ③ 테스트 shim: 필요 없음 (함수 호출만). | −103 |
| **C1-5 (_TASK_PANEL_JS + _task_panel_js)** | `refactor(monitor_server): _TASK_PANEL_JS → static/task_panel.js 이관` | ① `static/task_panel.js` 신규. ② core.py L4209–L4487 삭제, `_TASK_PANEL_JS = _load_static_text(...)` + `_task_panel_js()` wrapper 유지. ③ 테스트 shim: 없음 (attribute/function 접근만). | −277 |
| **C2-1 (stale static/ 정리)** | `refactor(monitor_server): 기존 stale static/style.css + app.js 삭제` | ① `scripts/monitor_server/static/style.css` + `.../app.js` 제거 (번들이 SSOT 이므로 더 이상 불필요). ② `handlers.py::_serve_local_static` 의 디스크 폴백 주석만 업데이트 (구현은 유지 — 미래 호환). ③ 검증: `GET /static/style.css` 200 + 번들 md5 불변 (디스크 폴백 경로 미진입). | 0 (core.py 무관) |
| **C3-1 (cleanup)** | `refactor(monitor_server/core): loader 섹션 주석 정리 + breadcrumb` | ① core.py 상단 loader 섹션을 단일 블록으로 통합, 각 원래 위치에 `# moved to monitor_server/static/{file}` breadcrumb 한 줄 유지. ② `__init__.py` 에 새 파일 구조 언급 docstring 업데이트 (core-decomposition refactor-04 선례). ③ `import` 정리 (Path 재사용). | 소폭 감소 |

**총 감소 예상**: 1,210 + 545 + 42 + 103 + 277 = **2,177 LOC** + loader
섹션 추가 (약 30 LOC) = net **−2,147 LOC**. core.py 5,418 → **~3,271 LOC**.
수용 기준 ≤ 3,000 에는 271 LOC 미달. §작업량 재평가 §12 참조.

### 3.6 핵심 패턴 — core-decomposition 계승

- **facade 불변**: `core.DASHBOARD_CSS`, `core._DASHBOARD_JS` 등 속성은
  같은 이름으로 계속 `hasattr` True. 값만 외부 파일 → 메모리로 경로 변경.
- **동작 보존**: `_minify_css(DASHBOARD_CSS)` 적용은 유지. `get_static_bundle`
  내부 concat 순서/구분자 (`\n`) 유지.
- **1 커밋 = 1 논리적 변경**: 자산 1개 = 커밋 1개 + 필요한 테스트 shim.
- **롤백**: `git revert <SHA>` 단건으로 가능. 커밋 간 의존성 없음 (C1-1 ~
  C1-5 는 독립). C2-1 (stale 삭제) 는 C1-1~C1-5 완료 후에만 실행.

## 4. 실측 재확인

### 4.1 블록 경계 (line count)

```
DASHBOARD_CSS         L488 – L1697   1,210 LOC
_DASHBOARD_JS         L2504 – L3048    545 LOC
_PANE_JS              L3323 – L3340     18 LOC
_PANE_CSS             L3342 – L3365     24 LOC
_task_panel_css (def) L4104 – L4206    103 LOC
_TASK_PANEL_JS (raw)  L4209 – L4482    274 LOC
_task_panel_js (def)  L4485 – L4487      3 LOC
────────────────────────────────────────────
SUM                                   2,177 LOC
```

### 4.2 Bundle 합성 결과

```
style.css bundle:  DASHBOARD_CSS(minified) + "\n" + _task_panel_css() + "\n" + _PANE_CSS
                   → 51,028 bytes (md5 dcab587d...)
app.js   bundle:   _DASHBOARD_JS + "\n" + _task_panel_js() + "\n" + _PANE_JS
                   → 35,079 bytes (md5 479d0ac1...)
```

### 4.3 테스트 영향 매트릭스

| 테스트 파일 | 접근 패턴 | 이관 후 조치 |
|-------------|-----------|--------------|
| `test_dashboard_css_tsk0101.py` | `getattr(mod, "DASHBOARD_CSS", "")` | 무변경 (attribute) |
| `test_font_css_variables.py` | regex-parse | **shim 적용** (C1-1) |
| `test_monitor_dep_graph_html.py` | regex-parse | **shim 적용** (C1-1) |
| `test_monitor_dep_graph_summary.py` | `hasattr(mod, "DASHBOARD_CSS")` | 무변경 |
| `test_monitor_e2e.py` | function call (`_task_panel_js`) | 무변경 |
| `test_monitor_filter_bar.py` | `monitor_server.DASHBOARD_CSS` | 무변경 |
| `test_monitor_fold.py` | regex-parse `_DASHBOARD_JS` | **shim 적용** (C1-2) |
| `test_monitor_fold_helper_generic.py` | regex-parse `_DASHBOARD_JS` | **shim 적용** (C1-2) |
| `test_monitor_fold_live_activity.py` | attribute + fallback to app.js | **shim 확장** (C1-2) |
| `test_monitor_info_popover.py` | `mod.DASHBOARD_CSS + mod._DASHBOARD_JS` | 무변경 |
| `test_monitor_kpi.py` | `mod.DASHBOARD_CSS` | 무변경 |
| `test_monitor_merge_badge.py` | `mod._task_panel_js()` | 무변경 (function) |
| `test_monitor_pane_size.py` | regex-parse `DASHBOARD_CSS` | **shim 적용** (C1-1) |
| `test_monitor_phase_badge_colors.py` | `mod.DASHBOARD_CSS` | 무변경 |
| `test_monitor_progress_header.py` | `mod._TASK_PANEL_JS` attribute | **shim 적용** (C1-5) |
| `test_monitor_render.py` | attribute + fallback to app.js | 무변경 (이미 fallback 보유) |
| `test_monitor_shared_css.py` | regex-parse `DASHBOARD_CSS` | **shim 적용** (C1-1) |
| `test_monitor_task_detail_api.py` | `mod._task_panel_css()` + file fallback | 무변경 |
| `test_monitor_task_expand_ui.py` | `hasattr(mod, "_task_panel_css")` | 무변경 |
| `test_monitor_task_row.py` | `mod.DASHBOARD_CSS` | 무변경 |
| `test_monitor_team_preview.py` | `getattr(ms, "DASHBOARD_CSS")` | 무변경 |
| `test_render_dashboard_tsk0106.py` | `mod.get_static_bundle("app.js")` | 무변경 (번들 경유) |

**총 shim 수정 대상**: 8개 테스트 파일 (7개 regex-parse + 1개
`_TASK_PANEL_JS` attribute).

## 5. 시각 회귀 방어 절차 (Phase 2-a/2-b 대비 엄격)

### 5.1 Baseline 기록 (C0-1, 실행 예시)

```bash
cd /Users/jji/project/dev-plugin
mkdir -p docs/features/core-dashboard-asset-split/baseline

# (a) pytest baseline
rtk proxy python3 -m pytest -q scripts/ --tb=no \
  > docs/features/core-dashboard-asset-split/baseline.txt 2>&1

# (b) 번들 md5 + 바이트 저장
python3 -c "
import sys, hashlib, pathlib
sys.path.insert(0, 'scripts')
from monitor_server import core
b = pathlib.Path('docs/features/core-dashboard-asset-split/baseline')
for name in ['style.css', 'app.js']:
    data = core.get_static_bundle(name)
    (b / name).write_bytes(data)
    print(f'{name} md5={hashlib.md5(data).hexdigest()} len={len(data)}')
" | tee -a docs/features/core-dashboard-asset-split/baseline.txt

# (c) 5개 심볼 개별 md5 (이관 단위 검증용)
python3 -c "
import sys, hashlib
sys.path.insert(0, 'scripts')
from monitor_server import core
for sym in ['DASHBOARD_CSS', '_DASHBOARD_JS', '_PANE_CSS', '_PANE_JS']:
    v = getattr(core, sym)
    print(f'{sym} md5={hashlib.md5(v.encode()).hexdigest()} len={len(v)}')
for fn in ['_task_panel_css', '_task_panel_js']:
    v = getattr(core, fn)()
    print(f'{fn}() md5={hashlib.md5(v.encode()).hexdigest()} len={len(v)}')
" | tee -a docs/features/core-dashboard-asset-split/baseline.txt

# (d) 실기동 HTTP baseline
python3 scripts/monitor-launcher.py --stop 2>/dev/null || true
python3 scripts/monitor-launcher.py --port 7321 --docs docs/monitor-v5 &
sleep 3
for path in "/" "/static/style.css" "/static/app.js" "/api/state" "/api/graph"; do
  echo -n "GET $path: "
  curl -sS "http://127.0.0.1:7321$path" | md5sum
done | tee -a docs/features/core-dashboard-asset-split/baseline.txt
python3 scripts/monitor-launcher.py --stop
```

### 5.2 커밋별 diff 확인 (매 C1-N 이후 실행)

```bash
# (a) 번들 md5 불변 확인
python3 -c "
import sys, hashlib
sys.path.insert(0, 'scripts')
from monitor_server import core
for name in ['style.css', 'app.js']:
    data = core.get_static_bundle(name)
    print(f'{name} md5={hashlib.md5(data).hexdigest()} len={len(data)}')
" > /tmp/post-commit-md5.txt
diff docs/features/core-dashboard-asset-split/baseline.txt /tmp/post-commit-md5.txt | grep "md5=" \
  && echo "DRIFT DETECTED — git revert HEAD" && exit 1

# (b) 심볼별 md5 불변 확인 (커밋 대상 심볼만 바뀌어서는 안 됨)
# → baseline.txt 의 DASHBOARD_CSS md5 와 현재 md5(core.DASHBOARD_CSS) 가 완전 동일해야 함.

# (c) 실기동 byte-identical (단, style.css/app.js 서빙 순서 의존성 확인)
python3 scripts/monitor-launcher.py --stop 2>/dev/null || true
python3 scripts/monitor-launcher.py --port 7321 --docs docs/monitor-v5 &
sleep 3
for path in "/" "/static/style.css" "/static/app.js" "/pane/%1"; do
  cur=$(curl -sS "http://127.0.0.1:7321$path" | md5sum)
  base=$(grep "GET $path" docs/features/core-dashboard-asset-split/baseline.txt)
  echo "path=$path cur=$cur base=$base"
done
python3 scripts/monitor-launcher.py --stop
```

### 5.3 pytest baseline 비교

```bash
rtk proxy python3 -m pytest -q scripts/ --tb=no 2>&1 | \
  tee /tmp/post-commit-pytest.txt
# baseline: 3 failed (1997 passed / 176 skipped) + 1 flaky 허용
# 신규 failed 0 건이어야 함 — diff 가 failed count 만 보고
grep -E "^[0-9]+ (passed|failed|skipped)" /tmp/post-commit-pytest.txt
```

### 5.4 드리프트 발생 시 절차

1. 즉시 `git revert HEAD` (해당 커밋만 되돌림).
2. `_load_static_text` 호출 결과와 원본 literal 의 byte-level diff 실행
   (`python3 -c "import difflib; ..."`).
3. 원인 분석 후 재작성. 주요 원인 후보:
   - line ending 변환 (CRLF vs LF) — Windows 파일 시스템 or editor 설정.
   - trailing newline 추가/제거 — `Write` 도구가 마지막에 `\n` 붙이는지
     확인.
   - UTF-8 BOM 삽입 — `open(..., "w", encoding="utf-8-sig")` 금지.
   - whitespace normalization — IDE autoformat 비활성화 확인.

## 6. 파일 계획

| 파일 | 역할 | 신규/수정 |
|------|------|-----------|
| `docs/features/core-dashboard-asset-split/baseline.txt` | pytest baseline + bundle md5 + 실기동 HTTP md5 | **신규** (C0-1) |
| `docs/features/core-dashboard-asset-split/baseline/` | 디렉터리 | **신규** (C0-1) |
| `docs/features/core-dashboard-asset-split/baseline/style.css` | 이관 전 번들 바이트 스냅샷 | **신규** (C0-1) |
| `docs/features/core-dashboard-asset-split/baseline/app.js` | 이관 전 번들 바이트 스냅샷 | **신규** (C0-1) |
| `scripts/monitor_server/static/dashboard.css` | DASHBOARD_CSS 원본 (pre-minify) 2,177 LOC 중 1,210 | **신규** (C1-1) |
| `scripts/monitor_server/static/dashboard.js` | _DASHBOARD_JS 원본 | **신규** (C1-2) |
| `scripts/monitor_server/static/pane.css` | _PANE_CSS 원본 | **신규** (C1-3) |
| `scripts/monitor_server/static/pane.js` | _PANE_JS 원본 | **신규** (C1-3) |
| `scripts/monitor_server/static/task_panel.css` | _task_panel_css return 값 concat (byte-level) | **신규** (C1-4) |
| `scripts/monitor_server/static/task_panel.js` | _TASK_PANEL_JS raw string | **신규** (C1-5) |
| `scripts/monitor_server/core.py` | 5개 인라인 블록 삭제 + loader 섹션 + `_task_panel_css/js` wrapper 재작성 | 수정 (C1-1~C1-5, C3-1) |
| `scripts/monitor_server/static/style.css` (기존 stale) | 제거 | **삭제** (C2-1) |
| `scripts/monitor_server/static/app.js` (기존 stale) | 제거 | **삭제** (C2-1) |
| `scripts/monitor_server/handlers.py` | `_serve_local_static` 주석 업데이트 (동작 무변경) | 수정 (C2-1) |
| `scripts/monitor_server/__init__.py` | docstring 모듈 구성 업데이트 | 수정 (C3-1) |
| `scripts/test_font_css_variables.py` | regex-parse → file-first shim | 수정 (C1-1) |
| `scripts/test_monitor_dep_graph_html.py` | regex-parse → file-first shim | 수정 (C1-1) |
| `scripts/test_monitor_shared_css.py` | regex-parse → file-first shim | 수정 (C1-1) |
| `scripts/test_monitor_dep_graph_summary.py` | regex-parse → file-first shim | 수정 (C1-1) |
| `scripts/test_monitor_pane_size.py` | regex-parse → file-first shim | 수정 (C1-1) |
| `scripts/test_dashboard_css_tsk0101.py` | (attribute 접근만 — 변경 불필요, 재검토 후 결정) | 선택 수정 (C1-1) |
| `scripts/test_monitor_fold.py` | regex-parse → file-first shim (`_DASHBOARD_JS`) | 수정 (C1-2) |
| `scripts/test_monitor_fold_helper_generic.py` | regex-parse → file-first shim | 수정 (C1-2) |
| `scripts/test_monitor_fold_live_activity.py` | fallback 경로 확장 (`dashboard.js` 우선) | 수정 (C1-2) |
| `scripts/test_monitor_progress_header.py` | `_TASK_PANEL_JS` attribute — file-first shim | 수정 (C1-5) |

**총 신규**: 6 static 파일 + 3 baseline 파일 + baseline.txt = 10 파일.
**총 수정**: core.py + handlers.py + __init__.py + 8~9 테스트 파일 = 11~12 파일.
**총 삭제**: 기존 static/style.css + static/app.js = 2 파일.

## 7. 진입점 (Entry Points)

N/A (내부 리팩토링 — 사용자 UI·URL·API 계약 변경 없음. `/static/*` 경로
자체는 그대로 유지되고 서빙 내용의 byte-level 재현성만 바뀌지 않음).

## 8. 주요 구조

### 8.1 Import 의존 그래프 (이관 전후)

```
Before:
  monitor_server.core  ← DASHBOARD_CSS (inline 1,210 LOC)
                       ← _DASHBOARD_JS (inline 545 LOC)
                       ← _PANE_CSS / _PANE_JS (inline 42 LOC)
                       ← _task_panel_css() / _task_panel_js() (inline 380 LOC)
  monitor_server.handlers._serve_local_static → core.get_static_bundle

After:
  monitor_server/static/dashboard.css  (new file, 1,210 LOC)
  monitor_server/static/dashboard.js   (new file, 545 LOC)
  monitor_server/static/pane.css       (new file, 24 LOC)
  monitor_server/static/pane.js        (new file, 18 LOC)
  monitor_server/static/task_panel.css (new file, 103 LOC)
  monitor_server/static/task_panel.js  (new file, 274 LOC)
  monitor_server.core._load_static_text(name) → read_text
  monitor_server.core.DASHBOARD_CSS ← _load_static_text("dashboard.css")
  (나머지 속성 동일 패턴)
  monitor_server.handlers._serve_local_static → core.get_static_bundle (변경 없음)
```

### 8.2 순환 참조 / 이니셜라이제이션 순서

- `core.py` 가 자기 디렉터리 아래 `static/*` 를 `Path(__file__).parent`
  로 읽음 → 외부 모듈 import 없음 → 순환 참조 불가.
- `_load_static_text` 를 `DASHBOARD_CSS = ...` 대입보다 **먼저 정의** 해야
  함. `_minify_css` 는 그 다음.
- `_STATIC_ROOT` 를 모듈 top-level 에 `Path(__file__).parent / "static"` 로
  정의 (core.py L50 부근의 import 섹션 바로 아래가 적절).

### 8.3 기존 코드 삭제 범위 (정확한 라인)

C1-1 삭제:
```
L488–L1697: DASHBOARD_CSS = """ ... """  (1,210 LOC 전체 raw string 포함)
```

C1-2 삭제:
```
L2504–L3048: _DASHBOARD_JS = """\ ... """  (545 LOC)
```

C1-3 삭제:
```
L3323–L3340: _PANE_JS = """\ ... """
L3342–L3365: _PANE_CSS = """\ ... """
```

C1-4 삭제:
```
L4104–L4206: def _task_panel_css() -> str: return ( ... )
(wrapper 재작성 시 새 정의는 loader 섹션에 위치)
```

C1-5 삭제:
```
L4209–L4482: _TASK_PANEL_JS = r""" ... """
L4485–L4487: def _task_panel_js() -> str: return _TASK_PANEL_JS
(wrapper 재작성 시 새 정의는 loader 섹션에 위치)
```

### 8.4 breadcrumb 주석 (C3-1 cleanup)

core-decomposition refactor.md §"거부된 개선 후보 §4" 원칙 계승 — 원래
위치에 한 줄 breadcrumb 유지:

```python
# L488 위치: (삭제 완료, moved to monitor_server/static/dashboard.css — C1-1)
# L2504 위치: (삭제 완료, moved to monitor_server/static/dashboard.js — C1-2)
# L3323/L3342 위치: (삭제 완료, moved to monitor_server/static/pane.{js,css} — C1-3)
# L4104 위치: (삭제 완료, moved to monitor_server/static/task_panel.css — C1-4)
# L4209 위치: (삭제 완료, moved to monitor_server/static/task_panel.js — C1-5)
```

## 9. 데이터 흐름

```
브라우저 GET /static/style.css?v={md5}
  → handlers.Handler.do_GET → _serve_static("style.css")
  → _serve_local_static("style.css")
  → core.get_static_bundle("style.css")
  → "\n".join([DASHBOARD_CSS, _task_panel_css(), _PANE_CSS]).encode()
     ──┬──        ──┬──                 ──┬──
       │            │                     │
       ▼            ▼                     ▼
  static/      static/              static/
  dashboard.css task_panel.css      pane.css
     (Path.read_text at import time, cached in module var)
  → response body (byte-identical to pre-migration)
```

## 10. 설계 결정 (대안이 있는 경우만)

### 10.1 파일 명명 — 섹션별 분리 vs 단일 번들 파일

- **결정**: 섹션별 분리 (6개 파일).
- **대안**: 기존 `style.css` / `app.js` 두 파일만 유지 (concat 결과 저장).
- **근거**: 단일 번들 방식은 **소스 코드 대응 관계 상실** — `DASHBOARD_CSS`
  에 버그 수정 시 어느 블록을 편집할지 불명확. 섹션별 분리는 core.py 의
  5개 심볼 ↔ 6개 파일 1:1 매핑 → diff 가독성 향상 + 시각 토큰 가드 작동.
  추가 I/O 비용은 import time 에 1회만 발생하므로 무시 가능.

### 10.2 `_task_panel_css` — 함수 유지 vs 상수 변환

- **결정**: **함수 wrapper 유지** (`_task_panel_css() -> str`).
- **대안**: `_task_panel_css` 를 단순 `str` 상수로 교체.
- **근거**: 22개 테스트 중 `test_monitor_task_detail_api.py`,
  `test_monitor_merge_badge.py`, `test_monitor_task_expand_ui.py` 등이
  `monitor_server._task_panel_css()` 함수 호출 패턴 사용. 상수 변환 시
  `TypeError: 'str' object is not callable`. 호출부 대량 수정은 범위 밖 —
  함수 wrapper 한 줄 추가가 저렴.

### 10.3 Loader 위치 — core.py 상단 vs `__init__.py`

- **결정**: **core.py 내부** (`_minify_css` 직전).
- **대안**: `monitor_server/__init__.py` 에서 loader 정의 + `core` 주입.
- **근거**: core-decomposition Phase 1 facade 원칙 — core.py 가 여전히
  `import monitor_server.core as c; c.DASHBOARD_CSS` 접근 경로의 유일한
  진실 위치. loader 가 `__init__.py` 로 이동하면 facade 재-export 가 또
  한 층 깊어져 core-http-split 순환 방지 패턴을 복잡화. 또한 core.py
  전체 docstring/테스트가 "monitor-server.py 또는 monitor_server/core.py
  에서 DASHBOARD_CSS 문자열을 추출" 로 기재되어 있어 (test_font_css_variables
  L23, test_dashboard_css_tsk0101 L22 등) core.py 가 실제 정의를 보유해야
  hasattr 이 성립.

### 10.4 테스트 shim — regex-parse 제거 vs file-first 우선순위 fallback

- **결정**: **file-first 우선순위 fallback** (regex-parse legacy 유지).
- **대안**: regex-parse 완전 제거, 파일 경로만 사용.
- **근거**: 본 feature 범위 최소화. legacy fallback 은 파일이 있으면 어차피
  진입하지 않으므로 런타임 비용 0. Refactor 단계에서 "fallback 제거" 를
  별도 항목으로 평가. 최소 diff = 최소 회귀 리스크.

### 10.5 외부화 대상 순서 — CSS 먼저 vs JS 먼저

- **결정**: **대상별 독립 커밋 — 크기 내림차순** (DASHBOARD_CSS 1,210 →
  _DASHBOARD_JS 545 → _task_panel_js 274 → _task_panel_css 103 → _PANE_CSS
  24 + _PANE_JS 18).
- **대안**: CSS 3건 먼저, JS 3건 나중 (도메인 그룹화).
- **근거**: 큰 블록 먼저 → 이관 패턴 초기 검증 + 시각 회귀 리스크 가장
  큰 `DASHBOARD_CSS` 부터 빠르게 롤백 가능 상태로 진입. 도메인 그룹화는
  커밋 간 의존성이 없으므로 장점 미미.

### 10.6 minify 적용 시점 유지

- **결정**: import time 에 `_minify_css(DASHBOARD_CSS)` 적용 (현재와 동일).
- **대안 A**: 디스크에 이미 minified 된 내용 저장 (빌드 시점 min).
- **대안 B**: 런타임 minify 완전 제거.
- **근거**: 대안 A 는 소스 편집 가독성 급락. 대안 B 는 bundle md5 변경 →
  시각 회귀 baseline 불일치. 현 동작 보존 = `_minify_css` 유지.

## 11. 선행 조건

- `core-decomposition` Phase 1 완료 (commit `caed787`) — 확인 완료.
- `core-http-split` Phase 2-a 완료 — 확인 완료 (handlers.py + handlers_*.py
  존재).
- `core-renderer-split` Phase 2-b 완료 (commit `265fd15` — state.json =
  `[xx]`) — 확인 완료.
- `scripts/monitor_server/static/` 디렉터리 존재 — 확인 완료.
- 현재 core.py 5,418 LOC — 확인 완료.
- 현재 bundle md5 / length 기록 (§0.1) — 확인 완료.
- pytest baseline: 3 failed / 1997 passed / 176 skipped (core-renderer-split
  refactor.md pytest 결과) — baseline 으로 채택.

## 12. 작업량 재평가 (spec.md §수용 기준 조정 제안)

### 12.1 spec.md 원래 수용 기준

- core.py LOC: 5,418 → **≤ 3,000** (≥ 2,400 LOC 감소).

### 12.2 실측 기반 재추정

| 항목 | spec 추정 | 실측 |
|------|-----------|------|
| 이관 대상 LOC | ~3,000 | **2,177** |
| core.py 추가 증가 (loader 섹션) | 0 | **+30** |
| net core.py 감소 | ~3,000 | **2,147** |
| core.py 최종 LOC | ~2,400 | **~3,271** |

### 12.3 수용 기준 조정 제안

| 항목 | 원래 기준 | 제안 기준 | 근거 |
|------|-----------|-----------|------|
| core.py LOC | ≤ 3,000 | **≤ 3,300** | 실측 이관 LOC 2,177 + loader 30 |
| NF-03 (≤ 800) | 해당 없음 | 해당 없음 | core.py 는 여전히 위반 → Phase 3 대상 (후속 feature) |
| 이관 자산 LOC | ≥ 2,400 감소 | **≥ 2,100 감소** | 실측 기반 |

### 12.4 시나리오 B 가 아니라는 결정이 작업량에 미치는 영향

- spec.md 비고: "시나리오 B(이미 외부화 완료)로 확정되면 본 feature의 실질
  작업량이 급감 → 수용 기준 조정".
- **본 조사 결론**: 시나리오 B 가 **아님** (§0.1 실측 md5 불일치). 기존
  디스크 파일은 stale 드리프트이며 런타임 번들 SSOT 가 여전히 인라인 상수.
- → **작업량 축소는 없다**. 반대로 "테스트 regex-parse lock" 이라는 **새로운
  고정비 항목 (8개 테스트 shim)** 이 발견되어 spec.md 추정치 대비 테스트
  작업량이 증가한다.
- 그러나 이관 LOC 는 spec 추정치보다 작으므로 **core.py 최종 LOC 는 목표
  미달**이다. 수용 기준 조정 (§12.3) 으로 대응.

### 12.5 Phase 3 (후속 feature) 후보

본 feature 완료 후에도 core.py 는 ~3,300 LOC 로 NF-03 (≤ 800) 의 4배 초과.
추가 분해 후보:

1. **HTTP handler 잔여 helper** (`_call_dep_analysis_graph_stats`,
   `_build_state_snapshot` 등, core-http-split refactor.md §"삭제 불가
   판정") → `handlers_*.py` 흡수. 예상 감소 ~300 LOC.
2. **Dashboard assembly** (`render_dashboard` + `get_static_bundle` 등)
   → `dashboard.py` 모듈. 예상 감소 ~200 LOC.
3. **나머지 SSR helpers** (`_esc`, `_refresh_seconds`, `_group_preserving_order`
   등) → `renderers/_util.py` 이관 (core-renderer-split 에서 보류함).

각 항목은 독립 feature 로 분리 가능하며 본 feature 범위 밖.

## 13. 리스크

- **HIGH — 테스트 regex-parse lock (1st order)**: 7개 테스트가 core.py
  소스에서 `r'DASHBOARD_CSS\s*=\s*"""(.*?)"""'` 매칭을 시도. C1-1 커밋
  직후 literal 이 사라지면 즉시 7개 fail → baseline Δ ≠ 0. **방어**:
  각 C1-N 커밋에 **동일 커밋 내 테스트 shim 적용** (분리 커밋 금지 —
  test/code gap 생기면 pytest red).
- **HIGH — byte-level drift**: 파일 저장 시 line ending (CRLF), trailing
  newline, BOM 중 하나라도 원본과 다르면 `get_static_bundle` md5 변경.
  **방어**: §5.2 md5 pinning + `open(..., "w", encoding="utf-8", newline="\n")`
  강제 + 파일 저장 후 `diff <(python3 -c "print(core.DASHBOARD_CSS, end='')") dashboard.css`
  수행.
- **HIGH — `_minify_css` 재적용 누락**: C1-1 에서 `DASHBOARD_CSS = _load_static_text(...)`
  를 작성하고 `DASHBOARD_CSS = _minify_css(DASHBOARD_CSS)` 호출을 빠뜨리면
  `core.DASHBOARD_CSS` 속성 값이 원본 (multi-line) 으로 반환되어 22개
  테스트 중 "minified 패턴 검증" 테스트 (없음 — 전부 substring 검사)
  는 영향 없으나 bundle md5 는 크게 변경 (`\n` → `' '` 차이). **방어**:
  C1-1 TDD 시 "minified substring 존재" 단언을 build 테스트에 포함.
- **HIGH — 삭제 범위 오차**: C1-1 의 L488–L1697 삭제 시, 닫는 `"""` 이후
  `_minify_css` 정의 (L1699) 와의 경계를 정확히 분리해야 함. 한 줄 더
  삭제 → `_minify_css` 깨짐 → 모든 CSS 가 non-minified → bundle md5 변경.
  **방어**: 각 삭제 전 `sed -n '488,1697p'` 로 범위 확인 + py_compile 테스트.
- **MEDIUM — stale 디스크 파일 의존 테스트 존재**: `test_monitor_render.py`
  L23–L25 는 `_APP_JS_PATH.read_text()` 를 fallback 으로 사용 중. C2-1 에서
  `static/app.js` 삭제 시 이 fallback 이 빈 문자열 반환 → 일부 단언 실패
  가능. **방어**: C2-1 전에 해당 테스트의 fallback 경로를 `dashboard.js`
  로 변경하는 추가 shim 필요 (test_monitor_fold_live_activity.py 와 동일
  패턴).
- **MEDIUM — CLAUDE.md Windows 원칙 위반 가능**: `newline="\n"` 명시 누락
  시 Windows 에서 CRLF 삽입. **방어**: Write 도구가 생성하는 파일은 LF
  유지 (verified 동작) — 단 수동 편집 후 저장 경로에 주의.
- **MEDIUM — 기존 `static/style.css` + `app.js` 제거의 외부 도구 영향**:
  만약 외부 도구 (IDE, pre-commit hook, 문서 뷰어 등) 가 해당 파일을
  참조 중이면 삭제 시 깨짐. **방어**: `git grep "static/style.css\|static/app.js"`
  로 참조 전수 조사 (본 조사에서 test fallback 5건만 발견 — 모두 C1/C2
  shim 으로 대응).
- **LOW — `_task_panel_css` 의 byte-level 복원**: core.py 의 함수 구현은
  Python string concat (여러 줄 문자열 + `+` 연산자) 이므로 외부 파일로
  저장하려면 "실제 실행 결과 bytes" 를 저장해야 함 (예: `python3 -c "import
  monitor_server.core as c; print(c._task_panel_css(), end='')" > task_panel.css`).
  **방어**: C1-4 에서 저장 전 `md5(core._task_panel_css())` 와 저장 후
  `md5(Path("task_panel.css").read_text())` 가 동일한지 검증.
- **LOW — Pylance 경고 증가**: loader 패턴이 `Path(__file__).parent` 호출
  추가 → Pylance "unused import" 또는 "string literal expected" 경고 가능.
  **방어**: core-decomposition refactor.md §"Pylance 잔존 진단" 원칙 — facade
  비용으로 허용. 경고 수 증감만 측정.

## 14. QA 체크리스트

### 14.1 baseline (C0-1)

- [ ] `rtk proxy python3 -m pytest -q scripts/ --tb=no` 실행 후
  `docs/features/core-dashboard-asset-split/baseline.txt` 에 저장 (exit 0,
  failed=3 pre-existing baseline, passed=1997, skipped=176).
- [ ] `get_static_bundle("style.css")` md5 = **dcab587d6fd4fc32f46117fbdce06e44**,
  len = **51028** 확인 후 baseline 에 기록.
- [ ] `get_static_bundle("app.js")` md5 = **479d0ac147cd74f4664c00acd0d38c78**,
  len = **35079** 확인 후 baseline 에 기록.
- [ ] 5개 심볼 개별 md5 baseline 기록 (`DASHBOARD_CSS`/minified, `_DASHBOARD_JS`,
  `_PANE_CSS`, `_PANE_JS`, `_task_panel_css()`, `_task_panel_js()`).
- [ ] 실기동 `GET /` / `/static/style.css` / `/static/app.js` / `/pane/{id}`
  md5 baseline 기록 (`monitor-launcher.py --port 7321 --docs docs/monitor-v5`).

### 14.2 C1 단계 (이관 5 커밋)

- [ ] C1-1 (DASHBOARD_CSS): pytest 3 failed 유지 (신규 failed 0).
  `md5(get_static_bundle("style.css"))` 불변. `hasattr(core, 'DASHBOARD_CSS')`
  True + minified 상태 (`\n` 없음, 공백 압축됨) 검증.
  7개 regex-parse 테스트 중 DASHBOARD_CSS 참조 6개 shim 적용 완료.
- [ ] C1-2 (_DASHBOARD_JS): pytest 3 failed 유지. `md5(get_static_bundle("app.js"))`
  불변. `hasattr(core, '_DASHBOARD_JS')` True. 3개 테스트 shim 적용 완료.
- [ ] C1-3 (_PANE_CSS + _PANE_JS): pytest 3 failed 유지. 두 bundle md5 불변.
  `GET /pane/%1` smoke 200 + HTML body md5 불변. 테스트 shim: 없음
  (`_PANE_*` 는 attribute 접근만 확인).
- [ ] C1-4 (_task_panel_css): pytest 3 failed 유지. bundle md5 불변.
  `core._task_panel_css()` 반환값 md5 = baseline 일치.
- [ ] C1-5 (_TASK_PANEL_JS + _task_panel_js): pytest 3 failed 유지. bundle
  md5 불변. `core._task_panel_js()` 반환값 md5 = baseline 일치.
  `test_monitor_progress_header.py` shim 적용 완료.
- [ ] 전 C1 단계 완료 후 core.py LOC 측정: 5,418 → **≤ 3,300**.

### 14.3 C2 단계 (stale 정리)

- [ ] C2-1: `scripts/monitor_server/static/style.css` + `.../app.js` 삭제
  후 pytest 3 failed 유지. `GET /static/style.css` 200 (bundle 경유), md5
  baseline 일치. `handlers._serve_local_static` 디스크 폴백 경로는 진입하지
  않음 (`sys.stderr` 로그 검증).

### 14.4 C3 단계 (cleanup)

- [ ] C3-1: core.py 상단 loader 섹션이 단일 블록 (`_STATIC_ROOT` +
  `_load_static_text` + 5개 속성 + 2개 wrapper). breadcrumb 주석이 원래
  위치에 한 줄씩 유지 (core-decomposition refactor-02 선례).
- [ ] `__init__.py` docstring 업데이트 — `monitor_server/static/*.css,*.js`
  디렉터리 구조 명시.

### 14.5 최종 수용 기준 (spec.md §수용 기준 + §12 조정치)

- [ ] `wc -l scripts/monitor_server/core.py` ≤ **3,300** (조정된 기준,
  원래 spec ≤ 3,000 은 실측 기반 미달 — §12 참조).
- [ ] 모든 신규 `static/*.css,*.js` 파일은 Python 모듈 아님 → NF-03 무관
  (자산 파일).
- [ ] `rtk proxy python3 -m pytest -q scripts/ --tb=no` → **3 failed /
  1997 passed / 176 skipped** (baseline Δ = 0).
- [ ] 실기동 smoke 5종 200 OK + md5 불변:
  - `GET /` 200 (HTML body 외부 `<link>` 경로 동일)
  - `GET /static/style.css` 200 + md5 = baseline
  - `GET /static/app.js` 200 + md5 = baseline
  - `GET /static/dashboard.css` 404 (신규 파일은 별도 URL 미노출 —
    `_STATIC_ASSET_WHITELIST` 에 추가되지 않음. spec.md 의 "신규
    `GET /static/dashboard.css` 200" 요구는 번들 내부 섹션을 가리키는
    것으로 재해석)
  - `GET /pane/%1` 200 + HTML body md5 = baseline
- [ ] facade 무결성: 아래 심볼 전부 `hasattr(core, name)` True + 반환값
  byte-identical.
  ```
  DASHBOARD_CSS (minified), _DASHBOARD_JS, _PANE_CSS, _PANE_JS,
  _TASK_PANEL_JS, _task_panel_css (callable), _task_panel_js (callable),
  get_static_bundle (callable), get_static_version (callable)
  ```
- [ ] 신규 참조 0건: `grep -rn "DASHBOARD_CSS = \"\"\"" scripts/monitor_server/`
  → 0 매치 (인라인 literal 완전 제거 확인).
- [ ] 테스트 shim 반영 확인: 8개 파일에서 `static/dashboard.css` 또는
  `static/dashboard.js` 경로 우선 로딩 패턴 존재.

## 15. 동작 보존 계약

- `/`, `/static/style.css`, `/static/app.js`, `/pane/{id}`, `/api/state`,
  `/api/graph`, `/api/merge-status`, `/api/task-detail` 엔드포인트의
  응답(HTML body + JSON schema + CSS/JS 바이트) 는 baseline 과
  **byte-identical**.
- `monitor_server.core` 의 `dir()` 집합은 이관 전 심볼 set 의 상위 집합
  (loader 함수 추가 허용, 기존 속성/함수 제거 금지).
- `DASHBOARD_CSS` (minified 된 상태) 속성값의 bytes 는 baseline md5 와 동일.
  `_DASHBOARD_JS` / `_PANE_CSS` / `_PANE_JS` / `_TASK_PANEL_JS` 도 동일.
- `_task_panel_css()` / `_task_panel_js()` 함수는 시그니처 `() -> str`
  유지, 반환값 md5 baseline 과 동일.
- `get_static_bundle(name)` 의 반환 bytes 는 이관 전후 md5 동일 — `style.css`:
  `dcab587d6fd4fc32f46117fbdce06e44`, `app.js`: `479d0ac147cd74f4664c00acd0d38c78`.
- `get_static_version(name)` 의 반환값 (md5 앞 8자) 도 동일.
- 테스트 파일 변경은 8~9개로 한정 (regex-parse shim 추가). 단언 의미론
  변경 없음 (fallback 경로만 확장).
- pre-existing 3 failed 는 baseline 으로 유지 (기존 core-renderer-split
  refactor.md 결과 승계).

dev-build 가 생성할 단위 테스트 + md5 비교 스크립트는 위 동작 보존 계약의
검증 기준선이 된다. Refactor 단계는 기능 변경 금지 — 품질 개선 (docstring,
loader 섹션 주석 정리, regex-parse legacy fallback 제거 판단) 만 수행.
