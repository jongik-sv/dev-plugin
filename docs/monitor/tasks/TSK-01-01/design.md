# TSK-01-01: HTTP 서버 뼈대 및 argparse 진입점 - 설계

## 요구사항 확인

- `scripts/monitor-server.py`에 argparse 기반 CLI 진입점과 `ThreadingHTTPServer` + `MonitorHandler` 서브클래스를 추가하여 `127.0.0.1:{port}`에서 HTTP 서버를 기동한다.
- `GET /`, `GET /api/state`, `GET /pane/{id}`, `GET /api/pane/{id}` 4개 엔드포인트 라우팅 스켈레톤을 제공하며, 이 Task에서는 501 stub 또는 기존 함수 연결 모두 허용한다.
- `GET` 외 메서드는 `405 Method Not Allowed`로 응답하고, `log_message`를 재정의해 stderr에 요청 라인 1건만 출력한다.

## 타겟 앱

- **경로**: N/A (단일 앱)
- **근거**: 플러그인 루트의 `scripts/` 디렉터리에 단일 파일로 배치되는 프로젝트이다.

## 구현 방향

- 기존 `scripts/monitor-server.py` 파일 하단의 `if __name__ == "__main__":` 블록(현재 skeleton placeholder)을 실제 argparse + ThreadingHTTPServer 기동 코드로 교체한다.
- `MonitorHandler(BaseHTTPRequestHandler)` 클래스를 파일에 추가하고, `do_GET()` 라우팅과 비-GET 메서드(`do_POST` 등)의 405 응답을 구현한다.
- `ThreadingHTTPServer`를 `("127.0.0.1", port)` 에 바인딩하고, `SIGTERM`/`KeyboardInterrupt`에서 정상 종료한다.
- `log_message`를 재정의하여 stdout은 비우고 stderr에만 요청 라인을 출력한다.
- 이미 파일에 존재하는 `render_dashboard()`, `_handle_api_state()`, `capture_pane()`, `list_tmux_panes()`, `scan_tasks()`, `scan_features()`, `scan_signals()` 함수들을 핸들러에서 호출한다.

## 파일 계획

| 파일 경로 | 역할 | 신규/수정 |
|-----------|------|-----------|
| `scripts/monitor-server.py` | argparse 진입점 + `MonitorHandler` 클래스 + `ThreadingHTTPServer` 기동 코드 추가 | 수정 |

## 진입점 (Entry Points)

N/A (backend domain — UI 진입점 없음)

## 주요 구조

- **`MonitorHandler(BaseHTTPRequestHandler)`**: HTTP 요청을 처리하는 핸들러 클래스.
  - `do_GET()`: URL 경로를 파싱하여 4개 엔드포인트로 분기. 미매칭 경로는 404 응답.
  - `do_POST()` / `do_PUT()` / `do_DELETE()` / `do_PATCH()` / `do_HEAD()`: 405 Method Not Allowed 응답.
  - `log_message(format, *args)`: `sys.stderr.write(f"{self.requestline}\n")` — stdout 비움.
  - `_route_root()`: `render_dashboard(model)` 호출 후 HTML 응답 (model 조립 포함).
  - `_route_api_state()`: `_handle_api_state(self)` 위임.
  - `_route_pane(pane_id)`: `capture_pane(pane_id)` 호출 후 HTML `<pre>` 응답.
  - `_route_api_pane(pane_id)`: `capture_pane(pane_id)` 호출 후 JSON 응답.
- **`build_arg_parser()`**: `argparse.ArgumentParser`를 생성하고 모든 CLI 인자를 등록하는 팩토리 함수.
- **`main(argv=None)`**: argparse 파싱 → `ThreadingHTTPServer` 생성 → `serve_forever()` 루프. `server.project_root`, `server.docs_dir`, `server.max_pane_lines`, `server.refresh_seconds`, `server.no_tmux` 속성을 핸들러가 읽을 수 있도록 서버 인스턴스에 주입.
- **`_html_response(handler, status, body_str)`**: UTF-8 인코딩 후 `Content-Type: text/html; charset=utf-8` + `Content-Length` 헤더를 설정하는 헬퍼.

## 데이터 흐름

```
CLI argv → argparse → main() → ThreadingHTTPServer(("127.0.0.1", port))
→ MonitorHandler.do_GET() → 경로 파싱 → 각 _route_*() 호출
→ 기존 scan_*/render_*/capture_pane 함수 → HTML/JSON 응답
```

## 설계 결정 (대안이 있는 경우만)

