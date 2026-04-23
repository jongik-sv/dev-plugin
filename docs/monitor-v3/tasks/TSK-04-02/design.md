# TSK-04-02: graph-client.js 노드 HTML 템플릿 - 설계

## 요구사항 확인

- `graph-client.js`에 `escapeHtml` 헬퍼와 `nodeHtmlTemplate(data)` 함수를 추가하여, cytoscape-node-html-label 플러그인이 각 노드 위에 2줄 카드 HTML을 오버레이한다.
- 기존 `nodeStyle().label` 필드(단일 텍스트 레이블 + ⚠ 이모지 prefix)를 제거하고, 노드 스타일을 투명 배경(`background-opacity: 0`, `border-width: 0`, `width: 180`, `height: 54`)으로 변경하여 HTML 레이어가 시각을 전담한다.
- 레이아웃을 `nodeSep: 60`, `rankSep: 120`으로 조정하고, 기존 팝오버·폴링 로직은 변경하지 않는다.

## 타겟 앱

- **경로**: N/A (단일 앱) — 플러그인 내 JS 벤더 파일 직접 수정
- **근거**: 이 프로젝트는 Python + 단일 벤더 JS 구조로 워크스페이스 없음

## 구현 방향

1. `skills/dev-monitor/vendor/graph-client.js`에서 `nodeStyle()` 의 `label` 필드를 제거하고, 반환 객체에서 label 키를 삭제한다.
2. `escapeHtml(s)` 헬퍼를 추가한다 (`& < > " '` 이스케이프).
3. `nodeHtmlTemplate(data)` 함수를 추가한다 — `status-*`, `critical`, `bottleneck` 클래스 계산 후 2줄 카드 div 반환.
4. `cy` 초기화 직후(탭·팝오버 이벤트 바인딩 전) `cy.nodeHtmlLabel([...])` 로 HTML 레이블 플러그인을 등록한다.
5. `cy = cytoscape({...})` 의 node style 블록에서 `label`, `font-size`, `color`, `text-valign`, `text-halign`, `width`(label 기반), `height`(label 기반), `padding` 을 HTML 레이어 전담값(`background-opacity: 0`, `border-width: 0`, `width: 180`, `height: 54`)으로 교체한다.
6. `applyDelta` 내부에서 `layout` 파라미터를 `nodeSep: 60`, `rankSep: 120`으로 변경한다.
7. 기존 `applyDelta`, `updateSummary`, 팝오버, 폴링 로직은 변경하지 않는다.

## 파일 계획

**경로 기준:** 프로젝트 루트 기준

| 파일 경로 | 역할 | 신규/수정 |
|-----------|------|-----------|
| `skills/dev-monitor/vendor/graph-client.js` | `escapeHtml`, `nodeHtmlTemplate` 추가; `nodeStyle()` label 제거; 노드 스타일 투명화; `cy.nodeHtmlLabel` 등록; `nodeSep/rankSep` 조정 | 수정 |
| `scripts/monitor-server.py` | `_STATIC_WHITELIST`에 `cytoscape-node-html-label.min.js` 추가; `_section_dep_graph` script 로드 순서 갱신(`cytoscape-node-html-label` 삽입); `.dep-node*` CSS 인라인 추가; `dep-graph-canvas` height `520→640`px | 수정 |
| `skills/dev-monitor/vendor/cytoscape-node-html-label.min.js` | HTML 레이블 플러그인 v2.0.1 벤더링 (~7 KB) | 신규 |
| `scripts/test_monitor_dep_graph_html.py` | `nodeHtmlTemplate` 2줄 구조, `escapeHtml`, bottleneck 클래스, nodeSep/rankSep 값을 검증하는 단위 테스트 | 신규 |

## 진입점 (Entry Points)

이 Task는 **공통 라이브러리 성격의 클라이언트 JS 수정**이다. 별도 라우트/메뉴 추가 없이 기존 `/` (대시보드 홈) → "Dependency Graph" 섹션이 자동으로 렌더한다.

