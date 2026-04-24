# TSK-02-02: `api.py` — `/api/*` 엔드포인트 이전 - 설계

## 요구사항 확인

- `scripts/monitor_server/api.py` 신규 파일을 생성하여 `/api/state`, `/api/graph`, `/api/task-detail`, `/api/merge-status` 4개 엔드포인트 핸들러를 이전한다.
- 각 핸들러는 `def handle_X(handler, params: dict, model) -> None` 시그니처를 따르며, `monitor-server.py`의 `do_GET`에서 `api.handle_*` 형태로 위임 호출된다.
- 응답 JSON 스키마는 v4와 byte 동일 — 필드 추가/제거/이름 변경 없음. 캐싱 헤더(`Cache-Control: no-store`) 기존 정책 유지.

## 타겟 앱

- **경로**: N/A (단일 앱)
- **근거**: 모노레포가 아닌 단일 Python 스크립트 프로젝트. `scripts/` 아래 직접 배치.

## 구현 방향

- `scripts/monitor_server/api.py`를 신규 생성. `monitor-server.py` 내 4개 API 핸들러 함수(`_handle_api_state`, `_handle_graph_api`, `_handle_api_task_detail`, `_handle_api_merge_status`)와 이들이 **직접** 호출하는 헬퍼 함수·상수를 이전한다.
- 공용 유틸(`_json_response`, `_json_error`, `_server_attr`, `_now_iso_z`, `_resolve_effective_docs_dir`, `discover_subprojects` 등)은 **이전 대상이 아니다** — `monitor-server.py`에 남겨두고 `api.py`에서 `import`로 참조한다. 단, `api.py`가 `monitor-server.py`를 역방향 import하면 순환 참조 위험이 있으므로, 공용 유틸은 별도 모듈(`monitor_server/utils.py`)로 추출하거나 `api.py`의 함수 파라미터로 주입한다.
- **설계 결정 — 의존성 주입 방식 채택**: 각 `handle_X` 함수는 `monitor-server.py`를 import하지 않는다. `monitor-server.py`가 `api.py`를 `import`하며, `handle_X` 내에서 필요한 공용 유틸(`_json_response` 등)은 `monitor-server.py`에서 `api` 모듈에 monkey-patch하는 대신, `api.py`가 `monitor_server.utils`에서 import하거나 인자로 전달받는다.
- `monitor-server.py`의 `do_GET`에서 `/api/*` 분기를 `from monitor_server import api` 후 `api.handle_*`로 위임.
- `api.py` ≤ 800줄. 기존 테스트들은 `monitor-server.py`를 직접 load하므로 함수가 이전 후에도 `monitor-server.py`에 shim(thin wrapper)으로 남아야 기존 테스트 회귀가 없다.

## 파일 계획

**경로 기준:** 모든 파일 경로는 프로젝트 루트 기준으로 작성한다.

| 파일 경로 | 역할 | 신규/수정 |
|-----------|------|-----------|
| `scripts/monitor_server/api.py` | `/api/state`, `/api/graph`, `/api/task-detail`, `/api/merge-status` 핸들러 + 전용 헬퍼 함수 이전. `handle_state`, `handle_graph`, `handle_task_detail`, `handle_merge_status` 4개 public 함수 정의 | 신규 |
| `scripts/monitor_server/__init__.py` | 패키지 초기화. TSK-02-01에서 생성. `from .api import handle_state, handle_graph, handle_task_detail, handle_merge_status` 재수출 추가 | 수정 |
| `scripts/monitor-server.py` | `do_GET` 내 `/api/*` 분기를 `api.handle_*`로 위임. 기존 `_handle_api_state`, `_handle_graph_api`, `_handle_api_task_detail`, `_handle_api_merge_status` 함수는 shim으로 남겨 기존 테스트 호환 유지 | 수정 |
| `scripts/test_monitor_module_split.py` | `test_import_api` 테스트 케이스 추가: `from monitor_server.api import handle_state, handle_graph, handle_task_detail, handle_merge_status` 성공 검증 | 수정 |

