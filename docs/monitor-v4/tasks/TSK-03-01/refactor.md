# TSK-03-01: 리팩토링 내역

## 변경 사항

| 파일 | 변경 내용 (요약) | 적용 기법 (콤마 구분) |
|------|-----------------|----------------------|
| skills/dev-monitor/vendor/graph-client.js | `getStatusKey()` if-체인을 `_STATUS_MAP` lookup table로 교체 + 도달 불가능한 `bypassed` 중복 분기 제거 | Replace Conditional with Lookup, Remove Dead Code |
| skills/dev-monitor/vendor/graph-client.js | `applyDelta()` 내 노드 추가/갱신/엣지 추가 로직을 `_addNode`, `_updateNode`, `_addEdge` 함수로 추출 | Extract Method |
| skills/dev-monitor/vendor/graph-client.js | `renderPopover()` HTML 빌더를 string concatenation에서 template literal로 통일 + popover 위치 계산을 `_positionPopover`로 추출 | Replace String Concatenation with Template Literal, Extract Method |
| skills/dev-monitor/vendor/graph-client.js | `renderPopover()`에서 label 출력 시 `escapeHtml` 적용 (XSS 방지 강화) | Security Fix |

## 테스트 확인
- 결과: PASS
- 실행 명령: `python3 -m unittest scripts.test_monitor_graph_hover scripts.test_monitor_dep_graph_html`
- 50 tests OK in 0.008s

## 비고
- 케이스 분류: A (성공) — 리팩토링 변경 적용 후 전체 단위 테스트 통과
- `_positionPopover` 추출로 pan/zoom 시에도 위치 갱신 로직이 재사용 가능해짐
- `renderPopover` 내 label의 `escapeHtml` 적용은 기존 누락이었던 XSS 방어 보강 (동작 변경이 아닌 보안 강화)
