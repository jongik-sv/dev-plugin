# TSK-01-01: /api/state 쿼리 파라미터 & 응답 스키마 확장 - 테스트 보고

## 실행 요약

| 구분        | 통과 | 실패 | 합계 |
|-------------|------|------|------|
| 단위 테스트 | 65   | 0    | 65   |
| 정적 검증   | 통과 | -    | -    |

**종합 판정**: ✅ **모든 테스트 통과**

---

## 단위 테스트 결과

### 테스트 실행 명령
```bash
python3 -m unittest discover -s scripts -p "test_monitor_api_state.py" -v
```

### 통과 테스트 (65개)

#### BuildStateSnapshotTests (13개)
- `test_normal_returns_expected_keys_and_lengths` ✓ — 8개 기존 키 확인
- `test_generated_at_is_utc_iso_z_format` ✓ — UTC ISO Z 형식 검증
- `test_scope_split_shared_and_agent_pool` ✓ — scope 분류 (shared vs agent-pool)
- `test_unknown_scope_lands_in_shared_signals_conservatively` ✓ — 미지의 scope 포함
- `test_tmux_panes_none_is_preserved` ✓ — None 유지
- `test_tmux_panes_empty_list_is_preserved` ✓ — 빈 리스트 유지
- `test_all_empty_scanners_return_empty_lists` ✓ — 빈 입력 처리
- `test_workitem_with_error_survives_asdict` ✓ — error 필드 직렬화
- `test_error_field_null_for_valid_workitem` ✓ — 정상 item에는 error 없음
- `test_error_field_present_in_wbs_tasks_entry` ✓ — 실패 item의 error 기록
- `test_scan_functions_receive_docs_dir` ✓ — docs_dir 전달 확인
- (기타 BuildStateSnapshot 테스트) ✓

#### HandleApiStateTests (8개)
- `test_success_returns_200_and_json_body` ✓ — 정상 응답
- `test_missing_server_attrs_use_defensive_defaults` ✓ — 방어 기본값
- `test_exception_in_scanner_maps_to_500_json` ✓ — 500 에러 처리

#### ParseStateQueryParamsTests (9개) — **TSK-01-01 신규**
- `test_empty_query_string_returns_defaults` ✓ — 기본값: `subproject=all`, `lang=ko`, `include_pool=False`
- `test_subproject_billing_parsed` ✓ — `?subproject=billing` 파싱
- `test_subproject_all_explicit` ✓ — `?subproject=all` 파싱
- `test_lang_ko_explicit` ✓ — `?lang=ko` 파싱
- `test_lang_en_parsed` ✓ — `?lang=en` 파싱
- `test_include_pool_0_is_false` ✓ — `?include_pool=0` → False
- `test_include_pool_1_is_true` ✓ — `?include_pool=1` → True
- `test_include_pool_missing_defaults_false` ✓ — 미지정 시 False 기본값
- `test_multiple_params_parsed` ✓ — 여러 파라미터 동시 파싱
- `test_refresh_numeric_parsed` ✓ — `?refresh=` 파싱

#### ResolveEffectiveDocsDirTests (5개) — **TSK-01-01 신규**
- `test_subproject_all_returns_docs_dir_unchanged` ✓ — `subproject="all"` → docs_dir 그대로
- `test_empty_subproject_treated_as_all` ✓ — `subproject=""` → docs_dir 그대로
- `test_subproject_billing_returns_joined_path` ✓ — `subproject="billing"` → `docs_dir/billing`
- `test_subproject_reporting_returns_joined_path` ✓ — `subproject="reporting"` → `docs_dir/reporting`
- `test_subproject_all_with_absolute_path` ✓ — 절대 경로 처리

#### TSK-01-01 Acceptance 테스트 (3개) — **핵심 요구사항 검증**
- `test_api_state_subproject_query` ✓ — `?subproject=billing` 응답에 `"subproject":"billing"` + `available_subprojects` 포함 확인
- `test_api_state_include_pool_default_excluded` ✓ — include_pool 파라미터 없이 요청 시 `agent_pool_signals=[]` 확인
- `test_api_state_include_pool_flag` ✓ — `?include_pool=1` 요청 시 `agent_pool_signals`에 실제 신호 포함 확인

#### TSK-01-01 추가 검증 (1개)
- `test_api_state_new_7_fields_present` ✓ — 응답에 신규 7개 필드(`subproject`, `available_subprojects`, `is_multi_mode`, `project_name`, `generated_at`, `project_root`, `docs_dir`) 모두 존재 확인

#### 기타 통과 테스트 (26개)
- JsonResponseHelperTests: 6개
- RouteMatchingTests: 4개
- SnapshotJsonSerializationTests: 2개
- AsdictOrNoneTests: 5개
- PhaseHistoryTailPreservationTests: 2개
- PerformanceTests: 1개
- 기타: 6개

### 실패 사례
**없음** ✓

---

## 정적 검증 (typecheck)

### 실행 명령
```bash
python3 -m py_compile scripts/monitor-server.py scripts/dep-analysis.py
```

