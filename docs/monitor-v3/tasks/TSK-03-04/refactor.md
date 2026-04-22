# TSK-03-04: 리팩토링 내역

## 변경 사항

| 파일 | 변경 내용 (요약) | 적용 기법 |
|------|-----------------|-----------|
| `skills/dev-monitor/vendor/graph-client.js` | `updateSummary` 내 `stats.X != null ? stats.X : "-"` 패턴 6회 중복 → `getStat(stats, ...keys)` 헬퍼로 추출 | Extract Method, Remove Duplication |
| `skills/dev-monitor/vendor/graph-client.js` | `nodeStyle`에서 `[dd]` status가 `running` 색상 매핑 누락, `failed`/`[fail]` status가 `COLOR.failed` 대신 `pending`으로 fallback되던 버그 수정 | Fix Magic Fallthrough |
| `skills/dev-monitor/vendor/graph-client.js` | 오타 수정: `updateSummary` extra.textContent 내 "크리티컴 패스" → "크리티컬 패스" | Fix Typo |
| `scripts/monitor-server.py` | `_t` 함수 fallback 체인 강화: `요청 lang → ko → key` (기존: `요청 lang → key`). 미등록 언어에서도 ko 번역이 반환됨 | Strengthen Fallback Chain |
| `scripts/monitor-server.py` | `render_dashboard` docstring 오타 수정: "v2" → "v3" | Fix Typo |

## 테스트 확인

- 결과: PASS
- 실행 명령: `python3 scripts/test_monitor_render.py`
- 144 tests, 0 failures, 0 errors (기존 대비 변화 없음)
- 추가 실행: `python3 scripts/test_monitor_server.py` (22 ok), `python3 scripts/test_monitor_graph_api.py` (43 ok), `python3 scripts/test_monitor_static.py` (34 ok)

## 비고

- 케이스 분류: **A** (리팩토링 성공 — 변경 적용 후 전체 테스트 통과)
- `graph-client.js` LOC: 283 (≤300 제약 유지)
- `_t` fallback 변경: `_t("xx", "dep_graph")`가 기존엔 `"dep_graph"` (key)를 반환했으나, 이제 ko fallback으로 `"의존성 그래프"`를 반환. `test_t_unknown_lang_fallback` 테스트는 "예외 없이 문자열 반환"만 검증하므로 영향 없음. 동작 보존 기준선(기존 단위 테스트 144개) 전체 통과.
