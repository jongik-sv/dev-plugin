# TSK-01-05: pane 캡처 엔드포인트 (/pane/{id}, /api/pane/{id}) - 설계

## 요구사항 확인
- `GET /pane/{pane_id}` → `text/html; charset=utf-8`, `GET /api/pane/{pane_id}` → `application/json` 두 라우트를 `MonitorHandler.do_GET`에 등록(PRD §4.3 / TRD §4.3·§4.4).
- URL path에서 `pane_id`를 분리 후 `^%\d+$` 검증 → 불일치 시 400 응답(HTML은 `<div class="error">...`, JSON은 `{"error":"invalid pane id","code":400}`). subprocess 실패(존재하지 않는 pane 등)는 **200 + "capture failed: {stderr}"** — 대시보드 전체 동작은 유지(PRD §5.3, acceptance 1번).
- HTML 본문은 `<pre class="pane-capture" data-pane="{id}">{escaped lines}</pre><div class="footer">captured at {ts}</div>`, JSON 본문은 `{pane_id, captured_at, lines, line_count, truncated_from}`. pane 상세 영역은 인라인 vanilla JS(의존성 0, setInterval + fetch 2초)로 부분 갱신하며 외부 리소스 로딩은 0건(acceptance 4번).

## 타겟 앱
- **경로**: N/A (단일 앱 플러그인 프로젝트)
- **근거**: 모노레포가 아니며 `scripts/monitor-server.py` 하나가 서버·렌더링·엔드포인트를 모두 담당하는 단일 파일 구조(TRD §8, monitor wbs.md `## Dev Config > Design Guidance > backend`).

## 구현 방향
TSK-01-02의 `MonitorHandler.do_GET()` 라우팅 분기에 두 개의 path 매처를 추가한다: (a) `/pane/` 접두어 + 접두어 제거 후 `^%\d+$` 검증, (b) `/api/pane/` 접두어 + 동일 검증. TSK-01-03의 `capture_pane(pane_id)` 헬퍼를 그대로 재사용하여 ANSI-stripped 본문을 얻고, 이를 (HTML용) f-string 또는 (JSON용) dict로 직렬화한다. `capture_pane`이 던지는 `ValueError`를 400 매핑의 단일 신호로 사용하고(핸들러 내 try/except), subprocess 실패 시 반환되는 stderr 문자열은 `"capture failed:"` 접두어 검출로 구분하여 200 응답에 그대로 싣는다. HTML 응답에는 동일 pane id를 2초마다 `fetch('/api/pane/{id}')`로 재조회해 `<pre>` 텍스트만 교체하는 vanilla JS 블록을 인라인 포함(CSP 등가 — 외부 src 0건). 모든 사용자 유래 문자열(pane_id, lines, stderr)은 **핸들러 내 한 곳에서** `html.escape(..., quote=True)` 처리 후 템플릿에 주입하여 XSS 표면을 최소화한다.

## 파일 계획

**경로 기준:** 모든 파일 경로는 **프로젝트 루트(`dev-plugin/`)** 기준.

| 파일 경로 | 역할 | 신규/수정 |
|-----------|------|-----------|
| `scripts/monitor-server.py` | `MonitorHandler.do_GET`의 라우팅 분기에 `/pane/{id}` 와 `/api/pane/{id}` 두 라우트 추가 — 이 파일이 곧 **router** 파일. 응답 빌더 `_render_pane(pane_id) -> (status, bytes)` 와 `_api_pane(pane_id) -> (status, bytes)` 메서드 신규 구현. 공통 내부 헬퍼 `_pane_capture_payload(pane_id) -> dict` 가 `{pane_id, captured_at, lines, line_count, truncated_from, error?}` 모델을 생성하여 두 렌더러가 공유한다. HTML 응답에 인라인 vanilla JS(`fetch + setInterval`) 블록을 함께 렌더. | 수정 |
| `scripts/monitor-server.py` (nav/menu 뷰 블록 — 같은 파일 내 논리적 서브구역) | **메뉴/네비게이션은 TSK-01-04에서 이미 완결** — `_section_team()`이 생성하는 `<a class="pane-link" href="/pane/{pane_id}">show output</a>` 링크가 본 Task 엔드포인트로 진입하는 메뉴이며, 본 Task는 해당 링크가 가리키는 라우트 핸들러(본문)만 추가한다. TSK-01-04의 href 포맷(`/pane/{html.escape(pane_id, quote=True)}`)과 본 Task의 정규식 검증(`^%\d+$`)이 정확히 호환됨을 주석으로 명시. pane 상세 페이지 자체에는 좌상단 `<a href="/">← back to dashboard</a>` 복귀 링크 1건 추가. | 참조(back 링크만 추가) |
| `scripts/test_monitor_pane.py` | `_render_pane()`·`_api_pane()`·`_pane_capture_payload()` 단위 테스트 — 정상/형식 위반/subprocess 실패/ANSI strip/XSS 페이로드/timeout/HTML에 외부 리소스 0건 케이스. `unittest.mock.patch('subprocess.run')` 으로 tmux를 스텁. 파일명 패턴 `test_monitor*.py` 로 wbs.md Dev Config의 unit-test 명령에 자동 포함. | 신규 |

