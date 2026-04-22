# TSK-03-04: Dependency Graph 섹션 (graph-client.js + SSR + 통합) - 설계

## 요구사항 확인

- `scripts/monitor-server.py`에 `_section_dep_graph(lang, subproject)` SSR 헬퍼를 추가하고, `_I18N` 테이블(없으면 이 Task에서 최소 형태로 도입)에 `dep_graph` 키(ko "의존성 그래프" / en "Dependency Graph")를 등록한 뒤, `render_dashboard`의 섹션 조립 체인과 `_build_dashboard_body` 레이아웃에 dep-graph 섹션을 편입한다.
- `skills/dev-monitor/vendor/graph-client.js`(≤300 LOC, ES2020, 번들러 없음)를 신규 작성한다: cytoscape + dagre LR 레이아웃, 2초 폴링(`/api/graph?subproject=${SP}`), diff 기반 delta 적용(노드 속성 갱신 기본 + 토폴로지 변경 시에만 layout 재실행), CSS transition(400ms) 색상 전환, 노드 클릭 팝오버, pan/zoom, 고정 색상 팔레트(done/running/pending/failed/bypassed + 크리티컬/기본 엣지), 병목 노드 `⚠ ` 라벨 prefix, `?subproject=` 쿼리 유지.
- 진행도 요약 카드(`#dep-graph-summary`)를 폴링 tick마다 `총 N · 완료 x · 진행 y · 대기 z · 실패 w · 바이패스 b` + `크리티컬 패스 깊이 D` + `병목 Task K개` 형태로 렌더한다.

## 타겟 앱

- **경로**: N/A (단일 앱)
- **근거**: 본 프로젝트는 모노레포가 아니다. `scripts/monitor-server.py`와 `skills/dev-monitor/vendor/graph-client.js`가 모두 저장소 루트 기준 경로다.

## 구현 방향

1. `scripts/monitor-server.py`에 `_I18N` 테이블(ko/en 2언어, dep_graph 키 포함)과 `_t(lang, key)` 헬퍼를 도입한다. 이미 존재하는 다른 섹션 `h2`는 본 Task에서 건드리지 않는다(스코프 제한 — i18n 확산은 동일 WP의 별도 Task). 단 `_I18N`/`_t` 선언 자체는 이 Task에서 최초 배치되어야 `_section_dep_graph`가 참조 가능하다.
2. `_section_dep_graph(lang, subproject)` 헬퍼를 `_section_*` 블록(2121~2700 라인대) 뒤에 신설한다. `_section_wrap("dep-graph", _t(lang, "dep_graph"), body)` 헬퍼 대신 TRD §3.9.5가 지정한 고유 마크업(summary aside + 캔버스 div + legend div + 4종 `<script>`)이 필요하므로 전용 HTML 리터럴을 구성한다. `subproject` 값은 `<section data-subproject="…">`로 노출하여 graph-client.js가 초기값으로 읽게 한다.
3. `render_dashboard`의 `sections` 딕셔너리에 `"dep-graph": _section_dep_graph(lang, subproject)` 키를 추가하고, `_build_dashboard_body` 레이아웃에서 `s["phase-history"]` 바로 앞(또는 그리드 바깥 full-width 위치)에 삽입한다. `lang`/`subproject`는 `render_dashboard` 시그니처 확장이 선행되어야 하므로, 시그니처에 `lang: str = "ko", subproject: str = "all"` 기본값 인자를 추가하고 기존 호출부는 그대로 동작(기본값)하게 한다.
4. `_SECTION_ANCHORS` 튜플에 `"dep-graph"`를 추가한다(앵커 검증/점프에 사용되는 경우 대비).
5. `skills/dev-monitor/vendor/graph-client.js`는 IIFE로 감싸 모듈 오염 없이 동작한다. `POLL_MS=2000`, `cy.add + layout({name:'dagre', rankDir:'LR', nodeSep:40, rankSep:80}).run()` 초기화 후 `setInterval(tick, POLL_MS)`. `tick`은 `fetch('/api/graph?subproject=' + encodeURIComponent(SP), {cache:'no-store'})` → `res.ok` 가드 → `applyDelta(cy, data)` → `updateSummary(data.stats)`.
6. `applyDelta`는 서버의 `nodes[]`/`edges[]`를 id 기반 Map으로 diff한다: (a) 추가된 노드/엣지는 `cy.add(...)`; (b) 삭제된 노드/엣지는 `cy.remove(ele)`; (c) 유지되는 노드는 `ele.data('color', …), ele.data('borderWidth', …), …` 스타일 속성만 갱신 — cytoscape 스타일시트의 `transition-property`가 400ms 페이드를 처리한다. (d) 병목 클래스는 `ele.toggleClass('bottleneck', node.is_bottleneck)`. (e) 토폴로지 변경(추가·삭제 발생)이 있을 때만 `cy.layout({name:'dagre', …}).run()`.
7. 노드 클릭 팝오버는 `cy.on('tap', 'node', evt => showPopover(evt.target))` — DOM 기반 floating div(`position:absolute`)로 제목·status·depends·phase_history 표시. 상태 변화/재폴링 시 팝오버가 열려 있으면 같은 id에 대해 데이터만 교체. 바깥 클릭 시 닫힘.
8. 색상 팔레트는 JS 상수(`COLOR`)로 고정: `{done:'#22c55e', running:'#eab308', pending:'#94a3b8', failed:'#ef4444', bypassed:'#a855f7', edge_default:'#475569', edge_critical:'#ef4444'}`. 크리티컬 노드 border는 `#ef4444 / 2px`. 렌더 전 서버 응답의 각 노드에 대해 `color`, `borderColor`, `borderWidth`, `label`(`⚠ ` prefix 또는 raw)을 계산하여 cytoscape data로 주입.
9. 서버 응답의 `stats`를 `updateSummary`가 `document.getElementById('dep-graph-summary')`에 기록한다. `label_total`/`label_done` 등은 DOM에 서버가 미리 SSR한 정적 텍스트(ko 기본)를 유지하되, 숫자만 `.textContent` 업데이트하는 구조 — JS는 국문/영문 구분하지 않고 수치만 채움. 라벨 문자열은 SSR 단계에서 `lang`에 따라 동결.

