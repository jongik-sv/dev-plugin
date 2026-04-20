# TSK-01-03: TDD 구현 결과

## 결과: PASS

## 생성/수정된 파일

| 파일 경로 | 변경 내용 | 신규/수정 |
|-----------|-----------|-----------|
| `scripts/monitor-server.py` | 최소 스켈레톤 + `SignalEntry`/`PaneInfo` dataclass(TRD §5.2/§5.3), `_SIGNAL_KINDS`/`_TMUX_FMT`/`_PANE_ID_RE`/`_ANSI_RE` 상수, `_iso_mtime()`/`_signal_entry()` 내부 헬퍼, `scan_signals()`/`list_tmux_panes()`/`capture_pane()` 공개 API 추가 | 신규 (TSK-01-02 design.md line 174 "파일 없으면 최소 shebang + `if __name__ == \"__main__\":` 골격 생성" 조항 적용 — TSK-01-01이 후속으로 HTTP 뼈대를 채움) |
| `scripts/test_monitor_signal_scan.py` | `scan_signals()` 유닛 테스트 — `tempfile.TemporaryDirectory` + `mock.patch.object(MS.tempfile, "gettempdir")`로 격리. 공유 scope/agent-pool scope/재귀/미등록 확장자 무시/디렉터리 부재/scope 병합/`SignalEntry` 필드 shape 등 9 케이스 | 신규 |
| `scripts/test_monitor_tmux.py` | `list_tmux_panes()`·`capture_pane()` 유닛 테스트 — `mock.patch.object(MS.shutil, "which")` + `mock.patch.object(MS.subprocess, "run")`. tmux 미설치(`None`), 서버 미기동(`[]`), 정상/비활성/malformed 라인, TimeoutExpired, pane_id 형식 위반 4종 ValueError, 존재하지 않는 pane 처리, ANSI 제거(단순/복합), subprocess 인자 검증(`shell=False`, `timeout`), `PaneInfo` 필드 shape 등 17 케이스 | 신규 |

## 테스트 결과

| 구분 | 통과 | 실패 | 합계 |
|------|------|------|------|
| 단위 테스트 | 26 | 0 | 26 |

실행 명령: `python3 -m unittest scripts.test_monitor_signal_scan scripts.test_monitor_tmux -v`
(Dev Config `backend.unit_test` = `python3 -m unittest discover -s scripts -p "test_monitor*.py" -v` — 동일 테스트 파일 두 개가 매칭됨.)

TDD 순서 검증:
- **Red**: `monitor-server.py` 부재 상태에서 두 테스트 모듈 모두 `FileNotFoundError`로 로드 실패 확인 (discover 결과 Ran 2, errors=2).
- **Green**: `monitor-server.py` 생성 후 26/26 PASS.

## E2E 테스트 (작성만 — 실행은 dev-test)

| 파일 경로 | 검증 대상 |
|-----------|-----------|
| N/A — backend domain | — |

`{DOMAIN}=backend`이므로 tdd-prompt-template.md "domain별 테스트 > E2E" 게이트에 의해 생략. Dev Config `backend.e2e_test` 도 `null`.

## 커버리지 (Dev Config에 coverage 정의 시)

- 커버리지: N/A (Dev Config `quality_commands`에 `coverage` 미정의, `lint`만 존재)
- 미커버 파일: N/A
- 정적 검증: `python3 -m py_compile scripts/monitor-server.py` → PASS.

## 비고

### 선행 조건 처리
- **TSK-01-01 미완료 상태에서 선제 적용**: design.md "선행 조건"은 TSK-01-01이 HTTP 뼈대를 먼저 만든다고 가정하지만 `docs/monitor/tasks/TSK-01-01/`이 아직 존재하지 않는다. TSK-01-02 design.md line 174의 완화책("dev-build 단계에서 파일 존재 여부를 먼저 확인하고, 없으면 최소 shebang + `if __name__ == \"__main__\":` 골격을 만들어 TSK-01-01이 나중에 본문을 채울 수 있도록 한다")을 그대로 적용하여 `scripts/monitor-server.py` 를 신규 생성. 골격 영역은 `# Entry point (skeleton — real CLI arrives with TSK-01-01)` 주석으로 명시하였으므로 TSK-01-01 빌드 시 argparse+HTTPServer 코드가 동일 블록을 대체하면 됨.

### design.md 기준 QA 체크리스트 매핑

