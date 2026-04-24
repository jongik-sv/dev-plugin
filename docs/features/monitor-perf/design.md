# monitor-perf: 모니터 대시보드 성능 최적화 - 설계

## 요구사항 확인
- 단일 monitor 페이지가 GPU 38%·WindowServer 18%·Terminal 14%·monitor 폴링 10.6 req/s를 잡아먹는 회귀를 잡는다 (브라우저 탭 닫으면 즉시 0%로 회수되므로 클라이언트 폴링·렌더링이 원인).
- 5개 개선안을 모두 반영: ① 폴링 주기·전송 모델, ② 그래프 diff 갱신, ③ visibilityState 기반 폴링 정지/감속, ④ ETag/304 캐싱, ⑤ GPU 레이어 남용 감사.
- 회귀 방지: 폴링 빈도(req/s)와 GPU/CPU util 회귀 테스트(헤드리스 브라우저 60초 측정)를 설계 산출물에 포함.

## 타겟 앱
- **경로**: N/A (단일 앱 — `scripts/monitor_server/` 패키지가 유일한 모니터 앱)
- **근거**: dev-plugin 저장소는 모노레포가 아니며, 모니터 서버는 `scripts/monitor-server.py`(228줄 얇은 엔트리) + `scripts/monitor_server/` 패키지(core.py 6947줄, api.py 640줄, handlers.py 351줄, static/app.js 27KB, static/style.css 42KB) 단일 구조다. 기존 CLAUDE.md / 메모리 색인의 "monitor-server.py(~5600줄) 인라인 모놀리스" 표현은 TSK-02-03 분리 이전 상태를 기록한 것이며, 현재는 `monitor_server/core.py`가 사실상의 모놀리스(SSR HTML/CSS/JS 다수 인라인)다.