> 이 플러그인은 단일-파일 HTTP 서버(TRD §8, 목표 300±50 LOC) 구조라 router·endpoint 본문이 모두 `scripts/monitor-server.py` 내부에 있다. dev-design의 "router/menu 파일" 가드는 다중 파일 프레임워크 기준이므로, 이 Task의 **router**는 `do_GET` 내부 if/elif 분기(`/pane/`·`/api/pane/` 접두어 매칭), **menu/navigation**은 TSK-01-04가 이미 배선한 `_section_team`의 pane 링크다(본 Task에서 새로 생성할 진입 menu 없음 — orphan endpoint 방지 규약은 **양방향**으로 이미 충족).

## 진입점 (Entry Points)

- **사용자 진입 경로**: `/dev-monitor` 실행 → 브라우저에서 `http://localhost:7321/` 대시보드 접근(1단계) → 상단 네비의 **Team** 앵커 클릭 또는 스크롤로 `#team` 섹션 이동(2단계) → 각 pane 행 우측 `[show output]` 링크(`/pane/{pane_id}`) 클릭(3단계) → pane 상세 페이지 진입. 상세 페이지는 로드 즉시 `<pre>` 영역에 최근 500라인을 표시하고 2초마다 `/api/pane/{pane_id}`로 fetch 갱신한다. 페이지 좌상단 `← back to dashboard` 링크로 대시보드(`/`)로 복귀.
- **URL / 라우트**: HTML = `GET /pane/{pane_id}`, JSON = `GET /api/pane/{pane_id}`. `pane_id`는 tmux 규약상 `%` + 숫자 형태(예: `%1`, `%12`). 전체 URL: `http://localhost:7321/pane/%1`, `http://localhost:7321/api/pane/%1`.
- **수정할 라우터 파일**: `scripts/monitor-server.py`의 `MonitorHandler.do_GET()` 메서드 — `urllib.parse.urlsplit(self.path).path`로 쿼리 스트링 분리 후 다음 분기를 **TSK-01-04가 추가한 `/` 분기 아래** 순서로 추가한다. (1) `if path.startswith("/api/pane/"):` → `pane_id = unquote(path[len("/api/pane/"):])` → `self._api_pane(pane_id)`. (2) `elif path.startswith("/pane/"):` → `pane_id = unquote(path[len("/pane/"):])` → `self._render_pane(pane_id)`. **순서 필수**: `/api/pane/`를 `/pane/` 앞에 두어야 `/api/pane/%1`이 `/pane/` 분기로 오매칭되지 않는다. 메서드 검사(`if self.command != "GET": return self.send_error(405)`)는 do_GET 상단의 공통 가드로 이미 존재.
- **수정할 메뉴·네비게이션 파일**: **신규 진입 메뉴 추가 없음** — 대시보드 Team 섹션의 `[show output]` 링크는 TSK-01-04의 `_section_team()`이 이미 생성한다. 본 Task는 (a) 해당 링크의 **목적지 라우트 핸들러**를 구현하고, (b) pane 상세 페이지 좌상단에 **복귀 링크** `<nav class="top-nav"><a href="/">← back to dashboard</a></nav>` 1건을 `_render_pane()` 출력에 포함한다. 해당 nav 블록은 `_render_pane` 함수 본문의 HTML f-string 내에 인라인으로 기재된다(같은 파일 내 명시적 sub-region).
- **연결 확인 방법**: E2E(TSK-01-06 수립 예정) — ① `http://localhost:7321/` 로드 → ② Team 섹션에서 실제 존재하는 pane 행의 `[show output]` 클릭(URL 직접 입력 금지) → ③ URL이 `/pane/%N` 으로 변경되고 HTTP 200 + `Content-Type: text/html; charset=utf-8` → ④ 페이지에 `<pre class="pane-capture" data-pane="%N">` 가 렌더됨 → ⑤ DevTools Network 탭에서 2초마다 `GET /api/pane/%N` 호출이 발생하는지 확인 → ⑥ `← back to dashboard` 링크 클릭 시 `/` 로 복귀.

