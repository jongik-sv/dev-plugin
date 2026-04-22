# monitor-redesign-v3: 리팩토링 내역

## 변경 사항

| 파일 | 변경 내용 (요약) | 적용 기법 (콤마 구분) |
|------|-----------------|----------------------|
| scripts/monitor-server.py | v1 잔재 함수 `_render_task_row`, `_section_wbs` 제거 (호출처 없음) | Remove Dead Code |
| scripts/monitor-server.py | 중복 ISO 파싱 함수 `_parse_iso` 제거; 유일 호출처 `_spark_buckets`를 `_parse_iso_utc`로 대체 | Remove Duplication |
| scripts/monitor-server.py | `_SUBAGENT_BADGE_CSS` dict 제거 (v3 CSS 전환 후 미사용) | Remove Dead Code |
| scripts/monitor-server.py | `_SPARK_COLORS` 값을 v1 색상 변수(`--orange`, `--red` 등)에서 v3 CSS 변수(`--run`, `--fail`, `--bypass`, `--done`, `--pending`)로 수정 | Rename |
| scripts/monitor-server.py | `_section_wp_cards`에서 미사용 `donut_style` 변수 제거 | Remove Dead Code |
| scripts/monitor-server.py | v1 CSS 선택자 블록 정리 — `.pane-row`, `ol.phase-list`, `.page`, `.page-col-left/right`, `.pane-link`, `.kpi-card .kpi-val`, `.kpi-card .kpi-lbl`, `.chip-group` 제거 (v3 동등 선택자로 이미 대체됨) | Remove Dead Code |
| scripts/monitor-server.py | `_section_live_activity`: `data-to` 값 `"run"` → `"running"`, `"fail"` → `"failed"` 수정; CSS 클래스 `a-time`→`t`, `a-id`→`tid`, `a-event`→`evt`, `a-elapsed`→`el`로 v3 정렬; `.panel .activity` 래퍼 추가 | Rename, Inline |
| scripts/monitor-server.py | `_section_phase_timeline`: CSS 클래스 `tl-lbl`→`lbl`, `tl-tick`→`tick major` + `tlabel`로 v3 정렬; `.tl-container` 제거; `.panel .timeline` 래퍼 추가 | Rename |
| scripts/monitor-server.py | `_section_wp_cards`: v1 `<div class="wp-card">` 구조를 v3 `<details class="wp" open>` + `wp-head` 마크업으로 완전 재작성 | Rename, Extract Method |
| scripts/monitor-server.py | `_section_features`: `.features-wrap` 래퍼 추가 | Rename |
| scripts/monitor-server.py | `_section_team`: `.panel .team` 래퍼 추가 | Rename |
| scripts/monitor-server.py | `_render_pane_row`: v3 `.pane-head` + `.name` + `.meta` + `.mini-btn` 구조로 재작성 | Rename |
| scripts/monitor-server.py | `_render_subagent_row`: v3 `.sub` 필 + `.sw` + `.n` 구조로 재작성 | Rename |
| scripts/monitor-server.py | `_section_subagents`: `<details>` 그룹 구조를 플랫 `.panel .subs` 구조로 전환 | Rename, Inline |
| scripts/monitor-server.py | `_section_kpi`: 칩 래퍼 클래스 `.chip-group` → `.chips`; 각 칩에 `.sw` 스팬 추가 | Rename |

## 테스트 확인
- 결과: PASS
- 실행 명령: `python3 -m unittest scripts.test_monitor_render -v`
- 119개 테스트 전체 통과 (Ran 119 tests in 0.284s)

## 비고
- 케이스 분류: A (성공) — 모든 리팩토링 변경 적용 후 단위 테스트 통과
- v3 CSS 설계 문서(`docs/features/monitor-redesign-v3/design.md`) 기준으로 Python 렌더러 출력 클래스명과 CSS 선택자를 전수 대조하여 불일치 10여 건 수정
- `_wp_donut_style`, `_timeline_svg` 함수는 테스트(`skipUnless(hasattr(...))` 가드)에서 직접 참조하므로 미사용이더라도 보존
- 공개 API(함수 시그니처, `/api/pane/{id}` 엔드포인트, 데이터클래스 필드, `scan_signals`/`list_tmux_panes` 반환 구조) 변경 없음
