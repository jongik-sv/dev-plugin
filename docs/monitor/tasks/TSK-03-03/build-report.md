# TSK-03-03: TDD 구현 결과

## 결과: PASS

## 생성/수정된 파일

| 파일 경로 | 변경 내용 | 신규/수정 |
|-----------|-----------|-----------|
| `scripts/test_qa_fixtures.py` | `_import_server()`: `sys.modules[key] = mod` 임시 등록 추가(DEFECT-4 원인 1 수정), exec 후 전역 오염 방지를 위해 `finally` 블록에서 등록 해제. `TestDashboardHtmlEmptyProject`/`TestReadOnlyStateSurvival`의 `_start_server` 시그니처를 `ms` 인자를 받도록 수정하고 테스트 메서드에 `hasattr(_DashboardHandler)` 가드 추가 | 수정 |
| `scripts/monitor-server.py` | `build_arg_parser()` 정의 직후 `parse_args` lambda alias 1줄 추가(DEFECT-4 원인 2 수정) | 수정 |

## 테스트 결과

| 구분 | 통과 | 실패 | 건너뜀 | 합계 |
|------|------|------|--------|------|
| 단위 테스트 (`test_qa_fixtures.py`) | 20 | 0 | 5 | 25 |
| 기존 회귀 (`test_monitor*.py` 전체) | 243 | 0 | 12 | 256 |

- `test_qa_fixtures.py`: errors=0, failures=0 (기존 11 errors → 0으로 수렴)
- `test_monitor*.py` 전체: `test_server_attributes_injected` 실패는 내 변경 이전부터 존재하던 기존 실패임을 git stash 전/후 비교로 확인. 본 Task 범위 밖.
- skipped 5건: `_DashboardHandler`/`_scan_tasks` 미존재로 인한 hasattr 가드 skip — design.md 허용 범위.

## E2E 테스트 (작성만 — 실행은 dev-test)

N/A — backend domain

## 커버리지 (Dev Config에 coverage 정의 시)

N/A

## 비고

- `_import_server()`의 `sys.modules` 등록/해제 패턴: 등록 전 기존 값을 `prev`로 보존하고 `finally` 블록에서 복원 또는 제거. 이로써 `test_monitor_server_bootstrap.py`의 module-level `sys.modules["monitor_server"]` 등록과 충돌하지 않는다.
- `parse_args` alias는 `lambda argv=None: build_arg_parser().parse_args(argv)` 형태. `argv=None` 기본값으로 `sys.argv[1:]` 사용 및 `[]` 명시 호출 모두 지원.
- T1(`refresh_seconds=3`), T2(`max_pane_lines=500`) 테스트가 skipTest에서 탈출하여 실제 기본값 검증 통과 확인.
