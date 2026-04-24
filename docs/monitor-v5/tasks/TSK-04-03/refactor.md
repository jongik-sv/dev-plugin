# TSK-04-03: 리팩토링 내역

## 변경 사항

| 파일 | 변경 내용 (요약) | 적용 기법 (콤마 구분) |
|------|-----------------|----------------------|
| `scripts/monitor-server.py` | `_render_pane_row`에서 선언 후 미사용 변수 `pane_idx` 제거 | Remove Dead Code |
| `scripts/monitor-server.py` | `_section_team`의 `_pane_last_n_lines` 호출에 `n=_PANE_PREVIEW_LINES` 명시 전달 — 기본값 암묵 의존 제거 | Make Implicit Explicit, Single Source of Truth |

## 테스트 확인
- 결과: PASS
- 실행 명령: `python3 scripts/test_monitor_pane_size.py` (9개) + `python3 scripts/test_monitor_team_preview.py` (35개)
- 총 44개 테스트 전부 통과.

## 비고
- 케이스 분류: A (리팩토링 성공 — 변경 적용 후 테스트 통과)
- `pane_idx`는 TSK-04-03 build 단계에서 `_pane_index` 사용 의도로 선언됐으나 실제 HTML 템플릿에 포함되지 않아 dead code 상태였음. 제거해도 모든 테스트 통과 및 렌더 결과 동일.
- `n=_PANE_PREVIEW_LINES` 명시는 동작을 변경하지 않으나(기본값과 동일), 호출 지점에서 "6줄"의 단일 출처가 명확히 드러나므로 향후 줄 수 변경 시 누락 없이 반영된다.
