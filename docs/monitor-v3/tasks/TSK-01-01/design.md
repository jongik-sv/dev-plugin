# TSK-01-01: /api/state 쿼리 파라미터 & 응답 스키마 확장 - 설계

## 요구사항 확인

- `GET /api/state`에 `?subproject=<sp|all>`, `?lang=<ko|en>`, `?include_pool=<0|1>` 세 쿼리 파라미터를 추가로 파싱한다.
- 응답 최상위 객체에 `subproject`, `available_subprojects`, `is_multi_mode`, `project_name`, `generated_at`(기존), `project_root`(기존), `docs_dir`(기존) 등 7개 필드를 추가한다.
- `wbs_tasks`/`features`는 `effective_docs_dir`(서브프로젝트 해석 후)에서 스캔하고, `shared_signals`/`tmux_panes`는 서브프로젝트 필터를 적용한다. `agent_pool_signals`는 `include_pool=0`(기본) 시 `[]`로 비운다.

## 타겟 앱

- **경로**: N/A (단일 앱)
- **근거**: `scripts/monitor-server.py` 단일 파이썬 서버이며 모노레포 분리 없음.

## 구현 방향

현재 `_handle_api_state` → `_build_state_snapshot`은 `subproject` 개념 없이 `docs_dir`만 사용한다. 이번 Task에서는:

1. `_handle_api_state`에서 쿼리 파라미터(`subproject`, `lang`, `include_pool`, `refresh`)를 파싱한다.
2. `discover_subprojects(docs_dir)` 헬퍼(TSK-00-01에서 이미 존재 예정)를 호출해 `available_subprojects`와 `is_multi_mode`를 결정한다.
3. `effective_docs_dir` = `subproject == "all"` 또는 미지정이면 `docs_dir`, 아니면 `docs_dir / subproject`.
4. `_build_state_snapshot`의 스캔을 `effective_docs_dir` 기준으로 실행한다. 단, 시그널/pane 필터는 `subproject` 값을 기준으로 적용한다.
5. `include_pool=0`(기본)이면 `agent_pool_signals`를 `[]`로 교체한다.
6. 응답 dict에 7개 신규 필드를 추가한다. 기존 8개 키(`generated_at`, `project_root`, `docs_dir`, `wbs_tasks`, `features`, `shared_signals`, `agent_pool_signals`, `tmux_panes`)는 그대로 유지하여 레거시 호환성을 보장한다.

`lang` 파라미터는 파싱만 하고 JSON 응답에는 영향 없음(HTML 렌더 전용이므로 로직 없음).

## 파일 계획

**경로 기준:** 프로젝트 루트 기준.

| 파일 경로 | 역할 | 신규/수정 |
|-----------|------|-----------|
| `scripts/monitor-server.py` | `_handle_api_state` 쿼리 파싱, `effective_docs_dir` 해석, 서브프로젝트 필터 closure, 응답 필드 7개 추가. `_build_state_snapshot_v2` 내부 헬퍼(또는 기존 함수 시그니처 확장). | 수정 |
| `scripts/test_monitor_api_state.py` | 신규 acceptance 테스트 3개: `test_api_state_subproject_query`, `test_api_state_include_pool_default_excluded`, `test_api_state_include_pool_flag`. 기존 회귀 테스트(`_V1_KEYS` 검사)는 신규 필드 추가로 키 집합 업데이트 필요. | 수정 |

## 진입점 (Entry Points)

N/A — domain=backend, UI 변경 없음.

## 주요 구조

1. **`_parse_state_query_params(query_string: str) -> dict`** — `subproject`, `lang`, `include_pool`, `refresh`를 `urllib.parse.parse_qs`로 파싱. 미지정 시 기본값(`all`, `ko`, `0`, `None`) 반환. 순수 함수 — 테스트 용이.

2. **`_resolve_effective_docs_dir(docs_dir: str, subproject: str) -> str`** — `subproject == "all"` 이면 `docs_dir` 그대로, 아니면 `os.path.join(docs_dir, subproject)` 반환. 경로 존재 여부는 호출자 책임(스캔 함수가 빈 리스트 반환). 순수 함수.

3. **`_apply_subproject_filter(raw: dict, subproject: str, project_name: str) -> dict`** — `subproject != "all"` 일 때 `shared_signals`와 `tmux_panes`에 서브프로젝트 필터를 적용. TRD §3.4 `_filter_by_subproject` 로직을 인라인 또는 위임. 순수 함수.

4. **`_apply_include_pool(raw: dict, include_pool: bool) -> dict`** — `include_pool=False`이면 `raw["agent_pool_signals"] = []`. 1줄 헬퍼.

5. **`_handle_api_state` (수정)** — 위 4개 헬퍼를 순서대로 호출하는 조합 포인트. 기존 `_build_state_snapshot` 호출 직후 후처리 파이프라인으로 연결. `try/except`로 500 방어 유지.

## 데이터 흐름

