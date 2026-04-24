# dep-graph-arrowheads: 리팩토링 내역

## 변경 사항

변경 없음(기존 코드가 이미 충분히 정돈됨)

변경 범위는 `skills/dev-monitor/vendor/graph-client.js`의 edge selector 스타일 객체에
`"arrow-scale": 2` 와 `"target-distance-from-node": 4` 두 줄을 추가한 것이 전부이다.
기존 스타일 객체의 속성 순서·네이밍·포맷팅이 파일 내 다른 스타일 블록과 일관되므로
추가 리팩토링이 필요한 코드 냄새(중복·긴 함수·마법 숫자 무맥락 노출 등)는 없다.

`"arrow-scale": 2` 숫자 상수는 `COLOR` 상수 패턴과 다르게 인라인으로 선언되어 있으나,
cytoscape 스타일 블록 내에서는 inline literal이 관용적 표현이며 단일 사용처라서 Named Constant
추출 대비 가독성 이점이 없다고 판단한다. 변경하지 않는다.

## 테스트 확인
- 결과: PASS
- 실행 명령: `python3 -m pytest docs/features/dep-graph-arrowheads/test_edge_style.py -v`
- 4 tests collected, 4 passed, 0 failed

## 비고
- 케이스 분류: A (성공 — 리팩토링 불필요 판정 후 테스트 통과)
