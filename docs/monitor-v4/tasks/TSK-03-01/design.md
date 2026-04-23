# TSK-03-01: Dep-Graph 2초 hover 툴팁 - 설계

## 요구사항 확인
- Cytoscape Dep-Graph 노드에 2초 hover(dwell) 시 popover를 표시한다. 기존 tap 동작은 회귀 없이 유지.
- hover 경로와 tap 경로를 `data-source` 속성("hover"|"tap")으로 구분하고, hover source popover는 mouseout 시 즉시 숨긴다.
- pan/zoom 중에는 hover 타이머가 취소되어 popover가 표시되지 않는다.

## 타겟 앱
- **경로**: N/A (단일 앱)
- **근거**: `skills/dev-monitor/vendor/graph-client.js`가 프로젝트 루트에 직접 위치한 단일 파일. 모노레포 구조가 아님.

## 구현 방향
- 기존 `graph-client.js` IIFE 내부에 `HOVER_DWELL_MS` 상수(2000)와 `hoverTimer` 변수를 추가한다.
- `cy.on("mouseover", "node", ...)` 핸들러에서 `setTimeout`으로 2초 후 `renderPopover(ele, "hover")`를 호출하고, `cy.on("mouseout", "node", ...)`에서 타이머를 취소한다.
- 기존 `renderPopover(ele)` 시그니처를 `renderPopover(ele, source)`로 확장하여 popover DOM에 `data-source` 속성을 설정한다.
- `hidePopover()` 호출 시 `data-source`가 "hover"인지 확인하여 조건부 숨김 처리를 mouseout 핸들러에 추가한다.
- pan/zoom 핸들러에 `clearTimeout(hoverTimer)`를 추가한다.

## 파일 계획

| 파일 경로 | 역할 | 신규/수정 |
|-----------|------|-----------|
| skills/dev-monitor/vendor/graph-client.js | hover 타이머, source 구분, mouseover/mouseout 핸들러 추가, renderPopover 시그니처 확장 | 수정 |
| scripts/monitor-server.py | 라우터 — `do_GET`에서 `/` 라우트가 Dep-Graph 섹션을 SSR. `/static/graph-client.js`를 화이트리스트로 서빙. 변경 없음 (참조용) | 변경 없음 |
| scripts/monitor-server.py (`top-nav` CSS + `_SECTION_ANCHORS`) | 네비게이션 — `top-nav` 클래스가 대시보드 내 섹션 간 빠른 이동 링크 제공. `_SECTION_ANCHORS`에 `dep-graph` 포함. 변경 없음 (참조용) | 변경 없음 |

## 진입점 (Entry Points)

- **사용자 진입 경로**: 대시보드 메인 페이지 로드 → Dep-Graph 섹션 자동 렌더 → 노드 위에 마우스 커서를 2초간 유지
- **URL / 라우트**: `/` (대시보드 메인, `?subproject=` 쿼리 파라미터 옵션)
- **수정할 라우터 파일**: `scripts/monitor-server.py` — `do_GET`의 `/` 라우트가 `_section_dep_graph()`로 Dep-Graph 섹션을 SSR. `/static/graph-client.js`를 `_STATIC_PATH_PREFIX` 화이트리스트로 서빙. **변경 불필요** (참조용으로 파일 계획에 포함)
- **수정할 메뉴/네비게이션 파일**: N/A — 대시보드 단일 페이지 내 섹션이므로 별도 메뉴/네비게이션 없음. Dep-Graph는 대시보드 로드 시 자동 렌더됨.
- **연결 확인 방법**: 대시보드 접속 → Dep-Graph 섹션에 노드가 렌더됨 → 특정 노드 위에 마우스를 2초간 올리면 popover가 표시됨. 이어서 마우스를 밖으로 이동하면 popover가 즉시 사라짐.

> **비-페이지 UI (기존 컴포넌트 내 인터랙션 개선)**: Dep-Graph는 대시보드 메인 페이지의 일부 섹션이다. 대시보드 E2E(`test_monitor_e2e.py`)에서 Dep-Graph 섹션 렌더링을 이미 검증 중.

## 주요 구조
- **`HOVER_DWELL_MS`**: 상수 `2000` — hover 체류 시간 임계값 (ms)
- **`hoverTimer`**: 모듈 스코프 변수 — `setTimeout` ID 보관, mouseout/pan/zoom 시 `clearTimeout` 대상
- **`renderPopover(ele, source)`**: 기존 함수 시그니처 확장. `source` 인자("hover"|"tap")를 받아 popover DOM의 `data-source` 속성에 저장. `source` 누락 시 기본값 "tap" (기존 호출 호환)
- **mouseover 핸들러**: 노드 진입 시 `setTimeout` 시작, 2초 후 `renderPopover(ele, "hover")` 호출
- **mouseout 핸들러**: `clearTimeout(hoverTimer)` + popover의 `data-source`가 "hover"이면 `hidePopover()`

