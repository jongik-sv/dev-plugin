# TSK-03-01: 리팩토링 내역

## 변경 사항

| 파일 | 변경 내용 (요약) | 적용 기법 |
|------|-----------------|-----------|
| `scripts/monitor-server.py` | `mobile_timeline_js` 로컬 변수를 `_MOBILE_TIMELINE_JS` 모듈 상수로 추출 | Extract Constant |
| `scripts/monitor-server.py` | col_left/col_right/grid HTML 빌딩 로직을 `_build_dashboard_grid()` 헬퍼 함수로 추출 | Extract Method |
| `scripts/monitor-server.py` | 문자열 연결(`+` 패턴)을 `"\n".join([...])` 패턴으로 일관성 있게 정리 | Simplify Conditional |

### 상세

**1. `_MOBILE_TIMELINE_JS` 모듈 상수 추출**

`render_dashboard` 안에서 매 호출마다 로컬 변수로 정의하던 모바일 타임라인 접힘 JS를 `_DASHBOARD_JS` 근처의 모듈 상수로 올렸다. 이 문자열은 호출마다 동일하므로 반복 생성은 불필요하다. 주석도 추가하여 의도를 명확히 했다.

**2. `_build_dashboard_grid()` 헬퍼 함수 추출**

`render_dashboard`에서 col_left/col_right/grid HTML을 구성하는 12줄을 별도 함수로 분리했다. 추출 후 `render_dashboard` 함수 본문이 35줄에서 15줄로 줄었다. 헬퍼는 독립적으로 단위 테스트 가능하며, 이후 그리드 구조가 변경될 때 수정 범위를 한 곳으로 제한한다.

**3. 문자열 조합 패턴 정리**

암묵적 문자열 연결(`"...\n" + expr + "\n" + "..."`)을 `"\n".join([...])` 패턴으로 변경했다. 새 함수와 기존 `_section_phase_history` 등에서 사용하는 패턴이 통일되어 일관성이 높아졌다.

## 테스트 확인
- 결과: PASS
- 실행 명령: `python3 -m unittest discover scripts/ -v`
- 통과: 339/339 (skipped 5)
- lint: `python3 -m py_compile scripts/monitor-server.py` PASS

## 비고
- 케이스 분류: A (성공) — 변경 적용 후 전체 테스트 통과
- 1차 실행에서 2건 실패가 관측되었으나, 리팩토링 변경 전 코드에서도 동일하게 재현됨(서버 포트 충돌로 인한 간헐적 실패). 2차 실행에서 339/339 통과 확인.