- **사용자 진입 경로**: 브라우저에서 `http://localhost:7321/` 접속 → "의존성 그래프" 섹션 확인 → 노드 카드에 2줄 레이블(ID 상단, 제목 하단) 및 상태 색상 스트립 확인
- **URL / 라우트**: `/` (메인 대시보드, `dep-graph` 섹션 포함)
- **수정할 라우터 파일**: `scripts/monitor-server.py` — `_section_dep_graph()` 함수 내 `<script>` 로드 순서에 `cytoscape-node-html-label.min.js` 추가 (기존 라우팅 구조 변경 없음)
- **수정할 메뉴·네비게이션 파일**: 해당 없음 — 섹션은 이미 메인 대시보드에 포함됨. `_STATIC_WHITELIST` 목록에 파일명만 추가
- **연결 확인 방법**: 브라우저에서 `http://localhost:7321/`를 직접 타이핑하여 접속 → "의존성 그래프" 섹션에서 노드 카드가 2줄(ID/제목)으로 표시되고 pan/zoom 시 추종하는지 확인

## 주요 구조

- **`escapeHtml(s)`**: `& < > " '` 5종 HTML 특수문자를 이스케이프. XSS 방지 헬퍼.
- **`nodeHtmlTemplate(data)`**: 노드 데이터(`nd`)를 받아 `status-{done|running|pending|failed|bypassed}` 클래스, `critical`/`bottleneck` 조건부 클래스, `dep-node-id`(ID), `dep-node-title`(label or id)로 구성된 2줄 카드 HTML 문자열 반환.
- **수정된 `nodeStyle(nd)`**: `color`, `borderColor`, `borderWidth` 계산 유지. `label` 키 제거.
- **`cy.nodeHtmlLabel` 등록 블록**: `cy = cytoscape(...)` 직후, 이벤트 바인딩 전에 호출. `tpl: data => nodeHtmlTemplate(data)` 콜백 사용.
- **cytoscape node style 블록**: `background-opacity: 0`, `border-width: 0`, `width: 180`, `height: 54`, `shape: roundrectangle` — 자리만 점유, 시각은 HTML 레이어.

## 데이터 흐름

`/api/graph` JSON 응답 → `applyDelta(data)` → 각 노드에 대해 `nodeStyle(nd)` (color/border 계산) + `nodeHtmlTemplate(nd)` (HTML 레이블) → `cy.nodeHtmlLabel` 플러그인이 pan/zoom에 따라 HTML DOM을 노드 위치에 추종시킴 → CSS(`.dep-node.*` 클래스)로 3중 시각 단서(좌측 스트립, ID 글자색, 배경 틴트) 렌더링

## 설계 결정 (대안이 있는 경우만)

- **결정**: `cy.nodeHtmlLabel` 플러그인(cytoscape-node-html-label v2.0.1) 사용
- **대안**: cytoscape `label: 'data(label)'` 방식 유지 + SVG foreignObject 커스텀 렌더러
- **근거**: TRD §3.10.2에 명시된 대로 기존 cytoscape 스택을 유지하면서 HTML 오버레이만 플러그인으로 추가 — 기존 팝오버/폴링 로직 변경 없이 최소 침습

---

- **결정**: `nodeHtmlTemplate`에서 `status` 필드를 그대로 사용 (`nd.status` → `nd.bypassed` 우선)
- **대안**: `nodeStyle`의 `color` 계산 로직을 `nodeHtmlTemplate`에 복제
- **근거**: 상태 클래스명은 CSS와 계약이고(`status-done` 등), `color` 계산은 cytoscape 속성 갱신용. 두 역할을 분리하면 중복 로직이 생기지 않음

## 선행 조건

- TSK-04-01: `cytoscape-node-html-label.min.js` 벤더 파일 추가 + `_STATIC_WHITELIST` + `_section_dep_graph` 로드 순서 + `.dep-node*` CSS 인라인이 완료되어야 TSK-04-02의 JS 변경이 실제로 동작함
  - TSK-04-01이 완료되지 않은 경우, 이 Task의 JS 코드는 작성 가능하나 브라우저 검증은 불가
