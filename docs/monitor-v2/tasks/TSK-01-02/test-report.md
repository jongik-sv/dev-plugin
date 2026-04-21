# TSK-01-02: `_section_sticky_header` + `_section_kpi` 렌더 함수 신규 - 테스트 결과

## 결과: FAIL (integration pending TSK-01-04)

## 실행 요약

| 구분 | 통과 | 실패 | 합계 |
|------|------|------|------|
| 단위 테스트 | 517 | 0 | 517 |
| E2E 테스트 | 29 | 7 | 36 |

## 상세 분석

### 단위 테스트 결과: ✅ PASS (517/517)

모든 unit test 통과. `test_monitor_kpi.py`의 KPI 관련 테스트 완전 통과:

**KPI 함수 단위 테스트 (52개 테스트)**:
- `TestKpiCountsFunction`: bypass > failed > running > done > pending 우선순위 검증 완전 통과
- `TestSparkBuckets`: phase_history 1분 버킷 집계, kind별 이벤트 매핑 모두 통과
- `TestKpiSparkSvg`: SVG polyline 생성, title 태그, viewBox 포맷 모두 통과
- `TestSectionStickyHeader`: sticky-hdr class, refresh-toggle, logo-dot, XSS escape 모두 통과
- `TestSectionKpi`: data-kpi 5개 속성, filter chips 4개, kpi-section class 모두 통과

### E2E 테스트 결과: ⚠️ FAIL (7개 테스트 실패)

**실패 원인**: `render_dashboard()` 함수에 `_section_sticky_header()`와 `_section_kpi()` 호출이 아직 추가되지 않음.

**설계상 현황**: design.md 명시 —  "E2E 검증은 TSK-01-04 완료 후 `/` GET 응답에서 수행". 즉, `render_dashboard()` 조립 로직은 **TSK-01-04 범위**.

**실패한 E2E 테스트** (모두 render_dashboard 미호출 원인):
1. `test_sticky_header_present` — `class="sticky-hdr"` 미포함
2. `test_kpi_section_present` — `class="kpi-section"` 미포함
3. `test_refresh_toggle_button_present` — refresh-toggle 버튼 미포함
4. `test_five_kpi_cards_present` — `data-kpi` 속성 미포함
5. `test_four_filter_chips_present` — `data-filter` 칩 미포함
6. `test_sparkline_svgs_in_kpi_cards` — sparkline SVG 미포함
7. `test_activity_section_id_present` — activity 섹션 미포함 (다른 TSK 범위)

## 정적 검증

| 구분 | 결과 | 비고 |
|------|------|------|
| lint | pass | `python3 -m py_compile scripts/monitor-server.py` 통과 |

## QA 체크리스트 판정

| # | 항목 | 결과 |
|---|------|------|
| 1 | `_kpi_counts([], [], [])` 반환값 합 == 0 | pass |
| 2 | bypass 우선순위 처리 | pass |
| 3 | bypass + failed 동시: bypass 선택 | pass |
| 4 | running + done 동시: running 선택 | pass |
| 5 | 5개 값 합 == 전체 Task 수 | pass |
| 6 | 중복 시그널 우선순위 처리 | pass |
| 7 | `_spark_buckets` span_min 범위 정확성 | pass |
| 8 | `_spark_buckets` 반환 리스트 길이 == span_min | pass |
| 9 | `_kpi_spark_svg` max_val=0 평탄선 | pass |
| 10 | `_kpi_spark_svg` SVG `<title>` 태그 | pass |
| 11 | `_section_kpi()` data-kpi 5개 | pass |
| 12 | `_section_kpi()` data-filter 4개 | pass |
| 13 | `_section_sticky_header()` class="sticky-hdr" | pass |
| 14 | `_section_sticky_header()` XSS escape | pass |
| 15 | `_section_sticky_header()` refresh 라벨 형식 | pass |
| 16 | model에 project_root 미포함: 정상 동작 | pass |
| 17 | sticky header 스크롤 고정 (E2E) | unverified |
| 18 | KPI 카드 1줄 5등분 레이아웃 (E2E) | unverified |

## 재시도 이력

첫 실행에 통과: Unit test 517/517 완전 성공

## 비고

**상황 정리**:

TSK-01-02는 함수 신규 추가(`_kpi_counts`, `_spark_buckets`, `_kpi_spark_svg`, `_section_sticky_header`, `_section_kpi`)를 담당. 이들 함수가 `render_dashboard()`에 호출되도록 조립하는 작업은 **TSK-01-04 범위**로 설계됨.

test_monitor_e2e.py의 StickyHeaderKpiSectionE2ETests는 render_dashboard 미호출로 인해 자연스럽게 실패하며, 설계상 이들 E2E 테스트는 TSK-01-04 이후 통과할 예정.

**Task 완성도**:
- 함수 구현: ✅ 완료
- 단위 테스트: ✅ 전체 통과 (517/517)
- 정적 검증: ✅ lint 통과
- 통합(render_dashboard): ⏳ TSK-01-04 대기

**결론**: TSK-01-02의 개별 함수들은 설계·구현·단위테스트 모두 완료. E2E 실패는 종속성(TSK-01-04) 미해결에 기인하는 자연스러운 결과.
