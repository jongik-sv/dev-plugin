# wp-progress-spinner: 리팩토링 내역

## 변경 사항

| 파일 | 변경 내용 (요약) | 적용 기법 |
|------|-----------------|-----------|
| `scripts/monitor_server/renderers/wp.py` | busy indicator HTML 생성 로직을 `_wp_busy_indicator_html(busy_label)` 헬퍼로 추출 | Extract Method |
| `scripts/monitor_server/core.py` | 동일한 busy indicator HTML 생성 로직을 `_wp_busy_indicator_html(busy_label)` 헬퍼로 추출 | Extract Method, Remove Duplication |

### 상세

`_section_wp_cards()` 내 busy indicator HTML 생성 로직이 `core.py`와 `renderers/wp.py` 양쪽에 if/else 분기로 인라인 중복 존재했다. 각 파일에 `_wp_busy_indicator_html(busy_label)` 헬퍼를 추출하여 가독성을 개선하고 중복을 제거했다.

헬퍼 시그니처:
```python
def _wp_busy_indicator_html(busy_label: "Optional[str]") -> str:
```
- `busy_label is None` → 빈 문자열 반환
- `busy_label` 있음 → `aria-live` 컨테이너 + `.wp-busy-spinner` + `.wp-busy-label` HTML 반환

## 테스트 확인

- 결과: PASS
- 실행 명령: `python3 scripts/test_monitor_wp_spinner.py` (34 tests OK)
- 추가 회귀 확인: `test_monitor_api_state.py` (71 OK), `test_monitor_etag.py` (24 OK), `test_monitor_perf_regression.py` (4 OK, skipped=4)

## 비고

- 케이스 분류: A (성공) — 리팩토링 적용 후 모든 테스트 통과
- `core.py`와 `renderers/wp.py`가 `_section_wp_cards`를 각각 독립 정의하는 구조는 기존 리팩토링 진행 중인 shim 전환 아키텍처이며, 이번 Feature 범위(wp-progress-spinner) 밖이므로 손대지 않았다.
