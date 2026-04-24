# monitor-server-perf: 설계

## 요구사항 확인

- monitor-server.py 서버 측 핫스팟 5개 제거: `/api/graph` 결과 TTL 캐시, `dep-analysis.py` 인프로세스 import, `scan_signals()` TTL 캐시, 대시보드 JS 폴링 일원화, `leader-watchdog.py` tmux 호출 통합.
- `/api/graph` p95 응답시간과 subprocess fork 횟수를 헤드리스 1분 측정 테스트에서 회귀 가드로 고정한다.
- 이미 `dev/WP-02-monitor-v5`가 main에 머지된 상태이므로(`scripts/monitor_server/` 패키지 존재 확인), 분리된 패키지 구조(`monitor_server/core.py`, `monitor_server/api.py`) 기준으로 구현한다. monitor-server.py는 얇은 엔트리만 담당하므로 수정하지 않는다.

## 타겟 앱

- **경로**: N/A (단일 앱, scripts/ 하위 Python 스크립트)
- **근거**: dev-plugin 모노레포 내 앱 구조 없음; 대상 파일은 `scripts/monitor_server/core.py`, `scripts/monitor_server/api.py`, `scripts/leader-watchdog.py`

## 구현 방향

1. **[항목1] `/api/graph` + `scan_signals()` TTL 메모이즈**: `monitor_server/core.py`에 스레드-안전 `_TTLCache` 헬퍼(lock + timestamp)를 추가한다. `_handle_graph_api`는 1초 TTL 캐시를 참조하여 캐시 히트 시 dep-analysis + scan을 건너뛴다. `scan_signals()`도 동일 TTL 캐시로 감싼다.

2. **[항목2] ETag/304 게이트**: `/api/graph` 응답에 `ETag: "<sha256[:12]>"` 헤더를 추가하고, `If-None-Match` 요청 헤더와 일치하면 304를 반환한다.

3. **[항목3] `dep-analysis.py` 인프로세스 import**: `_call_dep_analysis_graph_stats()` 구현을 `subprocess.run` → `importlib` 인프로세스 import로 교체한다. `dep_analysis` 모듈의 `compute_graph_stats(tasks_input)` 공개 함수를 직접 호출한다. subprocess fork 0회화.

4. **[항목4] 대시보드 메인 폴링 일원화**: `_DASHBOARD_JS`의 `fetchAndPatch`가 현재 `fetch('/')` (전체 HTML)를 사용 중 → `/api/state`로 전환하고 JSON 파싱 후 각 `[data-section]` DOM 패치로 변경한다. `refresh_seconds`를 서버로부터 `data-refresh-ms` 속성으로 주입하여 interval을 서버 설정으로 제어한다.

5. **[항목5] `leader-watchdog.py` tmux 호출 통합**: `window_exists()` + `pane_dead()` 순서로 2회 호출 → `list-windows -F "#{window_name}\t#{pane_dead}"` 한 번으로 통합한다. 매 poll interval당 tmux fork 횟수를 2→1로 감소.

6. **[항목6] `dep-analysis.py` 공개 함수 추가**: `dep-analysis.py`에 `compute_graph_stats(tasks_json_list: list) -> dict` 함수를 추가하여 CLI(`main()`)와 분리된 호출 가능 인터페이스를 제공한다. CLI 동작은 보존한다.

## 파일 계획

| 파일 경로 | 역할 | 신규/수정 |
|-----------|------|-----------|
| `scripts/monitor_server/core.py` | `_TTLCache` 추가, `scan_signals()` TTL 래핑, `_handle_graph_api` 캐시·ETag 적용, `_DASHBOARD_JS` fetch 일원화 (`fetch('/')` → `/api/state` JSON 패치) | 수정 |
| `scripts/monitor_server/api.py` | `_call_dep_analysis_graph_stats` subprocess→import 교체 | 수정 |
| `scripts/dep-analysis.py` | `compute_graph_stats(tasks_json_list)` 공개 함수 추출 | 수정 |
| `scripts/leader-watchdog.py` | `window_exists()` + `pane_dead()` → `check_window_and_pane()` 통합 (list-windows 1회 호출) | 수정 |
| `scripts/test_monitor_server_perf.py` | 헤드리스 1분 측정 테스트 (p95 응답시간, subprocess fork 횟수/분) | 신규 |

