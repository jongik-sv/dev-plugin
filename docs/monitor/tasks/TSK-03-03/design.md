# TSK-03-03: test_qa_fixtures 하네스 회귀 수정 (DEFECT-4 후속) - 설계

## 요구사항 확인
- `scripts/test_qa_fixtures.py`의 `_import_server()` 함수가 `sys.modules`에 모듈을 등록하지 않아 `@dataclass` 처리 시 `sys.modules.get(cls.__module__)`이 None 반환 → 11 errors 발생. 등록 순서를 정석 패턴(`sys.modules[key] = mod` 후 `exec_module`)으로 수정해야 한다.
- `monitor-server.py`에 `parse_args` 함수가 없고 `build_arg_parser`로 리네임된 상태. 하네스 T1/T2 테스트가 `skipTest` 처리되어 실제 기본값 검증이 이루어지지 않는다. `monitor-server.py`에 `parse_args` alias를 추가(1줄)하여 하네스 코드를 수정하지 않고 해결한다.
- 25 tests 전부 errors=0/failures=0으로 pass, 기존 240건 `test_monitor*.py` 회귀 없음.

## 타겟 앱
- **경로**: N/A (단일 앱)
- **근거**: 단일 Python 스크립트 프로젝트, 앱 분리 구조 없음.

## 구현 방향
- `scripts/test_qa_fixtures.py`의 `_import_server()` 함수(line 32-42): `module_from_spec(spec)` 이후, `exec_module(mod)` 호출 전에 `sys.modules[key] = mod`를 삽입한다. 이것이 정석 `importlib.util` 3단계 로딩 패턴이며, `@dataclass` decorator가 `cls.__module__`로 `sys.modules`를 조회할 때 None이 아닌 올바른 모듈 딕셔너리를 얻는다.
- `scripts/monitor-server.py`의 `build_arg_parser()` 정의 직후(line 1802 이후): `parse_args = lambda argv=None: build_arg_parser().parse_args(argv)` alias 1줄 추가. 하네스의 `ms.parse_args([])` 호출 패턴을 그대로 수용하고, 기존 `main()` 내 `build_arg_parser()` 직접 호출 경로는 변경하지 않는다.
- 두 수정 모두 stdlib only, 신규 의존성 없음.

## 파일 계획

**경로 기준:** 모든 파일 경로는 **프로젝트 루트 기준**으로 작성한다.

| 파일 경로 | 역할 | 신규/수정 |
|-----------|------|-----------|
| `scripts/test_qa_fixtures.py` | `_import_server()` 내 `sys.modules[key] = mod` 삽입 (DEFECT-4 원인 1 수정) | 수정 |
| `scripts/monitor-server.py` | `build_arg_parser()` 정의 직후 `parse_args` alias 1줄 추가 (DEFECT-4 원인 2 수정) | 수정 |

## 진입점 (Entry Points)

N/A — domain=backend. UI 없음.

## 주요 구조

- **`_import_server()` (test_qa_fixtures.py, line 32-42)**: `importlib.util` 정석 3단계 패턴 — `spec_from_file_location` → `module_from_spec` → `sys.modules[key] = mod` → `exec_module(mod)` 순서 적용. 기존에는 3번째 단계(`sys.modules` 등록)가 누락되어 있었다.
- **`parse_args` alias (monitor-server.py, build_arg_parser 정의 직후)**: `parse_args = lambda argv=None: build_arg_parser().parse_args(argv)`. 하네스가 `hasattr(ms, "parse_args")` 로 존재 여부를 확인하므로 이 alias가 있어야 skipTest에서 탈출하고 실제 기본값 검증이 실행된다.
- **T1/T2 테스트 (test_qa_fixtures.py)**: `ms.parse_args` alias가 생기면 `hasattr` 분기가 True → skipTest 탈출 → `refresh_seconds=3`, `max_pane_lines=500` 검증 실행.
- **`_scan_tasks` / `_DashboardHandler` 참조 (하네스)**: 실제 모듈에는 `scan_tasks` / `MonitorHandler`로 정의되어 있어 `hasattr` 가드에 의해 계속 skipTest 처리됨 — errors=0 요건 충족이면 이 skip은 허용 범위(본 Task 범위 밖).