| QA 체크리스트 | 대응 테스트 |
|---|---|
| shared `scope`/`kind`/`task_id` | `test_done_signal_in_shared_dir` |
| agent-pool scope tagging | `test_agent_pool_scope_tagging` |
| `claude-signals/` 부재 → `[]` | `test_missing_claude_signals_dir_returns_empty` |
| 무관 확장자 무시 | `test_unknown_extension_ignored` |
| `shutil.which("tmux") is None` → `None` | `test_returns_none_when_tmux_missing` |
| 서버 미기동 → `[]` | `test_returns_empty_when_no_server_running` |
| `capture_pane("notapane")` → `ValueError` | `test_raises_value_error_for_invalid_pane_id` (+ 3개 형식 위반 베리에이션) |
| 존재하지 않는 pane → stderr 문자열 | `test_returns_stderr_string_for_nonexistent_pane` |
| ANSI escape 제거 (`\x1b[31mB\x1b[0m` → `B`) | `test_strips_ansi_escape_sequences` + `test_strips_complex_ansi` |
| `shell=False`, `timeout=2`/`timeout=3` | `test_subprocess_run_kwargs_timeout_and_shell_false` (각 함수별 1건) |
| `SignalEntry`/`PaneInfo` → `dataclasses.asdict()` 직렬화 호환 (TSK-01-04 통합) | `test_asdict_round_trip`, `test_fields_match_trd` (`SignalEntry` + `PaneInfo`) |
| tmux 설치됐을 때 실제 `^%\d+$` pane_id 확인 | dev-test에서 실환경 검증 (본 Task는 mock 기반) |

### 추가 테스트 (QA 체크리스트 밖)

- `test_recursive_scan_claude_signals` — 다단계 하위 디렉터리(`claude-signals/proj/wp-01/`)까지 `os.walk`로 재귀되는지 명시 검증. TSK 요구사항 "재귀 스캔"의 회귀 방지.
- `test_multiple_agent_pool_dirs` — 여러 agent-pool 인스턴스가 공존할 때 scope가 디렉터리별로 독립 태깅되는지 검증.
- `test_shared_and_agent_pool_combined` — 두 경로가 동시에 존재할 때 결과 리스트가 merge 되면서 scope 구분이 유지되는지.
- `test_parses_inactive_pane` / `test_malformed_line_is_skipped` — 8열 format string의 경계 케이스. design.md 리스크 섹션의 "pane_current_path에 탭 포함" 방어(설계 line 63) 검증.
- `test_subprocess_timeout_expired_returns_empty_list` / `test_timeout_expired_returns_stderr_like_message` — `TimeoutExpired`가 호출자로 전파되지 않는지. acceptance "subprocess 실패 메시지 반환(예외 X)" 동일 정신 적용.
- 이유: `CLAUDE.md` "동작 보존의 기준선" 원칙 — refactor 단계에서 관찰 가능한 동작(exception-free 계약, subprocess 인자 등)을 고정하기 위해 QA보다 엄격한 경계를 두었다.

### 사전 존재한 무관 파일

- `scripts/test_monitor_scan.py` (untracked, TSK-01-02 스코프) — 본 빌드 전부터 워크트리에 남아 있던 파일. 자체 테스트 하네스가 `sys.modules[_spec.name] = module` 등록을 생략해 Python 3.9 dataclass `__module__` 해석 버그(`AttributeError: 'NoneType' object has no attribute '__dict__'`)를 유발함. TSK-01-03 범위 밖이므로 **수정하지 않음**. TSK-01-02 빌드 시 해당 Task가 본인의 test harness를 수정해 해결할 사안. `python3 -m unittest discover -s scripts -p "test_monitor*.py" -v` 실행 시 이 모듈 로드 실패가 Ran 27 중 errors=1로 보고되지만 TSK-01-03의 26 케이스는 모두 PASS (격리 실행으로 재확인).

### 구현 결정

- `_signal_entry()` 내부 헬퍼로 shared/agent-pool 두 경로의 엔트리 생성을 통합하여 DRY 원칙 적용. 확장자·task_id 분해와 mtime 포매팅을 한 곳에 고정.
- `_iso_mtime()` 도 별도 분리 — `os.path.getmtime` 실패 시 빈 문자열을 반환해 scan이 예외 없이 계속 진행되도록 함. design.md "디렉터리 자체 없음 → `[]` (예외 X)" acceptance를 파일 레벨 장애에도 확장 적용.
- `list_tmux_panes()`는 `returncode != 0`일 때 stderr 내용을 조건 분기하지 않고 일괄 `[]`로 통일 — "no server running" 문자열 매칭은 설계 line 34의 가이드이지만, 다른 이유의 비정상 종료(권한, 바이너리 크래시)에서도 동일한 exception-free 계약을 유지하기 위해 broader fallback 채택. ("no server running" 분기는 테스트로 명시 커버.)
- `capture_pane()`의 `TimeoutExpired` 핸들링은 stderr 문자열과 동일 포맷의 사람-가독 메시지(`"tmux capture-pane timed out after 3s for %X"`)를 반환 — UI에서 별도 분기 없이 그대로 렌더 가능.

### 제약 준수

- 모든 `subprocess.run` 은 list-form 명령 + `shell=False` + 명시적 `timeout`(list는 2초, capture는 3초). `test_subprocess_run_kwargs_timeout_and_shell_false` 2건으로 검증.
- Python 3.8+ stdlib 전용 (`glob`, `os`, `re`, `shutil`, `subprocess`, `tempfile`, `dataclasses`, `datetime`, `typing`) — 외부 패키지 없음.
- `tempfile.gettempdir()` 로 플랫폼별 TMPDIR 흡수 — Windows psmux 분기 불필요(CLAUDE.md 규약 준수).
- 파일 쓰기는 없음. 모든 파일 접근은 read-only.
