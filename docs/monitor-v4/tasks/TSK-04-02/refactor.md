# TSK-04-02: 리팩토링 내역

## 변경 사항

| 파일 | 변경 내용 (요약) | 적용 기법 |
|------|-----------------|-----------|
| `scripts/merge-preview-scanner.py` | `import datetime`를 모듈 상단으로 이동 (함수 내 지역 import 제거) | Remove Duplication, Move Import |
| `scripts/merge-preview-scanner.py` | `_classify_wp` 반환부에서 `pending_count` 이중 분기(`if/else`) 제거 → 단일 dict literal로 통합 | Simplify Conditional, Inline |
| `scripts/monitor-server.py` | `is_stale` 계산 로직(`(time.time() - mtime) > STALE_SECONDS + OSError fallback`)이 3곳 중복 → `_is_merge_status_stale(path, data)` 헬퍼로 추출 | Extract Method, Remove Duplication |

## 테스트 확인

- 결과: PASS
- 실행 명령: `python3 -m pytest -q scripts/test_merge_preview_scanner.py`
- 36 passed in 0.18s

전체 suite (`pytest -q scripts/`) 실행 결과: 1618 passed, 45 failed, 22 skipped. 실패 45건은 리팩토링 전과 동일한 pre-existing failures (E2E 서버 미기동 관련 e2e 테스트 + 다른 Task 미구현 기능 테스트)이며 TSK-04-02 범위 코드 변경으로 인한 회귀 없음 확인.

## 비고

- 케이스 분류: A (리팩토링 성공 — 변경 적용 후 테스트 통과)
- `_is_merge_status_stale` 헬퍼는 `_load_merge_status` (단일 WP 경로), `_load_merge_status` (전체 WP 목록 경로), `_collect_merge_summary` 세 곳에서 동일 패턴을 공유했던 중복을 해소. 향후 stale 임계값 변경 시 단일 지점만 수정하면 됨.