## 데이터 흐름
`spec_from_file_location` → `module_from_spec` → `sys.modules[key] = mod` (신규) → `exec_module(mod)` → `@dataclass` decorator가 `sys.modules[cls.__module__].__dict__` 조회 성공 → 모듈 정상 반환 → 하네스 테스트가 `parse_args` alias를 통해 기본값 검증 실행.

## 설계 결정 (대안이 있는 경우만)

- **결정**: `monitor-server.py`에 `parse_args` alias를 추가 (서버 파일 수정)
- **대안**: 하네스(`test_qa_fixtures.py`)의 `ms.parse_args([])` 호출부를 `ms.build_arg_parser().parse_args([])`로 전환 (하네스 수정)
- **근거**: PRD constraints "monitor-server.py 공개 API 변경 최소화 (alias 수준)"가 alias 추가를 명시적으로 허용하며, 서버에 alias를 두면 다른 테스트 파일이 동일 패턴으로 호출할 때도 일관성이 유지된다.

## 선행 조건
- TSK-01-09 완료 (wbs `depends` 필드) — `monitor-server.py`의 `build_arg_parser()` 함수가 존재하고 정상 동작해야 함 (현재 확인됨, line 1748).
- 기존 240건 `test_monitor*.py` 테스트가 OK 상태임 (수정 전 기준선 확인됨).

## 리스크
- LOW: `parse_args` lambda alias는 `argv=None` 기본값을 처리해야 함. `argparse.ArgumentParser.parse_args(None)`은 `sys.argv[1:]`을 사용 — 테스트는 `[]`로 명시 호출하므로 문제 없음.
- LOW: `sys.modules[key] = mod` 삽입 후, `_import_server()` 선두의 `del sys.modules[key]` 코드(line 35-36)가 이미 있어 반복 호출 시 중복 등록 문제 없음.
- LOW: `_scan_tasks` / `_DashboardHandler` 미존재로 인한 skip 테스트들은 본 Task 완료 후에도 skip 유지 — errors=0 요건을 충족하면 허용.

## QA 체크리스트
dev-test 단계에서 검증할 항목.

- [ ] `python3 scripts/test_qa_fixtures.py` 실행 결과 `errors=0, failures=0` (25 tests 전부 pass 또는 skip)
- [ ] `TestT1RefreshSeconds.test_default_refresh_seconds_is_3` — `parse_args([])` 결과 `refresh_seconds == 3` pass (skipTest 탈출 확인)
- [ ] `TestT2MaxPaneLines.test_default_max_pane_lines_is_500` — `parse_args([])` 결과 `max_pane_lines == 500` pass (skipTest 탈출 확인)
- [ ] `TestT1RefreshSeconds.test_custom_refresh_seconds` — `parse_args(["--refresh-seconds", "10"])` 결과 `refresh_seconds == 10` pass
- [ ] `TestT2MaxPaneLines.test_custom_max_pane_lines` — `parse_args(["--max-pane-lines", "1000"])` 결과 `max_pane_lines == 1000` pass
- [ ] `TestDashboardHtmlEmptyProject.test_empty_project_html_contains_no_tasks_message` — AttributeError 없이 pass 또는 skip
- [ ] `TestReadOnlyStateSurvival.test_server_survives_readonly_state` — AttributeError 없이 pass 또는 skip
- [ ] `TestScanTasksWithCorruptedState` 테스트들 — AttributeError 없이 pass 또는 skip
- [ ] `python3 -m unittest discover -s scripts -p "test_monitor*.py" -v` → 기존 240건 회귀 없음 (OK 유지)
- [ ] `monitor-server.py`의 기존 `main()` 함수가 `build_arg_parser()` 직접 호출로 정상 동작 (alias 추가 후 기존 경로 변경 없음)
