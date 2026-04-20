# TRD — dev-plugin 웹 모니터링 도구

**문서 버전:** 0.1 (초안)
**작성일:** 2026-04-20
**선행 문서:** `docs/monitor/prd.md`
**상태:** Draft

---

## 1. 시스템 개요

단일 Python 프로세스가 localhost에서 HTTP 서버로 동작하며, 요청 시마다 파일 시스템·tmux를 스캔하여 HTML/JSON으로 응답한다. 브라우저는 meta refresh + 부분 fetch로 자동 갱신한다. 외부 상태 저장소·메시지 큐·백그라운드 워커 없음.

```
┌────────────┐     HTTP GET       ┌──────────────────────┐
│  Browser   │ ────────────────▶ │ monitor-server.py    │
│ (refresh)  │ ◀──────────────── │ (python http.server) │
└────────────┘     HTML/JSON     └──────────┬───────────┘
                                            │ on-demand scan
                   ┌────────────────────────┼────────────────────┐
                   ▼                        ▼                    ▼
           state.json files          signal files           tmux/psmux
        (docs/tasks, features)    (/tmp/claude-signals)    (capture-pane)
```

## 2. 기술 스택

| 계층 | 선택 | 근거 |
|------|------|------|
| Runtime | Python 3.8+ | 플러그인 표준, stdlib만 사용 (`CLAUDE.md` 규약) |
| HTTP Server | `http.server.ThreadingHTTPServer` | stdlib. 요청 병렬 처리. 외부 프레임워크 불필요 |
| Handler | `BaseHTTPRequestHandler` subclass | 라우팅이 단순(4개 엔드포인트)하여 프레임워크 과잉 |
| Template | Python f-string + 인라인 CSS | 의존성 0. Jinja2 불필요 |
| 파일 탐색 | `pathlib.Path.glob` | stdlib |
| 외부 호출 | `subprocess.run` (`tmux capture-pane`, `tmux list-panes`) | timeout 설정으로 안전 |
| 프로세스 관리 | PID 파일 + `os.kill(pid, 0)` 생존 체크 | daemon 라이브러리 불필요 |

**명시적 거부 대상**: Flask, FastAPI, Starlette, uvicorn, websockets, watchdog, jinja2, psutil — 모두 pip 의존성을 요구하므로 금지.

## 3. 프로세스 및 기동 모델

### 3.1 기동 플로우

```
/dev-monitor [--port 7321] [--docs docs]
       │
       ▼
SKILL.md 실행
       │
       ├─ PID 파일 확인: ${TMPDIR}/dev-monitor-{port}.pid
       │   └─ 있고 살아있음 → URL 재출력 후 종료 (idempotent)
       │
       ├─ 포트 바인딩 테스트 (socket)
       │   └─ 실패 → 사용자 안내 후 종료
       │
       ├─ 백그라운드 기동 (monitor-server.py --port N --docs D --project-root $PWD)
       │   (nohup / Popen detach / psmux 환경별 분기)
       │
       ├─ PID 파일 기록
       │
       └─ "http://localhost:{port}" URL 출력
```

### 3.2 종료 모델

- 사용자가 직접 `kill $(cat ${TMPDIR}/dev-monitor-{port}.pid)` 또는 `/dev-monitor --stop`
- 서버는 `SIGTERM`에 즉시 응답, finally 블록에서 PID 파일 삭제
- 비정상 종료 시 PID 파일이 남을 수 있음 → 기동 시 `os.kill(pid, 0)` 로 좀비 감지 후 재사용

### 3.3 백그라운드화

- macOS/Linux: `subprocess.Popen(..., start_new_session=True, stdout=log, stderr=log)` 로 detach
- Windows(psmux): `Popen(..., creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP)` 로 분리
- 로그: `${TMPDIR}/dev-monitor-{port}.log` (append, 회전 없음 — 장기 운영 가정 아님)

## 4. 엔드포인트 상세

### 4.1 `GET /`

