# TSK-02-06: 리팩토링 내역

## 변경 사항

| 파일 | 변경 내용 (요약) | 적용 기법 |
|------|-----------------|-----------|
| `scripts/monitor-server.py` | `LOG_NAMES` → `_LOG_NAMES` (모듈 private 일관성 — 파일 내 다른 모든 상수가 `_` 접두사 사용) | Rename |
| `scripts/monitor-server.py` | `_tail_report` 내 `Path(path)` 3회 중복 호출 → 지역 변수 `p = Path(path)` 추출 후 재사용 | Extract Variable, Remove Duplication |

## 테스트 확인

- 결과: PASS
- 실행 명령:
  - `python3 -m pytest -q scripts/test_monitor_task_detail_api.py` → 63 passed
  - `python3 -m pytest -q scripts/ -k "logs or log_tail or collect_logs or slide_panel or section_order or panel_body or log_css"` → 19 passed (TSK-02-06 특정)
  - `python3 -m py_compile scripts/monitor-server.py` → OK
  - 전체 suite: 1344 passed, 14 pre-existing failed (TSK-02-06 변경과 무관)

## 비고

- 케이스 분류: **A (성공)** — 변경 적용 후 테스트 통과
- `LOG_NAMES` 이름 변경은 테스트 파일이 직접 import하지 않아 안전하게 적용 가능 (`grep` 확인 완료)
- `renderLogs` JS 내 `'마지막 200줄'` 하드코딩은 Python/JS 경계로 인해 런타임 상수 공유가 불가하며, constraints에 "상수 200 (환경변수 토글 없음)"이 명시되어 있어 수정 범위 외로 판단