## 주요 구조

### `MonitorHandler.do_GET()` (수정 · router)
- 기존 `/` 분기 아래에 두 분기 추가.
- 매칭 순서: (1) `"/api/state"` — TSK-01-02 예정, (2) `"/api/pane/" prefix` — 본 Task, (3) `"/pane/" prefix` — 본 Task, (4) `"/"` — TSK-01-04, (5) 그 외 404.
- 각 pane 분기: `pane_id = urllib.parse.unquote(path.split("/", maxsplit=N)[-1])`. pane_id에 공백/슬래시/빈 문자열이 포함되면 정규식 `^%\d+$` 가 자동 400 처리.

### `MonitorHandler._pane_capture_payload(pane_id: str) -> dict` (신규 · 공통 모델)
- 시그니처: `def _pane_capture_payload(self, pane_id: str) -> dict`
- 책임:
  1. `_PANE_ID_RE.fullmatch(pane_id)` 검증 (TSK-01-03이 정의한 **동일 모듈 상수** `_PANE_ID_RE = re.compile(r'^%\d+$')`를 재사용) — 실패 시 `raise ValueError("invalid pane id")`.
  2. `capture_pane(pane_id)` 호출(TSK-01-03의 함수). 반환은 문자열. 내부적으로 이미 `^%\d+$` 재검증 + ANSI strip을 수행하지만, **본 Task는 한 번 더 외부에서 검증**하여 핸들러 코드만으로 400 분기가 완결되도록 한다(검증 실패 경로에서 subprocess를 아예 생성하지 않아 fork 비용 절감 + defense in depth).
  3. `captured_at = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00","Z")` — TRD §4.4의 `"2026-04-20T10:30:05Z"` 포맷.
  4. `max_lines = self.server.max_pane_lines`(기본 500, TRD §9.1) — `output.splitlines()` 의 trailing N 라인만 채택. `original_line_count`는 split 결과 전체 길이, `lines`는 마지막 `max_lines`개.
  5. subprocess 실패 감지: `capture_pane` 반환 문자열이 `capture-pane` tmux stderr 포맷(보통 `"can't find pane:"`, `"no server running"`, `"pane not found"` 등)을 포함하거나 returncode가 비정상인 경로(TSK-01-03이 returncode≠0 시 stderr 그대로 반환)로 판정. 판정 기준: TSK-01-03 설계의 주석대로 "성공 경로는 stdout이 ANSI-stripped된 평문, 실패 경로는 stderr 텍스트" — 본 Task는 TSK-01-03에 `capture_pane`이 튜플(`(ok: bool, text: str)`)을 반환하도록 요청하거나, 또는 **TSK-01-03이 이미 반환하는 문자열에 대해 본 Task가 재호출 없이 구분할 수 없으므로**, TSK-01-03의 인터페이스를 그대로 쓰되 returncode 판정을 위해 `capture_pane_raw(pane_id) -> (int, str, str)` 형태의 보조 헬퍼를 TSK-01-03 참조영역에 **추가하지 않고**, 본 Task 핸들러가 직접 `subprocess.run` 호출하는 대신 TSK-01-03의 `capture_pane`을 유지하고 **에러 마커 접두 검출**(`text.startswith("capture failed:")` 은 TSK-01-03 현행 설계에 없음 — 아래 "설계 결정" 섹션 참조). 최종 정책은 아래 "설계 결정 — capture_pane 반환 규약 보강"을 따른다.
  6. 반환 dict: `{"pane_id": pane_id, "captured_at": captured_at, "lines": lines, "line_count": len(lines), "truncated_from": original_line_count, "error": <str|None>}`. 실패 시 `error`에 stderr 원문, `lines`는 `["capture failed: {stderr}"]` 1줄. **응답 코드는 200 유지**(acceptance 1번).

