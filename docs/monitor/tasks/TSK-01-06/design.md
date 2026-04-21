# TSK-01-06: /api/state JSON 스냅샷 엔드포인트 - 설계

## 요구사항 확인
- `MonitorHandler.do_GET` 라우팅에 `GET /api/state` 분기를 추가해 `scan_tasks`/`scan_features`/`scan_signals`/`list_tmux_panes` 결과를 합친 단일 스냅샷을 `application/json; charset=utf-8`로 반환한다(PRD §4.3, TRD §4.1/§4.2).
- 응답 스키마는 TRD §4.1 렌더링 모델과 **동일 필드 집합**(`generated_at`, `project_root`, `docs_dir`, `wbs_tasks`, `features`, `shared_signals`, `agent_pool_signals`, `tmux_panes`). 각 `WorkItem.phase_history_tail`은 최근 10건(TSK-01-02의 `_PHASE_TAIL_LIMIT=10`을 그대로 사용, PRD §8 T4).
- 직렬화는 `dataclasses.asdict()` + `json.dumps(..., default=str, ensure_ascii=False)`. 실패/예외는 `{"error": "msg", "code": <http>}` JSON 바디로 응답하며 HTML을 섞지 않는다(PRD §4.3, PRD §5 오류 정책).

## 타겟 앱
- **경로**: N/A (단일 앱 — 플러그인 루트)
- **근거**: `scripts/monitor-server.py` 한 파일이 서버·스캐너·렌더러를 모두 담고 있는 단일 파일 구조(TRD §8, wbs.md `## Dev Config > design_guidance > backend`).

## 구현 방향
TSK-01-02가 추가할 `MonitorHandler.do_GET` 라우트 테이블에서 `/api/state`를 **가장 먼저** 매칭한다(더 구체적인 prefix가 우선 — TSK-01-05 라우트 매칭 원칙과 동일). 핸들러는 (1) 스냅샷 모델을 `_build_state_snapshot()` 순수 함수로 조립, (2) dataclass → dict 변환을 `_asdict_or_none`으로 통일(리스트/단일/None 세 경우), (3) `_json_response(self, status=200, payload=...)` 공통 헬퍼로 `application/json; charset=utf-8` 헤더·`Cache-Control: no-store`·UTF-8 바이트 출력을 수행한다. 모든 스캔 함수는 TSK-01-02/03 설계상 **예외를 삼키고 정의된 반환값**을 돌려주므로, `_build_state_snapshot` 자체는 일반 경로에서 예외를 일으키지 않는다. 그럼에도 방어 계층으로 핸들러 최외곽을 `try/except Exception` 으로 감싸 예상치 못한 오류는 500 JSON(`{"error": <repr>, "code": 500}`)으로 매핑하고 stderr에 1줄 로그한다. `datetime`/`Path` 등 비-JSON 기본 타입은 `default=str`이 처리한다.

## 파일 계획

**경로 기준:** 모든 파일 경로는 **프로젝트 루트(`dev-plugin/`) 기준**으로 작성한다.

| 파일 경로 | 역할 | 신규/수정 |
|-----------|------|-----------|
| `scripts/monitor-server.py` | `MonitorHandler.do_GET`의 라우트 테이블에 `GET /api/state` 분기 등록(라우터 역할). 신규 메서드 `_handle_api_state(self)`, 순수 함수 `_build_state_snapshot(project_root, docs_dir, scanners) -> dict`, 직렬화 헬퍼 `_asdict_or_none(value)`, 공통 JSON 응답 헬퍼 `_json_response(handler, status, payload)`와 `_json_error(handler, status, message)` 추가. `datetime.now(timezone.utc).isoformat(...).replace("+00:00","Z")`로 `generated_at` 생성. | 수정 (TSK-01-02 HTTP 스켈레톤 위에 추가) |
| `scripts/test_monitor_api_state.py` | `_build_state_snapshot`/`_asdict_or_none`/`_json_response`/라우팅 분기의 단위 테스트. 정상/빈/tmux 미설치/손상 state.json/예외 경로/`default=str` 직렬화/Content-Type 헤더/응답 시간 상한/라우트 매칭 순서 검증. 파일명 패턴 `test_monitor*.py`로 wbs.md Dev Config의 unit-test 명령에 자동 포함. | 신규 |