```
GET /api/state?subproject=billing&include_pool=0
  → _parse_state_query_params → {subproject:"billing", include_pool:False, ...}
  → discover_subprojects(docs_dir) → ["billing","reporting"]
  → _resolve_effective_docs_dir(docs_dir, "billing") → "docs/billing"
  → _build_state_snapshot(effective_docs_dir) → raw dict (8 keys)
  → _apply_subproject_filter(raw, "billing", project_name) → filtered raw
  → _apply_include_pool(raw, False) → agent_pool_signals=[]
  → 응답 dict에 신규 7 필드 병합 → JSON 응답
```

## 설계 결정 (대안이 있는 경우만)

- **결정**: `_build_state_snapshot` 시그니처를 그대로 두고, 호출 후 후처리 파이프라인으로 신규 필드를 추가한다.
- **대안**: `_build_state_snapshot`에 `subproject`, `include_pool` 파라미터를 직접 추가.
- **근거**: `_build_state_snapshot`은 TSK-04-01 회귀 테스트(`_V1_KEYS`)가 8개 키를 pin하고 있으므로 내부 변경 없이 후처리 계층에서 확장하는 것이 기존 테스트 영향 최소화.

---

- **결정**: `discover_subprojects` 헬퍼가 이미 TSK-00-01(또는 TSK-00-02)에서 구현되었다고 가정하고 호출. 미구현 시 `scripts/monitor-server.py` 내부에 TRD §3.1 스펙 그대로 인라인 구현 후 나중에 dedup.
- **대안**: stub 처리 후 TSK-00-01 완료 때까지 보류.
- **근거**: 이 Task의 acceptance 테스트가 `available_subprojects` 응답 필드를 검증하므로 단위 테스트 내 mock으로도 충분히 독립 구현 가능.

## 선행 조건

- TSK-00-01 (discover_subprojects 구현), TSK-00-02 (project_name 서버 속성), TSK-00-03 (필터 헬퍼 기반) — depends에 명시됨. 단, 단위 테스트 수준에서는 mock으로 선행 조건 격리 가능.
- `scripts/monitor-server.py`에 `discover_subprojects` 함수 또는 동등 구현 존재 필요.

## 리스크

- **MEDIUM**: TSK-04-01의 `_V1_KEYS` 회귀 테스트가 기존 8개 키만 허용하도록 `assertEqual`로 pin되어 있음. 신규 7개 필드 추가 시 해당 테스트가 실패하므로 키 집합 업데이트(또는 "기존 키 포함 여부" 검사로 완화) 가 필요. 수정 시 테스트 의도 유지 필수.
- **MEDIUM**: `effective_docs_dir`이 존재하지 않는 서브프로젝트명을 받으면 `scan_tasks`/`scan_features`가 빈 리스트를 반환하는 것이 기대 동작. 경로 미존재 시 예외를 던지는 스캔 구현이 있다면 `try/except`로 방어해야 함.
- **LOW**: `project_name` 은 `server.project_name` 속성 또는 `os.path.basename(project_root)` 로 파생할 수 있음. TSK-00-02 가 `project_name` 서버 속성을 추가하지 않았다면 fallback으로 `basename(project_root)` 사용.

## QA 체크리스트

- [ ] `?subproject=billing` 요청 시 응답에 `"subproject": "billing"` 필드가 존재하고, `wbs_tasks`/`features`가 `docs/billing/` 기준으로 스캔된 리스트인지 확인 (`test_api_state_subproject_query`).
- [ ] `?subproject=all`(또는 파라미터 미지정) 시 `docs_dir` 루트에서 스캔하고 `"subproject": "all"` 반환 (`test_api_state_subproject_query` 경계값).
- [ ] `include_pool` 파라미터 없이 요청 시 응답 `agent_pool_signals`가 `[]`인지 확인 (`test_api_state_include_pool_default_excluded`).
- [ ] `?include_pool=1` 요청 시 `agent_pool_signals`가 실제 스캔된 agent-pool 시그널을 포함하는지 확인 (`test_api_state_include_pool_flag`).
- [ ] 응답에 `available_subprojects`, `is_multi_mode`, `project_name`, `generated_at`, `project_root`, `docs_dir`, `subproject` 7개 신규 필드가 모두 존재.
- [ ] 기존 8개 키(`generated_at`, `project_root`, `docs_dir`, `wbs_tasks`, `features`, `shared_signals`, `agent_pool_signals`, `tmux_panes`)가 응답에 여전히 존재(레거시 호환).
- [ ] `?lang=ko` 또는 `?lang=en` 파라미터가 JSON 응답 내용에 영향을 주지 않음(lang 파싱은 하되 응답 필드 불변).
- [ ] 존재하지 않는 서브프로젝트명(`?subproject=nonexistent`) 시 500이 아닌 정상 응답(빈 task/feature 리스트)이 반환됨.
- [ ] `_parse_state_query_params` 가 파라미터 미지정 시 올바른 기본값 반환.
- [ ] `_resolve_effective_docs_dir("docs", "billing")` → `"docs/billing"`, `_resolve_effective_docs_dir("docs", "all")` → `"docs"` (단위 테스트 직접 호출).