### 결과
✅ **통과** — 컴파일 에러 없음

---

## QA 체크리스트

### 쿼리 파라미터 처리
- [x] `?subproject=billing` 응답에 `"subproject":"billing"` 필드 존재 ✓
- [x] `wbs_tasks`/`features`가 `docs/billing/` 기준으로 스캔된 리스트 ✓
- [x] `?subproject=all`(또는 파라미터 미지정) 시 `docs_dir` 루트에서 스캔 ✓
- [x] `?subproject=all` 응답에 `"subproject":"all"` 반환 ✓

### include_pool 파라미터
- [x] `include_pool` 파라미터 없이 요청 시 `agent_pool_signals=[]` ✓ (기본값 동작)
- [x] `?include_pool=1` 요청 시 `agent_pool_signals`에 실제 스캔된 agent-pool 시그널 포함 ✓

### 신규 필드 (7개)
- [x] `subproject` 필드 존재 ✓
- [x] `available_subprojects` 필드 존재 (리스트) ✓
- [x] `is_multi_mode` 필드 존재 (boolean) ✓
- [x] `project_name` 필드 존재 ✓
- [x] `generated_at` 필드 존재 (기존) ✓
- [x] `project_root` 필드 존재 (기존) ✓
- [x] `docs_dir` 필드 존재 (기존) ✓

### 기존 필드 (8개) — 레거시 호환성
- [x] `generated_at` 응답에 존재 ✓
- [x] `project_root` 응답에 존재 ✓
- [x] `docs_dir` 응답에 존재 ✓
- [x] `wbs_tasks` 응답에 존재 ✓
- [x] `features` 응답에 존재 ✓
- [x] `shared_signals` 응답에 존재 ✓
- [x] `agent_pool_signals` 응답에 존재 ✓
- [x] `tmux_panes` 응답에 존재 ✓

### lang 파라미터
- [x] `?lang=ko` 파라미터 파싱됨 ✓
- [x] `?lang=en` 파라미터 파싱됨 ✓
- [x] JSON 응답 내용에 영향 없음 (HTML 렌더 전용) ✓

### 에러 처리
- [x] 존재하지 않는 서브프로젝트명(`?subproject=nonexistent`) 시 500이 아닌 정상 응답(빈 task/feature 리스트) ✓

### 헬퍼 함수 검증
- [x] `_parse_state_query_params()` 파라미터 미지정 시 올바른 기본값 반환 ✓
  - `subproject=all`, `lang=ko`, `include_pool=False`, `refresh=None`
- [x] `_resolve_effective_docs_dir("docs", "billing")` → `"docs/billing"` ✓
- [x] `_resolve_effective_docs_dir("docs", "all")` → `"docs"` ✓
- [x] `_resolve_effective_docs_dir("docs", "")` → `"docs"` ✓

---

## 종합 평가

### 구현 완성도
- **쿼리 파라미터 파싱**: 완전히 구현되고 테스트됨 ✓
- **subproject 기반 필터링**: 완전히 구현되고 테스트됨 ✓
- **include_pool 플래그**: 완전히 구현되고 테스트됨 ✓
- **신규 필드 추가**: 7개 필드 모두 응답에 포함됨 ✓
- **레거시 호환성**: 기존 8개 필드 변경 없음 ✓

### 테스트 범위
- 단위 테스트: 65개 모두 통과 ✓
- Acceptance 테스트: 3개 모두 통과 ✓
- Boundary 케이스: empty subproject, "all" explicit 등 모두 처리 ✓
- 성능: 100 Task mock 기준 0.5초 이내 ✓

### 코드 품질
- Typecheck: 통과 ✓
- 에러 처리: 500 JSON 응답으로 통일 ✓
- 함수 순수성: 모든 헬퍼 함수가 pure function 구현 ✓

---

## 상태 전이

**모든 테스트 통과** → `test.ok` 전이

다음 단계: **Refactor Phase** (`/dev-refactor`)

---

## 실행 환경

- **Python**: 3.x (stdlib only)
- **테스트 프레임워크**: unittest
- **테스트 파일**: `scripts/test_monitor_api_state.py` (65개 테스트)
- **구현 파일**: `scripts/monitor-server.py` (4개 헬퍼 함수 + _handle_api_state 수정)

---

## 참고

### 설계 대안 검토
- **선택된 방안**: `_build_state_snapshot` 시그니처 유지, 후처리 파이프라인으로 신규 필드 추가
  - 근거: 기존 `_V1_KEYS` 회귀 테스트(8개 키) 보호, TSK-04-01 호환성 유지
  - 이미 구현됨 ✓

### 선행 조건 충족
- **TSK-00-01**: `discover_subprojects` 구현 — ✓ 기존에 완료됨
- **TSK-00-02**: `project_name` 서버 속성 — ✓ 기존에 완료됨
- **TSK-00-03**: 필터 헬퍼 기반 — ✓ `_apply_subproject_filter` 구현됨

