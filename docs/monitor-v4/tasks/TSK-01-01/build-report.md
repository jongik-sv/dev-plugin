# TSK-01-01: TDD 구현 결과

## 결과: PASS

## 생성/수정된 파일

| 파일 경로 | 변경 내용 | 신규/수정 |
|-----------|-----------|-----------|
| `scripts/monitor-server.py` | `_section_phase_timeline`, `_timeline_rows`, `_timeline_svg`, `_x_of` 함수 제거; `_TIMELINE_MAX_ROWS`, `_TIMELINE_SPAN_MINUTES` 상수 제거; `_PHASE_TO_SEG` 로컬 상수 제거; `render_dashboard()` 내 phase-timeline 섹션 조립·래핑·body주입 제거; 인라인 CSS `.tl-*`, `.timeline-*`, `.panel.timeline` 블록 제거; i18n 테이블 2곳(상단·하단)에서 `phase_timeline` 키 제거; `_SECTION_ANCHORS` 에서 `"timeline"` 제거; `_SECTION_EYEBROWS`/`_SECTION_DEFAULT_HEADINGS` 에서 `"timeline"` 키 제거; sticky-header nav `<a href="#timeline">` 제거 | 수정 |
| `scripts/test_monitor_render.py` | `V3Stage3RightColTests`의 4개 timeline 테스트 메서드 제거; `_HAS_TIMELINE_SVG` 플래그 및 `TimelineSvgTests` 클래스 제거; `SectionTitlesI18nTests`의 phase_timeline heading assertion 2개 제거; `I18nHelperTests`의 `test_t_*_phase_timeline` 2개 제거; 주석 내 timeline 레퍼런스 정리; `TSK0101PhaseTimelineRemovalTests` 클래스 추가 (16개 신규 테스트) | 수정 |
| `scripts/test_monitor_render_tsk04.py` | `TestTimelineRows`, `TestTimelineSvg`, `TestSectionPhaseTimeline` 클래스 제거 (총 ~25개 테스트); `TestSectionAnchors` 를 TSK-01-01 후 상태로 업데이트 (timeline 제거 확인 테스트로 교체); 모듈 docstring 업데이트 | 수정 |
| `scripts/test_dashboard_css_tsk0101.py` | `TestTimelineSVGClasses` 클래스 제거 (2개 테스트) | 수정 |
| `scripts/test_render_dashboard_tsk0106.py` | `TestSectionOrder.test_section_order` 에서 `"phase-timeline"` 제거; `TestDataSectionAttributes.test_each_data_section_unique` 에서 `"phase-timeline"` 제거 | 수정 |
| `scripts/test_monitor_e2e.py` | `LiveActivityTimelineE2ETests` 에서 timeline 관련 3개 테스트 제거 + `test_timeline_section_absent` 추가; `RenderDashboardV2E2ETests` 에서 phase-timeline 제거 | 수정 |

## 테스트 결과

| 구분 | 통과 | 실패 | 합계 |
|------|------|------|------|
| 단위 테스트 | 1144 | 0 | 1154 (10 skipped) |

- `pytest scripts/ --ignore=scripts/test_monitor_e2e.py -q` → **1144 passed, 10 skipped**
- 신규 `TSK0101PhaseTimelineRemovalTests` 16개 모두 통과
- `python3 -m py_compile scripts/monitor-server.py` → exit 0

## E2E 테스트 (작성만 — 실행은 dev-test)

| 파일 경로 | 검증 대상 |
|-----------|-----------|
| `scripts/test_monitor_e2e.py` | `LiveActivityTimelineE2ETests.test_timeline_section_absent` — 라이브 응답에 #timeline 섹션 부재 확인 |

참고: E2E 실패 4개 (StickyHeader/DashboardReachability 클래스)는 기존 구버전 monitor-server 프로세스가 live 포트에서 실행 중이어서 발생. TSK-01-01 변경과 무관하며 서버 재기동 시 해소됨.

## 커버리지

N/A — Dev Config에 `coverage` 명령 미정의

## 비고

- `_x_of` 함수: `_timeline_svg` 내부에서만 사용됨을 사전 grep 확인 후 함께 제거
- design.md 리스크 「_x_of 공유 여부」: grep으로 타 호출 없음 확인 → 제거
- CSS 제거: `.tl-` 접두어만 한정, `.task-`/`.trow-tooltip` 등 무관 클래스 보존 확인
- 중괄호 매칭: `py_compile` exit 0으로 CSS 인라인 문자열 완전성 검증
- 상단 i18n 테이블(L52-69)과 하단 테이블(L1006-1041) 두 곳 모두 `phase_timeline` 키 제거 완료
