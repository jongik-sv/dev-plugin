# TSK-02-05: 리팩토링 내역

## 변경 사항

| 파일 | 변경 내용 (요약) | 적용 기법 |
|------|-----------------|-----------|
| `scripts/monitor-server.py` | `_render_task_row_v2` 내 `_retry_count(item)` 중복 호출 제거 — line 3058에서 이미 계산한 `rc` 변수를 retry 셀 렌더(line 3090)에 재사용 | Remove Duplication |

## 테스트 확인
- 결과: PASS
- 실행 명령:
  - `/usr/bin/python3 -m pytest scripts/test_monitor_task_row.py scripts/test_monitor_phase_models.py -v` → **73 passed**
  - `/usr/bin/python3 -m pytest scripts/ -q --ignore=scripts/test_monitor_e2e.py` → **1396 passed, 9 skipped**

## 비고
- 케이스 분류: **A (성공)** — 변경 적용 후 테스트 통과
- 나머지 코드(CSS, JS, 함수 구조)는 설계 의도를 이미 잘 반영하고 있어 추가 변경 불필요:
  - `_build_state_summary_json`과 `_render_task_row_v2`가 각자 독립적으로 `_retry_count`를 호출하는 구조는 함수 경계 원칙(pure function, 독립 테스트 가능)상 의도적 설계이므로 유지
  - `--warn` 변수 대신 `--pending` 사용은 `--warn`이 패널 스코프 한정 CSS 변수라 전역 대시보드에서 `--pending`(#f0c24a 황색)이 경고색으로 의도대로 작동함