- `cy.nodeHtmlLabel` API: cytoscape-node-html-label 플러그인이 로드된 후 `cy` 인스턴스에 `.nodeHtmlLabel()` 메서드가 존재해야 함

## 리스크

- **HIGH**: `cy.nodeHtmlLabel`이 플러그인 로드 실패 시 `TypeError: cy.nodeHtmlLabel is not a function` 으로 전체 그래프 초기화가 중단됨 → 방어: `if (typeof cy.nodeHtmlLabel === 'function')` 가드 추가
- **MEDIUM**: `nodeSep: 60`, `rankSep: 120` 변경으로 노드가 캔버스 밖으로 밀려날 수 있음 → `cy.fit()` 은 기존 코드에 없으므로, 레이아웃 완료 후 `cy.fit(undefined, 20)` 호출 고려 (단, 기존 동작과 차이가 생길 수 있어 선택적)
- **MEDIUM**: `applyDelta` 내 `cy.batch` 블록에서 `ele.data("label", ...)` 를 계속 갱신하면 HTML 레이블 플러그인과 간섭할 수 있음 — `label` 데이터 갱신 라인(`ele.data("label", style.label)`)을 제거하여 HTML 플러그인 단독 처리로 정리 필요
- **LOW**: `color-mix()` CSS 함수 미지원 구형 브라우저에서 배경 틴트(단서 3)가 투명으로 fallback → TRD §3.10.4 명시 허용 범위

## QA 체크리스트

dev-test 단계에서 검증할 항목.

- [ ] `nodeHtmlTemplate` 호출 결과 HTML에 `dep-node` 클래스를 가진 div가 존재한다
- [ ] `nodeHtmlTemplate` 호출 결과에 `dep-node-id` 내용이 입력 `nd.id`와 일치한다 (`test_dep_graph_node_template_contains_id_and_title`)
- [ ] `nodeHtmlTemplate` 호출 결과에 `dep-node-title` 내용이 `nd.label` 값과 일치한다 (`test_dep_graph_two_line_label`)
- [ ] `nd.is_bottleneck = true` 인 경우 `nodeHtmlTemplate` 결과 HTML에 `bottleneck` 클래스가 포함된다 (`test_dep_graph_bottleneck_class_renders`)
- [ ] `nd.is_critical = true` 인 경우 `nodeHtmlTemplate` 결과 HTML에 `critical` 클래스가 포함된다
- [ ] `nd.status = "done"` 이면 HTML에 `status-done` 클래스가 포함된다
- [ ] `nd.bypassed = true` 이면 상태 클래스가 `status-bypassed`로 오버라이드된다
- [ ] `escapeHtml("<script>")` 결과가 `&lt;script&gt;`로 이스케이프된다 (XSS 방지)
- [ ] `escapeHtml`이 `& < > " '` 5종 특수문자를 모두 정상 변환한다
- [ ] `nodeStyle(nd)` 반환 객체에 `label` 키가 존재하지 않는다
- [ ] cytoscape 노드 style의 `background-opacity`가 `0`이고 `border-width`가 `0`이다 (graph-client.js 소스 grep)
- [ ] cytoscape 노드 style의 `width`가 `180`, `height`가 `54`이다 (소스 grep)
- [ ] `applyDelta` 내 layout 호출 파라미터에 `nodeSep: 60`, `rankSep: 120`이 포함된다 (소스 grep)
- [ ] 기존 `cy.on("tap", "node", ...)` 팝오버 이벤트 핸들러가 제거되지 않았다 (소스 grep)
- [ ] `updateSummary` 함수가 제거되지 않았다 (소스 grep)

**fullstack/frontend Task 필수 항목 (E2E 테스트에서 검증):**
- [ ] (클릭 경로) 브라우저에서 `http://localhost:7321/`에 접속하여 "의존성 그래프" 섹션이 로드되고, 노드 카드가 2줄(상단 ID, 하단 제목)로 렌더된다
- [ ] (화면 렌더링) pan/zoom 조작 시 HTML 레이블이 노드 위치를 정확히 추종하며, 노드 클릭 시 팝오버가 정상 표시된다