**응답**: `text/html; charset=utf-8`

**렌더링 데이터** (단일 스캔 결과를 HTML로 변환):

```python
{
  "generated_at": "2026-04-20T10:30:00Z",
  "project_root": "/abs/path",
  "docs_dir": "docs",
  "wbs_tasks": [ <Task>, ... ],
  "features": [ <Feature>, ... ],
  "shared_signals": [ <Signal>, ... ],
  "agent_pool_signals": [ <Signal>, ... ],
  "tmux_panes": [ <Pane>, ... ] | null,    # null = tmux unavailable
}
```

**자동 갱신**: `<meta http-equiv="refresh" content="3">`

### 4.2 `GET /api/state`

**응답**: `application/json`

`/` 가 렌더링에 사용하는 동일 구조를 JSON으로 직렬화. 외부 스크립트·CI 연동용.

### 4.3 `GET /pane/{pane_id}`

**응답**: `text/html; charset=utf-8`

```html
<pre class="pane-capture" data-pane="%1">
  ...captured lines (최근 500, ANSI escape stripped)...
</pre>
<div class="footer">captured at 2026-04-20T10:30:05Z</div>
```

- `pane_id`는 `%숫자` 형태 (tmux pane id). URL path에서 추출 후 정규식 `^%\d+$` 로 검증. 불일치 시 400.
- 구현: `subprocess.run(["tmux", "capture-pane", "-t", pane_id, "-p", "-S", "-500"], timeout=3)`
- ANSI escape sequence 제거: `re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', output)`

### 4.4 `GET /api/pane/{pane_id}`

**응답**: `application/json`

```json
{
  "pane_id": "%1",
  "captured_at": "2026-04-20T10:30:05Z",
  "lines": ["...", "..."],
  "line_count": 312,
  "truncated_from": 500
}
```

### 4.5 공통 동작

| 항목 | 규칙 |
|------|------|
| Method 제한 | `GET`만 허용. 그 외 `405 Method Not Allowed` |
| 에러 포맷 | HTML은 `<div class="error">`, JSON은 `{"error": "msg", "code": 400}` |
| 로깅 | stderr 로 요청 라인(1줄)만 출력. stdout은 비움 |
| CORS | 미적용. localhost 전용이므로 불필요 |
| Bind | `127.0.0.1` only. `0.0.0.0` 바인딩 금지 |

## 5. 데이터 모델

### 5.1 Task / Feature 통합 스키마

`scan_tasks()` 와 `scan_features()` 는 다음 구조를 반환한다:

```python
@dataclass
class WorkItem:
    id: str                      # "TSK-01-01" | "feat-login"
    kind: str                    # "wbs" | "feat"
    title: str | None            # wbs.md 파싱 결과 (feat은 spec.md 첫 줄)
    path: str                    # state.json 절대 경로
    status: str                  # "[xx]" 등
    started_at: str | None       # ISO-8601
    completed_at: str | None
    elapsed_seconds: float | None
    bypassed: bool
    bypassed_reason: str | None
    last_event: str | None       # state.json.last.event
    last_event_at: str | None
    phase_history_tail: list[PhaseEntry]   # 최근 10개
    wp_id: str | None            # WBS일 때만 (e.g. "WP-01")
    depends: list[str]           # WBS일 때만
    raw_error: str | None        # JSON parse 실패 시 원문 앞 500B
```

### 5.2 Signal

```python
@dataclass
class SignalEntry:
    name: str                    # "TSK-01-01.running"
    kind: str                    # "running" | "done" | "failed" | "bypassed"
    task_id: str                 # "TSK-01-01"
    mtime: str                   # ISO-8601
    scope: str                   # "shared" | "agent-pool:{timestamp}"
```

### 5.3 tmux Pane

```python
@dataclass
class PaneInfo:
    window_name: str
    window_id: str               # "@5"
    pane_id: str                 # "%12"
    pane_index: int
    pane_current_path: str
    pane_current_command: str    # "claude" | "python" etc.
    pane_pid: int
    is_active: bool
```