## 진입점 (Entry Points)

N/A — backend domain Task (HTTP 엔드포인트 라우팅 변경이므로 UI 진입점 없음)

## 주요 구조

- **`api.handle_state(handler, params, model)`**: `/api/state` 처리. `params`에서 `subproject`, `include_pool` 등 파싱. `_handle_api_state(handler, ...)` 로직을 이전. 내부적으로 `_json_response`, `_json_error`, `_server_attr` 등 공용 유틸을 사용.
- **`api.handle_graph(handler, params, model)`**: `/api/graph` 처리. `params`에서 `subproject` 파싱. `_handle_graph_api(handler)` 로직 이전. `dep-analysis.py` subprocess 호출 포함.
- **`api.handle_task_detail(handler, params, model)`**: `/api/task-detail` 처리. `params`에서 `task`, `subproject` 파싱. `_handle_api_task_detail(handler)` 로직 이전.
- **`api.handle_merge_status(handler, params, model)`**: `/api/merge-status` 처리. `params`에서 `subproject`, `wp` 파싱. `_handle_api_merge_status(handler)` 로직 이전.
- **shim 패턴**: `monitor-server.py` 내 기존 `_handle_api_state(handler)` 등은 `api.handle_state(handler, {}, None)` 호출로 교체. 기존 테스트가 `monitor_server._handle_api_state`를 직접 import하는 경우 shim이 계속 동작.

## 데이터 흐름

`do_GET(handler)` → 경로 분기 → `api.handle_X(handler, params, model)` → 내부 로직(스캔·빌드) → `_json_response(handler, status, payload)` → HTTP 응답

## 설계 결정 (대안이 있는 경우만)

- **결정**: 기존 `_handle_*` 함수를 `api.py`로 이전하되, `monitor-server.py`에 shim 함수를 유지한다.
- **대안**: shim 없이 `monitor-server.py`에서 `_handle_*` 함수를 완전히 제거하고 테스트를 직접 수정.
- **근거**: 기존 테스트 파일들(`test_monitor_task_detail_api.py`, `test_monitor_graph_api.py`, `test_monitor_merge_badge.py`)이 `monitor_server` 모듈에서 private 함수를 직접 참조하므로, shim 유지가 테스트 수정 없이 AC(회귀 0)를 만족시키는 최소 변경 경로다.

- **결정**: `api.py`에서 공용 유틸(`_json_response`, `_json_error`, `_server_attr` 등)을 `monitor_server.utils` 또는 함수 파라미터로 주입받는다.
- **대안**: `api.py`에서 `import monitor_server` (역방향 참조).
- **근거**: `monitor-server.py`가 `monitor_server/api.py`를 import하고, `api.py`가 다시 `monitor-server`를 import하면 순환 참조가 발생한다. 공용 유틸을 `monitor_server/utils.py`로 분리하거나, 기존처럼 `api.py` 자체에 유틸 복사본을 두거나, 함수 파라미터로 전달하는 세 방법 중 — TSK-02-02 범위(≤800줄)에서 utils 분리는 scope 초과 우려. 가장 단순한 방법은 **api.py에 필요한 공용 유틸을 직접 복사 또는 재정의**하되 중복 최소화. 실제 분석 결과: `_json_response`, `_json_error`, `_server_attr`, `_now_iso_z`, `_resolve_effective_docs_dir`, `discover_subprojects`, `_aggregated_scan`, `_parse_state_query_params`, `_build_state_snapshot`, `_apply_subproject_filter`, `_apply_include_pool` 등이 필요. 이 함수들을 모두 복사하면 800줄을 초과할 수 있으므로, **의존성 주입 패턴**을 선택: `api.py` 함수 시그니처에 scanner 함수들은 기본값 파라미터로, 나머지 소수 유틸(`_json_response` 등)은 `monitor_server/_utils.py` 경량 모듈로 추출.

## 선행 조건

