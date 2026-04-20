# TSK-01-03: 시그널 및 tmux pane 스캔 (scan_signals, list_tmux_panes, capture_pane) - 설계

## 요구사항 확인
- `scan_signals()`로 `${TMPDIR}/claude-signals/` 재귀(scope=`shared`)와 `${TMPDIR}/agent-pool-signals-*` glob(scope=`agent-pool:{timestamp}`)을 합쳐 `SignalEntry` 리스트 반환. 확장자(`.running`/`.done`/`.failed`/`.bypassed`)로 kind 결정.
- `list_tmux_panes()`는 `shutil.which("tmux")`로 존재 확인 후 `tmux list-panes -a -F '...'` 실행(timeout=2). tmux 미설치 시 `None`, 서버 미기동 시 `[]` 반환.
- `capture_pane(pane_id)`는 `^%\d+$` 검증 후 `tmux capture-pane -t {id} -p -S -500`(timeout=3) 실행, ANSI escape sequence를 `re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', output)`로 제거.

## 타겟 앱
- **경로**: N/A (단일 앱)
- **근거**: 플러그인 레포 루트 `scripts/` 하위 단일 파일(`monitor-server.py`)에 누적 작성하는 구조 — `docs/monitor/wbs.md`의 backend design-guidance가 "단일 파일 스크립트" 관례를 명시함.

## 구현 방향
TSK-01-01에서 생성될 `scripts/monitor-server.py` 하단 헬퍼 영역에 모듈-레벨 함수 3개를 추가한다. 상태를 보관하지 않고 매 요청마다 on-demand 실행되는 순수 함수로 작성한다. `tempfile.gettempdir()`로 `${TMPDIR}`를 해석하고, 모든 `subprocess.run` 호출은 `shell=False`·list-form 인자·명시적 `timeout`을 강제한다. 데이터 클래스는 TRD §5.2/§5.3 스키마를 그대로 따르는 `@dataclass`로 정의한다. 예외는 정의된 실패 경로(디렉터리 없음, tmux 없음, 서버 없음, 잘못된 pane_id, subprocess 실패)에서 조용히 흡수하여 호출자가 분기 없이 사용할 수 있게 한다.

## 파일 계획

**경로 기준:** 모든 파일 경로는 **프로젝트 루트 기준**으로 작성한다. 단일 앱 프로젝트여도 루트 기준으로 작성한다.

| 파일 경로 | 역할 | 신규/수정 |
|-----------|------|-----------|
| `scripts/monitor-server.py` | `SignalEntry`/`PaneInfo` dataclass 정의 + `scan_signals()`, `list_tmux_panes()`, `capture_pane(pane_id)` 헬퍼 추가. import 보강: `re`, `glob`, `shutil`, `tempfile`, `subprocess`, `dataclasses.dataclass`, `datetime.datetime`/`timezone`. | 수정 (TSK-01-01 이후) |
| `scripts/test_monitor_signal_scan.py` | `scan_signals()` 유닛 테스트 — `tmp_path` 기반 임시 디렉터리에 4가지 kind 파일 + 무관 파일 생성 후 검증, 빈/부재 디렉터리 케이스 포함 | 신규 |
| `scripts/test_monitor_tmux.py` | `list_tmux_panes()`·`capture_pane()` 유닛 테스트 — `unittest.mock.patch`로 `shutil.which`/`subprocess.run`를 스텁하여 tmux 미설치/서버 없음/정상/존재하지 않는 pane id/`^%\d+$` 위반 경로 커버 | 신규 |

## 진입점 (Entry Points)

N/A (backend 도메인, UI 없음 — `domain: backend`)

## 주요 구조

