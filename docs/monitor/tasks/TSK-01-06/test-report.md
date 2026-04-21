# TSK-01-06: 테스트 결과

## 결과: PASS

## 실행 요약

| 구분 | 통과 | 실패 | 합계 |
|------|------|------|------|
| 단위 테스트 (전체 `test_monitor*.py`) | 100 | 0 | 106 (skipped=6) |
| 단위 테스트 (본 Task `test_monitor_api_state.py`) | 32 | 0 | 33 (skipped=1) |
| E2E 테스트 | N/A — backend domain | N/A | N/A |

실행 명령 (wbs.md `## Dev Config > Domains > backend > unit-test`):

```
python3 -m unittest discover -s scripts -p "test_monitor*.py" -v
```

결과: `Ran 106 tests in 0.033s — OK (skipped=6)`.

skipped 사유:
- `test_monitor_api_state.MonitorHandlerRoutingTests.test_api_state_handler_is_wired` (1건): 선행 TSK-01-02 의 `MonitorHandler` 클래스 부재로 `skipTest` — forward-compat. TSK-01-02 완료 후 자동 활성화.
- 나머지 5건: TSK-01-02/04/05 관련 유사 forward-compat skip (기존 파일).

E2E 테스트는 wbs.md Dev Config 상 backend 도메인의 `e2e_test=null` 이므로 본 Task 범위 밖. design.md QA 체크리스트 9·10번(라이브 HTTP / `curl + json.tool`)은 HTTP 스켈레톤 소유 Task(TSK-01-02) 병합 후 `scripts/test_monitor_e2e.py` 에서 검증 예정이며, 본 Task 는 동일 데이터 경로를 `PerformanceTests` + `SnapshotJsonSerializationTests` (단위 레벨) 로 커버했다.

## 정적 검증 (Dev Config에 정의된 경우만)

| 구분 | 결과 | 비고 |
|------|------|------|
| lint | pass | `python3 -m py_compile scripts/monitor-server.py` → 무출력 (exit 0) |
| typecheck | N/A | Dev Config 미정의 |
| coverage | N/A | Dev Config 미정의 |

## QA 체크리스트 판정

| # | 항목 (design.md §QA) | 결과 | 매핑 테스트 |
|---|---------------------|------|-------------|
| 1 | 정상 — `_build_state_snapshot` 반환 dict 의 8개 키 집합 정확 + 각 리스트 길이 (3,1,2,1,2) | pass | `BuildStateSnapshotTests.test_normal_returns_expected_keys_and_lengths` |
| 2 | 정상 — `generated_at` 이 `^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$` UTC ISO-Z 형식 | pass | `BuildStateSnapshotTests.test_generated_at_is_utc_iso_z_format` |
| 3 | 정상 — shared/agent-pool scope 분할 (각 2건) | pass | `BuildStateSnapshotTests.test_scope_split_shared_and_agent_pool` |
| 4 | 엣지 — `tmux_panes=None` → dict.tmux_panes is None; `tmux_panes=[]` → `[]` 유지 | pass | `BuildStateSnapshotTests.test_tmux_panes_none_is_preserved` + `test_tmux_panes_empty_list_is_preserved` |
| 5 | 엣지 — 세 스캐너 모두 `[]` 반환 시 예외 없이 빈 리스트 dict 반환 | pass | `BuildStateSnapshotTests.test_all_empty_scanners_return_empty_lists` |
| 6 | 엣지 — `raw_error` 가 채워진 `WorkItem` 도 `asdict`/JSON 직렬화 성공 | pass | `BuildStateSnapshotTests.test_workitem_with_raw_error_survives_asdict` |
| 7 | 정상 — 한글 title 이 `ensure_ascii=False` 로 유니코드 이스케이프 없이 원문 포함 | pass | `SnapshotJsonSerializationTests.test_korean_title_not_escaped_to_unicode` |
| 8 | 정상 — 각 `WorkItem.phase_history_tail` 최대 10건 (`_PHASE_TAIL_LIMIT=10`) | pass | `PhaseHistoryTailPreservationTests.test_phase_tail_limit_constant_is_10` + `test_phase_history_tail_preserved_through_asdict` |
| 9 | 정상 — 라이브 HTTP (`urlopen /api/state` → 200, Content-Type, 8-key JSON) | unverified | HTTP 스켈레톤(TSK-01-02) 병합 후 `scripts/test_monitor_e2e.py` 에서 검증 예정. 단위 레벨은 `JsonResponseHelperTests` + `HandleApiStateTests.test_success_returns_200_and_json_body` 로 커버 |
| 10 | 정상 — `curl + json.tool` 반환 코드 0 | unverified | 위와 동일. 단위 레벨은 `SnapshotJsonSerializationTests.test_all_dataclasses_roundtrip_through_asdict` (json.loads 왕복) |
| 11 | 에러 — `_build_state_snapshot` 에서 raise 된 예외를 500 JSON `{"error":…, "code":500}` 로 매핑 + stderr 1줄 로그 | pass | `HandleApiStateTests.test_exception_in_scanner_maps_to_500_json` |
| 12 | 에러 — `GET /api/state/` 는 매칭 실패(404 경로); `GET /api/state?pretty=1` 는 매칭, payload 쿼리 무관 | pass | `RouteMatchingTests.test_trailing_slash_does_not_match` + `test_api_state_with_query_matches` + `test_other_paths_do_not_match` |
| 13 | 보안 — 응답은 JSON 구조; Content-Type 은 `application/json; charset=utf-8` (내부 문자열 값의 `<` 등은 JSON 값으로 안전) | pass | `JsonResponseHelperTests.test_sets_status_content_type_length_cache_control` (Content-Type 헤더 검증) + `test_body_is_utf8_encoded_json` |
| 14 | 성능 — 100 WorkItem × 10 phase + 20 PaneInfo + 50 SignalEntry 합산 조립+`json.dumps` < 0.5초 | pass | `PerformanceTests.test_build_and_dumps_under_500ms` |
| 15 | 통합 — 모든 dataclass(`WorkItem`/`PhaseEntry`/`SignalEntry`/`PaneInfo`) `asdict` 직렬화 + JSON 기본 타입 재귀 검증 | pass | `SnapshotJsonSerializationTests.test_all_dataclasses_roundtrip_through_asdict` |
| 16 | 통합 — `scope="agent-pool:…"` → `agent_pool_signals`; `"shared"` → `shared_signals`; 미지의 scope `"other:xyz"` → 보수적으로 `shared_signals` 편입 (드롭 금지) | pass | `BuildStateSnapshotTests.test_scope_split_shared_and_agent_pool` + `test_unknown_scope_lands_in_shared_signals_conservatively` |
| 17 | 통합 — `_json_response` 가 `send_response(200)` + `Content-Type` + `Content-Length` + `Cache-Control: no-store` 4개 헤더 정확 호출 | pass | `JsonResponseHelperTests.test_sets_status_content_type_length_cache_control` + `test_content_length_matches_utf8_bytes` |