## 파일 계획

**경로 기준:** 모든 파일 경로는 **프로젝트 루트 기준**으로 작성한다.

| 파일 경로 | 역할 | 신규/수정 |
|-----------|------|-----------|
| `scripts/monitor-server.py` | `_I18N` 테이블 + `_t` 헬퍼 도입, `_section_dep_graph(lang, subproject)` 신규, `render_dashboard(model, lang, subproject)` 시그니처 확장 + `sections["dep-graph"]` 주입, `_build_dashboard_body`에 dep-graph 슬롯 삽입, `_SECTION_ANCHORS`에 `"dep-graph"` 추가 | 수정 |
| `skills/dev-monitor/vendor/graph-client.js` | cytoscape 초기화 + dagre LR 레이아웃 + 2s 폴링 + diff 기반 delta apply + 팝오버 + 요약 갱신. IIFE 스코프, ES2020 순수 브라우저 JS, ≤300 LOC | 수정 (기존 0B placeholder → 실제 구현) |
| `scripts/test_monitor_render.py` | `test_graph_section_embedded_in_dashboard` 추가 — `render_dashboard` HTML에 `<div id="dep-graph-canvas">`, `<aside … id="dep-graph-summary">`, `/static/cytoscape.min.js`·`/static/dagre.min.js`·`/static/cytoscape-dagre.min.js`·`/static/graph-client.js` `<script>` 4종, i18n h2 문자열(기본 ko "의존성 그래프", `?lang=en` 시 "Dependency Graph")이 모두 포함됨 검증 | 수정 |
| `scripts/test_monitor_render.py` | `test_dep_graph_section_marks_subproject_in_data_attribute` — SSR 시 `data-subproject="p1"`이 섹션 루트에 붙어 graph-client.js가 읽을 수 있는지 검증 | 수정 (같은 파일, 신규 케이스) |

> dep-graph 섹션은 **비-페이지 UI** (대시보드 내 섹션)다. 라우터/메뉴 파일은 이미 TSK-03-01/03-02/03-03 에서 확립된 단일 대시보드 라우트(`/`)와 고정 섹션 조립 체인이다 — 본 Task는 `_build_dashboard_body` 섹션 배열이 곧 "메뉴/네비게이션 파일" 역할을 한다 (아래 "진입점" 참조).

## 진입점 (Entry Points)

