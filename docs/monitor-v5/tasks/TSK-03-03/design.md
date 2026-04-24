# TSK-03-03: FR-05 크리티컬 패스 앰버 색 분리 + 범례 갱신 - 설계

## 요구사항 확인
- `scripts/monitor_server/static/style.css`의 `.dep-node.critical` 규칙에서 `border-color`/`box-shadow`를 `var(--fail)` 빨강에서 `var(--critical)` 앰버로 분리한다.
- `.dep-node.status-failed.critical` 동시 적용 시 failed(빨강)가 우선되도록 CSS specificity 또는 선언 순서로 보장한다.
- `scripts/monitor_server/renderers/depgraph.py`의 `#dep-graph-legend` DOM에 Critical Path 항목(`<li class="legend-critical">`)을 Failed 항목(`<li class="legend-failed">`)과 **별도**로 추가한다.
- `scripts/test_monitor_critical_color.py` 신규 — 4가지 AC를 pytest로 검증한다.

## 타겟 앱
- **경로**: N/A (단일 앱)
- **근거**: dev-plugin 프로젝트는 단일 Python 스크립트 패키지(`scripts/`)로 구성.

## 구현 방향

현재 코드베이스는 `monitor-server.py` 258KB 모놀리스이며, TSK-01-02/TSK-02-01 완료 후에는 CSS가 `scripts/monitor_server/static/style.css`, depgraph 렌더러가 `scripts/monitor_server/renderers/depgraph.py`로 분리된다. 본 Task는 그 분리된 파일들을 편집 대상으로 한다.

1. **CSS 수정** (`style.css`): `.dep-node.critical` 규칙에서 `var(--fail)` → `var(--critical)` 교체. `var(--critical)`은 TSK-03-01이 `:root`에 `#f59e0b` (amber)로 선언한 토큰.  
2. **CSS specificity 보장** (`style.css`): `.dep-node.status-failed.critical` 오버라이드 규칙을 `.dep-node.critical` 아래에 선언하여 failed 적색을 복원한다.  
3. **depgraph.py 범례 갱신**: `legend_html` 문자열에서 기존 failed `<span>` 계열 항목을 `<li class="legend-failed">`로 재구조화하고, `<li class="legend-critical">`를 추가한다. 나머지 상태 항목(done/running/pending/bypassed)도 동일한 `<li>` 구조로 통일하여 DOM 일관성을 확보한다.
4. **테스트 파일 신규**: `test_monitor_critical_color.py` — HTML 파싱(stdlib `html.parser` 또는 단순 문자열 검색)으로 4가지 AC를 검증.

## 파일 계획

**경로 기준:** 모든 파일 경로는 프로젝트 루트 기준으로 작성한다.

| 파일 경로 | 역할 | 신규/수정 |
|-----------|------|-----------|
| `scripts/monitor_server/static/style.css` | `.dep-node.critical` → `var(--critical)` 교체 + `.dep-node.status-failed.critical` override 추가 | 수정 (TSK-01-02 생성, TSK-03-01 편집, 본 Task 추가 편집) |
| `scripts/monitor_server/renderers/depgraph.py` | `legend_html` 생성부를 `<ul>/<li>` 구조로 재구성 + `<li class="legend-critical">` 추가 | 수정 (TSK-02-01 생성, 본 Task 편집) |
| `scripts/test_monitor_critical_color.py` | 4가지 AC 검증: amber 토큰 사용, failed 빨강 유지, failed가 critical보다 우선, 범례에 두 항목 별도 존재 | 신규 |

> **진입점 필수 체크**: domain=frontend이므로 라우터·메뉴 파일이 필요하나, 본 Task는 CSS 변수 교체 + 범례 DOM 수정으로 기존 라우트(`/`) 내 의존성 그래프 섹션을 수정한다. 신규 라우트/메뉴 추가 없음 — "비-페이지 UI" 분류.

## 진입점 (Entry Points)

