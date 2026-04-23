# TSK-05-02: Dep-Graph `applyFilter` 훅 + 노드/엣지 opacity - 설계

## 요구사항 확인

- `skills/dev-monitor/vendor/graph-client.js` IIFE에 `applyFilter(predicate)` 함수를 추가하고 `window.depGraph.applyFilter`로 전역 노출한다. TSK-05-01의 `applyFilters()`가 이 훅을 호출하여 Dep-Graph 노드/엣지 opacity를 1.0/0.3으로 제어한다.
- `/api/graph` payload 노드 dict에 `domain`, `model` 필드를 추가하여 predicate가 이 값으로 필터 매칭할 수 있도록 한다. wbs.md의 `- domain:` / `- model:` 필드에서 읽고, 미존재 시 `"-"` fallback.
- 2초 폴링 재렌더 후에도 `_filterPredicate` 모듈 스코프 상태가 생존하여 필터가 유지된다.

## 타겟 앱

- **경로**: N/A (단일 앱)
- **근거**: `skills/dev-monitor/vendor/graph-client.js` + `scripts/monitor-server.py`가 프로젝트 루트에 직접 위치한 단일 앱 구조.

## 구현 방향

- `graph-client.js` IIFE 내 모듈 스코프에 `_filterPredicate`, `FILTER_OPACITY_DIM`, `FILTER_OPACITY_ON` 상수를 추가한다.
- `applyFilter(predicate)` 함수를 정의한다. `predicate === null` 시 전체 노드/엣지 opacity 1.0 복원, `predicate instanceof Function` 시 노드별 match → opacity 분기, 엣지는 양 끝 노드 match 여부로 분기.
- 기존 `tick()` → `applyDelta()` → 그래프 재렌더 완료 후 `_filterPredicate`가 존재하면 `applyFilter(_filterPredicate)`를 재호출하여 필터 상태를 생존시킨다.
- `window.depGraph = window.depGraph || {}; window.depGraph.applyFilter = applyFilter;` 패턴으로 전역 노출 (기존 네임스페이스 속성 병합, 충돌 방지).
- `scripts/monitor-server.py`의 `/api/graph` 핸들러 (`_build_graph_payload` 함수, L4907 주변) 노드 dict에 `domain`, `model` 필드를 추가한다. `_load_wbs_title_map`이 이미 파싱하는 `(title, wp_id, depends, model)` 4-tuple에서 `model`을 읽으며, `domain`은 동일 패턴으로 wbs.md `- domain:` 라인을 파싱하여 WorkItem에 저장한 후 payload에 포함한다.

## 파일 계획

**경로 기준:** 모든 파일 경로는 **프로젝트 루트 기준**으로 작성한다.

| 파일 경로 | 역할 | 신규/수정 |
|-----------|------|-----------|
| `skills/dev-monitor/vendor/graph-client.js` | `applyFilter(predicate)` 함수 정의 + `FILTER_OPACITY_DIM`/`FILTER_OPACITY_ON` 상수 + `_filterPredicate` 모듈 스코프 변수 + `applyDelta` 완료 후 재적용 훅 + `window.depGraph.applyFilter` 전역 노출 | 수정 |
| `scripts/monitor-server.py` | `_load_wbs_title_map` 파싱 tuple에 `domain` 필드 추가 (5-tuple화) + `WorkItem.domain` 필드 추가 + `_build_graph_payload` 노드 dict에 `"domain": task.domain`, `"model": task.model` 추가 | 수정 |
| `scripts/test_monitor_graph_filter.py` | 단위 테스트: (1) `graph-client.js` 내 `applyFilter` 함수 텍스트 검증, (2) `/api/graph` 응답 노드에 `domain`/`model` 필드 검증 (mock wbs), (3) JSDOM-free JS 로직 검증(node opacity 분기 의사 실행) | 신규 |
| `scripts/test_monitor_graph_filter_e2e.py` | E2E 테스트: 실 브라우저에서 대시보드 접속 → 필터 바 셀렉트 조작(TSK-05-01 통합) → Cytoscape 노드 opacity `page.evaluate` 검증 | 신규 |