- **사용자 진입 경로**: `대시보드 루트 / 열기 → 스크롤하여 화면 하단의 'Dependency Graph' / '의존성 그래프' 섹션으로 이동` (앵커 링크 `#dep-graph`로도 도달 가능).
- **URL / 라우트**: `/#dep-graph` — 언어 전환 시 `/?lang=en#dep-graph`, 서브프로젝트 전환 시 `/?subproject=p1#dep-graph`.
- **수정할 라우터 파일**: `scripts/monitor-server.py`의 `render_dashboard`(라인 3102 근처) — `sections` 딕셔너리에 `"dep-graph"` 키를 추가하고, `_build_dashboard_body`(라인 3067 근처)의 `s` 인자 조립 체인에서 `s["phase-history"]` 앞에 `s["dep-graph"]` 삽입. 단일-파일 서버이므로 별도 라우터 테이블은 없고 이 함수가 라우터 역할.
- **수정할 메뉴·네비게이션 파일**: `scripts/monitor-server.py`의 `_SECTION_ANCHORS`(라인 661) — `"dep-graph"` 앵커 등록. 별도 사이드바 컴포넌트는 없고 `_SECTION_ANCHORS` 튜플이 곧 네비게이션 카탈로그.
- **연결 확인 방법**: 단위 테스트 `test_graph_section_embedded_in_dashboard`가 `render_dashboard()` 반환 HTML에서 `<section … data-section="dep-graph">`, `<div id="dep-graph-canvas">`, `<aside … id="dep-graph-summary">`, 4종 `<script src="/static/…">` 태그, i18n h2 텍스트("의존성 그래프" 또는 `lang=en` 시 "Dependency Graph")가 모두 등장함을 검증한다. 수동 E2E에서는 모니터를 기동하여 브라우저로 `/` 진입 → 페이지 스크롤 → dep-graph 섹션 캔버스에 노드가 그려지는지 확인, 앵커 `/#dep-graph` 직접 이동은 reachability 검증용이 아닌 **클릭/스크롤 플로우**의 보조 수단이다(URL 직접 입력 금지 원칙에 따라 페이지 내 스크롤이 기본 경로).

> **비-페이지 UI**(대시보드 내 섹션): 상위 페이지는 `/` 대시보드 루트 1개. 해당 페이지의 단위 테스트 `test_graph_section_embedded_in_dashboard`가 섹션 렌더링을 검증한다.

## 주요 구조

- **`_I18N: dict[str, dict[str, str]]` + `_t(lang, key) -> str`**: 모듈 상단 상수. 본 Task에서는 `dep_graph` 키만 필수 등록(ko/en). 다른 섹션 h2가 추후 i18n 전환될 때 같은 테이블을 공유할 수 있도록 구조만 미리 만든다. 미등록 키는 key 자체를 fallback 반환.
- **`_section_dep_graph(lang: str, subproject: str) -> str`**: SSR HTML 반환. `<section id="dep-graph" data-section="dep-graph" data-subproject="{subproject_esc}">` + `.section-head`(eyebrow `graph` + h2 `_t(lang, "dep_graph")` + `<aside … id="dep-graph-summary">loading…</aside>`) + `.dep-graph-wrap`(`<div id="dep-graph-canvas" style="height:520px;">` + `<div id="dep-graph-legend">정적 범례</div>`) + 4종 `<script src="/static/…">`. subproject 값은 `html.escape(quote=True)` 처리하여 XSS 방지.
- **`render_dashboard(model, lang="ko", subproject="all")`**: 시그니처 확장. 기존 호출부(`do_GET` 핸들러, 테스트)는 위치 인자 없이 호출 가능. `sections["dep-graph"]`를 추가하고 `_build_dashboard_body`에 넘긴다.
- **`_build_dashboard_body(s)`**: `s["phase-history"]` 앞에 `s["dep-graph"]` 배치 — 전체 폭(`shell` 최하단, grid 바깥)이어야 캔버스 520px에 충분한 좌우 공간 확보.
- **`graph-client.js` IIFE** — 주요 내부 함수:
  - `init()`: DOM 준비 확인 → `SP = data-subproject || 'all'` 읽기 → `cy = cytoscape({...})` 생성 → 스타일시트 등록 → `tick()` 즉시 1회 + `setInterval(tick, POLL_MS)`.
  - `tick()`: fetch → `applyDelta` → `updateSummary` → `lastSignature` 갱신. fetch 실패/4xx/5xx는 silent skip(다음 tick 재시도).
  - `applyDelta(cy, data)`: id 기반 diff, 추가/삭제/갱신 3갈래. 토폴로지 변경 플래그가 true이면 `cy.layout({name:'dagre', rankDir:'LR', nodeSep:40, rankSep:80}).run()`.
  - `updateSummary(stats)`: `#dep-graph-summary` 내부의 `<span data-stat="total">` 등 요소들 `textContent` 갱신. SSR이 한번에 라벨+숫자 구조를 출력해두어 JS가 라벨 없이 숫자만 교체.
  - `showPopover(node)`: `cy.extent()` 기반 좌표 변환으로 DOM 팝오버 위치 산출. 같은 노드 재클릭/다른 노드 클릭/바깥 클릭/ESC에 닫힘.
  - `nodeStyle(node)`: `{color, borderWidth, borderColor, label}` 계산. `is_critical` → borderColor `#ef4444` borderWidth 2; 아니면 borderWidth 0. `is_bottleneck` → label `⚠ ` prefix + `.bottleneck` class toggle.