> 본 Task는 backend domain(UI 없음)이므로 "진입점"·메뉴·라우터 UI 파일은 존재하지 않는다. 라우터 역할은 `do_GET` 내부 if/elif 분기에서 수행된다.

## 진입점 (Entry Points)

N/A — `domain: backend`, UI 없음. `/api/state`는 CLI(`curl`)·CI·프로그램 연동용 JSON 엔드포인트이며 대시보드 HTML에서 직접 링크되지 않는다(대시보드는 동일 데이터를 서버 측 렌더링으로 표시).

## 주요 구조

### 1. `MonitorHandler.do_GET()` 라우팅 분기 (수정 · router)

TSK-01-04/05의 매칭 순서 원칙(가장 구체적인 prefix 우선)에 본 Task가 합류한다. TSK-01-02가 기본 do_GET을 작성한 뒤 본 Task는 상단에 분기 1개를 추가한다.

```
매칭 순서 (최종 통합):
  1. path == "/api/state"              → _handle_api_state()              [본 Task]
  2. path.startswith("/api/pane/")     → _api_pane(pane_id)                [TSK-01-05]
  3. path.startswith("/pane/")         → _render_pane(pane_id)             [TSK-01-05]
  4. path == "/"                        → _render_dashboard()               [TSK-01-04]
  5. 그 외                              → send_error(404) (JSON 요청 경로라면 _json_error)
```

- path 추출은 `urllib.parse.urlsplit(self.path).path` 로 수행하여 쿼리스트링이 붙어도(`/api/state?pretty=1`) 정확히 매칭된다. 쿼리스트링은 **무시**(본 Task는 파라미터 없음 — 요구사항 미기재).
- trailing slash 처리: `/api/state/` 는 **404** (일치 실패). 엄격 매칭으로 혼동을 줄이고 TSK-01-05 `/pane/` 분기와 구분.

### 2. `_handle_api_state(self)` (신규 · 핸들러)

```python
def _handle_api_state(self) -> None:
    try:
        payload = _build_state_snapshot(
            project_root=self.server.project_root,
            docs_dir=self.server.docs_dir,
            scan_tasks=scan_tasks,
            scan_features=scan_features,
            scan_signals=scan_signals,
            list_tmux_panes=list_tmux_panes,
        )
    except Exception as exc:                       # 방어 계층 (일반 경로 미도달)
        sys.stderr.write(f"/api/state build failed: {exc!r}\n")
        _json_error(self, status=500, message=f"internal error: {exc!r}")
        return
    _json_response(self, status=200, payload=payload)
```

- 스캐너 함수를 **인자로 주입**하여 단위 테스트에서 mock 주입이 가능하게 한다(의존성 역전). TSK-01-02/03이 정의한 전역 함수명을 그대로 전달.
- `self.server.project_root` / `self.server.docs_dir`: TSK-01-02가 `ThreadingHTTPServer` 서브클래스(또는 속성 주입)로 노출하는 경로 문자열/Path. 없으면 `getattr(self.server, "project_root", "") or ""`로 방어. project_root는 서버 기동 시 1회 `resolve()` 후 고정(TRD §7.1 threat model — HTTP path traversal 차단).

### 3. `_build_state_snapshot(project_root, docs_dir, scan_tasks, scan_features, scan_signals, list_tmux_panes) -> dict` (신규 · 순수 함수)

책임:
1. `scan_tasks(Path(docs_dir))` / `scan_features(Path(docs_dir))` 호출 → `list[WorkItem]` × 2.
2. `scan_signals()` 호출 → `list[SignalEntry]`. 이를 `scope == "shared"` / `scope.startswith("agent-pool:")` 로 2분하여 `shared_signals` / `agent_pool_signals` 로 채운다.
3. `list_tmux_panes()` 호출 → `list[PaneInfo] | None`. `None` 이면 **JSON에서 `null` 유지**(tmux 미설치 신호 — acceptance 2번).
4. `generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")` (예: `"2026-04-30T10:30:00Z"`).
5. 각 dataclass 리스트를 `[asdict(x) for x in items]` 로 변환. `tmux_panes`는 `None | [asdict(p) for p in panes]`.

반환 dict 형식 (TRD §4.1 정확 준수):

