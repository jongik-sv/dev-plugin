# Phase 2 착수 판단 메모

core-decomposition feature 의 Refactor Phase 에서 측정된 결과로
Phase 2 (`core-http-split`) 착수 필요성을 문서화한다. design.md §8 의
임계값 표와 직접 비교한다.

## 측정값 (Refactor Phase 최종)

| 지표 | 임계 | 측정값 | 판정 |
|------|------|--------|------|
| core.py 잔여 LOC | > 2,000 | **6,874** | ❌ 초과 (3.4× 임계) |
| HTTP handler 그룹 LOC | > 1,500 | **484** (7개 `_handle_*` 합계) | ✅ 아직 미달 |
| MonitorHandler 메서드 수 | > 20 | **11** | ✅ 아직 미달 |
| NF-03 위반 (≥ 800) | core.py | **6,874** | ❌ 초과 (8.6× NF-03) |

측정 커맨드:

```bash
wc -l scripts/monitor_server/core.py
# 6874 scripts/monitor_server/core.py

# _handle_* 개별 LOC: refactor.md "측정 결과" 참조
# _handle_static 57, _handle_pane_html 32, _handle_pane_api 49,
# _handle_graph_api 154, _handle_api_task_detail 35,
# _handle_api_merge_status 27, _handle_api_state 130
# 합계 484 LOC

# MonitorHandler 메서드 수
awk '/^class MonitorHandler/,/^class [A-Z]|^def [a-z]|^run_server/' \
    scripts/monitor_server/core.py | grep -c "^    def "
# 11
```

## 의사결정

**Phase 2 착수 권고 = YES.**

근거:
- core.py 가 여전히 6,874 LOC 로 NF-03 (≤ 800) 를 8.6배 초과한다.
- design.md §8 에서 명시한 "한 지표라도 true 이면 Phase 2 착수" 기준을
  core.py 잔여 LOC 지표가 명확히 충족한다.
- HTTP handler 합계(484 LOC)는 임계 미달이지만, core.py LOC 의 다수는
  HTML 렌더러(`_render_*`/`_section_*` 계열 ~1,036 LOC) + DASHBOARD_CSS /
  _DASHBOARD_JS 인라인 상수(수천 LOC)가 차지한다. 이 인라인 자산은
  메모리 doc `project_monitor_server_inline_assets.md` 에서 지적한
  "시각 회귀 자석" 패턴에 해당한다.

## Phase 2 권장 범위 (별도 feature 로 분리)

Phase 2 를 일괄 1개 feature 로 다루기에는 scope 이 너무 크므로 순차 분할
권고:

1. **core-http-split** (Phase 2-a)
   - `MonitorHandler` + `_handle_*` 7 개 함수 → `handlers.py` 로 이관
   - 기대 core.py 감소: ~500 LOC

2. **core-dashboard-asset-split** (Phase 2-b, 선택)
   - `DASHBOARD_CSS`, `_DASHBOARD_JS`, `_PANE_CSS`, `_task_panel_css`,
     `_task_panel_js` 등 인라인 자산을 `static/dashboard.css` +
     `static/dashboard.js` 파일로 분리, `get_static_bundle()` 에서 파일
     로드로 대체
   - 기대 core.py 감소: ~3,000 LOC (dominate)
   - 리스크: 시각 회귀 검증 필요 (dashboard rendering smoke + snapshot)

3. **core-renderer-split** (Phase 2-c, 선택)
   - `_render_*` / `_section_*` 함수를 `renderers/` 서브패키지로 흡수
   - 기대 core.py 감소: ~1,000 LOC
   - 이미 `renderers/_util.py` 공유 인프라 존재 → 저비용

Phase 2-a 만 착수해도 `MonitorHandler` 메서드 수 임계(20)와 handler 그룹
LOC 임계(1,500)는 장기적으로 여유가 확보된다. Phase 2-b 는 시각 회귀
리스크로 별도 머지 전 시각 QA 필수.

## 본 feature 범위 완료 선언

- Phase 0 (cleanup): ✅ 완료 (baseline 과 Δ = 0)
- Phase 1 (5-way split): ✅ 완료 (각 신규 모듈 ≤ 800 LOC)
- Phase 2 (HTTP split): ⏭️ 별도 feature 로 분리 — 본 feature 는 착수하지
  않음 (design.md 명시 범위 밖)