## 데이터 흐름

브라우저 dep-graph 섹션 로드 → `graph-client.js` init → `GET /api/graph?subproject={SP}` (TSK-03-02) → JSON `{nodes[], edges[], stats, critical_path, generated_at}` → cytoscape diff → DOM 전환(CSS transition 400ms) + `#dep-graph-summary` textContent 갱신 → 2s 후 재폴링.

## 설계 결정 (대안이 있는 경우만)

### 결정 1 — `_I18N` 도입 시점
- **결정**: 본 Task에서 `_I18N`/`_t`를 최소 형태(`dep_graph` 1키)로 도입한다.
- **대안**: 별도 i18n Task(WP-00 범위)에서 도입하고, 본 Task는 하드코딩 "의존성 그래프" 문자열만 쓴다.
- **근거**: WBS 요구사항이 "`_I18N`에 `dep_graph` 키 추가"라고 명시한다. 아직 `_I18N`이 없으므로 최소 뼈대를 함께 만들어 키를 등록한다. 다른 섹션 h2 전환은 스코프 밖.

### 결정 2 — graph-client.js 모듈 포맷
- **결정**: IIFE(`(function(){ … })();`) 스코프. 외부 노출 없음.
- **대안**: ES module(`<script type="module">`) + export.
- **근거**: 본 프로젝트는 번들러/모듈 loader 없이 `<script src>` 4개를 순차 로드한다. cytoscape/dagre는 global `cytoscape`/`dagre`를 노출하는 UMD 빌드이고, graph-client.js는 이들을 읽어 init만 수행하면 된다. IIFE가 최소 오버헤드 + 구식 브라우저 호환.

### 결정 3 — 폴링 vs WebSocket/SSE
- **결정**: 2초 폴링 유지(TSK-03-02 `/api/graph`와 짝).
- **대안**: SSE 또는 WebSocket 푸시.
- **근거**: TRD §3.9.7 "상태 머신이 이미 파일 기반이라 폴링이 push 없이도 지연 2초 이내로 수렴". 서버 측 복잡도 대비 이득 없음. 본 설계도 동일 결정을 계승.

### 결정 4 — dep-graph 섹션 배치
- **결정**: `_build_dashboard_body`에서 `s["phase-history"]` 바로 앞 full-width 영역에 배치.
- **대안**: `.col` 그리드 내부 우측 컬럼 하단에 배치.
- **근거**: 캔버스 520px + 대규모 WBS의 노드·엣지 시각성을 고려하면 전체 폭이 필수. phase-history도 full-width이므로 이웃 배치가 자연스럽다.

### 결정 5 — subproject 전달 방식(SSR→JS)
- **결정**: `<section … data-subproject="{sp}">` data attribute로 전달. graph-client.js가 자체 `document.querySelector` 로 읽어 초기값으로 쓴다.
- **대안**: `window.__SP__` 전역 변수 주입 / `<meta>` 태그 / URL 쿼리 직접 파싱.
- **근거**: data attribute가 CSP 친화적(inline script 불필요) + SSR 동기 확정. URL 파싱 fallback은 TRD §3.9.4 예시 코드(`new URLSearchParams(location.search).get('subproject')`)가 이미 고려하므로 둘 다 지원: data attribute가 없거나 비면 URL에서 읽고, 둘 다 없으면 `'all'`.

## 선행 조건

