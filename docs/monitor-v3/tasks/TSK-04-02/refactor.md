# TSK-04-02: 리팩토링 내역

## 변경 사항

| 파일 | 변경 내용 (요약) | 적용 기법 (콤마 구분) |
|------|-----------------|----------------------|
| `skills/dev-monitor/vendor/graph-client.js` | `nodeHtmlTemplate`과 `nodeStyle`에 중복 존재하던 WBS 상태 코드 → CSS/COLOR 키 변환 로직을 `getStatusKey(node)` 헬퍼로 추출. `nodeStyle`에서 `COLOR[key]` 룩업으로 단순화. | Extract Method, Remove Duplication |

**LOC 변화**: 315 → 321 (헬퍼 함수 추가, ≤350 제약 유지)

## 테스트 확인
- 결과: PASS
- 실행 명령: `python3 -m pytest -q scripts/test_monitor_dep_graph_html.py`
- 통과: 24 / 24

## 비고
- 케이스 분류: A (리팩토링 성공 — 변경 적용 후 테스트 통과)
- `scripts/` 전체 실행 시 `test_monitor_dep_graph_html_e2e.py`의 `test_dep_node_css_present` 1개 실패 관찰. 이 실패는 stash 전후 동일하게 재현되는 **pre-existing 이슈** (현재 실행 중인 서버가 구버전 코드 기반이라 dep-node CSS가 미포함). TSK-04-02 리팩토링과 무관.
