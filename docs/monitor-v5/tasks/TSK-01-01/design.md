# TSK-01-01: `monitor_server` 패키지 스캐폴드 + `/static/*` 화이트리스트 라우트 - 설계

## 요구사항 확인
- `scripts/monitor_server/` Python 패키지를 생성하고 `handlers.py` 스켈레톤에 `/static/<path>` 화이트리스트 라우트를 구현한다. 화이트리스트는 `{"style.css", "app.js"}`, MIME + Cache-Control 헤더 부여, path traversal 차단.
- `scripts/monitor-server.py` 상단에 `sys.path.insert(0, str(Path(__file__).parent))` 1줄을 추가하고 하이픈/언더스코어 매핑 주석을 단다 (TRD R-H). 로직 이전 없음 — 기존 `do_GET` 동작 완전 보존.
- `scripts/test_monitor_static_assets.py` 신규 작성: 새 패키지 핸들러의 MIME, Cache-Control, 404, path traversal 차단을 pytest로 검증.

## 타겟 앱
- **경로**: N/A (단일 앱 — `scripts/` 단일 Python 프로젝트)
- **근거**: `scripts/` 하위 Python stdlib 서버로 모노레포 구조 없음.

## 구현 방향
- `scripts/monitor_server/__init__.py`: 빈 패키지 + `__version__ = "5.0.0"` 버전 문자열만 포함.
- `scripts/monitor_server/handlers.py`: `BaseHTTPRequestHandler` 서브클래스 `Handler` 정의. `/` 라우트는 기존 `monitor-server.py`의 `MonitorHandler.do_GET` 을 직접 위임(`super()` 또는 참조 없이 placehoolder `pass` 수준 — S6에서 완성). `/static/<path>` 라우트는 TRD §5.2 구현 블록 그대로 적용.
- `scripts/monitor_server/static/`: 빈 디렉토리. `style.css`, `app.js` 파일은 S2/S3 단계에서 채워짐. S1 단계에선 빈 파일 2개를 플레이스홀더로 생성해 테스트가 200을 받을 수 있도록 한다.
- `scripts/monitor-server.py` 상단(imports 바로 앞): `sys.path.insert(0, str(Path(__file__).parent))` + TRD R-H 주석 추가. 기존 로직 1줄도 건드리지 않음.
- 기존 `_STATIC_WHITELIST` (vendor JS) 와 신규 `_STATIC_WHITELIST` (style.css/app.js) 는 **별개의 상수**다 — 기존 것은 `monitor-server.py` 전역에 그대로 유지, 신규 것은 `handlers.py` 모듈 레벨에 정의.

## 파일 계획

**경로 기준:** 모든 파일 경로는 **프로젝트 루트 기준**으로 작성한다.

| 파일 경로 | 역할 | 신규/수정 |
|-----------|------|-----------|
| `scripts/monitor_server/__init__.py` | 빈 패키지 초기화 + `__version__ = "5.0.0"` | 신규 |
| `scripts/monitor_server/handlers.py` | `BaseHTTPRequestHandler` 서브클래스 `Handler`. `/` 스켈레톤 + `/static/<path>` 화이트리스트 라우트 구현 | 신규 |
| `scripts/monitor_server/static/style.css` | 빈 플레이스홀더 (S2에서 내용 채움) | 신규 |
| `scripts/monitor_server/static/app.js` | 빈 플레이스홀더 (S3에서 내용 채움) | 신규 |
| `scripts/monitor-server.py` | 상단에 `sys.path.insert` 1줄 + R-H 주석 추가. 기존 로직 무변경 | 수정 |
| `scripts/test_monitor_static_assets.py` | 신규 pytest 모듈 — MIME/Cache-Control/404/traversal 5개 테스트 | 신규 |

## 진입점 (Entry Points)
N/A — domain=backend, UI 없음.

## 주요 구조

- **`monitor_server.handlers.Handler`** (`BaseHTTPRequestHandler` 서브클래스): `do_GET` 라우터. `/static/<path>` 분기를 `_serve_static(self, path)` 메서드로 위임. `/` 및 기타 경로는 S1 단계에선 빈 404 fallback (S6에서 기존 `MonitorHandler` 로직 이전).
- **`_STATIC_ROOT`** (모듈 상수, `Path(__file__).parent / "static"`): `handlers.py` 기준 정적 파일 루트 경로.
- **`_STATIC_WHITELIST`** (모듈 상수, `{"style.css", "app.js"}`): 허용 파일명 집합. whitelist-only 전략으로 path traversal 원천 차단.
- **`_MIME`** (모듈 상수, `{"css": "text/css; charset=utf-8", "js": "application/javascript; charset=utf-8"}`): 확장자 → Content-Type 매핑.
- **`Handler._serve_static(self, path: str) -> None`**: TRD §5.2 구현 블록 그대로. `name not in _STATIC_WHITELIST` → 404, 파일 없음 → 404, 성공 → 200 + MIME + Cache-Control + body.