- **TSK-03-02**: `/api/graph` 엔드포인트 (응답 스키마 `{nodes, edges, stats, critical_path, generated_at, subproject, docs_dir}`). ✅ 완료 가정.
- **TSK-03-03**: `/static/` 화이트리스트 라우팅 + `skills/dev-monitor/vendor/{cytoscape.min.js, dagre.min.js, cytoscape-dagre.min.js, graph-client.js}` 4개 파일 존재. ✅ 완료(`ls`로 확인: cytoscape 365KB, dagre 277KB, cytoscape-dagre 12KB, graph-client.js는 0B placeholder).
- **TSK-02-02**: (의존성에 기재된 WP-02 selection/filter 관련 선행 Task). subproject 쿼리 파라미터가 `render_dashboard` 레벨까지 정상 전달되는 흐름이 확립되어 있어야 한다.
- 외부 브라우저 라이브러리: cytoscape.js 3.x(UMD), dagre 0.8.x(UMD), cytoscape-dagre 2.5.x(UMD). 이미 저장소에 vendor 커밋됨. 추가 pip/npm 의존성 없음.

## 리스크

- **HIGH**: `render_dashboard` 시그니처 확장(`lang`, `subproject` 인자 추가)이 기존 호출부·테스트에 영향. 완화: 기본값(`lang="ko"`, `subproject="all"`) 제공 + 기존 테스트(render 계열) regression run으로 확인. 호출부는 `do_GET` 핸들러 한 곳(라인 3856 근처)만 수정이 필요할 가능성이 크다.
- **HIGH**: `_I18N`을 이 Task에서 처음 도입하므로 테이블 오탈자나 language fallback 누락 시 KeyError 발생 가능. 완화: `_t`가 `.get(key, key)` fallback으로 항상 안전한 문자열 반환. 단위 테스트에 `_t("ko", "dep_graph") == "의존성 그래프"`, `_t("en", "dep_graph") == "Dependency Graph"`, `_t("xx", "unknown") == "unknown"` 3케이스 포함.
- **MEDIUM**: 대용량 WBS(100 Task, 200+ 엣지)에서 폴링마다 전체 JSON parse + diff가 프레임 부하를 유발할 수 있다. 완화: (a) `lastSignature`로 `generated_at` 변경 없을 시 diff 완전 스킵, (b) 토폴로지 불변 시 layout 스킵으로 가장 비싼 연산을 회피, (c) cytoscape의 `cy.batch(() => …)` 래핑으로 다중 data 업데이트를 1회 렌더로 묶음.
- **MEDIUM**: 노드 클릭 팝오버가 zoom/pan 중 좌표 계산이 어긋날 수 있다. 완화: `cy.on('pan zoom', () => repositionPopover())` 리스너로 재계산. 스크롤 이벤트(page scroll)도 리스너에 포함.
- **MEDIUM**: cytoscape-dagre 어댑터가 IIFE 로드 순서에 민감하다(dagre → cytoscape → cytoscape-dagre 순). TRD §3.9.5 예시는 `dagre → cytoscape → cytoscape-dagre → graph-client` 순이므로 이 순서를 엄수한다. 순서 어긋나면 `cytoscape.use(cytoscapeDagre)` 자동 등록이 실패.
- **LOW**: CSS transition 400ms + 0.5~2초 폴링 주기 중첩 시 "이중 fade" 착시가 날 수 있으나, 동일 상태는 diff에서 속성 재할당을 스킵하므로 실제로는 변경이 있을 때만 transition 재생.
- **LOW**: legend/범례는 정적 HTML로 SSR하므로 다국어 확장 시 별도 키가 필요. 본 Task는 ko 고정(또는 이모지/색상 아이콘 중심 언어 독립 디자인). 후속 Task로 영문화 가능.
- **LOW**: ES2020 Optional chaining/Nullish coalescing 사용. 지원 범위: Safari 14+, Chrome 80+, Firefox 74+ — 현대 개발 환경 전제 하 문제 없음.

## QA 체크리스트

dev-test 단계에서 검증할 항목. 각 항목은 pass/fail로 판정 가능해야 한다.

