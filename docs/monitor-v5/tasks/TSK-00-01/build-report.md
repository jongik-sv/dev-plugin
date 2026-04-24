# TSK-00-01: TDD 구현 결과

## 결과: FAIL

**사유**: `pytest -q scripts/` exit 1 — 3개 실패 (acceptance criterion: exit 0 미충족).
v4 기존 코드의 미해결 회귀 테스트 오불일치가 원인이며, TSK-00-01의 코드 변경 0 제약으로 수정 불가.

## 생성/수정된 파일

| 파일 경로 | 변경 내용 | 신규/수정 |
|-----------|-----------|-----------|
| `docs/monitor-v5/baseline.md` | v4 기준선 기록 (커밋 SHA, 태그명, pytest 결과, 플러그인 캐시 확인) | 신규 |

> 코드 변경 0 제약 — baseline.md 외 어떤 파일도 수정하지 않았다.

## 테스트 결과

| 구분 | 통과 | 실패 | 스킵 | 합계 | exit code |
|------|------|------|------|------|-----------|
| 단위 테스트 (`pytest -q scripts/`) | 1689 | **3** | 169 | 1861 | **1** |

### 실패 상세

| # | 테스트 | 원인 |
|---|--------|------|
| 1 | `test_monitor_dep_graph_html.py::TestDepGraphCanvasHeight640::test_dep_graph_canvas_height_640` | `height:640px` 단순 검색 실패 — 실제 구현 `clamp(640px, 78vh, 1400px)` |
| 2 | `test_monitor_render.py::KpiCountsTests::test_done_excludes_bypass_failed_running` | running 시그널 task가 done에서 미제외 (1 != 0) |
| 3 | `test_monitor_render.py::DepGraphSectionEmbeddedTests::test_canvas_height_640px` | `height:640px` 단순 검색 실패 (동일 원인) |

## E2E 테스트 (작성만 — 실행은 dev-test)

N/A — infra domain (코드 변경 없는 측정/태깅 Task)

## 커버리지

N/A — Dev Config에 coverage 미정의

## 비고

- **git tag 생성 완료**: `monitor-server-pre-v5` → `f1e7e7d7509675e8f579acf8282a4d3eafba4b9e`
- **플러그인 캐시 일치 확인**: `~/.claude/plugins/marketplaces/dev-tools/scripts/monitor-server.py` MD5 = `f360c1fc683e146b6713fc0c57d06940` (프로젝트와 동일)
- **3개 실패 테스트 분류**: TSK-04-03 구현 시 responsive height(`clamp`) 적용 후 테스트 미갱신 → v5 S1에서 수정 대상. KPI done 로직 버그 → v5 범위에서 수정.
- AC 중 태그 생성과 baseline.md 기재는 완료. `pytest exit 0`만 미충족.
