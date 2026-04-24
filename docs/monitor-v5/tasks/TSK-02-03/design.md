# TSK-02-03: `handlers.py` — HTTP 라우팅 이전 + `monitor-server.py` ≤ 500줄 - 설계

## 요구사항 확인

- `scripts/monitor_server/handlers.py`에 `BaseHTTPRequestHandler` 서브클래스 `Handler`를 작성하고, `do_GET`에서 `/`, `/api/*`, `/static/*`, `/vendor/*`, `/pane/*`, `/api/pane/*` 라우팅을 모두 dispatch한다.
- `scripts/monitor-server.py`를 `argparse` + `HTTPServer` 기동 + `serve_forever()` 만 남기는 얇은 entry로 축소하여 500줄 미만을 달성한다.
- TSK-02-01(renderers), TSK-02-02(api)에서 이전된 패키지를 `handlers.py`가 import하여 완전한 FR-07 S6 완결을 이룬다. 기존 단위/E2E 테스트 회귀 0.

## 타겟 앱

- **경로**: N/A (단일 앱 — `scripts/` 직속 Python 파일 + `scripts/monitor_server/` 패키지)
- **근거**: 프로젝트가 단일 Python 스크립트 프로젝트로, 모노레포 분리 구조 없음.

## 구현 방향

1. `scripts/monitor_server/handlers.py`에 `Handler(BaseHTTPRequestHandler)` 클래스를 작성한다. 기존 `MonitorHandler`의 `do_GET` 분기 로직 전체를 이전하되, 각 라우트별 위임 함수는 `monitor_server.api`(TSK-02-02에서 분리 완료 예정) 또는 `monitor_server.renderers`(TSK-02-01에서 분리 완료 예정)를 import하여 호출한다.
2. `/static/*` 서빙 로직(화이트리스트 + path traversal 방어)은 현재 `monitor-server.py`의 `_is_static_path` / `_handle_static` 구현을 `handlers.py` 내부 헬퍼로 이전한다. 기존 `_STATIC_WHITELIST`(vendor JS 파일 집합)와 TSK-00-01에서 정의된 `/static/style.css`, `/static/app.js` whitelist 두 집합을 단일 `Handler`에서 올바르게 dispatch한다.
3. `monitor-server.py` 본문에서 `MonitorHandler`, `ThreadingMonitorServer`, `build_arg_parser`, `pid_file_path`, `cleanup_pid_file`, `_setup_signal_handler`, `parse_args`, `main()`, `if __name__ == "__main__"` 블록만 잔류시키고, 나머지 6000+ 줄 전체를 `monitor_server` 패키지로 이전 완료 상태로 만든다. `monitor-server.py`는 `from monitor_server.handlers import Handler` 한 줄로 `Handler`를 가져와 `ThreadingMonitorServer`에 등록한다.
4. `monitor_server/__init__.py`를 통해 패키지 import가 동작하므로 `sys.path.insert(0, str(Path(__file__).parent))`가 `monitor-server.py` 상단에 이미 존재해야 한다(TSK-00-01 범위, 존재 확인만).
5. `scripts/test_monitor_module_split.py` 신규 작성: 엔트리 < 500줄 + handlers.py ≤ 800줄 + import 가능 여부 검증. `test_monitor_static_assets.py` / `test_monitor_e2e.py` 전량 회귀 확인.

## 파일 계획

| 파일 경로 | 역할 | 신규/수정 |
|-----------|------|-----------|
| `scripts/monitor_server/handlers.py` | `Handler(BaseHTTPRequestHandler)` — `do_GET` dispatch, non-GET 405, `/static/*` 서빙, `_route_root`, `_route_api_state`, `_route_not_found`. ≤ 800줄. | 신규(스켈레톤→완성) |
| `scripts/monitor-server.py` | 얇은 entry로 축소. `sys.path.insert` + import + `ThreadingMonitorServer((host,port), Handler)` + `serve_forever`. < 500줄. | 수정 |
| `scripts/test_monitor_module_split.py` | `test_monitor_server_entry_under_500_lines`, `test_handlers_under_800_lines`, `test_import_handlers` 3개 테스트. | 신규 |

## 진입점 (Entry Points)

N/A — domain=backend (HTTP 라우팅 인프라, UI 없음).

## 주요 구조

