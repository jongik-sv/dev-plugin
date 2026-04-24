# TSK-04-03: TDD 구현 결과

## 결과: PASS

## 생성/수정된 파일

| 파일 경로 | 변경 내용 | 신규/수정 |
|-----------|-----------|-----------|
| `scripts/monitor-server.py` | `.pane-head` padding `20px 14px 16px`; `.pane-preview` `max-height: 9em`, `overflow-y: auto`; `::before content "▸ last 6 lines"`; `[lang=ko] .pane-preview::before "▸ 최근 6줄"` 추가; `_PANE_PREVIEW_LINES = 6` 상수 추가; `_pane_last_n_lines` 기본값 `n=_PANE_PREVIEW_LINES`; `_section_team` 호출 `n=_PANE_PREVIEW_LINES` 명시 | 수정 |
| `scripts/test_monitor_pane_size.py` | AC-FR04-a~d 단위 테스트 (9개): max-height, label, padding, 상수, overflow-y, 기본값, 통합, 에러 케이스 | 신규 |
| `scripts/test_monitor_team_preview.py` | `test_returns_last_3_lines`, `test_strips_trailing_blank_lines`에 `n=3` 명시; `test_pane_preview_max_height`를 `9em` 기대값으로 업데이트 | 수정 |
| `scripts/test_monitor_e2e.py` | `PaneCardSizeE2ETests` 클래스 추가 (6개): team 섹션 도달, max-height, 라벨, padding, overflow-y, 한국어 모드 | 수정 (build 작성, 실행은 dev-test) |

## 테스트 결과

| 구분 | 통과 | 실패 | 합계 |
|------|------|------|------|
| 단위 테스트 (test_monitor_pane_size.py) | 9 | 0 | 9 |
| 단위 테스트 (test_monitor_team_preview.py) | 35 | 0 | 35 |
| 전체 단위 테스트 (E2E 제외) | 1660 | 12 | 1672 |

전체 12개 실패는 TSK-04-03 변경과 무관한 pre-existing 실패:
- 10개: TSK-04-02 미commit 변경으로 인한 `TskTooltipStateSummaryTests` 실패 (`#trow-tooltip` → `#trow-info-popover` 교체)
- 2개: HEAD 코드 기준 pre-existing 실패 (`KpiCountsTests::test_done_excludes_bypass_failed_running`, `TestDepGraphCanvasHeight640`)

## E2E 테스트 (작성만 — 실행은 dev-test)

| 파일 경로 | 검증 대상 |
|-----------|-----------|
| `scripts/test_monitor_e2e.py::PaneCardSizeE2ETests` | AC-FR04-a (max-height 9em), AC-FR04-b (last 6 lines 라벨), AC-FR04-d (padding), overflow-y auto, 한국어 ?lang=ko, team 섹션 reachability |

## 커버리지 (Dev Config에 coverage 정의 시)
- N/A (coverage 명령 미정의)

## 비고
- `_PANE_PREVIEW_LINES = 6` 상수를 `_pane_last_n_lines` 함수 정의 직전에 위치시켜 Python 전방 참조 문제 방지
- `test_monitor_team_preview.py`의 기존 `test_returns_last_3_lines`, `test_strips_trailing_blank_lines`는 기본값 의존에서 `n=3` 명시 호출로 업데이트 (design.md 리스크 섹션 예측 적중)
- `test_pane_preview_max_height` 기존 테스트를 `4.5em` → `9em` 기대값으로 업데이트