## 데이터 흐름
노드 mouseover → 2초 타이머 시작 → 타이머 완료 시 `renderPopover(ele, "hover")` → popover DOM에 `data-source="hover"` 설정 → 노드 mouseout → 타이머 취소 + popover 숨김.
tap 경로는 기존대로 즉시 `renderPopover(ele, "tap")` → `data-source="tap"` → 외부 클릭/ESC 시에만 숨김.

## 설계 결정

- **결정**: hover 타이머를 IIFE 모듈 스코프 변수(`hoverTimer`)로 관리
- **대안**: popover DOM에 타이머 ID를 `data-*` 속성으로 저장
- **근거**: 모듈 스코프가 클로저로 캡슐화되어 외부 접근 불가. DOM 속성 접근보다 오버헤드 없음.

- **결정**: `renderPopover`의 `source` 파라미터 기본값을 "tap"으로 설정
- **대안**: 기존 호출 지점을 모두 찾아 "tap" 명시
- **근거**: 기존 `applyDelta` 내부 폴링 시 `renderPopover(ele)` 호출(163행)이 있어 기본값 "tap"으로 회귀 방지.

- **결정**: pan/zoom 핸들러에서 타이머만 취소하고 popover는 유지 (tap source인 경우)
- **대안**: pan/zoom 시 모든 popover 숨김
- **근거**: 기존 tap popover는 pan/zoom 시 위치만 추종하여 유지되어야 함 (acceptance: "외부 클릭/ESC 까지 유지"). 타이머만 취소하면 tap popover 동작이 보존됨.

## 선행 조건
- TSK-00-02: API 응답 payload에 `phase_history_tail` 데이터가 포함되어 있어야 popover에서 실데이터 렌더 가능. 현재 `applyDelta`에서 `ele.data("_raw", nd)`로 원본 데이터를 이미 보관 중이므로 `raw.phase_history`가 있으면 자동 활용됨.

## 리스크
- MEDIUM: Cytoscape `mouseover`/`mouseout` 이벤트가 노드의 HTML 레이블(`nodeHtmlLabel` 플러그인) 오버레이 영역에서 정상 발생하는지 확인 필요. 플러그인이 DOM 오버레이를 생성하므로 이벤트 버블링 차단 가능성.
- LOW: hover 타이머와 2초 폴링 `tick()`의 race condition — `tick()`이 노드를 제거하면 타이머 콜백 시점에 노드가 존재하지 않을 수 있음. `cy.getElementById()`로 존재 확인 후 렌더.

## QA 체크리스트

- [ ] 노드 위에 마우스를 2초간 유지하면 popover가 표시된다 (`data-source="hover"`)
- [ ] 1.5초 후 마우스를 이동하면 popover가 표시되지 않는다 (타이머 취소)
- [ ] 노드 클릭(tap) 시 기존대로 즉시 popover가 표시된다 (`data-source="tap"`)
- [ ] tap popover는 외부 클릭, ESC 키, 빈 영역 클릭 시에만 사라진다
- [ ] hover popover는 mouseout 시 즉시 사라진다
- [ ] pan/zoom 중 hover 타이머가 취소되어 popover가 표시되지 않는다
- [ ] pan/zoom 중 이미 표시된 tap popover는 위치만 추종하고 유지된다
- [ ] `HOVER_DWELL_MS` 상수가 2000으로 선언되어 있다
- [ ] popover DOM은 1개뿐이며 hover/tap이 같은 DOM을 재사용한다
- [ ] `graph-client.js`에 `"mouseover"` + `"mouseout"` 이벤트 바인딩이 존재한다
- [ ] `renderPopover` 호출 시 `data-source` 속성이 "hover" 또는 "tap"으로 설정된다

**fullstack/frontend Task 필수 항목 (E2E 테스트에서 검증 — dev-test reachability gate):**
- [ ] (클릭 경로) 대시보드 메인 접속 → Dep-Graph 섹션에 노드가 렌더됨
- [ ] (화면 렌더링) 노드 위 2초 hover 시 popover가 브라우저에서 실제 표시되고, 마우스 이동 시 즉시 사라짐