## 진입점 (Entry Points)

N/A — 순수 백엔드/인프라 성능 개선. UI 변경 없음(대시보드 JS 내부 fetch URL 교체는 외부 라우트 변경 없음).

## 주요 구조

### `_TTLCache` (core.py 신규 클래스)
```
_TTLCache(ttl_seconds=1.0)
  .get(key) -> (value, hit: bool)
  .set(key, value) -> None
```
`threading.Lock`으로 스레드-안전 보장. `ThreadingHTTPServer`의 다중 스레드 동시 요청을 처리.

### `scan_signals_cached()` (core.py 신규 함수)
- `_SIGNALS_CACHE = _TTLCache(1.0)` 모듈 레벨 인스턴스
- `scan_signals_cached()` → 1초 TTL 히트 시 기존 결과 반환, 미스 시 `scan_signals()` 호출 후 캐시 저장
- `_handle_api_state`는 `scan_signals_cached()`를 기본값으로 사용

### `_GraphCache` 캐시 항목 (core.py)
- `_GRAPH_CACHE = _TTLCache(1.0)` 모듈 레벨 인스턴스 (subproject별 키)
- `_handle_graph_api`에서 캐시 히트 시 payload + ETag 즉시 반환, 304 처리
- ETag: `hashlib.sha256(json_bytes).hexdigest()[:12]` (stdlib만 사용)

### `compute_graph_stats(tasks_json_list)` (dep-analysis.py 신규 공개 함수)
- 기존 `--graph-stats` 모드의 계산 로직을 함수로 추출
- `main()`은 `compute_graph_stats()`를 내부 호출하여 CLI 동작 보존
- `api.py`의 `_call_dep_analysis_graph_stats()`에서 `importlib`으로 dep-analysis 모듈을 로드 후 `compute_graph_stats()` 직접 호출

### `check_window_and_pane(session, wt_name)` (leader-watchdog.py)
- `list-windows -t {session} -F "#{window_name}\t#{pane_dead}"` 1회 호출
- 반환: `(window_exists: bool, pane_is_dead: bool)`
- 기존 `window_exists()` + `pane_dead()` 2회 호출 대체

### 대시보드 JS 수정 (`_DASHBOARD_JS` in core.py)
- `fetchAndPatch(signal)`: `fetch('/')` → `fetch('/api/state' + window.location.search, {cache:'no-store'})`
- 응답 JSON의 필드를 기존 `[data-section]` DOM에 매핑하는 `_patchFromState(json)` 헬퍼 추가
- `data-refresh-ms` 속성을 `<body>` 또는 루트 엘리먼트에 서버 주입하여 `setInterval` 간격 제어

## 데이터 흐름

**`/api/graph` 요청 흐름 (캐시 미스):**
`GET /api/graph?subproject=all` → `_handle_graph_api` → 캐시 조회 미스 → `scan_tasks_fn()` + `scan_signals_cached()` + `compute_graph_stats()` (in-process) → payload 조립 → ETag 계산 → 캐시 저장 → JSON 200 응답

**`/api/graph` 요청 흐름 (캐시 히트):**
`GET /api/graph?subproject=all` → `_handle_graph_api` → 캐시 히트 → If-None-Match 비교 → 304 (ETag 일치) 또는 200 (ETag 불일치) — subprocess fork 0회

**대시보드 폴링 (수정 후):**
JS `setInterval(tick, refreshMs)` → `fetch('/api/state')` → JSON 응답 → `_patchFromState(json)` → `[data-section]` DOM 패치 (이전: `fetch('/')` → HTML 전체 파싱 → DOM 교체)

## 설계 결정 (대안이 있는 경우만)

