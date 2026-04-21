# TSK-01-02: 리팩토링 내역

## 변경 사항

| 파일 | 변경 내용 (요약) | 적용 기법 (콤마 구분) |
|------|-----------------|----------------------|
| `scripts/monitor-server.py` | `_kpi_labels` 로컬 dict를 모듈 상수 `_KPI_LABELS`로 추출, `_KPI_ORDER` 상수 추출 | Extract Variable (Module Constant), Remove Duplication |
| `scripts/monitor-server.py` | `_kpi_counts`에서 `bypass_ids & all_ids` 중복 집합 연산 제거 → `len(bypass_ids)`로 단순화 | Simplify Conditional, Remove Duplication |
| `scripts/monitor-server.py` | `_kpi_spark_svg`에서 중간 변수 `x = i` 제거, 리스트 컴프리헨션으로 포인트 생성 인라인화 | Inline, Simplify |

### 변경 상세

1. **모듈 상수 `_KPI_LABELS`, `_KPI_ORDER` 추출** (`_SPARK_COLORS` 바로 아래)
   - `_section_kpi` 내부에 매 호출마다 생성되던 `kpi_labels` dict와 `kpi_order` list를 모듈 수준 상수로 이동
   - `_SPARK_COLORS`, `_KPI_LABELS`, `_KPI_ORDER` 세 상수가 같은 위치에 모여 KPI 관련 설정을 한눈에 파악 가능

2. **`_kpi_counts` 중복 집합 연산 제거**
   - `bypass_ids`는 `{id for item in all_items if item.bypassed}` — 이미 `all_ids`의 부분집합
   - `n_bypass = len(bypass_ids & all_ids)` → `n_bypass = len(bypass_ids)`로 단순화
   - 의미가 동일하며 불필요한 집합 교집합 연산 제거

3. **`_kpi_spark_svg` 포인트 생성 인라인화**
   - 중간 변수 `x = i`(단순 재할당), 빈 리스트 `pts = []`, `pts.append(...)` 패턴을 리스트 컴프리헨션으로 교체
   - `pts = [f"{i},{24 - int(24 * val / max_val)}" for i, val in enumerate(buckets)]`

## 테스트 확인
- 결과: PASS
- 실행 명령: `python3 -m unittest discover scripts/ -v`
- 결과: 558 tests, 0 failures, 6 skipped
- lint: `python3 -m py_compile scripts/monitor-server.py` — OK

## 비고
- 케이스 분류: **A** (리팩토링 성공 — 변경 적용 후 단위 테스트 전체 통과)
- `_KPI_LABELS`의 CSS `text-transform: uppercase` 관계는 주석으로 기존 코드에도 명시되어 있음. 모듈 상수 추출로 `_section_kpi` 내부에서 동일 구조를 반복 정의하는 문제 해소.