> 별도 메뉴/네비게이션 파일 없음 — 필터 바 자체(TSK-05-01 `_section_filter_bar`)가 유일 진입점이며 본 Task는 훅 제공만 담당한다.

## 진입점 (Entry Points)

**domain=frontend Task — 진입점 필수 항목:**

- **사용자 진입 경로**: 대시보드 메인 로드 (`/?subproject=monitor-v4&lang=ko`) → 상단 sticky 필터 바(TSK-05-01) → 상태/도메인/모델 `<select>` 또는 검색 `<input>` 값 변경 → TSK-05-01의 `applyFilters()` 호출 → `window.depGraph.applyFilter(predicate)` 위임 → Dep-Graph 섹션 노드/엣지 opacity 즉시 반영
- **URL / 라우트**: `/?subproject=monitor-v4&lang=ko` (기존 대시보드 루트, 쿼리 파라미터 `?q=…&status=…&domain=…&model=…`로 필터 상태 URL 공유 — 필터 바 복원 시 `applyFilters()` → `applyFilter()` 자동 호출)
- **수정할 라우터 파일**: `scripts/monitor-server.py` — `_build_graph_payload` 함수(L4873~) 노드 dict 생성부에 `"domain"`, `"model"` 필드 추가. `do_GET`의 `/api/graph` 분기는 라우팅 변경 없이 payload 필드만 확장. `_load_wbs_title_map` 파싱 로직에 `domain` 추출 추가.
- **수정할 메뉴·네비게이션 파일**: 별도 메뉴 파일 없음. TSK-05-01의 `_section_filter_bar` 렌더 함수가 유일 진입점이며, 해당 함수 내 `applyFilters()` 코드가 `window.depGraph.applyFilter` 존재 여부를 확인 후 위임한다 (TSK-05-01 구현 범위). 본 Task는 `graph-client.js`에 훅 export만 담당.
- **연결 확인 방법**: E2E에서 대시보드 메인 접속 → 필터 바 `#fb-domain` `<select>` 를 `change` 이벤트로 조작 (URL 직접 입력 금지) → `page.evaluate(() => cy.nodes().map(n => n.style('opacity')))` 결과에서 비매칭 노드 `0.3` / 매칭 노드 `1` 확인.

## 주요 구조

- **`FILTER_OPACITY_DIM`** (`= 0.3`): IIFE 모듈 스코프 상수 — 비매칭 노드/엣지 opacity 값
- **`FILTER_OPACITY_ON`** (`= 1.0`): IIFE 모듈 스코프 상수 — 매칭(활성) 노드/엣지 opacity 값
- **`_filterPredicate`** (`let _filterPredicate = null`): 현재 필터 함수 보관. `null` = 필터 없음(전체 표시). `applyFilter` 호출 시 덮어씀. `applyDelta` 완료 후 재적용 훅이 이 값을 참조.
- **`applyFilter(predicate)`**: 핵심 공개 함수. 노드 전체 순회 → `predicate(node)` → opacity 설정. 엣지 전체 순회 → 양 끝 노드 match 여부 → opacity + `line-color` 설정. `predicate === null` 시 전체 복원.
- **재적용 훅**: `applyDelta` 완료 시점 (노드/엣지 추가·갱신 후, layout `layoutstop` 이벤트 콜백 포함) `if (_filterPredicate) applyFilter(_filterPredicate)` 삽입 — 2초 폴링 재렌더 후 필터 생존 보장.
- **`_load_wbs_title_map` 확장**: 현재 4-tuple `(title, wp_id, depends, model)` → 5-tuple `(title, wp_id, depends, model, domain)`. `- domain:` 라인 파싱 추가. `WorkItem` 에 `domain: Optional[str] = None` 필드 추가.

## 데이터 흐름

