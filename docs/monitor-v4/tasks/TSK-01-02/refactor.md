# TSK-01-02: 리팩토링 내역

## 변경 사항

| 파일 | 변경 내용 (요약) | 적용 기법 |
|------|-----------------|-----------|
| `scripts/monitor-server.py` | `_arow_data_to(event, to_s)` 헬퍼 추출 — data-to CSS 값 계산 로직을 `_section_live_activity` 내부 인라인에서 독립 함수로 분리 | Extract Method |
| `scripts/monitor-server.py` | `_render_arow(item_id, entry, dt, sig_content)` 헬퍼 추출 — 단일 phase_history 항목을 `.arow` div HTML로 렌더하는 ~30줄 루프 바디를 독립 함수로 분리. `_section_live_activity` 내 루프가 list comprehension 한 줄로 단순화 | Extract Method, Remove Duplication |
| `scripts/monitor-server.py` | `patchSection` JS 내 `wp-cards`/`live-activity` 분기 통합 — 동일한 3-line 패턴(`innerHTML=newHtml; applyFoldStates; bindFoldListeners`)이 두 번 반복되던 것을 `_FOLD_SECTIONS = {'wp-cards':1, 'live-activity':1}` 집합 조회 단일 분기로 치환. 향후 fold 섹션 추가 시 집합에만 항목을 추가하면 됨 | Remove Duplication, Introduce Explaining Variable |

## 테스트 확인
- 결과: PASS
- 실행 명령: `/usr/bin/python3 -m pytest scripts/ --ignore=scripts/test_monitor_e2e.py -q`
- 단위 테스트: 1157 passed, 0 failed, 15 skipped
- TSK-01-02 직접 테스트: `pytest scripts/test_monitor_fold_live_activity.py` → 18/18 passed
- E2E 실패(10건): 리팩토링 전(baseline)과 동일 — `git stash`로 baseline 검증 완료. 모두 pre-existing 이슈(외부 폰트 링크, E2E 서버 미연동 등)이며 TSK-01-02 변경 범위 밖

## 비고
- 케이스 분류: **A (리팩토링 성공)** — 변경 적용 후 단위 테스트 전부 통과
- `_render_arow` 분리로 `_section_live_activity` 함수 길이가 ~70줄 → ~20줄로 단축
- `_arow_data_to` 분리로 data-to 계산 로직을 독립 단위로 테스트 가능해짐 (현재 테스트는 통합 경로로 커버됨)
- JS `_FOLD_SECTIONS` 객체는 함수 내부 지역변수로 선언 — 전역 오염 없음. 인라인 JS 특성상 module scope가 없어 객체 리터럴 `{key:1}` 패턴을 Set 대신 사용