```python
{
    "generated_at": "2026-04-30T10:30:00Z",
    "project_root": "/abs/path",
    "docs_dir": "docs/monitor",
    "wbs_tasks": [ { ...WorkItem.asdict }, ... ],
    "features":  [ { ...WorkItem.asdict }, ... ],
    "shared_signals":     [ { ...SignalEntry.asdict }, ... ],
    "agent_pool_signals": [ { ...SignalEntry.asdict }, ... ],
    "tmux_panes": None | [ { ...PaneInfo.asdict }, ... ],
}
```

- `WorkItem.asdict()`는 중첩된 `phase_history_tail: list[PhaseEntry]`를 자동으로 dict 리스트로 변환한다(dataclasses.asdict 재귀 처리).
- `PhaseEntry`의 필드명은 `from_status`/`to_status`로 저장되어 있지만 JSON에서는 **파이썬 필드명 그대로 직렬화**한다(재매핑 금지 — TRD §5.1 스키마와 `asdict` 결과가 일관되도록). 클라이언트는 이 규약을 안다.
- 방어 접근: `scan_signals()` 가 돌려준 엔트리의 `scope` 가 두 패턴 중 어느 쪽에도 맞지 않으면(미래 확장) **`shared_signals`에 포함**한다(보수적 기본값). 알려지지 않은 scope라는 이유로 엔트리를 드롭하지 않는다 — 사용자가 상태를 볼 수 있어야 한다.

### 4. `_asdict_or_none(value)` (신규 · 직렬화 헬퍼)

```python
def _asdict_or_none(value):
    if value is None:
        return None
    if isinstance(value, list):
        return [asdict(x) if is_dataclass(x) else x for x in value]
    if is_dataclass(value):
        return asdict(value)
    return value
```

- `_build_state_snapshot`에서 dataclass 변환을 **한 줄 호출로 통일**해 반복 구문을 줄이고 `None`/일반 dict 혼입 시 안전 fallback.

### 5. `_json_response(handler, status, payload)` / `_json_error(handler, status, message)` (신규 · 응답 헬퍼)

```python
def _json_response(handler, status: int, payload: dict) -> None:
    body = json.dumps(payload, default=str, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    handler.wfile.write(body)

def _json_error(handler, status: int, message: str) -> None:
    _json_response(handler, status, {"error": message, "code": status})
```

- `default=str`이 `datetime`·`Path`·`decimal` 등을 모두 문자열로 변환. state.json 상의 `datetime` 인스턴스는 실전에서 이미 ISO-8601 문자열로 저장되지만(`wbs-transition.py` 규약), 미래 드리프트 방어 목적.
- `ensure_ascii=False`: 한글 title이 유니코드 이스케이프(`\uXXXX`)로 부풀지 않게 한다 — 응답 크기·가독성 모두 유리. 인코딩은 `.encode("utf-8")` 로 통일되어 헤더의 `charset=utf-8`과 일치.
- `Content-Length` 명시: 일부 클라이언트(`curl --http1.0`, 구 버전 httplib) 호환.
- `Cache-Control: no-store`: 대시보드가 짧은 주기로 재조회하므로 브라우저/프록시 캐싱을 차단.

### 6. 상수 / 유틸

- `_API_STATE_PATH = "/api/state"` — 라우트 문자열 상수화.
- 기존 TSK-01-02/03 상수(`_PHASE_TAIL_LIMIT`, `_SIGNAL_KINDS`, `_TMUX_FMT`, `_PANE_ID_RE`, `_ANSI_RE`)를 **재사용만** 하고 새 상수 추가는 최소화.

## 데이터 흐름

```
HTTP GET /api/state?..(쿼리 무시)
  → MonitorHandler.do_GET
  → urlsplit(self.path).path == "/api/state"
  → _handle_api_state(self)
     ├─ _build_state_snapshot(project_root, docs_dir, scan_*)
     │    ├─ scan_tasks(docs)        → list[WorkItem]
     │    ├─ scan_features(docs)     → list[WorkItem]
     │    ├─ scan_signals()          → list[SignalEntry]  (shared/agent-pool 분할)
     │    ├─ list_tmux_panes()       → list[PaneInfo] | None
     │    ├─ asdict(...) 재귀 변환
     │    └─ dict 반환
     └─ _json_response(200, dict)
         └─ json.dumps(..., default=str, ensure_ascii=False).encode("utf-8")
         → Content-Type: application/json; charset=utf-8
         → HTTP 200 + body
예외 경로:
  - 상위 try/except → 500 + {"error": ..., "code": 500}
  - 라우팅 미일치 → 404 경로는 TSK-01-02 기본 (JSON이 아닐 수 있음 — 본 Task 범위 밖)
```