```
TSK-05-01 applyFilters()
  → window.depGraph.applyFilter(predicate)
      → graph-client.js applyFilter(predicate)
          → _filterPredicate = predicate
          → cy.nodes() 순회: predicate(node) → node.style('opacity', 1.0 | 0.3)
          → cy.edges() 순회: predicate(src) && predicate(tgt) → edge.style(opacity, line-color)

2초 폴링 tick()
  → fetch /api/graph → applyDelta(data)
      → 노드/엣지 추가·갱신 완료
      → if (_filterPredicate) applyFilter(_filterPredicate)  ← 필터 재적용

/api/graph (서버)
  wbs.md - domain:/model: 파싱
  → WorkItem.domain, WorkItem.model
  → 노드 dict: {"id":…, "domain": task.domain or "-", "model": task.model or "-", …}
```

## 설계 결정

- **결정**: `applyFilter` 함수를 IIFE 내부 함수로 정의 후 `window.depGraph.applyFilter`로 노출 (기존 IIFE 패턴 유지)
- **대안**: ES module `export function applyFilter`로 변환
- **근거**: `graph-client.js`는 `(function(){})()` IIFE 패턴으로 작성됨 (L3). ES module 전환은 `<script type="module">` 로드 방식 변경 + HTML 수정이 필요해 변경 범위가 커짐. `window.depGraph` 네임스페이스 노출은 IIFE에서도 동일하게 동작.

- **결정**: 엣지 `line-color` 복원 시 빈 문자열(`''`) 대신 `COLOR.edge_default` 또는 `COLOR.edge_critical` 원래 값으로 복원
- **대안**: `edge.style('line-color', '')` 로 초기화
- **근거**: Cytoscape `data(color)` 방식으로 엣지 색상이 원래 정의되어 있어, `ele.data('color')` 로 원본 색상을 읽어 복원하는 것이 안전함. `''` 빈 문자열은 브라우저마다 동작이 다를 수 있음.

- **결정**: `domain` 필드를 `_load_wbs_title_map` 5-tuple 확장으로 파싱 (wbs.md `- domain:` 라인)
- **대안**: `wbs-parse.py`를 서브프로세스로 호출하여 `domain` 취득
- **근거**: `_load_wbs_title_map`이 이미 `model` 필드를 동일 패턴(`- model:` 라인)으로 파싱 중. `domain`도 동일 파서 확장으로 처리하면 추가 프로세스 없이 O(N) 단일 패스로 취득 가능.

- **결정**: `applyDelta` 완료 후 재적용 훅 위치 — `topoChanged` 분기의 `layoutstop` 콜백 내부 + `topoChanged=false` 경로(상태만 변경된 경우) 모두에 삽입
- **대안**: `tick()` 함수 마지막에만 삽입
- **근거**: `topoChanged=true`인 경우 layout이 비동기(`layoutstop`)이므로 layout 완료 후 적용해야 위치 지터가 없음. `topoChanged=false`(노드 상태 색상만 갱신)는 동기 완료이므로 `applyDelta` 함수 끝에 호출.

## 선행 조건

- **TSK-05-01**: 필터 바 `applyFilters()` 구현이 완료되어야 E2E 통합 테스트 `test_filter_affects_dep_graph`가 동작함. 단위 테스트(`test_graph_client_has_apply_filter_export`, `test_api_graph_payload_includes_domain_and_model`, `test_dep_graph_apply_filter_hook`)는 TSK-05-01 완료 전에 독립 실행 가능.
- **TSK-03-01**: 이미 완료(design.md, test-report.md 존재). `renderPopover` / `hidePopover` 경로는 본 Task에서 건드리지 않음.

## 리스크