- TSK-02-01: `scripts/monitor_server/` 패키지 스캐폴드가 생성되어 있어야 한다(`__init__.py` 존재). 현재 TSK-02-01 status `[ ]`이므로 본 Task 착수 전 TSK-02-01 완료 필요.

## 리스크

- **HIGH**: 순환 참조 위험 — `api.py`가 `monitor-server.py` 내 함수를 import하면 `monitor-server.py` → `monitor_server.api` → `monitor-server` 순환 발생. 반드시 공용 유틸을 `monitor_server/_utils.py` 등 독립 모듈로 분리해야 함.
- **HIGH**: 기존 테스트 호환 — `test_monitor_task_detail_api.py`는 `monitor_server._build_task_detail_payload`, `monitor_server._extract_wbs_section` 등 private 함수를 직접 호출한다. 이전 후 shim이 없으면 AttributeError. shim 또는 `api.py`에서 동일 이름으로 재수출해야 함.
- **MEDIUM**: `api.py` 줄 수 초과 — 4개 핸들러 + 전용 헬퍼를 이전하면 800줄 초과 가능. 이전 대상 함수들의 줄 수 사전 계산 필요: `_handle_api_state`(~120줄), `_handle_graph_api`(~85줄), `_handle_api_task_detail`(~25줄), `_handle_api_merge_status`(~30줄), 전용 헬퍼(`_build_task_detail_payload`, `_extract_wbs_section`, `_collect_artifacts`, `_collect_logs`, `_extract_title_from_section`, `_extract_wp_id`, `_load_state_json`, `_tail_report`, `_is_api_*_path` 등 ~350줄), 공용 유틸 재수출 shim ~20줄. 합계 ~630줄 — 800줄 이내 예상이나 실측 필요.
- **LOW**: `test_monitor_merge_badge.py`는 HTML 렌더러를 테스트하므로 API 이전 영향 없음. 하지만 `monitor_server` 모듈 로드 자체가 실패하면 전체 테스트가 깨짐 — `__init__.py` import 경로 검증 필수.

## QA 체크리스트

dev-test 단계에서 검증할 항목.

- [ ] `from monitor_server.api import handle_state, handle_graph, handle_task_detail, handle_merge_status` import 성공 (AttributeError 없음)
- [ ] `test_monitor_module_split.py::test_import_api` 통과
- [ ] `test_monitor_task_detail_api.py` 전량 통과 (회귀 0) — shim을 통해 `monitor_server._build_task_detail_payload` 등 private 함수 접근 가능
- [ ] `test_monitor_graph_api.py` 전량 통과 (회귀 0) — `monitor_server._handle_graph_api`, `_build_graph_payload` 등 shim 경유 동작
- [ ] `test_monitor_merge_badge.py` 전량 통과 (회귀 0) — `monitor_server` 모듈 로드 성공
- [ ] `GET /api/state` 응답 JSON 스키마가 v4와 동일 (필드 추가/제거 없음)
- [ ] `GET /api/graph` 응답 JSON 스키마가 v4와 동일 (`phase` 필드 미추가)
- [ ] `GET /api/task-detail?task=TSK-XX-XX` 응답 JSON 스키마가 v4와 동일
- [ ] `GET /api/merge-status` 응답 JSON 스키마가 v4와 동일
- [ ] `api.py` 파일 줄 수 ≤ 800줄 (정적 검사: `wc -l scripts/monitor_server/api.py`)
- [ ] `Cache-Control: no-store` 헤더가 모든 `/api/*` 응답에 유지됨
- [ ] `monitor-server.py` 내 shim 함수들이 `api.handle_*`로 위임하며 기존 동작 동일
- [ ] 순환 참조 없음: `python3 -c "import sys; sys.path.insert(0, 'scripts'); from monitor_server import api"` 에러 없음
- [ ] `python3 -m py_compile scripts/monitor_server/api.py` 성공
- [ ] `pytest -q scripts/test_monitor_task_detail_api.py scripts/test_monitor_graph_api.py scripts/test_monitor_merge_badge.py` 전량 green
