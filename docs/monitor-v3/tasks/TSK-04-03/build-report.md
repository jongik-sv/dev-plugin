# TSK-04-03: TDD 구현 결과

## 결과: PASS

## 생성/수정된 파일

| 파일 경로 | 변경 내용 | 신규/수정 |
|-----------|-----------|-----------|
| `scripts/monitor-server.py` | DASHBOARD_CSS `.dep-node*` 블록 전면 교체 (3중 단서, hover lift, critical 글로우, bottleneck dashed, color-mix graceful degradation, 캔버스 640px) | 수정 |
| `scripts/test_monitor_dep_graph_html.py` | TSK-04-03 3종 테스트 + 부가 테스트 추가 (TestDepGraphCssRulesPresent, TestDepGraphCanvasHeight640, TestDepGraphStatusMultiCue) | 수정 |
| `scripts/test_monitor_render.py` | `test_canvas_height_520px` → `test_canvas_height_640px` 업데이트 (520→640 반영) | 수정 |

## 테스트 결과

| 구분 | 통과 | 실패 | 합계 |
|------|------|------|------|
| 단위 테스트 (TSK-04-03 신규) | 14 | 0 | 14 |
| 전체 단위 테스트 (회귀 검사) | 1091 | 0 | 1091 |

E2E 테스트(test_monitor_e2e.py, test_monitor_dep_graph_html_e2e.py)는 현재 기동 중인 이전 버전 서버로 인해 일부 실패하나, 이는 dev-test 단계에서 새 서버 기동 후 검증 대상임.

## E2E 테스트 (작성만 — 실행은 dev-test)

| 파일 경로 | 검증 대상 |
|-----------|-----------|
| `scripts/test_monitor_dep_graph_html_e2e.py` | 기존 E2E: dep-node CSS 존재, graph-client.js 서빙, node-html-label 플러그인 로드 (서버 기동 후 자동 실행) |

## 커버리지 (Dev Config에 coverage 정의 시)
- N/A (Dev Config에 coverage 명령 미정의)

## 비고
- **기존 테스트 업데이트**: `test_monitor_render.py::DepGraphSectionEmbeddedTests::test_canvas_height_520px`가 구 동작(520px)을 고정하고 있었으므로 `test_canvas_height_640px`로 이름 변경 + 어서션 수정 (설계 변경 반영).
- **CSS 색상 토큰 일치 주석**: design.md 리스크 메모대로 `var(--done)=#4ed08a`, `var(--run)=#4aa3ff` 는 legend(`#22c55e`, `#eab308`)와 상이함. 스트립 색상과 legend 색상 정합은 후속 CSS 토큰 정합 TSK에서 처리 예정 (AC-21 완전 충족은 그 시점).
- **TSK-04-03 구현 내용 요약**: `.dep-node` width 180px/padding 10px 12px 10px 16px/border-left 4px, hover lift(translateY(-1px) + box-shadow), 5종 상태별 3중 단서(border-left-color + --_tint color-mix() + dep-node-id color), .dep-node.critical(붉은 글로우 + border-color: var(--fail)), .dep-node.bottleneck(border-style: dashed), canvas height 640px.