- **HIGH**: 2초 폴링 후 필터 상태 유실 — `applyDelta` 내 재적용 훅 누락 시 재현. 완화: `_filterPredicate` 모듈 스코프 유지 + `applyDelta` 두 경로(layout 동기/비동기) 모두에 `if (_filterPredicate) applyFilter(_filterPredicate)` 삽입. 단위 테스트 `test_dep_graph_apply_filter_hook`에서 "applyDelta 후 필터 재적용" 케이스 필수.
- **MEDIUM**: TSK-03-01 hover opacity와 filter opacity 충돌 — hover `renderPopover`는 팝오버 DOM만 조작하며 노드 `.style('opacity')`를 건드리지 않음(TSK-03-01 design.md 확인). filter는 `cy.nodes().forEach` 전체 순회로 적용. 두 레이어는 독립적으로 충돌 없음. 단, hover 직후 팝오버가 열려 있을 때 필터 적용 시 opacity는 즉시 갱신되지만 팝오버 위치(`_positionPopover`)는 그대로 유지됨 — 허용 범위. QA 체크리스트에 "hover popover 열린 상태에서 필터 적용 → 노드 opacity 변경되지만 popover 유지" 항목 추가.
- **MEDIUM**: 플러그인 캐시 동기화 누락 — `skills/dev-monitor/vendor/graph-client.js` 수정 시 `~/.claude/plugins/cache/dev-tools/dev/1.6.1/skills/dev-monitor/vendor/graph-client.js`에도 반드시 동기화해야 함 (CLAUDE.md feedback_always_sync_cache 규칙). 완화: QA 체크리스트에 명시. dev-build 구현 완료 후 캐시 동기화 스텝을 별도 커밋으로 분리.
- **LOW**: `window.depGraph` 네임스페이스 충돌 — `window.depGraph.applyFilter`를 설정할 때 기존 속성이 있으면 덮어쓰기 방지. 완화: `window.depGraph = window.depGraph || {};` 패턴으로 기존 속성 보존.
- **LOW**: `domain` 필드가 wbs.md에 없는 구버전 호환 — `_load_wbs_title_map`에서 `- domain:` 라인이 없으면 `None` → payload에서 `"-"` fallback. predicate가 `node.data('domain')` 호출 시 `"-"`를 받아 필터 비매칭 처리(모두 dim)가 아닌, 빈 문자열 비교 실패로 처리. 완화: predicate 쪽(TSK-05-01 범위)에서 `node.data('domain') === f.domain` 조건이 `f.domain=""` 이면 항상 `true`(필터 없음)이 되도록 설계. 노드의 `"-"` 값은 `f.domain=""` 대비 매칭 실패하지 않음(빈 문자열 필터 = 비활성).

## QA 체크리스트

dev-test 단계에서 검증할 항목. 각 항목은 pass/fail로 판정 가능해야 한다.

**단위 테스트 — `scripts/test_monitor_graph_filter.py`:**

- [ ] `test_graph_client_has_apply_filter_export`: `graph-client.js` 텍스트에 `applyFilter` 함수 정의 및 `window.depGraph.applyFilter = applyFilter` 대입 라인이 존재한다
- [ ] `test_graph_client_has_filter_constants`: `FILTER_OPACITY_DIM` = 0.3, `FILTER_OPACITY_ON` = 1.0 상수 선언이 존재한다
- [ ] `test_graph_client_has_filter_predicate_state`: `_filterPredicate` 변수 선언이 존재한다 (`let _filterPredicate = null`)
- [ ] `test_graph_client_has_reload_hook`: `_filterPredicate` 재적용 패턴 (`if (_filterPredicate)`)이 `applyDelta` 함수 내에 존재한다
- [ ] `test_api_graph_payload_includes_domain_and_model`: mock wbs.md(`- domain: frontend`, `- model: sonnet` 포함) 기반으로 `/api/graph` 핸들러 호출 시 응답 노드 dict에 `"domain": "frontend"`, `"model": "sonnet"` 필드가 존재한다
- [ ] `test_api_graph_payload_domain_fallback`: wbs.md에 `- domain:` 라인이 없는 Task 노드의 `domain` 필드가 `"-"` fallback임을 검증한다
- [ ] `test_dep_graph_apply_filter_hook`: `applyFilter(null)` 문자열 패턴이 opacity 복원 로직과 연결됨을 JS 코드 텍스트 분석으로 검증한다 (`predicate ? predicate : true` 또는 `predicate === null` 패턴)
- [ ] `test_dep_graph_apply_filter_null_restores`: `applyFilter` 함수에서 `predicate === null` 또는 `!predicate` 분기가 opacity 1.0으로 복원하는 코드 경로가 존재한다

