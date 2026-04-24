# TSK-05-02: 리팩토링 내역

## 변경 사항

| 파일 | 변경 내용 (요약) | 적용 기법 |
|------|-----------------|-----------|
| `scripts/_test_monitor_helpers.py` | `parse_frontmatter()` + `read_skill_md()` 공통 헬퍼 모듈 신규 추출 | Extract Module, Remove Duplication |
| `scripts/test_dev_monitor_skill_md.py` | 중복 `_parse_frontmatter` / `_read_skill_md` 인라인 정의 제거 → 헬퍼 import로 대체; `import re` 제거 | Remove Duplication, Inline |
| `scripts/test_dev_monitor_trigger.py` | 중복 `_parse_frontmatter` 인라인 정의 제거 → 헬퍼 import로 대체; 각 테스트 함수의 반복 `exists()`/`read_text()` 호출을 모듈 수준 `_FM` 상수로 통합 | Remove Duplication, Extract Variable |

### 핵심 변경 상세

- **중복 제거**: `_parse_frontmatter()` 함수가 두 테스트 파일에 각각 정의되어 있었음. 두 구현이 미묘하게 달랐는데(`strip('"')` vs 양끝 따옴표 분기처리), 더 정확한 `trigger.py` 방식을 공통 헬퍼에 채택하여 동작 통일.
- **반복 패턴 정리**: `test_dev_monitor_trigger.py`의 4개 테스트가 각각 `SKILL_MD.exists()` + `read_text()` + `_parse_frontmatter()` 3단계를 반복했음. 모듈 수준 `_FM = parse_frontmatter(read_skill_md())`로 한 번만 실행하도록 정리.
- **동작 보존**: 테스트 로직(assert 조건, 에러 메시지) 변경 없음. 동작을 바꾸는 일체의 수정 없음.

## 테스트 확인
- 결과: PASS
- 실행 명령: `python3 -m pytest -q scripts/test_dev_monitor_skill_md.py scripts/test_dev_monitor_trigger.py`
- 통과: 8/8

## 비고
- 케이스 분류: **A (리팩토링 성공)** — 변경 적용 후 테스트 통과.
- `infra` 도메인 Dev Config에 `unit_test: null`이 설정되어 있으나, TSK-05-02 전용 테스트 파일(`test_dev_monitor_skill_md.py`, `test_dev_monitor_trigger.py`)이 존재하므로 이를 대상으로 리팩토링 검증 수행.
