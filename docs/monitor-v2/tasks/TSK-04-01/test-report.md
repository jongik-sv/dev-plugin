# TSK-04-01: 단위 테스트 추가 (unittest) - Test Report

## 실행 요약

| 구분        | 통과 | 실패 | 합계 |
|-------------|------|------|------|
| 단위 테스트 | 277  | 2    | 299  |
| E2E 테스트  | -    | -    | -    |
| 정적 검증   | -    | -    | -    |

**테스트 결과**: 2개 실패, 22개 스킵 (정상)

## 실패 상세

### 1. test_meta_refresh_present_in_live_response
**위치**: `test_monitor_e2e.py::MetaRefreshLiveTests`

**실패 원인**:
```
AssertionError: 0 != 1 : expected exactly one meta refresh, got []
```

**근본 원인 분석**:
- E2E 테스트가 실제 서버 응답 HTML을 검사했을 때, `<meta http-equiv="refresh" content="...">` 태그가 없음
- `render_dashboard()` 함수의 소스 코드(line 1118)에는 분명히 메타 리프레시 태그 생성 로직이 있음:
  ```python
  f'  <meta http-equiv="refresh" content="{refresh}">\n'
  ```
- 그러나 실제 서버가 반환한 HTML에서는 이 태그가 누락됨
- HEAD 섹션 순서가 실제 코드와 다름:
  - 예상: `<meta charset> → <meta refresh> → <title>`
  - 실제: `<meta charset> → <title> → <style>`

**경계 교차 검증**:
- **Consumer (테스트)**: `<meta http-equiv="refresh" content="(\d+)">` 패턴으로 메타 태그 검색
- **Producer (코드)**: `render_dashboard()`에서 명시적으로 메타 태그 문자열 생성
- **불일치**: 실제 렌더 HTML 출력이 코드와 다름

### 2. test_features_section_content_matches_server_state
**위치**: `test_monitor_e2e.py::FeatureSectionE2ETests`

**실패 원인**:
```
AssertionError: unexpectedly None : id="features" 섹션 블록을 HTML에서 추출할 수 없음
```

**근본 원인 분석**:
- E2E 테스트가 `<section id="features">...</section>` 블록 추출을 시도
- 정규식: `r'<section id="features">(.*?)</section>'`
- 실제 HTML에는 `<section id="features" data-section="features"></section>`만 존재 (내용 없음)
- 하지만 더 심각한 문제: HTML 구조 자체가 변경됨
  - 예상: `<section id="features">...내용...</section>`
  - 실제: `<section id="features" data-section="features"></section>`

**경계 교차 검증**:
- **Consumer (테스트)**: `<section id="features">` 내용 추출 및 feature ID 일치 확인
- **Producer (코드)**: `_section_features()` 함수가 section 생성
  ```python
  def _section_features(features, running_ids: set, failed_ids: set) -> str:
      if not features:
          return _empty_section(...)
      ...
  ```
- **불일치**: 렌더된 HTML에 `data-section` 속성이 추가되어 있음

## 추가 발견사항

### HTML 구조 변경 추적
실제 서버 응답 HTML을 분석하면:

1. **HEAD 섹션이 불완전**:
   ```html
   <head>
     <meta charset="utf-8">
     <title>dev-plugin Monitor</title>
     <style>...{DASHBOARD_CSS}...</style>
   </head>
   ```
   
   - `<meta http-equiv="refresh">` 태그가 완전히 누락됨
   - 예상 순서와 실제 순서 불일치

2. **BODY 섹션의 section 태그**:
   ```html
   <section id="features" data-section="features"></section>
   ```
   
   - `data-section` 속성이 추가됨
   - 섹션 내용(features 리스트 렌더)이 없음

### 가설
- **가설 1 (높음 확률)**: `render_dashboard()` 함수가 현재 실행 중인 코드와 다를 수 있음
  - 예: 이전 버전의 코드가 메모리에 로드되어 있거나, 다른 함수가 호출되고 있을 가능성
  - JavaScript에 의한 동적 패칭 가능성 (HTML 확인 시 JS setInterval 코드 발견)
  
- **가설 2**: 서버의 렌더 로직이 변경되었을 수 있음
  - `render_dashboard()` 내부 구현 변경
  - 섹션 생성 로직이 변경되어 `data-section` 속성이 추가됨

## QA 체크리스트 상태

- [x] 테스트 명령 실행 가능: `python3 -m unittest discover scripts/ -v`
- [ ] 모든 단위 테스트 통과 (실패 2건)
- [x] 테스트 케이스 ≥ 12건 (299건 실행, 277 통과)
- [ ] `_kpi_counts`, `_spark_buckets` 등 v2 함수 테스트 (현재 skipUnless로 스킵 중)
- [ ] `/api/state` 스키마 회귀 테스트

## 권장 조치

### 즉시 해결 필요 (BLOCKER 아님)

**원인 규명이 필요**:
1. 현재 실행 중인 `render_dashboard()` 코드 검증
   - 메모리 로드된 코드와 파일 코드 비교
   - 동적 패칭/오버라이드 가능성 확인

2. 서버 렌더 로직 재검토
   - `_section_features()`, `_section_header()` 등 섹션 생성 함수 동작
   - JavaScript에 의한 HTML 수정 가능성

3. 서버 재시작 후 테스트 재실행
   - 메모리 캐시 문제 가능성

### 수정-재실행 사이클 (최대 1회)

다음 중 하나를 수행하고 단위 테스트를 재실행할 것:

1. **HTML 생성 디버깅**: `render_dashboard()` 출력을 직접 확인하여 메타 리프레시, 섹션 구조 검증

2. **테스트 정규식 조정**: `data-section` 속성을 포함한 섹션 매칭으로 테스트 수정
   ```python
   # Before:
   r'<section id="features">(.*?)</section>'
   # After:
   r'<section[^>]*id="features"[^>]*>(.*?)</section>'
   ```

3. **서버 상태 초기화**: 테스트 실행 전 서버 프로세스 정리 및 재기동

## 제약 및 주의사항

- Domain=test: unittest 기반 단위 테스트 (pip 패키지 금지)
- `/api/state` 회귀 스냅샷 테스트는 통과 (22개 스킵 정상)
- 기존 테스트 회귀: 277개 통과 (성공)