- `SignalEntry` (`@dataclass`): `name: str`, `kind: str`, `task_id: str`, `mtime: str` (ISO-8601), `scope: str`. TRD §5.2 그대로.
- `PaneInfo` (`@dataclass`): `window_name, window_id, pane_id, pane_index, pane_current_path, pane_current_command, pane_pid, is_active`. TRD §5.3 그대로 (`pane_index: int`, `pane_pid: int`, `is_active: bool`, 나머지 `str`).
- `scan_signals() -> list[SignalEntry]`: `shared`(재귀)와 `agent-pool:{timestamp}`(glob) 두 경로를 병합. 디렉터리 부재 시 해당 경로는 스킵. 확장자가 네 kind 중 하나가 아니면 무시. `task_id`는 파일명 stem(`{id}.running` → `{id}`). mtime은 `datetime.fromtimestamp(os.path.getmtime(p), tz=timezone.utc).isoformat()`.
- `list_tmux_panes() -> list[PaneInfo] | None`: `shutil.which("tmux")` 없으면 `None`. 있으면 `subprocess.run(["tmux","list-panes","-a","-F", FMT], capture_output=True, text=True, timeout=2, check=False)`. stderr에 `no server running` 포함 시 `[]`. 성공 시 stdout을 `\n`으로 분리해 각 줄을 tab-split → `PaneInfo`.
- `capture_pane(pane_id: str) -> str`: `re.fullmatch(r'^%\d+$', pane_id)`로 형식 검증 — 실패 시 `ValueError`(핸들러가 400으로 매핑, TSK에서 "400 예정"으로 명시). `subprocess.run(["tmux","capture-pane","-t",pane_id,"-p","-S","-500"], capture_output=True, text=True, timeout=3, check=False)` 실행. `returncode != 0` 이면 stderr 문자열 그대로 반환(예외 X). 성공 시 stdout에 `re.sub(r'\x1b\[[0-9;]*[a-zA-Z]','',output)` 적용하여 반환.
- 상수: `_TMUX_FMT = '#{window_name}\t#{window_id}\t#{pane_id}\t#{pane_index}\t#{pane_current_path}\t#{pane_current_command}\t#{pane_pid}\t#{pane_active}'`, `_SIGNAL_KINDS = {"running","done","failed","bypassed"}`, `_PANE_ID_RE = re.compile(r'^%\d+$')`, `_ANSI_RE = re.compile(r'\x1b\[[0-9;]*[a-zA-Z]')`.

## 데이터 흐름

입력: 환경(`tempfile.gettempdir()`), tmux 서버 상태, pane_id(URL path) → 처리: 파일시스템 재귀/glob 스캔 + subprocess 호출 + 정규식 검증/스트립 → 출력: `list[SignalEntry]`, `list[PaneInfo] | None`, pane 캡처 문자열.

## 설계 결정 (대안이 있는 경우만)

- **결정**: `capture_pane`에서 `returncode != 0`일 때 stderr을 문자열로 반환(예외 X).
- **대안**: `subprocess.CalledProcessError` 를 그대로 전파하여 핸들러가 try/except.
- **근거**: TSK acceptance 기준 "존재하지 않는 pane id → subprocess 실패 메시지 반환(예외 X)"을 직접 만족. 핸들러 쪽 오류 경로가 한 갈래로 단순해짐(`ValueError` = 400, 나머지 = 200 + 에러 텍스트).

- **결정**: pane_id 형식 불일치 시 `ValueError` 발생.
- **대안**: `None` 반환 또는 빈 문자열.
- **근거**: TSK 명세 "pane_id 형식 검증: `^%\d+$` 정규식, 불일치 시 **400 예정**"을 핸들러와 공유하는 명확한 시그널. 200으로 빈 문자열을 흘리면 후속 Task가 400 매핑을 놓친다.

- **결정**: `scope="agent-pool:{timestamp}"`의 `{timestamp}`는 디렉터리명(`agent-pool-signals-{timestamp}`) 꼬리를 그대로 사용.
- **대안**: 디렉터리 mtime을 파싱.
- **근거**: `agent-pool` 스킬이 `{TEMP}/agent-pool-signals-{timestamp}-$$` 규약(CLAUDE.md)으로 timestamp를 이미 디렉터리명에 포함시킴. 디렉터리명 suffix를 그대로 사용하면 재해석 비용 0, 프로세스 PID 접미사까지 보존.

## 선행 조건

- TSK-01-01(`scripts/monitor-server.py` 뼈대 + argparse) 완료 전제. import 블록과 `if __name__ == "__main__"` 가 이미 존재해야 본 Task의 함수 3종을 얹을 수 있다.
- Python 3.8+ stdlib만 사용(`dataclasses`, `tempfile`, `shutil`, `subprocess`, `re`, `glob`, `datetime`, `os.path`). 외부 패키지 없음.

## 리스크