### `MonitorHandler._render_pane(pane_id: str)` (신규 · HTML 응답)
- 시그니처: `def _render_pane(self, pane_id: str) -> None` (응답을 self.wfile에 직접 기록)
- 책임:
  1. `try: payload = self._pane_capture_payload(pane_id)` — `ValueError` → `self._send_error_html(400, "invalid pane id")` 후 즉시 리턴.
  2. `escaped_id = html.escape(pane_id, quote=True)` / `escaped_lines = "\n".join(html.escape(ln, quote=False) for ln in payload["lines"])` / `escaped_ts = html.escape(payload["captured_at"])` / `escaped_err = html.escape(payload["error"]) if payload["error"] else None`.
  3. HTML 본문 f-string:
     ```
     <!doctype html><html lang="en"><head><meta charset="utf-8">
     <title>pane {escaped_id}</title>
     <style>{PANE_CSS}</style></head><body>
     <nav class="top-nav"><a href="/">← back to dashboard</a></nav>
     <h1>pane <code>{escaped_id}</code></h1>
     {optional <div class="error">capture failed: {escaped_err}</div>}
     <pre class="pane-capture" data-pane="{escaped_id}">{escaped_lines}</pre>
     <div class="footer">captured at {escaped_ts}</div>
     <script>{PANE_JS}</script>
     </body></html>
     ```
  4. `PANE_JS`(모듈 상수)는 `pane_id`를 `pre.pane-capture` DOM의 `data-pane` 속성에서 읽어 2초마다 `fetch('/api/pane/' + encodeURIComponent(paneId))` → `<pre>`의 `textContent`만 교체하고 footer의 timestamp도 갱신. 외부 `<script src="...">` 없음, fetch 실패 시 현재 루프는 silent 유지(다음 tick에서 회복).
  5. 응답 헤더: `Content-Type: text/html; charset=utf-8`, `Cache-Control: no-store`. 본문은 `.encode("utf-8")`. 응답 코드는 200 (error 필드 존재 여부와 무관).

### `MonitorHandler._api_pane(pane_id: str)` (신규 · JSON 응답)
- 시그니처: `def _api_pane(self, pane_id: str) -> None`
- 책임:
  1. `try: payload = self._pane_capture_payload(pane_id)` — `ValueError` → `self._send_error_json(400, "invalid pane id")`.
  2. JSON 직렬화: `json.dumps(payload, ensure_ascii=False).encode("utf-8")`. `payload["error"]`가 `None`이면 그대로, 있으면 그대로 유지(클라이언트가 구분할 수 있게).
  3. 응답 헤더: `Content-Type: application/json; charset=utf-8`, `Cache-Control: no-store`. **`line_count` 필드는 모든 정상/실패 경로에서 반드시 존재**(acceptance 3번).

### `MonitorHandler._send_error_html(code, msg)` / `_send_error_json(code, msg)` (TSK-01-02에서 제공, 없으면 본 Task 최소 구현)
- HTML: `<!doctype html><html><body><div class="error">{html.escape(msg)}</div></body></html>` + `Content-Type: text/html; charset=utf-8`.
- JSON: `json.dumps({"error": msg, "code": code}, ensure_ascii=False)` + `Content-Type: application/json; charset=utf-8`.
- 두 헬퍼 모두 `self.send_response(code)` → `self.send_header(...)` → `self.end_headers()` → `self.wfile.write(body)` 순서.

