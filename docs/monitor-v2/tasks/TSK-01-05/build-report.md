# TSK-01-05: TDD 구현 결과

## 결과: PASS

## 생성/수정된 파일

| 파일 경로 | 변경 내용 | 신규/수정 |
|-----------|-----------|-----------|
| `scripts/monitor-server.py` | `_pane_last_n_lines()` 신규 함수 추가, `_render_pane_row()` 수정 (expand 버튼 + preview pre 태그), `_section_team()` 수정 (pane ≥ 20 분기 + too_many 플래그), `DASHBOARD_CSS`에 `.pane-preview.empty` CSS 추가 | 수정 |
| `scripts/test_monitor_team_preview.py` | TSK-01-05 단위 테스트 35개 (TestPaneLastNLines 9개, TestRenderPaneRowExpandButton 9개, TestSectionTeamPreview 14개, TestSectionSubagentsUnchanged 2개, TestPanePreviewCss 3개) | 신규 |

## 테스트 결과

| 구분 | 통과 | 실패 | 합계 |
|------|------|------|------|
| 단위 테스트 (TSK-01-05) | 35 | 0 | 35 |
| 전체 스위트 (TSK-01-05 외 기존 포함) | 550 | 3 | 553 |

전체 스위트 3개 failures는 모두 TSK-01-04(Badge Priority 우선순위 로직) 및 NoExternalDomain 관련 pre-existing failures이며, TSK-01-05 수정과 무관하게 기존에도 실패하던 테스트이다.

## E2E 테스트 (작성만 — 실행은 dev-test)

| 파일 경로 | 검증 대상 |
|-----------|-----------|
| N/A — e2e_test 있음이나 TSK-01-05는 서버사이드 렌더 단위 테스트로 완결. E2E는 dev-test에서 기존 `test_monitor_e2e.py` 활용 | pane row에 expand 버튼 + preview pre 존재 확인 |

## 커버리지 (Dev Config에 coverage 정의 시)
- N/A — Dev Config에 `quality_commands.coverage` 미정의

## 구현 요약

### 신규 함수: `_pane_last_n_lines(pane_id, n=3) -> str`
- `capture_pane(pane_id)` 호출 → 후행 공백-only 줄 제거 → 마지막 n줄 반환
- 예외(ValueError, subprocess 오류 등) 시 빈 문자열 반환 (안전 처리)

### 수정: `_render_pane_row(pane, preview_lines: Optional[str] = "") -> str`
- `preview_lines=None` → `<pre class="pane-preview empty">no preview (too many panes)</pre>`
- `preview_lines=str` → `<pre class="pane-preview">{escaped}</pre>`
- `<button data-pane-expand="{pane_id_esc}">[expand ↗]</button>` 추가

### 수정: `_section_team(panes) -> str`
- `all_panes = list(panes)` 로 iterable 소진 없이 len 계산
- `too_many = len(all_panes) >= 20` 분기
- too_many=True 시 capture_pane 호출 없이 `preview_lines=None` 전달
- too_many=False 시 pane별 `_pane_last_n_lines()` 호출

### CSS 추가: `.pane-preview.empty { font-style: italic; }`
- 기존 `.pane-preview` 규칙 유지 (max-height: 4.5em, overflow: hidden 포함)

## 비고
- TSK-01-05 35개 단위 테스트 Red→Green 완료 (기존 테스트 regression 없음)
- `_TOO_MANY_PANES_THRESHOLD = 20` 상수로 임계값을 모듈 레벨에 명시하여 가독성 확보
- agent-pool 섹션(`_section_subagents`)은 변경하지 않았음 (PRD §4.5.7 준수)