## 구현 방향
- **서버**: `monitor_server/core.py`의 `_handle_graph_api`, `_handle_api_state`(필요 시), 그리고 dashboard SSR 핸들러(`/` 응답)에 ETag/If-None-Match 처리를 넣는다. 응답 본문 직렬화 직후 SHA-256(또는 BLAKE2b-128) 해시를 계산해 `ETag` 헤더로 노출하고, 요청의 `If-None-Match`가 일치하면 본문 없이 304를 반환한다.
- **클라이언트 폴링 정책**: `static/app.js`의 메인 폴링(`startMainPoll`/`tick`, 현재 5000ms)과 drawer 폴링(`startDrawerPoll`/`tickDrawer`, 현재 2000ms)에 (a) `document.visibilityState==='hidden'`이면 폴링을 정지하고 `visibilitychange`로 재개, (b) 폴링 응답이 304면 본문 파싱·DOM 교체를 스킵, (c) 메인 폴링 주기를 5s 그대로 유지하되 visibility-aware로 전환해 백그라운드 탭 부하를 0으로 만드는 경로를 추가한다. **SSE/WebSocket으로의 push 전환은 권장하지 않는다** — tradeoff 논의는 "설계 결정" 참조.
- **그래프 diff 갱신**: 현재 dep-graph 영역은 `patchSection`이 `name==='dep-graph'`를 무조건 스킵해(static/app.js:115-117) 5초 폴링이 cytoscape canvas를 destroy하지 않는다. `/api/graph` 엔드포인트는 존재하지만 이를 폴링하는 `graph-client.js` 파일은 **현재 스튜브(존재하지 않음)** 다(core.py:121 주석 + scripts/monitor_server/static/ 디렉토리 ls 결과 graph-client.js 없음). 따라서 본 Feature는 (a) graph-client.js를 신규로 만들거나 (b) 기존 SSR dep-graph 갱신을 도입할 때 처음부터 diff 모드로 짜도록 **설계 가이드라인을 문서화**한다 — diff 알고리즘은 "주요 구조"의 `applyGraphDiff` 참조. 즉 본 Feature 구현 단계에서는 graph-client.js를 새로 만들지 않으며, "회귀 방지" 항목으로 SSR dep-graph가 폴링에 의해 매번 재구성되지 않는지 검증하는 테스트만 추가한다.
- **GPU 레이어 감사**: `style.css`(42KB) + `app.js`(27KB) + `core.py` 인라인 SSR을 grep으로 전수 감사한 결과 `will-change`·`translateZ`·`transform: translate3d`는 **0건**(이미 적절). 본 Feature는 "감사 결과 0건"을 baseline으로 기록하고, 향후 추가될 코드에서 reactive하게 `will-change`를 사용하지 못하도록 lint 가이드를 design.md에 못박는다(아래 "QA 체크리스트"). 기존 5개 `@keyframes`(spin/pulse/led-blink/breathe/fade-in)는 transform 또는 opacity만 변경해 합성 레이어 사용이 적절하다(추가 조치 불필요).
- **회귀 테스트**: 헤드리스 Chrome(`mcp__plugin_playwright_playwright__browser_*` 또는 standalone Playwright)을 이용한 60초 측정 하니스를 `scripts/test_monitor_perf_regression.py`로 추가. 측정 항목: req/s, /api/* 304 hit ratio, document.visibilityState=hidden 전환 시 req/s가 0으로 떨어지는지, dep-graph DOM mutation count. CI 환경에 Playwright가 없을 수 있으므로 부재 시 **skip**(unittest skipUnless)으로 처리해 회귀 테스트의 자체 회귀를 막는다.

## 파일 계획

**경로 기준:** dev-plugin은 단일 앱(저장소 루트)이라 모든 경로는 저장소 루트 기준이다.

| 파일 경로 | 역할 | 신규/수정 |
|-----------|------|-----------|
| `scripts/monitor_server/core.py` | `_json_response` 헬퍼에 ETag/304 처리 추가, dashboard SSR 핸들러(`/`)에도 동일 적용. SSR HTML 본문 해시 계산. | 수정 |
| `scripts/monitor_server/api.py` | `handle_graph`/`handle_state` 위임 함수에 ETag/304 처리 hook (또는 `_json_response`에서 일괄 처리되면 변경 불필요). | 수정 가능 |
| `scripts/monitor_server/handlers.py` | dispatcher 변경 없음 (라우팅 그대로). 다만 `If-None-Match` 헤더가 핸들러까지 흐르도록 `BaseHTTPRequestHandler.headers` 그대로 전달됨을 문서화. | 검토만 |
| `scripts/monitor_server/static/app.js` | (a) `startMainPoll`/`startDrawerPoll`에 `visibilitychange` 이벤트 핸들러 부착, (b) `fetch(...)` 응답 처리에 304 분기, (c) `If-None-Match` 헤더 송신을 위한 etag 캐시(window-scope 메모리 객체 또는 sessionStorage). | 수정 |
| `scripts/monitor_server/static/style.css` | 변경 없음 (이미 will-change/translateZ 0건). 단, 파일 상단 주석으로 "performance baseline: no will-change/translateZ — keep it that way" 가이드 1줄 추가. | 수정(주석만) |
| `scripts/monitor_server/etag_cache.py` | (선택) ETag 계산 헬퍼 (`compute_etag(payload_bytes) -> str`, `check_if_none_match(handler, etag) -> bool`). core.py 인라인이 6947줄이라 신규 모듈로 분리하면 단위 테스트가 쉬워짐. | 신규 |
| `scripts/test_monitor_etag.py` | ETag 헤더 형식·일치 시 304·미일치 시 200·잘못된 If-None-Match 처리 단위 테스트. ThreadingMonitorServer를 임시 포트로 띄우고 urllib.request로 호출. | 신규 |
| `scripts/test_monitor_polling_visibility.py` | app.js의 visibility-aware 폴링 로직 단위 테스트 (jsdom 없이 Python으로는 한계가 있으므로 (a) app.js를 정규식·AST로 파싱해 `document.addEventListener('visibilitychange'`/`hidden` 가드 존재 여부를 단언, (b) Playwright가 있으면 통합 테스트로 강화). | 신규 |
| `scripts/test_monitor_perf_regression.py` | 헤드리스 브라우저 회귀 하니스: 60초간 monitor 페이지 부하 측정 → req/s ≤ 0.5, 304 hit ratio ≥ 80%, hidden 시 req/s = 0. Playwright 부재 시 skip. | 신규 |
| `scripts/test_monitor_gpu_audit.py` | static/style.css·app.js·core.py에서 `will-change`·`translateZ`·`transform: translate3d` grep count == 0을 단언하는 정적 회귀 가드. 토큰 0짜리 1초 테스트. | 신규 |
| `docs/features/monitor-perf/design.md` | 본 문서. | 신규 (이미 작성 중) |

> **dev-build 대상 — 비-UI 페이지 변경:** 본 Feature는 신규 페이지·메뉴를 추가하지 않는다 (도메인이 backend로 분류된 이유). `/` 라우트는 그대로며, `/api/graph`·`/api/state`·`/api/pane/*`도 경로 변경 없이 응답 헤더만 보강된다. 따라서 라우터·메뉴 파일은 "수정 없음".

## 진입점 (Entry Points)

N/A — 본 Feature는 **backend 성능 최적화**다 (도메인=backend로 분류). 신규 페이지·라우트·메뉴 항목이 없고, 기존 `/`·`/api/*` 응답에 캐시 헤더와 클라이언트 폴링 가드만 추가한다. 사용자가 새로 클릭할 진입점이 없다.

> 참고: spec.md 작성 시 caller가 "fullstack"으로 분류했으나, 실제 변경 surface가 (a) HTTP 응답 헤더 추가, (b) 기존 인라인 JS 함수 행동 보강, (c) static asset 1바이트 주석 추가 — 어느 것도 "사용자 진입 경로"를 만들지 않는다. fullstack/frontend 분류 시 dev-design 게이트가 라우터·메뉴 파일을 강제하는데, 본 Feature는 그런 파일이 존재하지 않는 영역이므로 backend 분류가 정확하다. dev-build/test/refactor도 동일 분류 유지.

## 주요 구조

- **`compute_etag(payload_bytes: bytes) -> str`** (etag_cache.py 신규): 응답 본문에 대해 SHA-256 후 hex 14자(약 56비트) + `W/` weak-etag prefix 부여 → `'W/"a1b2c3d4e5f6g7"'`. weak-etag로 두는 이유: gzip/brotli 후처리·whitespace 정규화 대비 byte-exact 보장 의무 회피.
- **`check_if_none_match(handler, etag: str) -> bool`** (etag_cache.py 신규): `handler.headers.get('If-None-Match')`에서 다중 값(`,` 분리)·weak-prefix 정규화 후 일치 여부 반환. 일치 시 호출자는 `_json_304_response(handler, etag)`를 호출.
- **`_json_response(handler, status, payload)` 보강** (core.py:6420 수정): 직렬화한 JSON 바이트에 대해 etag 계산 → If-None-Match 일치 시 304 반환(헤더만), 아니면 기존대로 200 + ETag 헤더 추가.
- **`startMainPoll()` / `startDrawerPoll()` 보강** (app.js): IIFE 모듈 상단에 `state.visible = (document.visibilityState!=='hidden')`. `init()`에서 `document.addEventListener('visibilitychange', onVisibilityChange)`. `onVisibilityChange`는 hidden→visible 전환 시 즉시 `tick()` 1회 + 폴링 재개, visible→hidden 전환 시 `stopMainPoll()` + `stopDrawerPoll()`. **drawer는 hidden 시 무조건 정지** (사용자가 안 보고 있음).
- **`fetchAndPatch(signal)` 보강** (app.js:95): `fetch(...)`에 `headers: {'If-None-Match': state.mainEtag||''}` 추가. 응답이 304면 즉시 return (DOMParser·patchSection 호출 안 함). 200이면 `state.mainEtag = r.headers.get('ETag')` 갱신 후 기존 흐름.
- **`tickDrawer()` 보강** (app.js:197): 동일 패턴 — `state.drawerEtagByPane[id]` per-pane etag 캐시.
- **(가이드라인) `applyGraphDiff(prevPayload, nextPayload, cy)`** (graph-client.js — 현재 스튜브, 본 Feature에서는 작성하지 않음): 향후 graph-client.js를 도입할 때의 diff 알고리즘 표준을 design.md에 못박아둔다. (1) 노드 id 집합 비교 → 추가/삭제 산출, (2) 공통 노드는 `data.status`/`data.bypassed` 필드만 비교 → 변경된 노드 id만 `cy.getElementById(id).data(...)` 갱신, (3) 엣지 변경 시에만 dagre 재레이아웃, 그 외에는 레이아웃 호출 금지. cytoscape 전체 destroy는 `cy.destroy()` 호출이 명시된 경우만 허용.

## 데이터 흐름

**서버 측 (요청당)**: 클라이언트 fetch(`If-None-Match: W/"abc"`) → `Handler.do_GET` → `api.handle_graph` → `_handle_graph_api` → `scan_tasks` + `dep-analysis.py --graph-stats` → `_build_graph_payload` → JSON.dumps → `compute_etag(bytes)` → If-None-Match 일치 시 **304 (본문 0바이트)**, 아니면 **200 + ETag 헤더 + 본문**.

**클라이언트 측 (탭당)**: `init()` → `startMainPoll()` → 5s마다 `tick()` → `fetchAndPatch(signal, etag=state.mainEtag)` → 304면 noop, 200이면 DOMParser → `patchSection` → `applyFilter`. `visibilitychange` 이벤트 → hidden이면 `stopMainPoll()`+`stopDrawerPoll()`, visible이면 즉시 1회 fetch + 폴링 재개.

## 설계 결정

### 결정 1: SSE/WebSocket push 전환 보류, ETag+visibility 조합으로 충분
- **결정**: 폴링 주기는 5s 유지(이미 100ms가 아님 — 코드 확인 결과 메인 5000ms·drawer 2000ms). SSE/WebSocket 전환은 **하지 않는다**. 대신 ETag 304 + visibility 가드로 (a) 백그라운드 탭 0 req/s, (b) 미변경 시 페이로드 0바이트 + 클라이언트 redraw 0회 달성.
- **대안**: SSE(EventSource) 푸시 — 서버가 변경 시점에만 push.
- **근거**: (1) 현재 폴링이 5s 주기라 SSE 절감폭이 5s/요청 수준에 불과 (사용자 spec 추정 100ms는 코드와 불일치). (2) `ThreadingHTTPServer` 기반 동기 서버라 SSE 장기 연결을 도입하면 thread 1개를 영구 점유 — 다중 탭에서 thread starvation 위험. (3) "변경 감지" 트리거가 파일 시스템 watcher(inotify/FSEvents)로 추가 의존성 증가. (4) ETag만 추가해도 미변경 응답은 1KB 미만 304 + 클라이언트 redraw 0 → req/s는 그대로지만 GPU·CPU·네트워크 모두 ~0. 단순도·테스트 용이성·플랫폼 호환성 모두 우위.

### 결정 2: weak-etag(`W/"..."`) 사용
- **결정**: ETag prefix `W/` (weak validator) 부여.
- **대안**: strong etag (byte-exact 보장).
- **근거**: 본 응답은 JSON.dumps 결과로 dict iteration order에 영향받을 수 있고(Python 3.7+ insertion order지만 코드 변경 시 흔들림), gzip 등 transformation도 추후 도입 가능. weak-etag면 "의미적으로 동일"만 보장하면 되므로 운영 부담 감소. RFC 7232 §2.3 권장.

### 결정 3: ETag 계산 위치는 `_json_response` 1곳 집중
- **결정**: `core.py:_json_response` 헬퍼에서 모든 JSON 응답에 자동 ETag/304 처리 (api.handle_state, handle_graph, handle_task_detail, handle_merge_status, _handle_pane_api 모두 일괄 적용).
- **대안**: 각 핸들러에서 개별 처리.
- **근거**: 6개 핸들러 × 각각 같은 코드 = 중복. 헬퍼 1곳에서 처리하면 회귀 가드 단언도 1곳이면 충분(test_monitor_etag.py).

### 결정 4: graph diff 알고리즘은 가이드라인만 — 구현은 다음 Feature
- **결정**: `applyGraphDiff` 표준만 design.md에 명시, graph-client.js 신규 작성은 본 Feature 범위에서 제외.
- **대안**: graph-client.js를 본 Feature에서 함께 작성.
- **근거**: 현재 graph-client.js는 placeholder(파일 자체 없음)이고 dep-graph는 SSR로만 표시된다. cytoscape를 클라이언트에서 폴링 갱신하는 시나리오 자체가 미구현 — diff 갱신을 코드로 구현할 대상이 없다. SSR 폴링은 `patchSection`이 dep-graph를 무조건 스킵하므로 이미 회귀 안전. 향후 graph-client.js를 도입하는 별도 Feature(예: `monitor-graph-live`)에서 본 design.md의 diff 가이드라인을 reference하여 구현한다.

### 결정 5: GPU 레이어 감사는 "0건 baseline 고정 + 회귀 가드"
- **결정**: 감사 결과 `will-change`·`translateZ`·`translate3d` 모두 0건 — 이 baseline을 `test_monitor_gpu_audit.py`로 하드코딩 단언. 향후 PR에서 무심코 추가하면 CI에서 즉시 fail.
- **대안**: 코딩 가이드만 문서화(테스트 없음).
- **근거**: 메모리 색인의 `project_monitor_server_inline_assets.md`에 "시각 토큰 가드 부재로 동시 머지 시 무성 회귀 위험"이 이미 기록됨 — 가드 추가가 정확히 그 기록의 후속 조치다.

## 선행 조건

- 없음. 모든 변경이 기존 코드 보강 + 신규 헬퍼 모듈 1개 + 테스트 4개로 자족적.
- (선택) Playwright 설치 — 회귀 테스트 `test_monitor_perf_regression.py` 통합 모드용. 부재 시 자동 skip.

## 리스크

- **MEDIUM — `_json_response` 변경이 6개 핸들러에 일괄 영향**: ETag 추가가 기존 응답 형식을 깨면 광범위한 회귀. 완화: (1) 본문 1바이트도 변경하지 않음(헤더만 추가), (2) `test_monitor_api_state.py`(40KB·기존)·`test_monitor_dep_graph_html.py`(27KB·기존) 등 대형 회귀 스위트가 이미 응답 본문 모양을 단언 중 — 깨지면 즉시 감지.
- **MEDIUM — visibility-aware 폴링이 일부 사용자 시나리오를 깨뜨릴 위험**: "탭 전환 후 돌아오면 즉시 fresh 데이터" 기대를 만족시켜야 함. 완화: visible 전환 시 `tick()` 1회 즉시 호출 + 폴링 재개로 사용자가 "오래된 데이터를 보는" 시간 = 0.
- **MEDIUM — 회귀 테스트의 환경 의존성**: 헤드리스 브라우저 측정은 CI 환경별 GPU 드라이버에 따라 수치 변동 가능. 완화: 임계값을 보수적으로 (req/s ≤ 0.5, 304 hit ratio ≥ 80% 등) + Playwright 부재 시 skip + req/s·DOM mutation count는 환경 무관.
- **LOW — weak-etag 충돌 확률**: SHA-256 hex 14자 = 약 56비트 → 충돌 확률 무시 가능. 단 클라이언트 측 등호 비교에서 quote 정규화(`"abc"` vs `abc`) 미스할 수 있음 — RFC 7232 §3.2 형식 준수.
- **LOW — IIFE 모듈 추가 변경의 minification 호환성**: 현재 app.js는 minify되지 않음 (서버가 그대로 서빙). 향후 minify 도입 시 새 함수명도 mangle 대상에 포함되므로 영향 없음.

## QA 체크리스트
dev-test 단계에서 검증할 항목. 각 항목은 pass/fail로 판정 가능해야 한다.

**ETag/304 캐싱 (정상)**
- [ ] 동일 상태에서 `/api/state`를 두 번 GET하면 두 번째 응답이 304이고 본문 길이가 0이다.
- [ ] 동일 상태에서 `/api/graph`를 두 번 GET하면 두 번째 응답이 304이다.
- [ ] 200 응답에는 항상 `ETag` 헤더가 있고 형식이 `W/"[hex16자 이내]"`이다.
- [ ] If-None-Match 헤더의 ETag가 일치하지 않으면 200 + 본문 + 새 ETag를 반환한다.

**ETag/304 캐싱 (엣지/에러)**
- [ ] If-None-Match에 다중 값(`W/"a", W/"b"`)이 와도 한 개라도 일치하면 304를 반환한다.
- [ ] If-None-Match가 빈 문자열이면 일반 200 응답으로 처리한다.
- [ ] 응답 본문이 변경되면(예: scan_tasks가 1개 더 발견) ETag가 달라지고 304가 아닌 200을 반환한다.
- [ ] 304 응답에 `Content-Length: 0` 또는 본문 누락이 적합하게 처리되어 클라이언트가 hang하지 않는다.

**Visibility-aware 폴링**
- [ ] `app.js` 소스에 `document.addEventListener('visibilitychange'`와 `document.visibilityState` 분기 코드가 존재한다 (정적 grep 단언).
- [ ] (Playwright 가능 시) 페이지 로드 후 `page.evaluate(() => document.dispatchEvent(new Event('visibilitychange')))` + `document.hidden=true` 시뮬레이션 후 60초간 `/api/*` 요청 카운트가 0이다.
- [ ] (Playwright 가능 시) hidden 상태에서 visible로 복귀하면 1초 이내에 `/api/state` 요청이 1회 이상 발생한다.

**그래프 diff 회귀 방지**
- [ ] dep-graph 영역(`[data-section="dep-graph"]`)이 메인 폴링 5초 후에도 cytoscape canvas DOM이 destroy/recreate되지 않는다 (canvas element의 reference identity 유지).
- [ ] `patchSection('dep-graph', ...)` 호출이 early return으로 동작 변경 없음을 단위 테스트로 확인.

**GPU 레이어 감사 (회귀 가드)**
- [ ] `static/style.css`에서 `will-change`·`translateZ`·`translate3d` grep 결과 0건.
- [ ] `static/app.js`에서 `will-change`·`translateZ`·`translate3d` grep 결과 0건.
- [ ] `monitor_server/core.py` 인라인 SSR 영역에서 `will-change`·`translateZ`·`translate3d` grep 결과 0건.

**성능 회귀 (Playwright 가능 시)**
- [ ] 60초 측정 동안 `/api/*` + `/` 폴링 합계 평균 req/s ≤ 1.5 (foreground), ≤ 0.05 (background hidden).
- [ ] 60초 측정 동안 `/api/*` 응답 중 304 hit ratio ≥ 80% (상태 변화 없는 idle 측정 가정).
- [ ] 60초 측정 동안 dep-graph DOM mutation 횟수 ≤ 2 (초기 렌더 + 노이즈 마진).

**통합 케이스**
- [ ] 기존 `test_monitor_api_state.py`·`test_monitor_dep_graph_html.py` 등 대형 회귀 스위트가 모두 통과 (응답 본문 변경 0).
- [ ] `monitor-launcher.py --status`·`--stop`이 PID 파일·서버 라이프사이클을 그대로 유지 (성능 변경이 lifecycle을 깨지 않음).