- **결정**: `dep-analysis.py`를 `importlib.util.spec_from_file_location`으로 동적 import
- **대안A**: dep-analysis 로직을 monitor_server/ 패키지 내부 모듈로 완전 이식
- **대안B**: multiprocessing Pool로 한 번만 fork 후 재사용
- **근거**: 대안A는 dep-analysis.py가 wbs-parse.py 등 다른 스킬에서도 CLI로 사용되므로 단일 파일 유지가 의존성 분리에 유리; 대안B는 프로세스 복잡도 증가. 동적 import는 stdlib만으로 zero-dependency를 유지하면서 fork를 완전 제거.

- **결정**: 대시보드 메인 폴링을 `fetch('/')` (HTML) → `fetch('/api/state')` (JSON)으로 변경
- **대안**: HTML 응답에 SSE(Server-Sent Events) 또는 WebSocket 사용
- **근거**: stdlib `http.server`는 SSE/WS를 기본 지원하지 않음. 기존 fetch+patch 패턴을 유지하면서 payload 크기만 줄이는 방식이 변경 범위 최소.

- **결정**: TTL 캐시를 단순 `time.monotonic()` + `threading.Lock` 으로 구현
- **대안**: `functools.lru_cache` + `threading.Timer` 만료 무효화
- **근거**: TTL 캐시는 stdlib만으로 10줄 이내 구현 가능; lru_cache는 TTL을 기본 지원하지 않아 별도 무효화 로직이 복잡해짐.

- **결정**: 현재 main 브랜치 기준(`monitor_server/` 패키지 존재)으로 설계 수행
- **근거**: `dev/WP-02-monitor-v5`가 이미 main에 머지되어 `scripts/monitor_server/core.py` (~6947줄), `scripts/monitor_server/api.py` (~640줄) 존재 확인. spec.md의 "주의" 사항(WP-02 머지 후 캐시 누락 경고)은 실제로 WP-02 머지 완료 후를 기준으로 한 경고이며, 현재 main에 패키지 분리가 이미 반영된 상태임.

## 선행 조건

- Python 3.8+ stdlib (hashlib, importlib.util, threading 모두 표준 포함)
- `dep-analysis.py`의 `compute_graph_stats()` 추출이 다른 항목들보다 먼저 완료되어야 api.py 변경 가능 (순서 의존)
- tmux 설치 여부와 무관하게 leader-watchdog 변경은 독립 적용 가능

## 리스크

- **HIGH**: `dep-analysis.py` 동적 import 시 모듈이 `sys.argv` 또는 `sys.stdin` 에 의존하는 전역 초기화 코드가 있으면 인프로세스 호출에서 예상치 못한 부작용 발생. → `compute_graph_stats()` 추출 시 `if __name__ == "__main__":` 가드 안에 `main()` 진입을 제한하고 전역 실행 코드를 함수 내부로 이동.
- **HIGH**: `_TTLCache`의 스레드 경합. `ThreadingHTTPServer`는 요청별 새 스레드를 생성하므로 cache.set()과 .get() 사이에 race가 발생할 수 있음. → `threading.Lock` acquire/release를 `with` 블록으로 atomic하게 처리. double-check locking 패턴 사용.
- **MEDIUM**: 대시보드 JS 폴링 변경(`fetch('/')` → `/api/state`) 후 기존 `[data-section]` 패치 로직과 JSON 필드 매핑 불일치. → `_patchFromState` 구현 시 기존 `patchSection(name, html)` 함수를 재활용하고, `/api/state` JSON 응답에 섹션별 pre-rendered HTML 필드를 추가하는 방안도 검토. 단 응답 크기 증가 trade-off 있음.
- **MEDIUM**: `importlib.util.spec_from_file_location`으로 로드한 dep-analysis 모듈이 `sys.modules`에 중복 등록될 경우 캐시 오염. → `_DEP_ANALYSIS_MODULE_NAME = "dep_analysis_inproc"` 고유 키로 등록, 이미 있으면 재사용.
- **LOW**: leader-watchdog `list-windows -F "#{window_name}\t#{pane_dead}"` 포맷이 tmux 구버전(< 2.6)에서 `#{pane_dead}` 미지원. → 지원 여부는 기존 코드에서 이미 `display-message -t {target} -p "#{pane_dead}"` 사용 중이므로 동일 tmux 버전 요구사항 유지. 변경 없음.
- **LOW**: ETag 헤더로 304 반환 시 클라이언트(graph-client.js)가 200만 기대하면 오작동. → graph-client.js가 이미 `cache:'no-store'`를 사용 중이므로 304 수신 시 브라우저가 캐시에서 재구성. fetch API의 304 처리는 브라우저 표준 동작.