## 데이터 흐름
```
HTTP GET /static/<name>
  → Handler.do_GET → _serve_static(path)
  → name = path[len("/static/"):]
  → name not in _STATIC_WHITELIST → send_error(404)
  → asset = _STATIC_ROOT / name
  → asset.is_file() 확인 → send_error(404) if not
  → body = asset.read_bytes()
  → send_response(200) + Content-Type + Content-Length + Cache-Control + body
```

## 설계 결정 (대안이 있는 경우만)

- **결정**: `_serve_static` 을 `Handler` 의 인스턴스 메서드로 정의 (`self` 수신).
- **대안**: TRD §5.2처럼 `handler: BaseHTTPRequestHandler` 파라미터를 받는 모듈 수준 함수.
- **근거**: S1은 스켈레톤 단계 — S6에서 `MonitorHandler.do_GET` 이 `Handler` 로 완전 이전될 때 메서드 형태가 더 자연스럽다. TRD §5.2 코드 블록도 `self`를 사용하는 메서드 형태가 의도임.

- **결정**: S1 단계에서 `static/style.css`, `static/app.js` 를 빈 파일로 생성.
- **대안**: 파일 없이 `is_file()` → 404 경로로만 테스트.
- **근거**: WBS test-criteria `test_css_served_with_mime` 가 200 응답을 요구하므로 빈 파일이라도 반드시 존재해야 한다. TRD S2 전에 파일 내용이 비어있어도 무관.

## 선행 조건
- TSK-00-01 완료 (현재 `scripts/monitor-server.py` 6937줄 상태, 기존 테스트 전량 green 확인 후 시작).
- `scripts/` 디렉토리에 쓰기 권한.

## 리스크

- **HIGH**: `sys.path.insert` 추가 위치가 잘못되면 기존 import 순서가 바뀌어 현재 6937줄 전체가 임포트 실패할 수 있다. `import sys` 및 `from pathlib import Path` 라인 **이후**, 다른 로컬 패키지 import **이전** 에 삽입해야 한다. `monitor-server.py` 의 기존 import 블록은 L35~L44 표준 라이브러리만 사용하므로 L44 직후가 안전한 삽입 위치다.
- **HIGH**: 기존 `_STATIC_WHITELIST` (vendor JS 파일들) 와 신규 `_STATIC_WHITELIST` (style.css/app.js) 는 다른 상수다. `handlers.py` 와 `monitor-server.py` 각각에 독립 정의해야 하며, `monitor-server.py` 의 기존 상수를 덮어쓰거나 교체하면 기존 `/static/` 라우트(vendor JS 서빙)가 깨진다.
- **MEDIUM**: `_STATIC_ROOT = Path(__file__).parent / "static"` 에서 `__file__`은 `handlers.py` 경로를 가리킨다. `monitor-server.py` 에서 `import`할 때 `__file__` 이 올바른 절대 경로를 반환하는지 확인 필요 (`sys.path.insert` 로 경로를 삽입하므로 일반적으로 문제 없음).
- **LOW**: `open(..., "w", encoding="utf-8", newline="\n")` 규칙 — 빈 파일 생성 시에도 준수. `Path.write_text("", encoding="utf-8", newline="\n")` 또는 `open(..., "w", encoding="utf-8", newline="\n")` 사용.

## QA 체크리스트
dev-test 단계에서 검증할 항목. 각 항목은 pass/fail로 판정 가능해야 한다.

- [ ] (정상 케이스) `GET /static/style.css` → 200, `Content-Type: text/css; charset=utf-8`, `Cache-Control: public, max-age=300` 헤더 포함.
- [ ] (정상 케이스) `GET /static/app.js` → 200, `Content-Type: application/javascript; charset=utf-8`, `Cache-Control: public, max-age=300` 헤더 포함.
- [ ] (에러 케이스) `GET /static/evil.sh` → 404 (화이트리스트 미포함).
- [ ] (에러 케이스) `GET /static/../../etc/passwd` → 404 (path traversal 시도, `..` 포함 or whitelist miss).
- [ ] (에러 케이스) `GET /static/` (빈 파일명) → 404.
- [ ] (통합 케이스) `python3 -c "import sys; sys.path.insert(0, 'scripts'); import monitor_server"` 성공 — 패키지 import 가능.
- [ ] (회귀) 기존 `pytest -q scripts/` 전량 통과 — 기존 `/static/` (vendor JS) 라우트 포함 어떤 기능도 회귀 없음.
- [ ] (구조) `scripts/monitor_server/__init__.py`, `scripts/monitor_server/handlers.py`, `scripts/monitor_server/static/` 디렉토리가 존재함 (AC-FR07-a).
- [ ] (구조) `scripts/monitor-server.py` 줄 수가 수정 전보다 감소하지 않음 (엔트리 로직 추가만, S1 제약).
