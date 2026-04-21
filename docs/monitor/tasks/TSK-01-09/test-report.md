# TSK-01-09: HTML 렌더 경로 dataclass 보존 (DEFECT-3 후속) - 테스트 보고서

**실행일**: 2026-04-21
**실행 모델**: Opus (호출자 지정)
**Domain**: backend (unit_test 정의됨, e2e_test 없음)

---

## 실행 요약

| 구분 | 통과 | 실패 | 스킵 | 합계 |
|------|------|------|------|------|
| 자동화 단위·통합 테스트 (monitor 계열 9개 파일) | 240 | 0 | 4 | 244 |
| 수동 HTML 렌더 회귀 검증 (live server) | 4 | 0 | 0 | 4 |

---

## 1. 자동화 테스트

**명령**:
```
python3 -m pytest scripts/test_monitor_server_bootstrap.py scripts/test_monitor_render.py scripts/test_monitor_api_state.py scripts/test_monitor_server.py scripts/test_monitor_tmux.py scripts/test_monitor_scan.py scripts/test_monitor_launcher.py scripts/test_monitor_pane.py scripts/test_monitor_signal_scan.py -q
```

**결과**: `240 passed, 4 skipped in 5.62s`

핵심 통과 그룹:
- `test_monitor_api_state.py` (17개 `_build_state_snapshot` 호출 지점 포함) — 모두 통과 → **외부 JSON 계약 불변 확인**
- `test_monitor_render.py` — `_render_task_row` / `_section_wbs` / `_section_features` 등 렌더러 단위 테스트 통과
- `test_monitor_scan.py` — `scan_tasks` / `scan_features`의 `error` 필드 포함 케이스 포함

---

## 2. 수동 HTML 렌더 회귀 검증 (live HTTP)

서버를 `scripts/monitor-launcher.py --port 7321 --docs docs/monitor` 로 기동하고 curl로 직접 검증했다.

| # | 검증 항목 | 기대값 | 실제값 | 판정 |
|---|-----------|--------|--------|------|
| H1 | `GET /` task-row 개수 | 13 (현재 docs/monitor/tasks/TSK-* 개수) | 13 | **PASS** |
| H2 | 첫 task-row id span | `<span class="id">TSK-00-01</span>` | `<span class="id">TSK-00-01</span>` | **PASS** |
| H3 | 첫 task-row title span | 비어있지 않음 (WBS에서 불러온 제목) | `dev-monitor 스킬 디렉터리 생성 및 plugin.json 등록` | **PASS** |
| H4 | 첫 task-row status 배지 | `✅ DONE` (state.json `[xx]` 반영) | `<span class="badge badge-xx">✅ DONE</span>` | **PASS** |

`GET /api/state` JSON 응답에서는 `wbs_tasks[0]`의 16개 필드(`bypassed`, `completed_at`, `depends`, `elapsed_seconds`, `error`, `id`, `kind`, `last_event`, `last_event_at`, `path`, `phase_history_tail`, `started_at`, `status`, `title`, `wp_id`, `bypassed_reason`) 모두 보존 확인 — **JSON 계약 불변**.

---

## QA 체크리스트 판정

- [x] `_build_render_state()`가 `_build_state_snapshot()`과 동일한 8개 key 반환 — PASS
- [x] `_build_render_state()` 반환의 원소가 `WorkItem` dataclass 인스턴스 — PASS (H2~H4가 getattr 성공의 증거)
- [x] `_build_state_snapshot()` 시그니처 불변 (17개 기존 테스트 통과) — PASS
- [x] `GET /` task-row의 id/title/status span에 실제 값 렌더 — PASS (H1~H4)
- [x] `/api/state` JSON 8개 최상위 키 + `wbs_tasks[0]` 16개 필드 보존 — PASS
- [x] monitor 계열 자동화 테스트 240건 회귀 없음 — PASS

---

## 최종 판정

**테스트 상태: PASS**

**근거**:
- 자동화 240건 통과, 회귀 없음
- HTML 렌더 H1~H4 전부 통과, DEFECT-3 재현 안 됨
- `/api/state` JSON 계약 수치적으로 불변

**상태 전이**: `test.ok` → status `[ts]`

---

**테스트 실행자**: TSK-01-09 수행 세션 (Opus)
**실행 환경**: macOS Darwin 25.4.0, Python 3.9 stdlib
**검증 일시**: 2026-04-21 UTC