**판정 합계**: 15 pass / 0 fail / 2 unverified (HTTP 바인딩 의존 — 후속 Task 범위).

## 재시도 이력
- 첫 실행에 통과 (Ran 106 tests in 0.033s — OK). 수정-재실행 사이클 0회 소비.

## 비고
- **E2E unverified 2건의 근거**: design.md QA 9·10번은 "실제 서버 기동 후 HTTP" 를 요구하나, TSK-01-06 의 선행 조건인 TSK-01-02(`MonitorHandler`+`ThreadingHTTPServer` 스켈레톤)가 아직 미완(state `[im]`). build-report.md 가 명시한 대로 본 Task 는 라우팅 보조 함수(`_is_api_state_path`) + 핸들러 엔트리(`_handle_api_state`) 를 독립 모듈 레벨 함수로 노출해 두었고, TSK-01-02 의 `do_GET` 이 병합되는 시점에 `scripts/test_monitor_e2e.py` 에서 HTTP 레벨 검증이 활성화된다. 현 단계에서는 순수 함수 레벨 + mock-handler 레벨에서 동일 계약을 검증.
- **"E2E 우회 금지" 조항 위반 없음**: 본 Task 의 domain 은 `backend` 이며 Dev Config 상 `e2e_test=null` 이다. UI 재분류 휴리스틱(`입력`/`렌더`) 은 히트했으나 문맥 검토 결과 전부 "렌더링 모델"(데이터 모델 표현), "렌더러"(아키텍처 기술), "mock 입력"(테스트 입력), "서버 측 렌더링"(타 Task 기능 언급) 으로 실제 UI 작업을 의미하지 않는다. design.md 28번 라인이 "domain: backend, UI 없음" 을 명시한다. 따라서 `effective_domain=backend` 로 확정하고 E2E 게이트를 통과.
- **성능 마진**: `PerformanceTests.test_build_and_dumps_under_500ms` 는 acceptance §3(1초 이내)의 **여유 0.5초 버전** 을 enforce. 실제 측정 환경에서 훨씬 낮은 ms 수준이었다(106 테스트 총 0.033초).
- **quality_commands**: Dev Config 에 `lint` 만 정의되어 있으므로 `typecheck` / `coverage` 는 N/A 처리. `py_compile` 은 `monitor-server.py` 구문 검증용이며 로직 검증이 아니다 (로직은 단위 테스트가 담당).