## 설계 결정 (대안이 있는 경우만)

- **결정**: 스냅샷 조립을 **순수 함수 `_build_state_snapshot`로 추출**하고 스캐너들을 인자로 주입.
- **대안**: 핸들러 메서드 내부에서 전역 함수 직접 호출.
- **근거**: (1) 단위 테스트에서 HTTP 스택 없이 dict만 검증 가능. (2) 스캐너 mock 주입이 자연스러움. (3) `/` 핸들러(TSK-01-04의 `render_dashboard`)가 동일 모델을 사용하므로 **공유 지점**으로 승격 가능 — 추후 TSK-01-04/06 리팩터에서 공통화하기 쉽다.

- **결정**: `tmux_panes` 가 `None` 일 때 **JSON에서 `null`** 로 유지(빈 리스트로 대체 금지).
- **대안**: `None` → `[]` 로 정규화.
- **근거**: acceptance 2번 "`tmux_panes`는 tmux 미설치 시 `null`"을 문자 그대로 만족. 클라이언트(curl/jq/스크립트)가 `.tmux_panes == null` 과 `.tmux_panes == []` (서버 미기동)를 구분할 수 있어야 한다 — 의미론적 차이 보존.

- **결정**: `phase_history_tail`은 **TSK-01-02의 기본(10건)** 을 유지하고 별도 파라미터 도입 없음.
- **대안**: `/api/state?phase_tail=N` 쿼리로 동적 조정.
- **근거**: PRD §8 T4가 "기본 10 — 조정 가능"을 허용하지만 본 Task의 acceptance는 기본값만 요구. 조정 파라미터는 `scan_tasks` 시그니처 변경을 동반하므로 **후속 리팩터 Task에서 다룰 범위**(yagni). 현재는 TSK-01-02의 10건 고정을 재사용.

- **결정**: 쿼리스트링(`?pretty=1` 등)은 **매칭에만 사용하고 내용은 무시**.
- **대안**: `?pretty=1` → `json.dumps(indent=2)`.
- **근거**: 요구사항에 미기재. `curl ... | python3 -m json.tool` 로 포매팅하는 것이 표준 UX(acceptance 1번). 파라미터를 늘리면 테스트 표면이 커진다.

- **결정**: 응답 헤더에 `Cache-Control: no-store` 추가.
- **대안**: 캐시 헤더 미지정.
- **근거**: 대시보드 주기 갱신과 외부 CI 연동 모두에서 **stale 데이터**를 방지한다. `Content-Length` 명시도 같은 이유(스트리밍/청크 전환 방지).

- **결정**: scope가 `shared`/`agent-pool:*` 어느 패턴에도 맞지 않으면 **`shared_signals`에 포함**.
- **대안**: 드롭하거나 별도 `other_signals` 필드 추가.
- **근거**: `scan_signals`는 현재 두 scope만 반환하므로 실전에서는 미도달. 만약 미래에 새 scope가 추가되어도 사용자가 상태를 볼 수 있어야 한다 — 보수적 기본값. 새 필드를 만드는 건 TRD §4.1 스키마 변경이라 본 Task 범위를 넘는다.

## 선행 조건

- **TSK-01-02**: `MonitorHandler(BaseHTTPRequestHandler)` 스켈레톤 + `do_GET` 라우트 훅 + `ThreadingHTTPServer` 서브클래스(또는 wrapper)가 `self.server.project_root` / `self.server.docs_dir` 속성을 노출. 서버는 `127.0.0.1` 전용 바인딩(TRD §7.1). **설계 완료(`status: [dd]` 이상)** — 본 Task는 이 기반 위에 분기 1개를 추가.
- **TSK-01-03**: `scan_signals()` / `list_tmux_panes()` / `SignalEntry` / `PaneInfo` 가 본 Task의 import 시점에 정의되어 있어야 한다. 본 Task는 이들을 **그대로 호출만** 한다. **설계 완료(`status: [dd]` 이상)**.
- `scan_tasks()` / `scan_features()` / `WorkItem` / `PhaseEntry` (TSK-01-02 일부): 마찬가지로 import 만 한다.
- Python 3.8+ stdlib 전용 (`json`, `datetime`, `dataclasses.asdict` + `is_dataclass`, `urllib.parse.urlsplit`, `sys`, `pathlib`). 외부 의존성 0 (CLAUDE.md 규약).
- Dev Config의 `unit_test`: `python3 -m unittest discover -s scripts -p "test_monitor*.py" -v` — 테스트 파일명을 이에 맞춘다.

