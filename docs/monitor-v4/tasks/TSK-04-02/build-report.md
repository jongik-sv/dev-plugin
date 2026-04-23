# TSK-04-02: TDD 구현 결과

## 결과: PASS

## 생성/수정된 파일

| 파일 경로 | 변경 내용 | 신규/수정 |
|-----------|-----------|-----------|
| `scripts/merge-preview-scanner.py` | WP별 merge-preview.json 집계 + AUTO_MERGE_FILES 필터 + 상태 판정(ready/waiting/conflict) + merge-status.json 원자 쓰기. CLI: `--docs`, `--force`, `--daemon`. | 신규 |
| `scripts/monitor-server.py` | `/api/merge-status` 라우트 추가 (_is_api_merge_status_path, _handle_api_merge_status, _load_merge_status, _collect_merge_summary, _badge_label_for_state). `_build_state_snapshot`에 `merge_summary` 필드 추가. `do_GET` 분기 추가. `import time` 추가. | 수정 |
| `scripts/test_merge_preview_scanner.py` | TSK-04-02 단위 테스트 (36개): scanner 로직, API 라우트, /api/state 번들, race-safe. | 신규 |
| `scripts/test_monitor_api_state.py` | `_build_state_snapshot` 키 집합 테스트에 `merge_summary` 추가 (스키마 확장 반영). | 수정 |

## 테스트 결과

| 구분 | 통과 | 실패 | 합계 |
|------|------|------|------|
| 단위 테스트 (신규) | 36 | 0 | 36 |
| 단위 테스트 (기존 회귀) | 68 | 0 | 68 |

## E2E 테스트 (작성만 — 실행은 dev-test)

N/A — backend domain

## 커버리지 (Dev Config에 coverage 정의 시)

N/A — Dev Config에 coverage 명령 미정의

## 비고

- `import time` 누락: `monitor-server.py`는 기존에 `time` 모듈을 import하지 않았으나 `_load_merge_status`와 `_collect_merge_summary`에서 `time.time()` 사용이 필요하여 추가.
- pre-existing 실패: `test_monitor_filter_bar.py` 2건(applyFilter/depGraph 누락), E2E 서버 의존 테스트들은 TSK-04-02 변경 전부터 실패 중이었으며 본 Task 변경과 무관함.
- 경계 조건 설계 결정: `is_stale`은 `now - mtime > STALE_SECONDS`(strictly greater)로 구현하여 정확히 1800s 경계는 stale로 판정하지 않음.
- merge-preview.json 기록: uncommitted changes로 skip (non-fatal).
