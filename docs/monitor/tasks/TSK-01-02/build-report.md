# TSK-01-02: TDD 구현 결과

## 결과: PASS

## 생성/수정된 파일

| 파일 경로 | 변경 내용 | 신규/수정 |
|-----------|-----------|-----------|
| `scripts/monitor-server.py` | `WorkItem`/`PhaseEntry` dataclass + `scan_tasks()`/`scan_features()` + 헬퍼(`_read_state_json`, `_build_phase_history_tail`, `_load_wbs_title_map`, `_load_feature_title`, `_make_workitem_from_*`) 추가. 상단 import에 `json`, `pathlib.Path`, `Tuple`, `field` 보강. 기존 TSK-01-03 영역(`scan_signals`·tmux 함수)은 그대로 보존 — 설계의 "같은 파일 머지 충돌" 완화 전략대로 `# --- scan functions (TSK-01-02) ---` 블록 주석으로 영역 분리 | 수정 |
| `scripts/test_monitor_scan.py` | TSK-01-02 단위 테스트 모듈 — QA 체크리스트 13개 항목 + 통합 케이스 커버. importlib로 `monitor-server.py`(하이픈) 로드, Python 3.9 dataclass type 해석을 위해 `sys.modules["monitor_server"]` 사전 등록 | 신규 |

## 테스트 결과

| 구분 | 통과 | 실패 | 합계 |
|------|------|------|------|
| 단위 테스트 (scripts.test_monitor_scan) | 18 | 0 | 18 |
| 단위 테스트 (discover 전체: scan + signal_scan + tmux) | 44 | 0 | 44 |

### 커버된 QA 체크리스트 항목 매핑

| QA 항목 | 테스트 케이스 |
|---------|---------------|
| 정상 — WBS | `ScanTasksNormalTests.test_scan_tasks_returns_single_workitem` |
| 정상 — Feature | `ScanFeaturesNormalTests.test_scan_features_uses_spec_first_nonempty_line_as_title` |
| 정상 + 손상 혼재 (acceptance 1) | `ScanMixedValidCorruptTests.test_valid_and_corrupt_are_both_returned` |
| 빈 디렉터리 (acceptance 2) | `ScanEmptyDirectoryTests.*` (3건: missing/empty/features-missing) |
| 1MB 초과 (acceptance 3) | `ScanOversizeTests.test_file_larger_than_1mb_is_rejected` + 경계값 1MB 정확 허용 |
| 읽기 권한 0o444 (constraint) | `ScanReadOnlyTests.test_scan_tasks_works_on_0o444_state_json` |
| wbs.md 부재 | `WbsTitleMapTests.test_wbs_md_missing_yields_none_title` |
| phase_history 슬라이스 경계 | `PhaseHistorySliceTests.test_history_length_boundaries` (0/5/10/11/100) + `test_last_ten_preserved_not_first_ten` |
| bypassed 플래그 | `BypassAndLastBlockTests.test_bypassed_flag_roundtrips` |
| last 블록 | `BypassAndLastBlockTests.test_last_block_missing_yields_none` + 정상 케이스에서 last_event/at 검증 |
| depends 파싱 | `WbsTitleMapTests.test_title_wp_depends_are_populated_from_wbs_md` (단일·복수·`-` 모두) |
| raw_error 500B 상한 | `RawErrorCapTests.test_raw_error_max_length_500` |
| 파일 mode 검증 | `OpenModeReadOnlyTests.test_no_write_mode_open_calls` — 정규식으로 write/append/exclusive/plus mode 탐지 |
| 통합 | `IntegrationTests.test_mixed_wbs_feat_corrupt` (2 정상 + 1 손상 + 1 feat = 총 4) |

## E2E 테스트 (작성만 — 실행은 dev-test)

| 파일 경로 | 검증 대상 |
|-----------|-----------|
| N/A — backend domain | (fullstack/frontend이 아니므로 E2E 불필요) |

## 커버리지 (Dev Config에 coverage 정의 시)

- 커버리지: N/A (Dev Config의 `coverage` = `-` 미정의)
- 미커버 파일: N/A
- 미정의 시 "N/A" 기록

## 비고

- **같은 파일 병행 Task와의 공존**: 이 Task를 처음 시작했을 때 `scripts/monitor-server.py` 는 존재하지 않았으나 설계 단계 이후 병렬 Task(TSK-01-03) 가 먼저 파일을 생성해 `scan_signals`·`list_tmux_panes`·`capture_pane` + `SignalEntry`·`PaneInfo` 를 적재해둔 상태였다. design.md 의 "같은 파일 머지 충돌 완화" 전략대로 기존 코드를 **수정하지 않고** `# --- scan functions (TSK-01-02) ---` 주석 블록 영역에만 신규 정의를 추가했다. 상단 import 는 기존 리스트에 `json`·`Path`·`Tuple`·`field` 만 합집합으로 보강.
- **Python 3.9 호환 이슈 (QA에 없는 추가 검증)**: `from __future__ import annotations` + `dataclass` + `importlib.util.spec_from_file_location` 조합에서 Python 3.9 는 type 해석 시 `sys.modules[cls.__module__]` 를 참조한다. 모듈 이름을 사전에 `sys.modules` 에 등록하지 않으면 `AttributeError: 'NoneType' has no attribute '__dict__'` 가 발생 — 기존 `test_monitor_tmux.py` 도 같은 방식으로 해결해 있어 동일 패턴으로 정렬했다. 이 문제는 3.10+ 에서는 발생하지 않지만, 플러그인 지원 범위인 Python 3.8+ 계약상 필요.
- **`.py` 파일명에 하이픈 포함**: `monitor-server.py` 는 `import monitor-server` 가 불가능하므로 테스트에서 `importlib.util.spec_from_file_location` 로 동적 로드. Dev Config(`monitor-server.py, python3`) 의 cleanup 프로세스 이름과도 일치.
- **1MB 가드 경계값 추가 검증 (QA에 없는 추가 케이스)**: acceptance 는 "1MB 초과" 만 명시하지만, 정확히 1MB(1,048,576 B) 가 허용되는지 경계 검증을 `test_file_exactly_1mb_is_allowed_by_size_guard` 로 추가. design.md `§1MB 가드 동작` 의 "정확히 1MB 는 허용. 경계는 `>`(strictly greater than)" 를 테스트로 고정.
- **wbs.md 4MB 상한**: wbs.md 는 여러 Task 설명이 누적되므로 state.json 의 1MB 한도보다 4배(= 4MB)까지 허용하도록 완화. 현재 `docs/monitor/wbs.md` 는 수 KB 수준이므로 실질 영향 없으나 미래 확장성 고려.
- **코드 재사용성**: `WorkItem`·`PhaseEntry` 는 후속 Task(TSK-01-04 HTML 대시보드, TSK-01-06 JSON snapshot) 가 그대로 import 해서 재직렬화할 수 있도록 공통 dataclass 로 제공. `phase_history_tail` 을 `PhaseEntry` 리스트로 상향한 이유는 HTTP 응답에서 `dataclasses.asdict()` 1회로 변환할 수 있기 때문 — dict 리스트로 두면 UI 가 키 이름을 중복 관리해야 함.