- **MEDIUM**: tmux pane의 `pane_current_path`·`pane_current_command`에 탭 문자가 들어가면 tab-split 이 어긋난다. TRD의 FMT는 탭 구분이므로 해당 필드는 tmux가 자체적으로 탭을 공백으로 렌더하지만, 사용자 쉘 PS1 설정이 개입하면 오염 가능. → 한 줄당 split(`\t`) 결과 길이가 8이 아니면 해당 줄 스킵(조용히 무시)으로 방어.
- **MEDIUM**: `${TMPDIR}/claude-signals/` 하위에 예측 외 확장자(`.tmp`, `.bypassed.lock` 등)가 있으면 현재 정책은 "무시". 반대로 `.DS_Store` 같은 숨김 파일도 확장자 필터로 자연 배제. → acceptance "무관 파일 무시" 와 일치.
- **LOW**: Windows psmux 환경에서도 `tmux` alias로 동작하지만, `shutil.which("tmux")` 가 `.bat`/`.exe` 확장자를 찾도록 `PATHEXT` 의존. 알려진 psmux 설치 기준으론 문제 없음.
- **LOW**: `tempfile.gettempdir()` 경로가 네트워크 마운트로 설정된 환경은 `CLAUDE.md`가 이미 금지. 기본 로컬 경로만 가정.

## QA 체크리스트

dev-test 단계에서 검증할 항목. 각 항목은 pass/fail로 판정 가능해야 한다.

- [ ] (정상) `${TMPDIR}/claude-signals/dev/TSK-01-02.done` 을 수동 생성 후 `scan_signals()` 호출 시 `SignalEntry(name="TSK-01-02.done", kind="done", task_id="TSK-01-02", scope="shared", mtime=<ISO-8601>)` 가 결과 리스트에 포함된다
- [ ] (정상) `${TMPDIR}/agent-pool-signals-20260420-123456-999/TSK-A.running` 생성 시 해당 엔트리의 `scope == "agent-pool:20260420-123456-999"` 이다
- [ ] (엣지) `scan_signals()` 호출 전에 `${TMPDIR}/claude-signals/` 자체를 삭제해도 예외 없이 `[]` 반환(shared 경로 부재 시 agent-pool 경로 결과만 반환)
- [ ] (엣지) 확장자가 `.running`/`.done`/`.failed`/`.bypassed`가 아닌 파일(`TSK-X.log`, `.DS_Store`)은 결과에 포함되지 않는다
- [ ] (정상) tmux 설치된 환경에서 활성 세션이 있을 때 `list_tmux_panes()` 가 `list[PaneInfo]` 를 반환하며 각 항목의 `pane_id` 가 `^%\d+$` 를 만족한다
- [ ] (에러) `shutil.which("tmux")` 가 `None` 인 환경(mock)에서 `list_tmux_panes()` 가 `None` 을 반환한다(빈 리스트 아님)
- [ ] (에러) tmux 설치됐으나 서버 미기동 상태(mock: stderr="no server running on ...")에서 `list_tmux_panes()` 가 `[]` 를 반환하고 예외를 발생시키지 않는다
- [ ] (에러) `capture_pane("notapane")` 호출 시 `ValueError` 가 발생한다(`^%\d+$` 미준수)
- [ ] (에러) `capture_pane("%9999")` (존재하지 않는 pane) 호출 시 예외 없이 tmux stderr 메시지 문자열이 반환된다
- [ ] (정상) `capture_pane("%1")` 결과에서 ANSI escape sequence(`\x1b[31m` 등)가 모두 제거됐는지 — 모의 stdout `"A\x1b[31mB\x1b[0mC"` 입력 시 `"ABC"` 가 반환된다
- [ ] (보안) 모든 `subprocess.run` 호출이 `shell=False`(list-form) 이고, `list_tmux_panes` 는 `timeout=2`, `capture_pane` 은 `timeout=3` 으로 호출되는지 — `unittest.mock.patch('subprocess.run')` 의 call_args 로 검증
- [ ] (통합) TSK-01-04(=JSON 직렬화) 에서 `SignalEntry`/`PaneInfo` 가 `dataclasses.asdict()` 로 문제 없이 직렬화 가능하다(필드명이 TRD §5.2/§5.3 과 일치)