- **`Handler(BaseHTTPRequestHandler)`** (`handlers.py`): `do_GET` 단일 메서드에서 `urlsplit(self.path).path`를 분기하여 아래 라우트로 위임. non-GET 메서드는 모두 405.
  - `/ ` → `_route_root(self)` → `monitor_server.renderers.render_dashboard` 호출 (TSK-02-01 의존)
  - `/api/state` → `monitor_server.api.handle_state(self)` (TSK-02-02 의존)
  - `/api/graph` → `monitor_server.api.handle_graph(self)`
  - `/api/task-detail` → `monitor_server.api.handle_task_detail(self)`
  - `/api/merge-status` → `monitor_server.api.handle_merge_status(self)`
  - `/api/pane/{id}` → `monitor_server.api.handle_pane_api(self, pane_id)`
  - `/pane/{id}` → `monitor_server.api.handle_pane_html(self, pane_id)`
  - `/static/{name}` → `_serve_static(self, path)` (handlers.py 내부 헬퍼)
  - 나머지 → 404
- **`_serve_static(self, path)`** (`handlers.py` 내부): 기존 `_is_static_path` / `_handle_static` 로직 이전. whitelist `frozenset` 두 집합 병합(vendor JS + CSS/JS). path traversal 이중 방어(prefix+whitelist 체크, Path.resolve() 검사).
- **`ThreadingMonitorServer`** (`monitor-server.py` 잔류): `allow_reuse_address = True`, 서버 config 속성(docs_dir, project_root, plugin_root 등) 주입. `from monitor_server.handlers import Handler`로 Handler 등록.
- **`main(argv)`** (`monitor-server.py` 잔류): `parse_args` → PID 파일 → `ThreadingMonitorServer(("127.0.0.1", port), Handler)` → config 속성 주입 → SIGTERM 핸들러 → `serve_forever`.
- **`test_monitor_module_split.py`**: `ast.parse` 또는 `wc -l` 방식으로 줄 수 검증. `importlib.import_module("monitor_server.handlers")` 성공 여부 검증.

## 데이터 흐름

HTTP 요청 → `Handler.do_GET` path dispatch → 해당 api/renderer 함수 호출(server 속성에서 config 추출) → HTTP 응답 반환. config(docs_dir, project_root, plugin_root, refresh_seconds 등)는 `self.server.<attr>`로 접근.

## 설계 결정 (대안이 있는 경우만)

- **결정**: `do_GET` 분기를 단일 메서드에 inline으로 작성(체인드 if-elif).
- **대안**: URL prefix별 dict 라우터 + 정규식 매칭 테이블.
- **근거**: 기존 `MonitorHandler.do_GET` 패턴을 그대로 이전하여 회귀 위험 최소화. 라우트 수가 8개 미만으로 dict 라우터 오버엔지니어링.

---

- **결정**: `_serve_static`의 whitelist를 vendor JS(`cytoscape.min.js` 등)와 CSS/JS(`style.css`, `app.js`) 두 집합을 단일 `frozenset`으로 병합하고, 서빙 경로는 파일 확장자(`.css`/`.js`)로 분기하여 MIME type 결정.
- **대안**: whitelist를 두 개로 분리하고 경로에 따라 resolver를 분기.
- **근거**: 단일 whitelist가 단순하고, MIME은 확장자로 항상 결정 가능하여 구조 이원화 불필요.

---

- **결정**: `monitor-server.py`에 `ThreadingMonitorServer` 클래스와 `main()`, `pid_file_path`, `cleanup_pid_file`, `_setup_signal_handler`, `parse_args` 함수를 잔류시킨다.
- **대안**: 이 함수들도 `monitor_server/server.py`로 이전하고 `monitor-server.py`를 3줄 shell wrapper로.
- **근거**: TSK-02-03 AC-FR07-c의 목표가 "< 500줄"이며 이 잔류 함수들의 합계가 ~150줄로 안전 마진 내. 추가 이전은 AC에서 요구하지 않으며, `monitor-launcher.py`가 `monitor-server.py`를 직접 subprocess로 호출하므로 entry 인터페이스 변경은 위험.

## 선행 조건

- TSK-02-01 완료: `monitor_server/renderers/` 패키지 존재 + `render_dashboard()` import 가능.
- TSK-02-02 완료: `monitor_server/api.py` 존재 + `handle_state`, `handle_graph`, `handle_task_detail`, `handle_merge_status`, `handle_pane_api`, `handle_pane_html` import 가능.
- TSK-00-01 완료: `monitor_server/__init__.py` + `monitor_server/static/` 존재, `monitor-server.py`에 `sys.path.insert(0, str(Path(__file__).parent))` 추가됨.