- **결정**: `MonitorHandler`에서 `do_POST`, `do_PUT` 등을 개별 메서드로 정의해 405 응답
- **대안**: `do_GET` 외부에서 메서드를 체크하는 방어 코드 삽입
- **근거**: `BaseHTTPRequestHandler`는 메서드별 `do_XXX`를 호출하므로 개별 메서드 정의가 더 명시적이고 표준적이다.

- **결정**: `main(argv=None)` 함수로 진입점을 분리하고 `if __name__ == "__main__": main()` 패턴 사용
- **대안**: 모든 코드를 `if __name__ == "__main__":` 블록 안에 인라인 작성
- **근거**: `main(argv)` 시그니처로 단위 테스트에서 인자를 직접 주입할 수 있어 테스트 용이성이 높다.

- **결정**: 핸들러가 `self.server.project_root`, `self.server.docs_dir` 등 속성으로 설정값을 읽음
- **대안**: 전역 변수로 서버 설정 공유
- **근거**: `ThreadingHTTPServer`가 각 요청마다 핸들러 인스턴스를 생성하므로 `server` 속성을 통한 공유가 스레드-안전하고 테스트에서 mock이 용이하다.

## 선행 조건

- `scripts/monitor-server.py`에 이미 구현된 `render_dashboard()`, `_handle_api_state()`, `capture_pane()`, `_json_response()`, `_json_error()`, `scan_tasks()`, `scan_features()`, `scan_signals()`, `list_tmux_panes()` 함수들이 존재해야 한다 (현재 파일에 이미 구현되어 있음 — TSK-01-02/03/04/06 산출물).
- Python 3.8+ 환경.

## 리스크

- **MEDIUM**: pane_id URL 파싱 시 `%`가 URL 인코딩 문자로 혼동될 수 있다. `urllib.parse.urlsplit().path`로 경로를 추출한 뒤, path segment를 그대로 `capture_pane()`에 전달하면 된다. `capture_pane()`이 내부에서 `^%\d+$` 정규식으로 검증하므로 추가 검증은 불필요하다.
- **LOW**: `ThreadingHTTPServer`의 기본 `allow_reuse_address`는 False이다. 포트 충돌 시 `OSError: [Errno 48] Address already in use`가 발생하므로 서버 생성 후 `server.allow_reuse_address = True`를 설정하거나 subclass에서 클래스 속성으로 정의해 테스트 재실행 시 포트 점유 문제를 방지해야 한다.
- **LOW**: 기존 파일 하단에 `if __name__ == "__main__":` skeleton placeholder가 있으므로, 이 블록 전체를 새 `main()` 함수 정의 + `if __name__ == "__main__": main()` 호출로 교체해야 한다. 파일 중간 삽입 시 기존 함수와 충돌하지 않도록 순서 확인이 필요하다.

## QA 체크리스트

dev-test 단계에서 검증할 항목. 각 항목은 pass/fail로 판정 가능해야 한다.

- [ ] `python3 scripts/monitor-server.py --port 7321 &` 로 서버 기동 후 `curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:7321/` 가 200 또는 501을 반환한다.
- [ ] 기동 중인 서버에 `curl -s -o /dev/null -w "%{http_code}" -X POST http://127.0.0.1:7321/` 가 405를 반환한다.
- [ ] `python3 scripts/monitor-server.py --no-tmux --port 7322 &` 로 기동 시 인자 파싱 에러 없이 서버가 시작된다.
- [ ] `python3 scripts/monitor-server.py --help` 출력에 `--port`, `--docs`, `--project-root`, `--max-pane-lines`, `--refresh-seconds`, `--no-tmux` 인자가 모두 포함된다.
- [ ] `main(["--port", "7323"])` 을 테스트에서 호출 시 `ThreadingHTTPServer`가 `127.0.0.1:7323` 에 바인딩되어 응답한다 (기동 후 즉시 shutdown 포함).
- [ ] 서버 기동 중 `GET /api/state` 요청 시 `Content-Type: application/json` 헤더와 함께 JSON 응답이 반환된다.
- [ ] 서버 기동 중 `GET /pane/%1` 요청 시 tmux 미설치 환경에서도 400 또는 HTML 에러 메시지가 반환되고 서버가 크래시하지 않는다.
- [ ] 서버 기동 중 `GET /nonexistent` 요청 시 404 응답이 반환된다.
- [ ] 서버 요청 처리 중 stderr에 요청 라인이 출력되고 stdout에는 아무것도 출력되지 않는다.
- [ ] `0.0.0.0`으로 바인딩되지 않음 — `ss -tlnp | grep 7321` 또는 `lsof -i :7321` 결과에서 `127.0.0.1:7321`만 표시된다.
