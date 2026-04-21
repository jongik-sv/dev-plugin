# TSK-04-03: 리팩토링 내역

## 변경 사항

| 파일 | 변경 내용 (요약) | 적용 기법 (콤마 구분) |
|------|-----------------|----------------------|
| `scripts/test_platform_smoke.py` | `tearDownClass` 중복 로직을 `_cleanup_proc()` 헬퍼로 추출 | Extract Method, Remove Duplication |
| `scripts/test_platform_smoke.py` | `_has_main_section()` 헬퍼로 중복 섹션 검증 조건식 추출 | Extract Method, Remove Duplication |
| `scripts/test_platform_smoke.py` | `_TEST_PORT_SHUTDOWN = 7397` 상수로 인라인 매직 넘버 제거 | Replace Magic Number |
| `scripts/test_platform_smoke.py` | `subprocess`, `tempfile` import를 함수 내부에서 모듈 최상단으로 이동 | Inline, 불필요한 지역 import 제거 |
| `scripts/test_platform_smoke.py` | `_start_server()` 반환문을 불필요한 중간 변수 없이 직접 return으로 단순화 | Simplify |
| `scripts/test_platform_smoke.py` | 미사용 `urllib.error` import 제거 | Remove Dead Code |

## 테스트 확인
- 결과: PASS
- 실행 명령: `python3 -m unittest scripts/test_platform_smoke.py -v`
- 11/11 통과 (1.746s)

## 비고
- 케이스 분류: A (성공) — 리팩토링 적용 후 전체 테스트 통과
- 동작 보존: dev-build가 통과시킨 11개 단위 테스트 모두 동일하게 통과
- 기능 변경 없음: 테스트 로직(포트, 대기 시간, 검증 조건)은 변경하지 않았으며, 코드 구조 개선만 적용