## 리스크

- **HIGH**: TSK-02-01/02가 미완료 상태에서 `handlers.py`가 `monitor_server.renderers` / `monitor_server.api`를 import하면 `ImportError`. 선행 Task 완료 상태를 먼저 확인하고, 미완료 시 해당 import를 stub으로 처리하거나 `monitor-server.py`의 기존 함수를 직접 호출하는 fallback 경로를 유지해야 한다.
- **HIGH**: `_serve_static` 이전 시 기존 vendor JS whitelist(`_STATIC_WHITELIST`: cytoscape 등 5개)와 TSK-00-01의 CSS/JS whitelist(`style.css`, `app.js`)를 혼동하면 기존 vendor 서빙이 404로 깨짐. whitelist 병합을 정확히 수행해야 한다.
- **MEDIUM**: `monitor-server.py` 줄 수 축소 후 `test_monitor_server_bootstrap.py` 등 기존 테스트가 `monitor-server.py` 내부 함수(`_handle_api_state`, `_handle_pane_html` 등)를 직접 import하고 있을 경우 `ImportError`. 기존 테스트 파일들의 import 패턴을 Build 단계에서 반드시 확인하고, `handlers.py` 또는 `api.py`의 새 경로로 수정해야 한다.
- **MEDIUM**: `monitor-server.py`의 `ThreadingMonitorServer`가 `MonitorHandler`를 참조하고 있다면 `Handler`로 교체 시 타입 힌트나 주석 불일치 발생. class명은 `Handler`(`handlers.py`)로 통일, `monitor-server.py`에서 `MonitorHandler` 잔류 금지.
- **LOW**: Python `__pycache__` 오염으로 이전 `MonitorHandler` 정의가 캐시에 남아 테스트 환경에서 오동작. `sys.pycache_prefix = "/tmp/codex-pycache"` 설정이 이미 있으므로 대부분 해소.

## QA 체크리스트

- [ ] `scripts/monitor-server.py` 줄 수가 500 미만이다 (`test_monitor_module_split.py::test_monitor_server_entry_under_500_lines` pass).
- [ ] `scripts/monitor_server/handlers.py` 줄 수가 800 이하이다 (`test_monitor_module_split.py::test_handlers_under_800_lines` pass).
- [ ] `from monitor_server.handlers import Handler` import가 성공한다 (`test_monitor_module_split.py::test_import_handlers` pass).
- [ ] `monitor_server/` 하위 어떤 파일도 800줄을 초과하지 않는다 (NF-03, `test_monitor_module_split.py` 또는 별도 검증).
- [ ] `python3 scripts/monitor-server.py --port 9999 --docs docs/monitor-v5` 실행 시 서버가 정상 기동하며 stderr에 `monitor_server.handlers.Handler` 기반 요청 로그가 출력된다 (AC-FR07-b).
- [ ] `GET /` 응답이 200 HTML이고 대시보드가 렌더링된다 (`test_monitor_e2e.py` 회귀 0).
- [ ] `GET /api/state` 응답이 v4 계약과 동일한 JSON 구조를 반환한다.
- [ ] `GET /api/graph`, `/api/task-detail`, `/api/merge-status` 응답이 v4 계약 무변경이다.
- [ ] `GET /pane/{id}`, `GET /api/pane/{id}` 응답이 기존과 동일하다.
- [ ] `GET /static/style.css`, `GET /static/app.js` 응답이 200 + 올바른 MIME + `Cache-Control: public, max-age=300`이다 (`test_monitor_static_assets.py` 회귀 0).
- [ ] `GET /static/cytoscape.min.js` 등 vendor JS 응답이 200 + `application/javascript; charset=utf-8`이다.
- [ ] `GET /static/evil.sh`, `GET /static/../../etc/passwd` 응답이 404이다 (path traversal 방어).
- [ ] `GET /unknown-route` 응답이 404이다.
- [ ] POST/PUT/DELETE/PATCH/HEAD 메서드 요청이 모두 405를 반환한다.
- [ ] `monitor-launcher.py`의 기존 subprocess 호출 인터페이스(`--port`, `--docs`)가 회귀 없이 동작한다 (`test_monitor_launcher.py` 전량 pass).
- [ ] `pytest -q scripts/` 전체 실행 시 기존 테스트가 모두 green이다 (AC-FR07-f, v4 AC-20 regression 0).