### `PANE_CSS` / `PANE_JS` (신규 · 모듈 상수)
- `PANE_CSS` (~30줄 이내): monospace 폰트, 다크 배경, `<pre>`의 `white-space:pre-wrap; word-break:break-all; max-height:75vh; overflow:auto`, `.error` 박스, `.footer` 회색 작은 글씨, `nav.top-nav a` 링크 스타일. `DASHBOARD_CSS`(TSK-01-04)와 이름 분리하여 섞이지 않게 한다.
- `PANE_JS` 개념도(실제 코드는 dev-build가 작성):
  ```
  (function(){
    var pre = document.querySelector('pre.pane-capture');
    var ftr = document.querySelector('.footer');
    if (!pre) return;
    var paneId = pre.getAttribute('data-pane');
    function tick(){
      fetch('/api/pane/' + encodeURIComponent(paneId), {cache:'no-store'})
        .then(function(r){ return r.ok ? r.json() : null; })
        .then(function(j){
          if (!j) return;
          pre.textContent = (j.lines || []).join('\n');
          if (ftr) ftr.textContent = 'captured at ' + j.captured_at;
        })
        .catch(function(){ /* keep silent, loop continues */ });
    }
    setInterval(tick, 2000);
  })();
  ```
  - 외부 리소스 로딩 0건, `innerHTML` 미사용(`textContent`만 사용하여 XSS 추가 표면 차단).

## 데이터 흐름
HTTP GET `/pane/{id}` (또는 `/api/pane/{id}`) → `MonitorHandler.do_GET()` 라우팅 → `urlsplit` + prefix 분리 + `unquote` → `_pane_capture_payload(pane_id)` → `^%\d+$` 검증(실패 시 400 즉시 종료) → `capture_pane(pane_id)` (TSK-01-03) → stdout/stderr 분기 → dict 페이로드 → `_render_pane` 또는 `_api_pane` → UTF-8 bytes → 브라우저 렌더. HTML 경로의 경우 브라우저가 2초마다 `/api/pane/{id}`를 fetch하여 `<pre>` 텍스트만 교체 (페이지 전체 리로드 없음).

## 설계 결정 (대안이 있는 경우만)

- **결정**: subprocess 실패(`returncode != 0`, 존재하지 않는 pane 등)를 **200 + error 문자열**로 반환(JSON은 `error` 필드 동반, HTML은 `<div class="error">`).
- **대안**: 5xx 또는 404 반환.
- **근거**: TSK acceptance 1번 "`%99` (존재하지 않는 pane) → 200 with capture failed 메시지" 를 직접 충족. 대시보드의 부분 fetch가 pane 종료를 감지해도 2초 loop가 중단되지 않도록 하는 UX 요구와도 일치(PRD §5.3 "pane 캡처 실패 — 대시보드는 계속 동작").

- **결정**: 라우트 매칭 순서를 `/api/pane/` → `/pane/` 순으로 강제.
- **대안**: 단일 정규식 `re.match(r'^(/api)?/pane/(%\d+)$', path)` 로 통합 매칭.
- **근거**: prefix 매칭 + startswith 방식이 문자열 연산만 사용하므로 re 컴파일 비용 없이 동일한 명확성을 제공. `/api/pane/`를 먼저 검사해 `/pane/api/` 같은 인위적 오입력이 `/pane/` 분기로 빠지지 않도록 보장.

- **결정**: HTML 응답의 부분 갱신을 **vanilla JS `setInterval + fetch`**로 구현(인라인 `<script>`).
- **대안**: `<meta http-equiv="refresh" content="2">` 로 전체 페이지 리로드.
- **근거**: 대시보드(`/`)는 `meta refresh 3s`, pane 상세는 `2s fetch`로 분리된 TSK 명세. meta refresh를 그대로 쓰면 URL·스크롤·선택 텍스트가 매 2초 리셋되어 "로그를 읽는" UX를 해친다. 의존성 0 vanilla JS 제약(TSK constraints) 때문에 `fetch`/`setInterval`/`encodeURIComponent`(전부 브라우저 내장)만 사용.

- **결정**: pane_id 정규식 검증을 핸들러 레벨에서 **한 번 더** 수행(`capture_pane`이 내부에서 이미 검증함에도).
- **대안**: `capture_pane`의 `ValueError`에만 의존.
- **근거**: (1) 검증 실패 경로에서 subprocess를 **아예 생성하지 않아** fork 비용 절감, (2) 정규식 위반 시 "왜 400인지" 단일 진입점 단일 책임으로 코드 리뷰에서 읽기 쉬움, (3) TSK-01-03 인터페이스 변경 시에도 엔드포인트 레벨 보장이 깨지지 않음(defense in depth).

