# TSK-01-06: 리팩토링 내역

## 변경 사항

| 파일 | 변경 내용 (요약) | 적용 기법 (콤마 구분) |
|------|-----------------|----------------------|
| `scripts/monitor-server.py` | `_asdict_or_none` 내부의 `is_dataclass(x) and not isinstance(x, type)` 중복 조건을 `_is_dataclass_instance(value)` 헬퍼로 추출. dataclass 인스턴스 판정의 의도를 이름으로 드러내고 list-element 분기와 single-value 분기가 동일 규칙임을 명시. | Extract Method, Remove Duplication |
| `scripts/monitor-server.py` | `_build_state_snapshot` 내부에 인라인으로 있던 `generated_at` 조립(`datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00","Z")`)을 `_now_iso_z()` 헬퍼로 추출. TRD §4.1의 "ISO-Z" 계약을 단일 지점에 고정하고 후속 Task가 동일 포맷을 필요로 할 때 재사용 가능. | Extract Method |
| `scripts/monitor-server.py` | signal scope 분류 루프(shared/agent-pool 분기)를 `_classify_signal_scopes(signals) -> (shared, agent_pool)` 헬퍼로 추출. prefix 문자열 `"agent-pool:"`를 모듈 상수 `_AGENT_POOL_SCOPE_PREFIX` 로 이름 부여하여 매직 스트링 제거. `_build_state_snapshot` 본문이 "스캔 → 분류 → 조립" 세 단계로 평탄화됨. | Extract Method, Replace Magic String |
| `scripts/monitor-server.py` | `_handle_api_state` 의 이중 `getattr(getattr(handler, "server", None), name, "") or ""` 패턴을 `_server_attr(handler, name)` 헬퍼로 추출. project_root/docs_dir 두 속성 읽기가 한 줄로 축소되고 `str()` 변환까지 헬퍼가 흡수. 기존 속성 방어 동작(missing attr → ""), 공백값 처리는 그대로 유지. | Extract Method, Remove Duplication |

**변경 없음 항목**: `_json_response` / `_json_error` / `_is_api_state_path` 는 이미 단일 책임이며 리팩터 여지 미발견. 상수 `_API_STATE_PATH` 는 그대로 유지.

## 테스트 확인
- 결과: PASS
- 실행 명령: `python3 -m unittest discover -s scripts -p "test_monitor*.py" -v`
- 결과 요약: `Ran 106 tests in 0.052s — OK (skipped=6)` — 리팩터 전후 동일. 실패 0건, 되돌림 없음.
- 추가 검증 (Dev Config `quality_commands.lint`): `python3 -m py_compile scripts/monitor-server.py` → OK.

## 비고
- 케이스 분류 (SKILL.md 단계 3 참조): **A (리팩토링 성공)** — 동작 보존 상태로 품질 개선 적용.
- **기존 테스트가 신규 헬퍼 4종을 우회적으로 전부 커버**:
  - `_is_dataclass_instance` ← `AsdictOrNoneTests` 5개 케이스가 dataclass/list/None/scalar 모든 분기 검증
  - `_now_iso_z` ← `BuildStateSnapshotTests.test_generated_at_is_utc_iso_z_format` 가 `^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$` 정규식으로 포맷 fix
  - `_classify_signal_scopes` ← `test_scope_split_shared_and_agent_pool` + `test_unknown_scope_lands_in_shared_signals_conservatively` 가 shared/agent-pool/unknown 3가지 scope 분기 모두 검증
  - `_server_attr` ← `HandleApiStateTests.test_missing_server_attrs_use_defensive_defaults` + `test_success_returns_200_and_json_body` 가 missing/정상 속성 두 경로 검증
  신규 테스트 추가 없이도 회귀 방어가 충분하므로 test 파일 변경 없음.
- **행동 보존 근거**: (1) `_is_dataclass_instance` 는 기존 인라인 조건과 bit-exact 동치. (2) `_now_iso_z` 는 기존 인라인 표현의 순수 추출. (3) `_classify_signal_scopes` 는 루프 본문을 그대로 옮겼고 shared/agent-pool 판정 순서·기본값(unknown→shared) 동일. (4) `_server_attr` 은 기존 이중 getattr 체인을 단일 호출로 압축하되 `server=None`·missing attr·blank value·non-str value 네 경로 모두 동일 출력 보장 (`str(value)`로 강제 문자열화는 기존 명시 호출 `str(project_root)` 과 동치).
- **선행 Task 의존성 무변경**: TSK-01-02(MonitorHandler) 미완 상태에서 `MonitorHandlerRoutingTests` 1건이 skipTest 처리되는 것은 baseline 과 동일 (6 skipped 유지).
- **성능 영향 없음**: `PerformanceTests.test_build_and_dumps_under_500ms` 통과 — 헬퍼 분리로 인한 함수 호출 오버헤드는 100 WorkItem × 10 phase tail + 20 pane + 50 signal 입력 기준에서 무시 가능 수준이며 0.5초 임계 미도달을 전후 동일하게 확인.
