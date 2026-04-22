# TSK-03-03: /static/ 라우팅 + 벤더 JS 바인딩 - 설계

## 요구사항 확인
- `scripts/monitor-server.py`에 `/static/{file}` GET 라우트를 추가한다. 화이트리스트 4종(`cytoscape.min.js`, `dagre.min.js`, `cytoscape-dagre.min.js`, `graph-client.js`)만 서빙하고 그 외 경로(포함 `..` traversal)는 404.
- 파일 base는 `${CLAUDE_PLUGIN_ROOT}/skills/dev-monitor/vendor/`이며, MIME `application/javascript; charset=utf-8` + `Cache-Control: public, max-age=3600`으로 응답한다.
- 벤더 JS 3종(`cytoscape.min.js`, `dagre.min.js`, `cytoscape-dagre.min.js`)을 저장소에 실제 파일로 추가한다. `graph-client.js`는 TSK-03-04 산출물이므로 빈 placeholder 파일을 선행 배치한다.

## 타겟 앱
- **경로**: N/A (단일 앱)
- **근거**: 단일 Python 스크립트 기반 프로젝트

## 구현 방향
- `scripts/monitor-server.py`의 `do_GET` 디스패치 체인에 `_is_static_path(path)` 분기를 추가하고 `_handle_static(handler, path)` 핸들러를 구현한다.
- 핸들러는 `handler.server.plugin_root`에서 vendor 디렉터리 경로를 해석하고, 화이트리스트 검사 → `..` 포함 여부 검사 → 파일 읽기 → 응답 헤더 설정 순으로 처리한다.
- `ThreadingMonitorServer`에 `plugin_root` 속성을 추가하고 `main()`에서 `${CLAUDE_PLUGIN_ROOT}` 환경변수를 읽어 주입한다. 환경변수가 없으면 서버 파일(`monitor-server.py`)의 부모-부모 디렉터리를 fallback으로 사용한다.
- `skills/dev-monitor/vendor/` 디렉터리를 신설하고 CDN에서 오프라인으로 다운로드한 벤더 JS 3종 + `graph-client.js` 빈 파일을 커밋한다.

## 파일 계획

| 파일 경로 | 역할 | 신규/수정 |
|-----------|------|-----------|
| `scripts/monitor-server.py` | `_is_static_path()`, `_handle_static()`, `do_GET` 분기, `ThreadingMonitorServer.plugin_root`, `main()` plugin_root 주입 추가 | 수정 |
| `skills/dev-monitor/vendor/cytoscape.min.js` | Cytoscape.js 벤더 파일 | 신규 |
| `skills/dev-monitor/vendor/dagre.min.js` | Dagre 레이아웃 엔진 벤더 파일 | 신규 |
| `skills/dev-monitor/vendor/cytoscape-dagre.min.js` | Cytoscape-Dagre 어댑터 벤더 파일 | 신규 |
| `skills/dev-monitor/vendor/graph-client.js` | TSK-03-04 산출물 placeholder (빈 파일) | 신규 |

## 진입점 (Entry Points)
N/A — `domain=infra`, UI 없음.

## 주요 구조

- **`_is_static_path(path: str) -> bool`**: `/static/` 접두어 여부 + `..` 포함 여부 + 화이트리스트 파일명 해당 여부를 종합해 bool 반환. `..` 포함 또는 화이트리스트 외 파일이면 False.
  - 상수 `_STATIC_PATH_PREFIX = "/static/"` 정의.
  - 상수 `_STATIC_WHITELIST: frozenset[str]` — 4개 파일명 집합.
- **`_handle_static(handler: BaseHTTPRequestHandler, path: str) -> None`**: 실제 파일 IO + HTTP 응답 담당.
  - `plugin_root`를 `handler.server.plugin_root`에서 읽는다.
  - `filename = path[len(_STATIC_PATH_PREFIX):]`로 파일명 추출.
  - `vendor_dir = Path(plugin_root) / "skills" / "dev-monitor" / "vendor"` 로 절대 경로 조립.
  - `path.resolve()` 후 vendor_dir 하위인지 재검증(2차 traversal 방어).
  - 파일 읽기 실패(OSError) → 404.
  - 성공 시 `Content-Type: application/javascript; charset=utf-8`, `Cache-Control: public, max-age=3600` 응답.