- **결정**: `capture_pane` 반환 규약 — TSK-01-03 설계가 성공 시 ANSI-stripped stdout 문자열, subprocess 실패 시 stderr 원문 문자열을 반환하는 **단일 문자열 시그니처**로 확정했으므로, 본 Task는 반환값에서 성공/실패를 구분하기 위해 **TSK-01-03에 변경을 요청하지 않고** 다음과 같이 처리한다: `capture_pane`을 호출한 뒤 **returncode를 다시 얻을 방법이 없으므로**, `_pane_capture_payload`는 TSK-01-03이 반환한 문자열을 그대로 `lines`에 싣고 `error`는 None으로 둔다. 즉, HTTP 관점에서는 **tmux의 stderr 본문도 성공 케이스처럼 렌더**되며, "capture failed" 문자열 포함 여부는 브라우저/JSON 소비자가 휴리스틱으로 판정하거나, pane 존재 여부를 대시보드에서 선제 검증한다.
- **대안**: TSK-01-03의 `capture_pane` 시그니처를 `(ok: bool, text: str)` 튜플로 변경.
- **근거**: (1) TSK-01-03은 이미 설계 완료(`status: dd`)되어 본 Task에서 **시그니처 재설계를 강제하면 충돌**한다("기존 설계와 모순되는 재설계 금지"). (2) acceptance 1번("존재하지 않는 pane → 200 with capture failed 메시지")은 stderr 원문이 `lines`에 그대로 포함되기만 하면 만족 — 사용자는 pre 블록에서 `"can't find pane: %99"` 를 읽는다. (3) 대안 추구 시 TSK-01-03의 통합 테스트가 깨지므로 **본 Task 단독 범위를 벗어남**. 실패 구분이 꼭 필요하다면 후속 리팩터 Task에서 TSK-01-03/05를 함께 수정.

## 선행 조건
- **TSK-01-02**: `MonitorHandler` 클래스 스켈레톤 + `do_GET` 라우팅 훅 + 공통 에러 응답 헬퍼(`_send_error_html`/`_send_error_json` 또는 유사). `self.server.max_pane_lines` 속성(argparse `--max-pane-lines` 주입, 기본 500) 존재.
- **TSK-01-03**: `capture_pane(pane_id) -> str` 헬퍼 — `^%\d+$` 검증 시 `ValueError`, subprocess 실패 시 stderr 문자열 반환, 성공 시 ANSI-stripped stdout 문자열 반환. 모듈 상수 `_PANE_ID_RE = re.compile(r'^%\d+$')`를 **본 Task 핸들러가 그대로 import/재사용**. **본 Task의 시그니처·리턴 규약은 TSK-01-03 설계와 1:1 일치**.
- **TSK-01-04**: `_section_team()`이 `<a class="pane-link" href="/pane/{pane_id}">show output</a>` 링크를 렌더. 본 Task는 이 링크의 목적지를 제공(양방향 orphan 방지). `DASHBOARD_CSS` 상수와 본 Task의 `PANE_CSS`는 이름 분리.
- Python 3.8+ stdlib만 사용(`urllib.parse.urlsplit/unquote`, `re`, `html`, `json`, `datetime`). 외부 패키지 0.

## 리스크

- **HIGH — `capture_pane` 반환 구분 불가**: TSK-01-03이 성공/실패를 단일 문자열로 반환하므로 본 Task에서 `error` 필드를 채울 명확한 신호가 없다(위 "설계 결정 — capture_pane 반환 규약"). 완화: `_pane_capture_payload`는 `error=None`을 기본값으로 두고, acceptance가 요구하는 "capture failed 메시지"는 tmux stderr 원문이 `lines`에 포함됨으로써 간접 충족. 테스트에서 mock으로 `capture_pane` 반환값을 `"can't find pane: %99"` 로 주입 시 최종 HTML/JSON에 해당 문자열이 포함되는지만 검증(필드 구조가 아니라 가시성 기반). 추후 필요 시 TSK-01-03/05를 함께 수정하는 리팩터 Task 발생 가능.

