# TSK-01-04: TDD 구현 결과

## 결과: PASS

## 생성/수정된 파일

| 파일 경로 | 변경 내용 | 신규/수정 |
|-----------|-----------|-----------|
| `scripts/monitor-server.py` | 신규 함수 9개 추가: `_parse_iso_utc`, `_fmt_hms`, `_fmt_elapsed_short`, `_live_activity_rows`, `_section_live_activity`, `_phase_of`, `_timeline_rows`, `_x_of`, `_timeline_svg`, `_section_phase_timeline`. `_SECTION_ANCHORS`에 `activity`, `timeline` 앵커 2개 추가 (상수 4개: `_KNOWN_PHASES`, `_LIVE_ACTIVITY_LIMIT`, `_TIMELINE_MAX_ROWS`, `_TIMELINE_SPAN_MINUTES`) | 수정 |
| `scripts/test_monitor_render_tsk04.py` | 신규 단위 테스트 60개 (9개 클래스: `TestParseIsoUtc`, `TestFmtHms`, `TestFmtElapsedShort`, `TestLiveActivityRows`, `TestSectionLiveActivity`, `TestTimelineRows`, `TestTimelineSvg`, `TestSectionPhaseTimeline`, `TestSectionAnchors`) | 신규 |
| `scripts/test_monitor_e2e.py` | TSK-01-04 E2E 테스트 클래스 `LiveActivityTimelineE2ETests` 6개 케이스 추가 | 수정 (build 작성, 실행은 dev-test) |

## 테스트 결과

| 구분 | 통과 | 실패 | 합계 |
|------|------|------|------|
| 단위 테스트 (TSK-01-04 전용) | 60 | 0 | 60 |
| 전체 단위 테스트 (기존 포함) | 319 | 0 | 319 |

기존 319개 테스트 모두 통과 확인 (5개 skip 유지).

## E2E 테스트 (작성만 — 실행은 dev-test)

| 파일 경로 | 검증 대상 |
|-----------|-----------|
| `scripts/test_monitor_e2e.py` → `LiveActivityTimelineE2ETests` | QA 체크리스트 fullstack/frontend 필수 항목: #activity/#timeline 네비 앵커 reachability, 섹션 id 존재, inline SVG 외부 자원 미포함 |

## 커버리지 (Dev Config에 coverage 정의 시)
- N/A (Dev Config에 `quality_commands.coverage` 미정의)

## 비고
- design.md에 명시된 함수 8개 + `_phase_of`(내부 헬퍼) + `_x_of`(SVG 좌표 변환) 총 10개 함수 추가. `_phase_of`와 `_x_of`는 설계 코드 예시에 포함된 함수이지만 별도 명시되지 않아 추가 구현 이유를 기록함.
- `_SECTION_ANCHORS`에 `activity`/`timeline` 앵커 추가 → `_section_header`가 자동으로 nav 링크 생성.
- `render_dashboard` sections 리스트에 `_section_live_activity`/`_section_phase_timeline` 삽입은 TSK-01-07(상위 조립) 범위이므로 이 Task에서는 함수 정의만 수행.
- WpCardsSectionE2ETests / StickyHeaderKpiSectionE2ETests 12개 E2E 실패는 TSK-01-03/TSK-01-02 기능이 현재 worktree에 미병합된 pre-existing 상태로 TSK-01-04 변경과 무관.
