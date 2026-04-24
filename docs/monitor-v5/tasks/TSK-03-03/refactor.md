# TSK-03-03: 리팩토링 내역

## 변경 사항

| 파일 | 변경 내용 (요약) | 적용 기법 (콤마 구분) |
|------|-----------------|----------------------|
| `scripts/monitor_server/renderers/depgraph.py` | `import html as _html`을 함수 내 지역 임포트에서 모듈 레벨 임포트로 이동. `<ul>` 태그의 불필요한 `class="dep-graph-legend"` 제거 (CSS에 해당 클래스 셀렉터 규칙 없음, id 셀렉터로 충분) | Move Import to Module Level, Remove Dead Code |

## 테스트 확인
- 결과: PASS
- 실행 명령: `python3 -m pytest -q scripts/test_monitor_critical_color.py -v`
- 16/16 테스트 통과

## 비고
- 케이스 분류: A (성공) — 리팩토링 변경 적용 후 테스트 통과
- `style.css`는 코드 품질 관점에서 이미 충분히 정돈되어 있어 변경 없음 (토큰 선언, 규칙 순서, 주석 모두 명확)
- `test_monitor_critical_color.py`도 테스트 구조가 명확하고 중복 없음 — 변경 없음