쿼리:
```
tmux list-panes -a -F '#{window_name}\t#{window_id}\t#{pane_id}\t#{pane_index}\t#{pane_current_path}\t#{pane_current_command}\t#{pane_pid}\t#{pane_active}'
```

## 6. 스캔 알고리즘

### 6.1 `scan_tasks(docs_dir: Path)`

1. `docs_dir / "tasks"` 가 없으면 `[]` 반환
2. `glob("*/state.json")` 로 순회
3. 각 state.json 읽기:
   - JSON 파싱 성공 → `WorkItem.kind = "wbs"` 생성
   - 실패 → `raw_error` 에 앞 500B 저장
4. `docs_dir / "wbs.md"` 를 Task 제목·WP 매핑에 활용 (가능할 때만, 실패 시 title=None)
5. `phase_history_tail` 은 마지막 10개만 슬라이스

### 6.2 `scan_features(docs_dir: Path)`

동일 로직, `docs_dir / "features"` 순회. title은 `spec.md` 첫 non-empty 줄.

### 6.3 `scan_signals()`

- **Shared**: `${TMPDIR}/claude-signals/` 하위 모든 디렉터리 재귀 스캔 → `scope="shared"`
- **Agent-pool**: `${TMPDIR}/agent-pool-signals-*` glob → `scope=f"agent-pool:{timestamp}"`
- 파일 확장자로 `kind` 결정 (`.running` 등). 그 외 파일은 무시.

### 6.4 `list_tmux_panes()`

1. `shutil.which("tmux")` 로 존재 확인. 없으면 `None` 반환
2. `subprocess.run(["tmux", "list-panes", "-a", "-F", FMT], timeout=2)` 호출
3. stderr에 `no server running` 포함 시 `[]` 반환
4. 각 줄을 tab-split → `PaneInfo` 리스트

## 7. 보안 및 안전성

### 7.1 Threat Model

| 위협 | 완화 |
|------|------|
| 로컬 외 접근 | `127.0.0.1` 바인딩 강제. `0.0.0.0` 금지 |
| Command injection via pane_id | `^%\d+$` 정규식 검증. list 형 subprocess 호출 (`shell=False`) |
| Path traversal via docs param | 기동 시 1회 `resolve()` 후 고정. HTTP 요청에서 경로 파라미터 수용 금지 |
| subprocess hang | 모든 `subprocess.run` 에 `timeout=3` |
| 거대 state.json | 파일 크기 > 1MB 시 읽기 거부, "file too large" 표시 |
| XSS (pane 캡처에 HTML 포함) | 모든 사용자 유래 문자열 `html.escape()` 처리 |

### 7.2 Read-Only 보장

- `open()` 호출은 모두 `mode="r"`
- `subprocess` 호출 목록: `tmux list-panes`, `tmux capture-pane`, `tmux list-sessions` — 모두 읽기 전용
- 단위 테스트에서 `os.chmod 0o444` 로 테스트 대상 state.json 권한을 막아도 동작해야 함

## 8. 파일/모듈 구조

```
scripts/monitor-server.py           # 단일 파일 엔트리
  ├─ class MonitorHandler(BaseHTTPRequestHandler)
  │    ├─ do_GET()
  │    ├─ _render_dashboard()
  │    ├─ _render_pane(pane_id)
  │    └─ _api_state() / _api_pane()
  ├─ def scan_tasks() / scan_features() / scan_signals()
  ├─ def list_tmux_panes() / capture_pane()
  ├─ def render_html(model) -> str
  └─ if __name__ == "__main__": argparse + serve_forever
```

목표 LOC: 300 ± 50. 이를 초과하면 같은 디렉터리에 `monitor_lib.py` 보조 모듈 도입 검토 (단, 플러그인의 단일-파일 스크립트 관례 유지를 우선).

## 9. 설정/CLI

### 9.1 `monitor-server.py` 인자

