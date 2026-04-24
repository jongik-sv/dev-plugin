# TSK-02-01: 리팩토링 내역

## 변경 사항

| 파일 | 변경 내용 (요약) | 적용 기법 (콤마 구분) |
|------|-----------------|----------------------|
| `scripts/monitor_server/renderers/activity.py` | `Optional` import 추가 + `"str | None"` 문자열 리터럴 타입 힌트를 `Optional[str]`로 통일 — 다른 모듈(`subagents.py`, `team.py`, `wp.py`)과 일관성 확보 | Rename, Coding Style |
| `scripts/monitor_server/renderers/depgraph.py` | `_phase_data_attr` import 주석 정확도 개선: "used by `_build_graph_payload` indirectly" → "re-exports via `monitor_server.renderers.depgraph` for downstream consumers" (실제 사용 경로 명확화) | Rename (주석 수정) |
| `scripts/monitor_server/renderers/_util.py` | 심볼 그룹 분리 + 주석 보완: (1) 현재 렌더러에서 활성 사용하는 심볼 그룹과 (2) taskrow.py 커밋 6(본문 이전) 이후 활성화 예정인 예비 심볼 그룹으로 분리. `_drawer_backdrop_html = None` 불필요 라인 제거. 각 섹션에 의도를 명시하는 주석 추가 | Rename (주석/구조 정리), Remove Duplication |

## 테스트 확인
- 결과: PASS
- 실행 명령: `python3 -m pytest -q scripts/test_monitor_module_split.py scripts/test_monitor_api_state.py scripts/test_monitor_graph_api.py`
- 통과: 144개 (test_monitor_module_split.py 21개 + test_monitor_api_state.py 68개 + test_monitor_graph_api.py 55개)
- 실패: 0개

**전/후 실패 수 동일 확인**: 리팩토링 전 stash → 동일 테스트 셋 실행 → 동일 13개 pre-existing 실패 확인 → 리팩토링 변경이 실패에 영향 없음 검증 완료.

## 비고
- 케이스 분류: **A (성공)** — 변경 적용 후 단위 테스트 통과
- 동작 변경 0 확인: 타입 힌트·주석·코드 구조 정리만. 런타임 로직 변경 없음.
- `_util.py`의 예비 심볼 10개(`_wrap_with_data_section`, `_PHASE_LABELS`, `_PHASE_CODE_TO_ATTR`, `_row_state_class`, `_format_elapsed`, `_clean_title`, `_retry_count`, `_MAX_ESCALATION`, `_encode_state_summary_attr`, `_build_state_summary_json`)는 현재 렌더러에서 직접 import하지 않으나 유지. taskrow.py 커밋 6(본문 이전) 시점까지 보존 필요.
- 모듈 크기 변화: `_util.py` 69→74줄, `activity.py` 66→68줄 소폭 증가. 모두 AC-FR07-c(≤800줄) 충족.
- pre-existing 실패 13개(E2E/render): TSK-02-01 범위 외 — `test_monitor_e2e.py`, `test_monitor_render.py`의 후속 WP Task 범위 실패로 본 Task 리팩토링과 무관.