- **MEDIUM — URL 디코딩 경계**: 브라우저는 `%1`의 `%`를 자동 인코딩하지 않지만, 서드파티 클라이언트(curl `--data-urlencode` 등)가 `%251`로 더블 인코딩한 요청을 보낼 수 있다. `urllib.parse.unquote("%251")` → `"%1"`로 정규화되어 정상 동작. `unquote("abc")` → `"abc"` → 정규식 실패 → 400 — 의도된 동작. 완화: 테스트에 `/pane/%251` 케이스 포함.

- **MEDIUM — XSS 탈출**: pane 캡처 본문은 사용자 쉘 출력이며, 공격자가 `<script>alert(1)</script>` 문자열을 echo하면 pane_id 또는 stdout에 그대로 포함될 수 있다. 완화: `html.escape(s, quote=True)` 를 `<pre>` 내용·`data-pane` 속성·`<div class="error">`·`<title>`·`<h1><code>` 다섯 곳 모두에 강제. JS는 `textContent`만 사용. 단위 테스트에 `"A</pre><script>alert(1)</script>B"` 페이로드 케이스 포함.

- **MEDIUM — subprocess timeout 누적**: 2초 fetch 간격 < `capture_pane` timeout 3초. 브라우저가 연속 fetch를 보내고 서버가 모두 timeout에 걸리면 큐가 누적. 완화: `ThreadingHTTPServer`(TSK-01-02 전제)로 요청 병렬 처리, `Cache-Control: no-store` 명시. 추가 완화는 TSK-01-06 E2E에서 부하 확인 후 별도 이슈로.

- **LOW — tmux 미설치 환경**: `list_tmux_panes()` 가 `None`이면 대시보드 Team 섹션에 pane 링크 자체가 렌더되지 않으므로 본 엔드포인트에 정상 유입이 없다. URL 직접 호출 시 TSK-01-03의 `capture_pane` 내부가 `shutil.which` 분기 또는 `FileNotFoundError`를 스텁 처리하지 않으면 500이 발생할 수 있음 — TSK-01-03 설계 재확인 결과 `shutil.which` 분기는 `list_tmux_panes()`에만 있고 `capture_pane`에는 없다. 완화: 본 Task 핸들러가 `FileNotFoundError`를 캐치하여 `error="tmux not available"` 페이로드로 반환(200). 이는 본 Task의 방어 계층이며 TSK-01-03 변경 없음.

- **LOW — `/api/state` 라우트와의 prefix 충돌**: TSK-01-02 예정인 `/api/state` 와 본 Task의 `/api/pane/` 는 prefix가 겹치지 않지만, 향후 `/api/...` 하위가 늘면 dispatch 테이블 명시화 필요. 완화: `do_GET` 상단에 주석으로 "라우트 매칭 순서: longest prefix first" 원칙을 박제.

## QA 체크리스트
dev-test 단계에서 검증할 항목. 각 항목은 pass/fail로 판정 가능해야 한다.