- **`ThreadingMonitorServer.plugin_root: str`**: 서버 전역 속성. `main()`이 주입.
- **`_resolve_plugin_root() -> str`**: `os.environ.get("CLAUDE_PLUGIN_ROOT")` 우선, 없으면 `Path(__file__).resolve().parent.parent` (scripts/ 의 부모).
- **`do_GET` 디스패치 분기 추가**: `_is_static_path(path)` 분기를 기존 pane 분기 앞에 삽입.

## 데이터 흐름
`GET /static/cytoscape.min.js` 요청 → `do_GET` → `_is_static_path("/static/cytoscape.min.js")` True → `_handle_static(handler, "/static/cytoscape.min.js")` → `plugin_root/skills/dev-monitor/vendor/cytoscape.min.js` 읽기 → `200 application/javascript` + 파일 바이트 응답.

## 설계 결정 (대안이 있는 경우만)

- **결정**: `_is_static_path()`가 `..` 포함 경로를 False 반환 (404로 처리).
- **대안**: `_handle_static()`에서 `path.resolve()`로 traversal 후 vendor_dir 하위 여부를 검증하는 단일 방어선.
- **근거**: 이중 방어(디스패치 레벨 차단 + 핸들러 레벨 resolve 검증)로 directory traversal 공격면을 최소화한다.

- **결정**: 화이트리스트를 `frozenset`으로 정의.
- **대안**: 정규표현식 또는 `.endswith()` 체인.
- **근거**: frozenset O(1) 조회 + 불변성이 명시적이어서 코드 안전성이 높다.

- **결정**: `plugin_root` fallback을 `Path(__file__).resolve().parent.parent`(= 저장소 루트)로 설정.
- **대안**: 환경변수 없을 때 예외를 발생시키거나 빈 경로 유지.
- **근거**: 로컬 개발·테스트 시 환경변수 없이도 동작해야 한다. `__file__` 기반 경로는 항상 안정적이다.

## 선행 조건
- TSK-03-03 이전에 `ThreadingMonitorServer` + `main()` 구조가 완성되어 있어야 함 (TSK-01-01 완료) — 완료됨.
- 벤더 JS 파일 다운로드 소스: Cytoscape.js 3.x, Dagre 0.8.x, cytoscape-dagre 2.5.x CDN 릴리즈 (오프라인 커밋).

## 리스크

- **HIGH**: 없음.
- **MEDIUM**: 벤더 JS 파일 크기 — cytoscape.min.js는 ~200 KB 수준이며 저장소 크기 증가. 이미 요구사항에 커밋이 명시되어 있으므로 허용.
- **LOW**: `plugin_root` fallback 경로 해석이 심볼릭 링크 환경에서 `resolve()` 후 달라질 수 있음. 실제 symlink를 쓰는 환경이 없으므로 무시.
- **LOW**: 향후 화이트리스트 확장 시 코드 변경 필요. 현재 4개 파일로 고정, 확장 요건 없음.

## QA 체크리스트

- [ ] `GET /static/cytoscape.min.js` → HTTP 200, `Content-Type: application/javascript; charset=utf-8`, `Cache-Control: public, max-age=3600`, 본문 비어있지 않음.
- [ ] `GET /static/dagre.min.js` → HTTP 200.
- [ ] `GET /static/cytoscape-dagre.min.js` → HTTP 200.
- [ ] `GET /static/graph-client.js` → HTTP 200 (빈 파일이더라도 200, 본문은 0바이트 허용).
- [ ] `GET /static/../secrets` → HTTP 404 (`..` 포함 경로 traversal 차단).
- [ ] `GET /static/evil.js` → HTTP 404 (화이트리스트 외 파일명 차단).
- [ ] `GET /static/` (파일명 없음) → HTTP 404.
- [ ] `GET /static/%2F%2E%2E%2Fsecrets` (URL 인코딩된 traversal) — `urlsplit().path`를 통과한 후에도 `..` 포함 여부 검사가 동작하는지 확인 (`urllib.parse.unquote` 후 검사 포함).
- [ ] `ls skills/dev-monitor/vendor/*.js` — cytoscape.min.js, dagre.min.js, cytoscape-dagre.min.js, graph-client.js 4종 모두 존재.
- [ ] `plugin_root` 환경변수 없이 서버 기동 시 fallback 경로로 vendor 디렉터리를 정상 해석.
- [ ] 단위 테스트 `test_static_route_whitelist_allows_vendor_js` 통과.
- [ ] 단위 테스트 `test_static_route_rejects_traversal` 통과.