**비-페이지 UI (기존 페이지 내 컴포넌트 수정)**: 신규 라우트/메뉴 없음. 대시보드 루트 `/`의 의존성 그래프 섹션 내 시각 변경.

- **사용자 진입 경로**: 대시보드 메인(`http://localhost:7321/`) 직접 접근 → 의존성 그래프 섹션으로 스크롤
- **URL / 라우트**: `http://localhost:7321/` (기존 대시보드 루트, 신규 라우트 없음)
- **수정할 라우터 파일**: 없음 — 신규 라우트 불필요. 기존 `/` 핸들러가 depgraph 섹션을 포함하여 렌더
- **수정할 메뉴·네비게이션 파일**: 없음 — 메뉴 추가 없음
- **연결 확인 방법**: 대시보드(`/`) 렌더 HTML에서 `#dep-graph-legend` 내 `<li class="legend-critical">` 존재 확인 (`test_monitor_critical_color.py::test_legend_has_critical_and_failed_items`). 크리티컬 노드에 `var(--critical)` 적용 확인.

## 주요 구조

### `style.css` — 수정 대상 규칙 (3블록)

```css
/* 1. critical modifier: var(--fail) → var(--critical) */
.dep-node.critical {
  border-color: var(--critical);
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--critical) 35%, transparent);
}

/* 2. failed 상태 규칙 유지 (변경 없음) */
.dep-node.status-failed {
  border-left-color: var(--fail);
  --_tint: color-mix(in srgb, var(--fail) 10%, transparent);
}
.dep-node.status-failed .dep-node-id { color: var(--fail); }

/* 3. 동시 적용 시 failed 우선 (specificity 2+2 > critical 1+1) */
.dep-node.status-failed.critical {
  border-color: var(--fail);
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--fail) 35%, transparent);
}
```

**Specificity 분석**:
- `.dep-node.critical` → (0,2,0) — 클래스 2개
- `.dep-node.status-failed.critical` → (0,3,0) — 클래스 3개 → failed가 반드시 우선

### `depgraph.py` — `legend_html` 생성 함수

현재 `legend_html`은 `<span class="leg-item">` 열거. 이를 `<ul id="dep-graph-legend">` + `<li>` 구조로 교체:

```python
legend_html = (
    '<ul id="dep-graph-legend" class="dep-graph-legend">'
    '<li class="legend-done leg-item" style="color:#22c55e">&#9632; done</li>'
    '<li class="legend-running leg-item" style="color:#eab308">&#9632; running</li>'
    '<li class="legend-pending leg-item" style="color:#94a3b8">&#9632; pending</li>'
    '<li class="legend-failed leg-item" style="color:#ef4444">&#9632; failed</li>'
    '<li class="legend-bypassed leg-item" style="color:#a855f7">&#9632; bypassed</li>'
    '<li class="legend-critical leg-item" style="color:#f59e0b">&#9632; critical path</li>'
    '<label class="dep-graph-wheel" for="dep-graph-wheel-toggle">'
    '<input type="checkbox" id="dep-graph-wheel-toggle">'
    f'<span>{wheel_label}</span></label>'
    '</ul>'
)
```

**주의**: 현재 CSS `#dep-graph-legend` 규칙은 `display:flex`로 정의됨. `<ul>`로 교체 시 기존 `display:flex` 레이아웃을 유지하려면 CSS에서 `#dep-graph-legend { list-style:none; margin:0; padding:0; display:flex; }` 를 확인/추가해야 한다. 기존 규칙이 `div`→`ul` 교체에도 selector(`#dep-graph-legend`)로 동일하게 적용되므로 레이아웃 회귀는 없다.

### `test_monitor_critical_color.py` — 4개 테스트 함수