- [ ] (정상) `_pane_capture_payload("%1")` 호출 시(mock: `capture_pane` → `"line1\nline2"`) 반환 dict에 `pane_id=="%1"`, `lines==["line1","line2"]`, `line_count==2`, `truncated_from==2`, `captured_at`이 ISO-8601 + `Z` 접미어로 끝난다.
- [ ] (정상) `_render_pane("%1")`가 반환한 HTML 문자열에 `<pre class="pane-capture" data-pane="%1">line1\nline2</pre>`, `<div class="footer">captured at ...</div>`, `<script>` 블록이 정확히 각 1회 등장하고, 좌상단 `<a href="/">← back to dashboard</a>` 링크가 포함된다. `Content-Type` 헤더가 `text/html; charset=utf-8`.
- [ ] (정상) `_api_pane("%1")`가 반환한 JSON에 `pane_id`, `captured_at`, `lines`, `line_count`, `truncated_from` 5개 필드가 모두 존재하고, `Content-Type` 헤더가 `application/json; charset=utf-8` 이다 (acceptance 3번).
- [ ] (에러) `curl http://localhost:7321/pane/abc` (정규식 위반) → HTTP 400 + HTML 본문에 `<div class="error">invalid pane id</div>` 포함 (acceptance 2번).
- [ ] (에러) `curl http://localhost:7321/api/pane/abc` → HTTP 400 + JSON `{"error":"invalid pane id","code":400}`.
- [ ] (에러) `curl http://localhost:7321/pane/%99` (존재하지 않는 pane, mock: `capture_pane` → `"can't find pane: %99"`) → HTTP **200** + HTML에 `can't find pane: %99` 문자열 포함, `<pre>`는 존재하지만 내용이 해당 에러 메시지 (acceptance 1번).
- [ ] (에러) `/api/pane/%99` 동일 케이스 → HTTP 200 + JSON의 `lines` 필드에 stderr 원문이 포함되고 `line_count` 필드가 존재(값은 1).
- [ ] (엣지) ANSI escape sequence가 포함된 pane 출력(`"A\x1b[31mB\x1b[0mC"`) 이 들어왔을 때(mock: TSK-01-03의 `capture_pane`이 이미 strip) `lines`에는 `["ABC"]`만 담기고 `<pre>` 본문에도 `\x1b` 리터럴이 없다.
- [ ] (엣지) `max_pane_lines=500`, `capture_pane` 반환이 700줄일 때 `lines` 길이 = 500, `truncated_from` = 700. `max_pane_lines=500`, 반환이 10줄일 때 `lines` 길이 = 10, `truncated_from` = 10.
- [ ] (보안) XSS 페이로드가 pane 출력으로 들어와도(`capture_pane` → `"</pre><script>alert(1)</script>"`) 응답 HTML에 `<script>alert(1)</script>` 리터럴이 **존재하지 않고** 모두 `&lt;script&gt;alert(1)&lt;/script&gt;` 로 이스케이프된다.
- [ ] (보안) HTML 응답 전체에 외부 URL 리소스 로딩이 0건 — 정규식 `re.findall(r'<(?:script|link|img|iframe)[^>]*\s(?:src|href)=["\']?https?://', html)` 결과가 `[]` (acceptance 4번).
- [ ] (보안) `_render_pane`/`_api_pane`/`_pane_capture_payload` 함수 본문에 `subprocess.` 문자열이 0건 — 모든 subprocess 호출은 TSK-01-03 `capture_pane` 내부로만 위임.
- [ ] (보안) `FileNotFoundError`(tmux 바이너리 부재) 케이스에서 500이 아닌 200 + `error="tmux not available"` 페이로드가 반환된다(mock: `subprocess.run` → `FileNotFoundError`).
- [ ] (통합) 라우트 매칭 순서 — `do_GET` 스텁 호출 시 `/api/pane/%1` 이 `_api_pane`로, `/pane/%1` 이 `_render_pane`로, `/pane/` (trailing 빈문자열) 은 `ValueError` 경로로 400을 반환한다(mock으로 핸들러 본문만 격리 테스트).
- [ ] (통합) `/api/pane/%251` (더블 인코딩)을 요청하면 내부적으로 `unquote` 후 `%1`로 정규화되어 200을 반환한다.
- [ ] (통합) HTTP 라이브 테스트 — 실제 서버 기동 후 `urllib.request.urlopen('http://127.0.0.1:7321/pane/%1')` → 200, `Content-Type` 헤더가 `text/html; charset=utf-8`, 본문을 UTF-8 디코드하여 `"<pre class=\"pane-capture\""` 부분 문자열 존재 검증.

**fullstack/frontend Task 필수 항목 (E2E 테스트에서 검증 — dev-test reachability gate):**
- [ ] (클릭 경로) 메뉴/사이드바/버튼을 클릭하여 목표 페이지에 도달한다 (URL 직접 입력 금지) — `http://localhost:7321/` 대시보드 로드 → Team 섹션의 첫 pane 행 `[show output]` 링크 클릭으로 `/pane/%N` 페이지에 도달.
- [ ] (화면 렌더링) 핵심 UI 요소가 브라우저에서 실제 표시되고 기본 상호작용이 동작한다 — `<pre class="pane-capture">` DOM 존재 + 최소 1줄 텍스트 + 2초 후 Network 탭에 `GET /api/pane/%N` 요청 기록 + `← back to dashboard` 클릭 시 `/` 로 복귀.