## 리스크

- **MEDIUM — `self.server.project_root` / `docs_dir` 속성 존재 여부**: TSK-01-02가 어떤 이름으로 주입하는지 현시점에 확정되지 않음(TSK-01-02 설계 완료 상태 확인 필요). **완화**: 핸들러에서 `getattr(self.server, "project_root", "") or ""` / `getattr(self.server, "docs_dir", "") or ""` 방어적 접근. TSK-01-02가 다른 이름을 쓰면 dev-build 단계에서 해당 속성으로 교체. 리스크는 dev-build의 step 0 검토에서 해소된다.
- **MEDIUM — 100 Task 규모의 응답 시간 1초 제약 (acceptance 3)**: `scan_tasks` + `scan_features` + `scan_signals` + `list_tmux_panes` 각 호출의 실제 시간은 디스크 I/O · subprocess(tmux) 의존. `list_tmux_panes` 는 `timeout=2` 라 최악 2초 누적 가능 → 1초 제약 위반 가능. **완화**: (1) tmux subprocess timeout을 본 Task에서 변경하지 않음(TSK-01-03 계약 존중). (2) 단위 테스트에 "100 Task + scan_* 전체 mock 없이 dict 조립" 시간 측정 추가하고 0.5초 이내 어서션. (3) `list_tmux_panes`의 2초는 "tmux 비정상" 엣지 케이스 — 정상 상황에서 수십 ms. acceptance 해석은 "정상 환경 기준 1초 이내"로 합의하고 test-report에 명시.
- **MEDIUM — `json.dumps` 직렬화 가능성**: `dataclasses.asdict` 는 nested dict/list/primitive 로만 전개하므로 `json.dumps` 기본 인코더가 처리 가능해야 한다. `WorkItem.path`는 `_resolve_abs_path` 결과로 **이미 str** (TSK-01-02가 `str(path.resolve())` 사용), `started_at`/`completed_at` 도 state.json 문자열이 그대로 저장됨. **완화**: `default=str` 추가로 미래 드리프트 흡수. 단위 테스트에 `datetime` 리터럴이 필드에 들어간 인위적 케이스 포함하여 회귀 방지.
- **LOW — ThreadingHTTPServer 하에서 scan 중 state.json 쓰기**: 동일 파일을 다른 프로세스가 쓰는 동안 읽기 — `_read_state_json`의 JSON 파싱 실패로 전이되고 `raw_error` 로 표시되므로 요청 자체는 실패하지 않음. 완화 불필요.
- **LOW — 아주 큰 응답 바디**: `phase_history_tail`이 10건으로 제한되므로 Task 100개 × 500B ≈ 50KB 수준. 문제 없음.

## QA 체크리스트

dev-test 단계에서 검증할 항목. 각 항목은 pass/fail로 판정 가능해야 한다.

