# TSK-01-06: TDD 구현 결과

## 결과: PASS

## 생성/수정된 파일

E2E 테스트는 backend 도메인이므로 작성 대상 없음.

| 파일 경로 | 변경 내용 | 신규/수정 |
|-----------|-----------|-----------|
| `scripts/monitor-server.py` | `/api/state` 엔드포인트 헬퍼 추가: 상수 `_API_STATE_PATH`, 라우트 매칭 `_is_api_state_path(path)`, 직렬화 헬퍼 `_asdict_or_none(value)`, 스냅샷 조립 순수 함수 `_build_state_snapshot(project_root, docs_dir, scan_tasks, scan_features, scan_signals, list_tmux_panes)`, JSON 응답 헬퍼 `_json_response(handler, status, payload)` / `_json_error(handler, status, message)`, 핸들러 엔트리 `_handle_api_state(handler, *, scan_tasks=..., scan_features=..., scan_signals=..., list_tmux_panes=...)`. import에 `sys`/`asdict`/`is_dataclass`/`Any`/`Callable`/`urlsplit` 추가. `__main__` placeholder의 `import sys` 중복 제거(상단에서 이미 import). | 수정 |
| `scripts/test_monitor_api_state.py` | `_build_state_snapshot`·`_asdict_or_none`·`_json_response`·`_json_error`·`_handle_api_state`·`_is_api_state_path` 단위 테스트 (33개 케이스 중 1개는 `MonitorHandler` 통합 forward-compat skipTest). 성능 어서션 포함 (100 WorkItem × 10 phase tail + 20 pane + 50 signal 입력이 0.5초 이내). | 신규 |

## 테스트 결과

| 구분 | 통과 | 실패 | 합계 |
|------|------|------|------|
| 단위 테스트 (전체 `test_monitor*.py`) | 100 | 0 | 106 (skipped=6) |
| 단위 테스트 (본 Task `test_monitor_api_state.py`) | 32 | 0 | 33 (skipped=1) |

실행 명령 (wbs.md Dev Config backend 도메인):
```
python3 -m unittest discover -s scripts -p "test_monitor*.py" -v
```
결과: `Ran 106 tests in 0.118s — OK (skipped=6)`.

Red→Green 확인: 신규 함수 6개가 부재한 초기 상태에서 `AttributeError` 31건 발생, 구현 후 모두 통과. `_json_response` Content-Length 어서션 오류 1건(테스트 쪽 기대값이 `json.dumps` 기본 separator의 `": "` 공백 미반영)을 한 차례 수정 후 Green.

### 품질 검증 (Dev Config `quality_commands.lint`)

| 명령 | 결과 |
|------|------|
| `python3 -m py_compile scripts/monitor-server.py` | OK |

Dev Config에 `typecheck` / `coverage` 정의 없음.

## E2E 테스트 (작성만 — 실행은 dev-test)

| 파일 경로 | 검증 대상 |
|-----------|-----------|
| N/A — backend domain | design.md QA 체크리스트 중 라이브 HTTP (`urllib.request.urlopen`) / `curl + json.tool` 는 TSK-01-02 의 HTTP 서버 스켈레톤 병합 이후 `scripts/test_monitor_e2e.py` 범위에서 검증 예정. backend 단일 도메인에서는 단위 테스트만 실행. |

acceptance 1 (`curl http://localhost:7321/api/state | python3 -m json.tool`) 은 HTTP 바인딩(TSK-01-02) 의존이므로 본 Task 단위 테스트 범위 밖. 동일 데이터 경로를 `PerformanceTests.test_build_and_dumps_under_500ms` 및 `SnapshotJsonSerializationTests` 로 커버 — `json.dumps(payload, default=str, ensure_ascii=False)` 의 결과가 `json.loads` 로 왕복 가능함을 확인.

## 커버리지 (Dev Config에 coverage 정의 시)
- 커버리지: N/A — `wbs.md ## Dev Config > Quality Commands > coverage` 가 `-` 로 명시됨
- 미커버 파일: N/A

## 비고

- **Dependency injection 유지**: design.md §3 이 정한 순수 함수 시그니처(`_build_state_snapshot(project_root, docs_dir, scan_tasks, scan_features, scan_signals, list_tmux_panes)`) 를 그대로 구현했다. 스캐너 4종을 인자로 주입받으므로 HTTP 스택 없이 단위 테스트 가능.
- **MonitorHandler 미존재 대응**: 선행 조건인 TSK-01-02 는 `[im]` 상태(build.ok 도달, refactor 미완) 이며 monitor-server.py 에 아직 `MonitorHandler` 클래스가 없다. 본 Task 는 설계대로 **라우팅 보조 함수 `_is_api_state_path` 와 핸들러 엔트리 `_handle_api_state` 를 독립 모듈 레벨 함수로 노출**했다. TSK-01-02 의 refactor (또는 TSK-01-01 의 HTTP bootstrap) 에서 `MonitorHandler.do_GET` 내부 if/elif 분기가 `_is_api_state_path(path)` 를 호출하고 `_handle_api_state(self)` 로 위임하도록 배선되면 라우트 통합이 완료된다. forward-compat 테스트(`MonitorHandlerRoutingTests`) 는 클래스 부재 시 `skipTest` 하도록 구성.
- **`_handle_api_state` 기본 인자 바인딩**: 함수 기본값은 `def` 평가 시점의 모듈 전역 `scan_tasks`/`scan_features`/`scan_signals`/`list_tmux_panes` 에 대한 단일 참조를 캡처한다. TSK-01-02 에서 추후 동일 이름 전역이 재정의되어도 본 함수의 기본값은 변경되지 않지만, 테스트/실전 호출자가 kw 인자로 명시 주입하면 의존성 역전이 유지된다.
- **라우팅 우선순위**: design.md §1 의 매칭 순서표(`/api/state → /api/pane/ → /pane/ → /` → 404) 의 최종 강제는 `MonitorHandler.do_GET` 소유 Task(TSK-01-02) 가 수행한다. 본 Task 는 `_is_api_state_path` 만 제공하며 상대적 순서를 강제하지 않는다 — 설계 §1 의 "라우터 역할은 do_GET 내부 if/elif 분기에서 수행된다" 문구와 일치.
- **테스트 추가 이유 (QA 체크리스트 외)**: `test_scan_functions_receive_docs_dir`, `test_phase_tail_limit_constant_is_10`, `test_json_error_supports_404_status`, `AsdictOrNoneTests` 5개 — design.md QA 체크리스트가 주로 snapshot 결과만 검증하므로, 의존성 주입 계약(스캐너가 docs_dir 을 받는지) 과 `_asdict_or_none` 4가지 입력 유형의 내부 분기를 리팩터 회귀 방어 목적으로 추가.
- **`is_dataclass` 안전장치**: `_asdict_or_none` 은 `is_dataclass(x) and not isinstance(x, type)` 로 dataclass 클래스 객체 자체가 잘못 들어올 때 발생할 `TypeError` 를 차단하고 원본을 반환한다.
- **`sys` 중복 import 제거**: 기존 `__main__` 블록이 함수 내부에서 `import sys` 했으나 본 Task 에서 모듈 최상단 import 에 `sys` 를 추가했으므로 중복 제거. 동작 변경 없음.
