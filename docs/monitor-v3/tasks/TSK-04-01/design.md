# TSK-04-01: cytoscape-node-html-label 벤더 추가 - 설계

## 요구사항 확인
- `skills/dev-monitor/vendor/` 에 `cytoscape-node-html-label.min.js` (v2.0.1, ~7 KB)를 벤더링하여 외부 네트워크 의존 없이 서빙한다.
- `scripts/monitor-server.py`의 `_STATIC_WHITELIST`에 파일명을 추가하고, `_section_dep_graph` 내 `<script>` 로드 순서를 `dagre → cytoscape → cytoscape-node-html-label → cytoscape-dagre → graph-client`로 변경한다.
- `GET /static/cytoscape-node-html-label.min.js` → HTTP 200, MIME `application/javascript; charset=utf-8`; 기존 `/static/*.js` regression 없음.

## 타겟 앱
- **경로**: N/A (단일 앱)
- **근거**: 플러그인 내 단일 프로젝트 구조. 벤더 파일은 `skills/dev-monitor/vendor/`, 서버는 `scripts/monitor-server.py`에 직접 위치한다.

## 구현 방향
- GitHub Releases(`cytoscape/cytoscape.js-node-html-label`)에서 v2.0.1 minified 파일을 다운로드하여 `skills/dev-monitor/vendor/cytoscape-node-html-label.min.js`로 커밋한다.
- `_STATIC_WHITELIST` frozenset에 `"cytoscape-node-html-label.min.js"` 한 항목을 추가한다. 기존 `_handle_static` 라우터를 그대로 재사용하므로 라우팅 로직 변경은 없다.
- `_section_dep_graph`의 `scripts_html` 문자열에서 `cytoscape.min.js` 태그 직후, `cytoscape-dagre.min.js` 태그 직전에 `cytoscape-node-html-label` 태그를 삽입하여 명세된 로드 순서를 맞춘다.

## 파일 계획

**경로 기준:** 프로젝트 루트 기준

| 파일 경로 | 역할 | 신규/수정 |
|-----------|------|-----------|
| `skills/dev-monitor/vendor/cytoscape-node-html-label.min.js` | cytoscape-node-html-label v2.0.1 minified 벤더 파일 | 신규 |
| `scripts/monitor-server.py` | `_STATIC_WHITELIST`에 파일명 추가 + `_section_dep_graph` script 로드 순서 수정 | 수정 |

## 진입점 (Entry Points)

N/A — domain=infra, 비-UI Task.

## 주요 구조
- **`_STATIC_WHITELIST` (frozenset, line 121)**: 허용 벤더 파일명 집합. 여기에 `"cytoscape-node-html-label.min.js"` 추가.
- **`_handle_static(handler, path)` (line 4200)**: 경로를 whitelist에서 검증 후 vendor 디렉토리에서 파일을 읽어 응답. 수정 없이 재사용.
- **`_section_dep_graph(...)` (line ~3085)**: `scripts_html` 다중행 문자열에 `<script src="/static/cytoscape-node-html-label.min.js"></script>` 태그 삽입.
- **`cytoscape-node-html-label.min.js`**: cytoscape.js 확장 플러그인. cytoscape 로드 후, cytoscape-dagre 로드 전에 반드시 위치해야 한다.

## 데이터 흐름
클라이언트 `GET /static/cytoscape-node-html-label.min.js` 요청 → `do_GET` 디스패치 → `_handle_static` → whitelist 검증 통과 → `vendor/` 파일 바이너리 읽기 → `application/javascript` MIME으로 200 응답.

## 설계 결정 (대안이 있는 경우만)

- **결정**: GitHub Releases에서 직접 minified 파일 다운로드 후 커밋 (벤더링 방식)
- **대안**: npm/CDN URL을 런타임에 fetch하여 serving
- **근거**: 요구사항에 "외부 네트워크 의존 없음"으로 명시됨. 기존 벤더 파일(cytoscape, dagre, cytoscape-dagre, graph-client)도 모두 동일 방식으로 커밋되어 있음.

## 선행 조건
- 없음. TSK-04-01은 depends: `-` 이며 기존 `_handle_static` 인프라가 이미 존재한다.

## 리스크
- **LOW**: GitHub Releases URL이 삭제/이동될 경우 다운로드 실패. 단, 설계 단계에서 파일을 미리 커밋하므로 런타임에는 영향 없음. 빌드 환경에서만 주의 필요.
- **LOW**: 파일명 오타로 whitelist 검증 실패 시 404 발생. 테스트 케이스 `test_static_route_serves_node_html_label`로 즉시 감지 가능.

## QA 체크리스트
dev-test 단계에서 검증할 항목. 각 항목은 pass/fail로 판정 가능해야 한다.

- [ ] `GET /static/cytoscape-node-html-label.min.js` 응답 → HTTP 200, Content-Type `application/javascript; charset=utf-8` (`test_static_route_serves_node_html_label`)
- [ ] 응답 바디가 비어있지 않음 (파일 실제 내용 존재, 최소 100 bytes 이상)
- [ ] `_section_dep_graph` HTML 출력에 `<script>` 태그가 `dagre → cytoscape → cytoscape-node-html-label → cytoscape-dagre → graph-client` 순으로 포함됨 (`test_dep_graph_script_load_order`)
- [ ] 기존 `GET /static/cytoscape.min.js`, `/static/dagre.min.js`, `/static/cytoscape-dagre.min.js`, `/static/graph-client.js` → 각각 HTTP 200 (regression 없음)
- [ ] `GET /static/unknown.js` → HTTP 404 (whitelist 방어 동작 유지)
