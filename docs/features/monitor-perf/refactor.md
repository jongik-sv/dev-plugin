# monitor-perf: 리팩토링 내역

## 변경 사항

| 파일 | 변경 내용 (요약) | 적용 기법 |
|------|-----------------|-----------|
| `scripts/monitor_server/static/app.js` | `onVisibilityChange`의 visible 복귀 경로: `tick()` + `stopMainPoll()` + `setInterval()` 수동 3단계를 `startMainPoll()` 단일 호출로 통합 (`startMainPoll`이 내부적으로 `stopMainPoll` + `tick` + `setInterval` 순서를 이미 보장하므로 중복 제거) | Inline, Remove Duplication, Simplify Conditional |
| `scripts/monitor_server/etag_cache.py` | `_normalize_etag` docstring: "RFC 7232 §2.3: weak-etag 비교는 대소문자 구분 없음" 표현이 부정확하여 실제 의도("SHA-256 hex는 항상 소문자이므로 클라이언트 혼합 대소문자를 정규화")로 개선 | Clarify Doc |
| `scripts/monitor_server/core.py` | `_json_response` 200 분기의 헤더 설정 순서를 304 분기와 일치시킴: `ETag` → `Content-Type` → `Content-Length` → `Cache-Control` (기능 변화 없음, 가독성·일관성 향상) | Normalize |

## 테스트 확인

- 결과: **PASS**
- 실행 명령:
  ```
  python3 -m pytest scripts/test_monitor_etag.py scripts/test_monitor_polling_visibility.py scripts/test_monitor_gpu_audit.py scripts/test_monitor_perf_regression.py -v
  ```
- 결과 요약: 39 passed, 4 skipped (Playwright 미설치로 인한 성능 회귀 테스트 4건 skip — 설계 시 의도된 skip 조건)

## 비고

- 케이스 분류: **A** (리팩토링 성공 — 변경 적용 후 테스트 전량 통과)
- 인라인 모놀리스(`core.py` 6947줄) 범위 외 정리는 Feature 범위 원칙에 따라 이번 사이클에서 제외. 변경 surface를 monitor-perf 구현 영역(ETag/visibility 관련 3개 파일)으로 최소화.
- 테스트 4개 파일의 공통 MockHandler/setUp 패턴은 각각 독립적이고 가볍게 유지되어 있어 공통 base class 추출보다 현상 유지가 유지보수 관점에서 유리하다고 판단 — 중복 정리 대상에서 제외.