```python
# 구조 스케치 (stdlib html.parser 또는 문자열 검색 사용, no pip)

def _load_style_css() -> str: ...   # style.css 파일 텍스트 로드
def _render_legend_html() -> str:   # depgraph.py 렌더 함수 직접 호출 or 문자열 생성

def test_critical_uses_amber_token():
    # style.css에 ".dep-node.critical" 블록 내 "var(--critical)" 포함 확인
    # ".dep-node.critical" 블록에 "var(--fail)" 없음 확인 (amber 전용)

def test_failed_keeps_red_token():
    # ".dep-node.status-failed" 블록에 "var(--fail)" 포함 확인
    # v4 회귀 0: border-left-color/--_tint/dep-node-id 색 유지

def test_failed_wins_over_critical():
    # ".dep-node.status-failed.critical" 블록 존재 확인
    # 해당 블록에 "var(--fail)" 포함 확인 (failed 우선 규칙)

def test_legend_has_critical_and_failed_items():
    # depgraph 렌더 HTML에서 'class="legend-critical"' 포함 확인
    # 'class="legend-failed"' 별도 포함 확인
    # 두 항목이 서로 다른 <li> 태그에 있음 확인
```

## 데이터 흐름

CSS 규칙 변경: `.dep-node.critical` 클래스 → `border-color: var(--critical)` (#f59e0b amber) / 동시 `.status-failed.critical` → `var(--fail)` (#ff5d5d red)

HTML 생성: `depgraph.py::legend_html` 문자열 → HTTP 응답 SSR HTML → 클라이언트 브라우저 `#dep-graph-legend` 렌더

## 설계 결정 (대안이 있는 경우만)

- **결정**: `.dep-node.status-failed.critical` 단독 override 규칙 추가 (specificity 방식)
- **대안**: 선언 순서만 조정 (`.dep-node.critical`을 `.dep-node.status-failed` 앞에 배치)
- **근거**: 선언 순서 방식은 `border-color` 단축 속성과 `border-left-color` 개별 속성이 혼용될 때 예상치 못한 override가 발생할 수 있음. specificity 방식은 의도가 명확하고 lint 도구가 검출 가능. 요구사항이 "specificity 또는 선언 순서"로 허용하지만, specificity가 더 견고.

- **결정**: `<div>` → `<ul>/<li>` 구조로 범례 교체
- **대안**: `<div>` + `<span>` 유지하되 `class` 속성만 추가 (`<span class="legend-critical leg-item">`)
- **근거**: WBS 요구사항이 `<li class="legend-critical">` DOM 구조를 명시. 테스트 기준이 `<li>` 태그 기반이므로 `<span>` 유지 시 AC-FR05-d 실패.

- **결정**: `legend_html`에서 amber swatch 색상을 `style="color:#f59e0b"` 인라인으로 유지 (var() 대신 리터럴)
- **대안**: `style="color:var(--critical)"` 사용
- **근거**: CSS 변수는 `style` 속성의 인라인 컨텍스트에서도 지원되나, 기존 범례 항목들이 모두 `#rrggbb` 리터럴을 사용하고 있어 일관성 유지. 테스트도 hex 값으로 검증 가능. `--critical: #f59e0b` 토큰 정의(TSK-03-01)와 값이 동일하므로 색상 드리프트 없음.

## 선행 조건

- **TSK-03-01 완료**: `scripts/monitor_server/static/style.css` `:root` 블록에 `--critical: #f59e0b` 선언 존재. 본 Task가 이 변수를 `.dep-node.critical` 규칙에서 참조.
- **TSK-02-01 완료**: `scripts/monitor_server/renderers/depgraph.py` 존재 + `legend_html` 생성 코드 이전 완료. 본 Task가 해당 파일을 수정.
- 상기 선행 Task가 미완료 상태이면 파일이 존재하지 않아 수정 불가 → CI 게이트.

## 리스크

- **HIGH**: TSK-03-01(style.css 생성) 또는 TSK-02-01(depgraph.py 생성)이 미완료이면 편집 대상 파일 없음. WP-03 리더가 선행 완료 확인 후 착수.
- **MEDIUM**: `<div>` → `<ul>` 교체로 인한 CSS 레이아웃 회귀. 기존 `#dep-graph-legend { display:flex; }` 규칙이 `ul` 엘리먼트에도 적용되므로 flex 레이아웃은 유지되나, 브라우저 기본 `ul { margin:8px 0; padding-left:40px; }` 스타일이 적용될 수 있음. CSS에 `list-style:none; margin:0; padding:0;` 추가 필요.
- **MEDIUM**: `monitor-server.py` 인라인 CSS를 직접 수정하는 중간 상태(TSK-01-02 미완료)에서는 style.css가 없음. 이 경우 `monitor-server.py` 인라인 CSS의 `.dep-node.critical` 블록을 직접 수정해야 하는 실행 경로가 생길 수 있음 — WP-03 리더가 실행 순서 확인 필수.
- **LOW**: `.dep-node.status-failed.critical` override 규칙이 `border-color` 단축 속성을 재선언하면 `border-width`, `border-style`도 같이 리셋될 수 있음. 단축 속성 대신 `border-top-color`, `border-right-color`, `border-bottom-color` 개별 속성으로 작성하거나 `border-color`만 override (기존 `.dep-node.critical`도 `border-color`만 사용하므로 동일 패턴 적용).
- **LOW**: 범례 색상 사용(`#f59e0b`) — `--critical` 토큰 값과 동일해야 함. TSK-03-01 설계에서 `--critical: #f59e0b`로 고정했으므로 드리프트 없음. 단 TSK-03-01 구현 시 값이 변경되면 범례도 수동 동기화 필요.

## QA 체크리스트

dev-test 단계에서 검증할 항목. 각 항목은 pass/fail로 판정 가능해야 한다.

- [ ] (정상) `test_critical_uses_amber_token`: `style.css` 내 `.dep-node.critical` 블록에 `var(--critical)` 포함, `var(--fail)` 미포함 확인.
- [ ] (정상) `test_failed_keeps_red_token`: `style.css` 내 `.dep-node.status-failed` 블록에 `border-left-color: var(--fail)`, `--_tint: color-mix(in srgb, var(--fail) 10%, transparent)` 포함, `.dep-node.status-failed .dep-node-id`에 `color: var(--fail)` 포함 확인.
- [ ] (정상) `test_failed_wins_over_critical`: `style.css` 내 `.dep-node.status-failed.critical` 블록 존재 + `border-color: var(--fail)` 및/또는 `box-shadow` 포함 확인 (failed 우선 override).
- [ ] (정상) `test_legend_has_critical_and_failed_items`: depgraph 렌더 HTML에 `class="legend-critical"` 및 `class="legend-failed"` 가 각각 별도 `<li>` 태그로 존재.
- [ ] (엣지) `.dep-node.critical`에 `var(--fail)` 리터럴이 남아 있지 않음 — grep으로 교체 완전성 확인.
- [ ] (엣지) `ul#dep-graph-legend` 에 `list-style:none; margin:0; padding:0` CSS 적용 확인 — 브라우저 기본 ul 스타일 리셋 여부.
- [ ] (회귀) `.dep-node.status-failed` 규칙이 v4 기준(`border-left-color`, `--_tint`, `.dep-node-id { color }`)에서 변경 없음 — v4 회귀 0 확인.
- [ ] (회귀) `test_monitor_dep_graph_html.py` 기존 통과 케이스가 그대로 통과 — 범례 구조 변경(`<span>` → `<li>`)으로 인한 회귀 없음.
- [ ] (통합) 대시보드 서버 기동 후 `/` 응답 HTML에 `<li class="legend-critical">` 및 `<li class="legend-failed">` 별도 포함 확인.
- [ ] (클릭 경로) 메뉴/사이드바/버튼을 클릭하여 목표 페이지에 도달한다 (URL 직접 입력 금지)
- [ ] (화면 렌더링) 핵심 UI 요소가 브라우저에서 실제 표시되고 기본 상호작용이 동작한다
