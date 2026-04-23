# TSK-04-04: 리팩토링 내역

## 변경 사항

| 파일 | 변경 내용 (요약) | 적용 기법 (콤마 구분) |
|------|-----------------|----------------------|
| `scripts/monitor-server.py` | `_section_dep_graph` 내 `summary_html` 6회 반복 문자열 연결을 `_STAT_STATES` 튜플 + generator expression + `" ".join()` 으로 압축 (20줄 → 6줄) | Remove Duplication, Replace Inline Repetition with Loop |
| `scripts/test_monitor_dep_graph_summary.py` | 각 TestCase의 `setUp` 중복(`_import_server()` 호출 + `hasattr` 가드)을 `_DepGraphBase` 공통 base class로 추출. `_REQUIRES_DEP_GRAPH`/`_REQUIRES_CSS` 플래그로 skip 조건 선언적 관리. `legend_colors` dict comprehension으로 정리 | Extract Superclass, Remove Duplication, Simplify Conditional |

## 테스트 확인
- 결과: PASS
- 실행 명령: `python3 -m pytest scripts/test_monitor_dep_graph_summary.py scripts/test_monitor_render.py -v`
- TSK-04-04 관련 5개 + 기존 render 235개 = 총 240개 모두 통과

## 비고
- 케이스 분류: A (리팩토링 성공 — 변경 적용 후 테스트 통과)
- `scripts/` 전체 실행(`pytest scripts/ --tb=no -q`) 시 17개 실패가 나타나나, 이는 아직 미구현 TSK(04-01/02/03/05/06)의 테스트 파일(untracked)과 pre-existing E2E 이슈(`test_monitor_e2e.py`)이며 TSK-04-04 리팩토링 전후 동일하게 존재함 — 회귀 없음
- CSS 색상 토큰(`var(--done)` 등) 교체는 설계 시 제외(리스크 섹션 명시): `DASHBOARD_CSS`의 `--done=#4ed08a`와 legend 하드코딩 `#22c55e`이 달라 `test_dep_graph_summary_legend_parity`가 실패하므로 이번 범위 밖