**E2E 테스트 — `scripts/test_monitor_graph_filter_e2e.py`:**

- [ ] `test_filter_affects_dep_graph`: 대시보드 접속 → Dep-Graph 렌더 확인 → 필터 바 `#fb-status` `<select>` 값을 `running`으로 변경(클릭 경로) → `page.evaluate`로 Cytoscape 노드 opacity 확인: 매칭 노드 `1`, 비매칭 노드 `0.3`
- [ ] `test_filter_null_restores_opacity`: 필터 적용 후 `#fb-reset` 클릭(초기화) → 모든 노드 opacity 1.0 복원
- [ ] `test_filter_survives_2s_poll`: 필터 적용 후 2초 대기(폴링 발생) → 노드 opacity가 필터 적용 상태 그대로 유지됨
- [ ] `test_edge_color_on_partial_match`: 일부 노드만 매칭 시 양 끝 노드 모두 매칭된 엣지는 기본 색상 유지, 하나라도 비매칭인 엣지는 opacity 0.3으로 처리됨

**acceptance 검증 (PRD §5 AC-28):**

- [ ] `window.depGraph.applyFilter(node => node.data('status') === 'running')` 호출 → running 노드만 opacity 1.0
- [ ] 전체 노드 중 일부만 match 하면 엣지도 회색(opacity 0.3) 처리됨
- [ ] `applyFilter(null)` 호출 → 모든 노드/엣지 opacity 1.0 복원
- [ ] `/api/graph` 응답 노드에 `domain`, `model` 필드 존재
- [ ] 2초 폴링 후 그래프 재로드 시에도 필터 상태 유지(비매칭 노드 opacity 0.3 그대로)

**회귀 테스트:**

- [ ] TSK-03-01 hover/tap popover 경로 회귀 없음: `hidePopover()` / `renderPopover()` 시그니처 변경 없음 확인
- [ ] `test_monitor_graph_api.py` 기존 테스트 전체 통과 (`pytest -q scripts/test_monitor_graph_api.py`)
- [ ] pan/zoom 중 hover 타이머 취소 동작 유지 (TSK-03-01 기존 E2E 회귀)

**frontend 필수 항목 (E2E 테스트에서 검증 — dev-test reachability gate):**

- [ ] (클릭 경로) 메뉴/사이드바/버튼을 클릭하여 목표 페이지에 도달한다 (URL 직접 입력 금지) — 필터 바 `<select>` 조작을 클릭/change 이벤트로 수행, `page.goto` 직접 접근 금지
- [ ] (화면 렌더링) 핵심 UI 요소가 브라우저에서 실제 표시되고 기본 상호작용이 동작한다 — Dep-Graph 노드가 렌더되고 필터 변경 시 opacity가 브라우저에서 실제 변화한다

**플러그인 캐시 동기화:**

- [ ] `skills/dev-monitor/vendor/graph-client.js` 수정 후 `~/.claude/plugins/cache/dev-tools/dev/1.6.1/skills/dev-monitor/vendor/graph-client.js`에 동기화 완료

## TSK-05-01과의 계약

본 Task(TSK-05-02)는 `applyFilter` 훅 **제공만** 담당한다. 호출은 TSK-05-01의 `applyFilters()` 내부에서 다음 패턴으로 이루어진다 (TSK-05-01 범위):

```javascript
// TSK-05-01 applyFilters() 내부 Dep-Graph 분기 (참조용 — 본 Task 구현 범위 아님)
if (window.depGraph && window.depGraph.applyFilter) {
  var allEmpty = !f.q && !f.status && !f.domain && !f.model;
  if (allEmpty) {
    window.depGraph.applyFilter(null);
  } else {
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
}
```

TSK-05-01 통합 후 E2E 통합 항목(`test_filter_affects_dep_graph`)을 필수로 실행한다.