## QA 체크리스트

### 정상 케이스

- [ ] `/api/graph` 첫 요청 후 1초 이내 재요청 시 캐시 히트 — scan/dep-analysis 실행 없이 즉시 응답 반환 (헤드리스 타이밍 측정으로 검증)
- [ ] `/api/graph` 첫 요청 응답에 `ETag` 헤더가 포함된다
- [ ] 동일 ETag를 `If-None-Match`로 재요청 시 HTTP 304가 반환된다 (본문 없음)
- [ ] `/api/graph` 캐시 TTL(1초) 만료 후 요청 시 신선 데이터로 갱신된다
- [ ] `dep-analysis.py` subprocess fork 횟수가 1분 측정에서 0회 (인프로세스 호출)
- [ ] `/api/graph` p95 응답시간이 100ms 이하 (캐시 히트 기준)
- [ ] `scan_signals()` 반복 호출 시 1초 TTL 내 캐시 히트 — os.walk 호출 0회
- [ ] leader-watchdog 폴 사이클당 tmux subprocess 호출이 1회 (`list-windows` 단독)
- [ ] `compute_graph_stats()` 직접 호출 결과가 기존 subprocess CLI 결과와 동일 (JSON 구조 비교)
- [ ] 대시보드 `/api/state` 폴링 응답으로 `[data-section]` DOM이 올바르게 갱신된다

### 엣지 케이스

- [ ] `scan_signals()`가 빈 디렉터리를 반환할 때 캐시가 `[]`로 올바르게 저장된다
- [ ] `/api/graph` 1초 경계에서 동시 요청(멀티스레드) 시 두 요청 모두 올바른 응답을 받는다 (race condition 없음)
- [ ] `dep-analysis.py` 동적 import 후 `sys.modules["dep_analysis_inproc"]`가 재사용된다 (중복 import 없음)
- [ ] leader-watchdog `list-windows` 결과에 해당 `wt_name`이 없으면 `window_exists=False` 반환

### 에러 케이스

- [ ] `compute_graph_stats()` 내부 예외 시 api.py가 HTTP 500 JSON을 반환한다 (서버 크래시 없음)
- [ ] `importlib` dep-analysis 로드 실패 시 기존 subprocess fallback으로 자동 전환된다 (degraded mode)
- [ ] TMux 미설치 환경에서 `check_window_and_pane()` 호출 시 `(False, False)` 반환 (예외 없음)
- [ ] ETag가 None이거나 생성 실패 시 ETag 없이 200 응답 정상 반환 (ETag optional)

### 통합/회귀 케이스

- [ ] `test_monitor_server_perf.py` 헤드리스 1분 측정: subprocess fork 횟수 0/분 (dep-analysis 인프로세스 전환 후)
- [ ] `test_monitor_server_perf.py` 헤드리스 1분 측정: `/api/graph` p95 응답 ≤ 100ms
- [ ] 기존 `test_monitor_server_*.py` 테스트 전체 통과 (회귀 없음)
- [ ] `dep-analysis.py` CLI (`python3 scripts/dep-analysis.py --graph-stats`) 동작 불변
- [ ] `leader-watchdog.py --interval` 실행 후 로그에 `list-windows` 1회만 기록
- [ ] `/api/state` 폴링으로 전환 후 `[data-section="wp-cards"]`, `[data-section="live-activity"]` 등 기존 섹션 fold 상태가 DOM 교체 후에도 복원된다
