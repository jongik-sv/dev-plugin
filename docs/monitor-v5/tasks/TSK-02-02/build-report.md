# TSK-02-02: TDD 구현 결과

## 결과: PASS

## 생성/수정된 파일

| 파일 경로 | 변경 내용 | 신규/수정 |
|-----------|-----------|-----------|
| `scripts/monitor_server/api.py` | `/api/state`, `/api/graph`, `/api/task-detail`, `/api/merge-status` 4개 public 핸들러 + 전용 헬퍼 함수. 643줄 (≤800 제약 충족). | 신규 |
| `scripts/monitor_server/__init__.py` | TSK-02-02: `from .api import handle_state, handle_graph, handle_task_detail, handle_merge_status` 재수출 추가. | 수정 |
| `scripts/monitor-server.py` | `do_GET` 내 `/api/graph`, `/api/task-detail`, `/api/merge-status` 분기를 `api.handle_*`로 위임. `_route_api_state`도 `api.handle_state`로 위임. 기존 `_handle_api_state`, `_handle_graph_api`, `_handle_api_task_detail`, `_handle_api_merge_status` 함수는 shim으로 유지. | 수정 |
| `scripts/test_monitor_module_split.py` | `ApiModuleImportTests` 클래스 추가: `test_import_api` (4개 함수 import 검증), `test_api_under_800_lines` (줄 수 제약 검증). | 수정 |

## 테스트 결과

| 구분 | 통과 | 실패 | 합계 |
|------|------|------|------|
| 단위 테스트 (4개 파일 통합) | 188 | 0 | 188 |

상세:
- `test_monitor_module_split.py`: 23/23 passed (신규 ApiModuleImportTests 2개 포함)
- `test_monitor_task_detail_api.py`: 63/63 passed (회귀 0)
- `test_monitor_graph_api.py`: 55/55 passed (회귀 0)
- `test_monitor_merge_badge.py`: 47/47 passed (회귀 0)

## E2E 테스트 (작성만 — 실행은 dev-test)

| 파일 경로 | 검증 대상 |
|-----------|-----------|
| N/A — backend domain | 백엔드 엔드포인트 이전만 (UI 없음) |

## 커버리지 (Dev Config에 coverage 정의 시)

N/A — Dev Config에 coverage 명령 미정의

## 비고

- **순환참조 방지**: `api.py`는 `monitor-server.py`를 직접 import하지 않음. `_get_monitor_server_fn()` 헬퍼로 `sys.modules['monitor_server']`에서 flat 모듈 함수를 지연 참조.
- **shim 패턴**: 기존 `_handle_api_state`, `_handle_graph_api`, `_handle_api_task_detail`, `_handle_api_merge_status`는 monitor-server.py에 그대로 유지 — 기존 테스트들이 flat 모듈 로딩으로 직접 접근하므로 회귀 없음 확인.
- **api.py 줄 수**: 643줄 (AC-FR07-c: ≤800 충족).
- design.md에 없는 파일 추가 없음.
- Merge Preview: uncommitted changes로 merge-preview.json 기록 실패(무해, 선택적 가드레일).