| 인자 | 기본 | 설명 |
|------|------|------|
| `--port` | 7321 | 바인딩 포트 |
| `--docs` | `docs` | docs 루트 (프로젝트 root 기준 상대 또는 절대) |
| `--project-root` | `$PWD` | 프로젝트 루트 (절대 경로로 resolve) |
| `--max-pane-lines` | 500 | pane 캡처 라인 수 상한 |
| `--refresh-seconds` | 3 | 대시보드 meta refresh 간격 |
| `--no-tmux` | false | tmux 스캔 비활성화 (단위 테스트용) |

### 9.2 `/dev-monitor` 스킬 인자

| 인자 | 기본 | 설명 |
|------|------|------|
| `--port` | 7321 | monitor-server 에 전달 |
| `--docs` | `docs` | monitor-server 에 전달 |
| `--stop` | - | 해당 포트의 PID 파일 기반 종료 |
| `--status` | - | 기동 상태 확인 (PID alive + URL 출력) |

## 10. 테스트 전략

### 10.1 단위 테스트 (수동 QA 기반, 자동화 optional)

- `scan_tasks()` — 정상 state.json / JSON 파손 / 빈 디렉터리 / 권한 차단
- `scan_signals()` — 각 kind 별 파일 인식, 무관 파일 무시
- `list_tmux_panes()` — tmux 없음 / 서버 없음 / 정상
- `render_html()` — 빈 모델에서 예외 없이 HTML 생성

### 10.2 통합 시나리오 QA

1. 빈 프로젝트에서 기동 → `/` 가 "no tasks/features" 안내를 정상 렌더
2. `/dev-team` 실행 중 `/dev-monitor` 기동 → WBS 섹션·tmux 섹션·시그널 섹션 모두 채워짐
3. `/feat login` 실행 중 → Feature 섹션 채움
4. 고의로 state.json 손상 → 해당 Task만 ⚠️ 표시, 나머지 정상
5. 포트 충돌 재기동 → idempotent 재사용 안내

### 10.3 플랫폼 매트릭스

- macOS (`/tmp` + tmux) ✅
- Linux (`/tmp` + tmux) ✅
- WSL2 (`/tmp` + tmux) ✅
- Windows native (psmux + `%TEMP%`) — `detect_mux()` 가 psmux 인식, `capture-pane` 동작 확인

## 11. 관측성

- stderr 에 요청 라인 1건 출력 (`BaseHTTPRequestHandler.log_message` 재정의)
- 에러 발생 시 traceback 전체를 `${TMPDIR}/dev-monitor-{port}.log` 에 append
- 운영자용 `/healthz` 엔드포인트 추가 검토 (P2)

## 12. 마이그레이션 / 호환성

- 기존 스킬 수정 0건 — 모든 데이터는 이미 파일로 존재
- 플러그인 버전은 `1.5.0` 으로 minor bump (신규 기능 추가, 기존 동작 불변)
- 롤백: `scripts/monitor-server.py` + `skills/dev-monitor/` 제거만 하면 원상복구

## 13. 오픈 이슈 (PRD §8 연동)

| ID | 내용 | 결정 마감 |
|----|------|-----------|
| T1 | refresh 기본값 3s vs 5s | WBS 작성 전 |
| T2 | pane 캡처 기본 500 vs 1000 라인 | WBS 작성 전 |
| T3 | `--stop` / `--status` 서브커맨드 제공 여부 | WBS 작성 전 |
| T4 | `/api/state` 의 `phase_history_tail` 길이 | WBS 작성 전 |
| T5 | 다중 프로젝트 지원 — 현재는 단일(CWD)만 | v1.5 이후 논의 |

## 14. 참고

- 선행 PRD: `docs/monitor/prd.md`
- 상태 머신: `references/state-machine.json`
- 시그널 프로토콜: `references/signal-protocol.md`
- 플랫폼 유틸: `scripts/_platform.py`
- 기존 스킬 CLAUDE.md: 프로젝트 루트
