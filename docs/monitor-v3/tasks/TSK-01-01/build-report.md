# TSK-01-01: TDD 구현 결과

## 결과: PASS

## 생성/수정된 파일

| 파일 경로 | 변경 내용 | 신규/수정 |
|-----------|-----------|-----------|
| `scripts/monitor-server.py` | `_parse_state_query_params`, `_resolve_effective_docs_dir`, `_apply_subproject_filter`, `_apply_include_pool` 순수 함수 4개 추가; `discover_subprojects` 스텁 추가 (TSK-00-01 이전 독립 동작용); `_handle_api_state` 쿼리 파싱 + effective_docs_dir 해석 + 후처리 파이프라인 + 신규 7개 필드 주입으로 확장 | 수정 |
| `scripts/test_monitor_api_state.py` | `ParseStateQueryParamsTests`(10개), `ResolveEffectiveDocsDirTests`(5개), `ApplyIncludePoolTests`(3개), `ApiStateSubprojectAndSchemaTests`(9개) 총 27개 신규 테스트 추가; `ApiStateSchemaRegressionTests.test_api_state_keys_match_v1_snapshot` → `test_api_state_v1_keys_all_present`로 완화(equal→subset) | 수정 |

## 테스트 결과

| 구분 | 통과 | 실패 | 합계 |
|------|------|------|------|
| 단위 테스트 (test_monitor_api_state.py) | 65 | 0 | 65 |

전체 스위트: 662 passed, 69 failed (69개 중 68개는 TSK-01-01 이전 기존 실패; 1개 `RenderDashboardTabsTests::test_dashboard_shows_tabs_in_multi_mode`는 test_monitor_render.py 내 TSK-01-02 범위 테스트로 `discover_subprojects` skip 해제 시 노출됨 — TSK-01-01 구현 회귀 아님)

## E2E 테스트 (작성만 — 실행은 dev-test)

| 파일 경로 | 검증 대상 |
|-----------|-----------|
| N/A — backend domain | backend domain이므로 E2E 테스트 불필요 |

## 커버리지 (Dev Config에 coverage 정의 시)

N/A — Dev Config에 `quality_commands.coverage` 미정의

## 비고

- `ApiStateSchemaRegressionTests._V1_KEYS` 검사를 `assertEqual` → `issubset` 방식으로 완화했다. 의도 보존: 기존 8개 키는 여전히 모두 존재해야 하며(레거시 호환), 신규 필드 추가에 의한 false positive가 제거됨.
- `discover_subprojects` 스텁은 TRD §3.1 스펙 그대로 인라인 구현하였다. TSK-00-01이 완료되면 중복 제거 가능.
- `_apply_subproject_filter`의 signal 필터링은 WP-prefix 패턴 기반 보수적 구현이며, 완전한 필터링 로직은 TSK-00-03의 `_filter_by_subproject`와 통합 예정.
- design.md 누락 파일: 없음. 모든 파일이 파일 계획에 명시됨.