- [ ] (정상 - SSR 렌더) `render_dashboard(model)` 출력에 `<section … data-section="dep-graph">`, `<div id="dep-graph-canvas" style="height:520px;">`, `<aside … id="dep-graph-summary">`가 모두 포함된다.
- [ ] (정상 - 벤더 스크립트 4종) 같은 출력에 `/static/dagre.min.js`, `/static/cytoscape.min.js`, `/static/cytoscape-dagre.min.js`, `/static/graph-client.js` 4개 `<script src="…">` 태그가 이 순서로 존재한다.
- [ ] (정상 - i18n ko 기본) `render_dashboard(model)` 출력의 dep-graph 섹션 `<h2>`가 "의존성 그래프"이다.
- [ ] (정상 - i18n en) `render_dashboard(model, lang="en")` 출력의 dep-graph 섹션 `<h2>`가 "Dependency Graph"이다.
- [ ] (정상 - subproject 전달) `render_dashboard(model, lang="ko", subproject="p1")` 출력에 `data-subproject="p1"` 속성이 dep-graph 섹션에 붙는다.
- [ ] (정상 - 기본 subproject) `subproject` 미지정 시 `data-subproject="all"`.
- [ ] (정상 - 앵커 등록) `_SECTION_ANCHORS` 튜플에 `"dep-graph"`가 포함된다.
- [ ] (정상 - `_t` fallback) `_t("ko", "dep_graph") == "의존성 그래프"`, `_t("en", "dep_graph") == "Dependency Graph"`, `_t("en", "unknown_key") == "unknown_key"`.
- [ ] (엣지 - SSR XSS 방어) subproject 값에 `"><script>alert(1)</script>` 주입 시도 시 data attribute 값이 HTML-escape되어 브라우저가 실행하지 않는다(`html.escape(quote=True)` 적용 확인).
- [ ] (엣지 - 빈 모델) `render_dashboard({})` 호출이 예외 없이 완료되고 dep-graph 섹션이 여전히 출력된다(클라이언트가 fetch로 데이터 채움).
- [ ] (통합 - 기존 섹션 regression) `test_monitor_render.py` 내 기존 케이스들(wp-cards/features/team/subagents/live-activity/phase-timeline/phase-history) 모두 여전히 통과.
- [ ] (통합 - acceptance AC-12) 서버 응답의 critical edge(`is_critical=true`)가 graph-client.js에서 `#ef4444` 3px+ 굵기로 렌더되고 노드 테두리에 `#ef4444` 2px가 적용된다(브라우저 수동 확인 + JS 단위 로직의 color 매핑 확인).
- [ ] (통합 - acceptance AC-13) `is_bottleneck=true` 노드의 label이 `⚠ ` prefix를 갖고 `.bottleneck` 클래스가 토글된다.
- [ ] (통합 - acceptance AC-14) `#dep-graph-summary`에 `총 N · 완료 x · 진행 y · 대기 z · 실패 w · 바이패스 b` + `크리티컬 패스 깊이 D` + `병목 Task K개`가 모두 표시되며, 폴링 tick마다 stats 값에 맞게 갱신된다.
- [ ] (통합 - acceptance AC-16) Task `[im]` → `[xx]` 전환 후 2~3초 내 해당 노드 color가 `#eab308`→`#22c55e`로 CSS transition(400ms)을 타고 변경된다. 페이지 리로드 없음.
- [ ] (통합 - acceptance AC-17) 마우스 휠 pan/zoom이 기본 동작하며 노드 클릭 시 팝오버에 Task 제목, status, depends, phase_history가 표시된다. 팝오버는 바깥 클릭/ESC로 닫힌다.
- [ ] (통합 - 성능) 100개 Task WBS로 폴링 10회 반복 시 프레임 드랍 없음(DevTools Performance 탭 수동 확인). 토폴로지 변경 없는 tick에서 `cy.layout().run()` 호출이 없다(`spyOn` 대체로 console.log 카운터로 확인).
- [ ] (통합 - 오프라인) Wi-Fi 끈 상태에서 모니터 재기동 → 브라우저가 `/static/*.js` 4종을 정상 로드하여 cytoscape가 빈 캔버스로 초기화된다(fetch는 404/네트워크 에러로 stats 비어있음이지만 JS 초기화는 성공).
- [ ] (통합 - test_graph_section_embedded_in_dashboard) WBS 요구 단위 테스트 통과.

**fullstack/frontend Task 필수 항목 (E2E 테스트에서 검증 — dev-test reachability gate):**
- [ ] (클릭 경로) 메뉴/사이드바/버튼을 클릭하여 목표 페이지에 도달한다 (URL 직접 입력 금지) — 본 Task는 대시보드 루트 `/`의 내부 섹션이므로 "페이지 스크롤로 dep-graph 섹션 도달 + `#dep-graph` 앵커가 `_SECTION_ANCHORS`에 등록되어 있음"을 클릭 경로로 대체 검증한다.
- [ ] (화면 렌더링) 핵심 UI 요소가 브라우저에서 실제 표시되고 기본 상호작용이 동작한다 — cytoscape 캔버스에 노드가 그려지고, 노드 클릭 팝오버와 pan/zoom이 동작한다.