- [ ] (정상) `_build_state_snapshot(project_root="/abs", docs_dir="docs", scan_tasks=stub([wbs 3]), scan_features=stub([feat 1]), scan_signals=stub([shared 2 + agent-pool 1]), list_tmux_panes=stub([pane 2]))` 호출 시 반환 dict 의 키 집합이 정확히 `{"generated_at","project_root","docs_dir","wbs_tasks","features","shared_signals","agent_pool_signals","tmux_panes"}` 8개이고, 각 리스트 길이가 (3, 1, 2, 1, 2) 이다.
- [ ] (정상) `generated_at` 이 `^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$` 정규식을 만족하고 UTC 시각이다 (`datetime.now(timezone.utc)` 기반).
- [ ] (정상) `scan_signals()`가 `[shared, shared, agent-pool:20260501-xxx, agent-pool:20260501-yyy]` 4건을 리턴하도록 mock 했을 때 `shared_signals` 길이 2, `agent_pool_signals` 길이 2이고 scope 필드가 그대로 보존된다.
- [ ] (엣지) `list_tmux_panes` mock이 `None` 을 반환하면 결과 dict 의 `tmux_panes` 가 `None`(→ JSON `null`) 이다. 빈 리스트 `[]` 이면 `tmux_panes == []` 가 유지된다 (두 상태 구분 유지, acceptance 2번).
- [ ] (엣지) `scan_tasks`/`scan_features`/`scan_signals` 모두 `[]` 를 반환하면 결과 dict 의 해당 리스트 3개가 모두 `[]` 이고 예외 없이 정상 dict 반환.
- [ ] (엣지) `WorkItem` 중 `raw_error` 가 채워진 항목이 있어도 `asdict` 변환이 성공하고 JSON 직렬화가 깨지지 않는다 (파싱 실패한 Task 도 JSON에 포함).
- [ ] (정상) `json.dumps(payload, default=str, ensure_ascii=False)` 결과에 **한글 title** 이 유니코드 이스케이프 없이 원문 그대로 포함된다(ensure_ascii=False 증거).
- [ ] (정상) `phase_history_tail` 배열 길이가 각 WorkItem 에서 **최대 10** 이다 (TSK-01-02의 `_PHASE_TAIL_LIMIT` 적용 확인).
- [ ] (정상) 라이브 HTTP 테스트 — 실제 서버 기동 후 `urllib.request.urlopen("http://127.0.0.1:{port}/api/state")` → 200, `Content-Type == "application/json; charset=utf-8"`, 본문 `json.loads()` 성공, 결과 dict 에 위 8개 키 존재.
- [ ] (정상) `curl -sS http://127.0.0.1:{port}/api/state | python3 -m json.tool` 의 반환 코드가 0 (acceptance 1번).
- [ ] (에러) `_handle_api_state` 가 `_build_state_snapshot` 에서 raise 된 가짜 `RuntimeError("boom")` 를 캐치해 **500 + JSON `{"error":"internal error: RuntimeError('boom')","code":500}`** 를 반환하고 stderr에 1줄 로그가 남는다(mock 주입).
- [ ] (에러) 라우트 매칭 테스트 — `GET /api/state/` (trailing slash) 는 `_handle_api_state` 로 가지 않는다(404 경로). `GET /api/state?pretty=1` 은 `_handle_api_state` 로 매칭되고 payload 는 쿼리와 무관하게 동일.
- [ ] (보안) 응답 바디가 HTML을 포함하지 않는다 — `re.search(r'<[a-zA-Z/]', body)` 결과가 None 이거나, 존재한다면 그것은 **문자열 값 내부에 그대로 담긴 사용자 데이터**(예: title 에 `<script>` 가 들어 있는 XSS 페이로드)이고 Content-Type 은 여전히 `application/json; charset=utf-8` 이다. JSON 구조 내부 값은 escape 불필요(브라우저가 JSON을 HTML로 해석하지 않는다) — constraint "JSON 응답만, HTML 섞지 않음"을 충족.
- [ ] (성능) 100개 WorkItem (phase_history_tail 각 10건) + 20개 PaneInfo + 50개 SignalEntry 크기의 mock 입력에서 `_build_state_snapshot` + `json.dumps` 합산 실행 시간이 **0.5초 이내** (acceptance 3 여유분, tmux subprocess 제외).
- [ ] (통합) TSK-01-02/03/04 에서 정의된 dataclass (`WorkItem`/`PhaseEntry`/`SignalEntry`/`PaneInfo`) 가 모두 `dataclasses.asdict` 로 직렬화 가능하고, 모든 최상위 필드가 JSON 기본 타입(str/int/float/bool/None/list/dict)으로 변환된다(재귀 순회 검증).
- [ ] (통합) `scope="agent-pool:20260501-999"` 인 SignalEntry 가 `agent_pool_signals` 로 분류되고 `scope="shared"` 는 `shared_signals` 로 분류된다. 미지의 scope `"other:xyz"` 는 `shared_signals` 로 편입되어 **드롭되지 않는다**(보수적 기본값 검증).
- [ ] (통합) `_json_response(handler, 200, {"k":"v"})` 가 handler.send_response(200), `Content-Type: application/json; charset=utf-8`, `Content-Length: 9`, `Cache-Control: no-store` 네 항목을 정확히 호출한다(mock handler 로 검증).
