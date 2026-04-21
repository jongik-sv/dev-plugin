# TSK-04-02: 브라우저 수동 QA (Chrome / Safari / Firefox × 3 뷰포트) - 설계

## 요구사항 확인

- Chrome / Safari / Firefox 3개 브라우저 × 1440px / 1024px / 390px 3개 뷰포트 = 9개 매트릭스 셀 전체 수동 검증
- 각 셀에서 레이아웃·애니메이션·드로어 ESC 닫힘·필터 칩·auto-refresh 토글·`prefers-reduced-motion` 동작을 체크
- 장시간(5분+) 폴링 시 Chrome DevTools Performance로 메모리 증가량 측정, 결과를 `docs/monitor-v2/qa-report.md`에 기록

## 타겟 앱

- **경로**: N/A (단일 앱 — `scripts/monitor-server.py` 기동 후 브라우저로 접근)
- **근거**: 이 Task는 코드를 작성하지 않는 수동 QA 절차 설계; 신규 코드 파일 없음

## 구현 방향

- 코드 구현 없음 — 수동 QA 체크리스트 문서(`docs/monitor-v2/qa-report.md`)를 정의하고 실제 브라우저에서 항목별로 확인한 후 결과를 기록한다.
- 서버는 `python3 scripts/monitor-launcher.py --port 7321 --docs docs`로 기동, 브라우저 DevTools Responsive 모드로 뷰포트를 전환한다.
- `prefers-reduced-motion` 테스트는 각 OS의 접근성 설정 또는 DevTools 에뮬레이션으로 활성화한다.
- 메모리 측정은 Chrome DevTools → Performance → Memory 타임라인 레코딩 5분 이상 수행 후 Heap 증가량을 기록한다.
- 결과는 3×3 매트릭스 표 + 개별 항목 체크박스 + PASS/FAIL 결론 형식으로 `qa-report.md`에 저장한다.

## 파일 계획

| 파일 경로 | 역할 | 신규/수정 |
|-----------|------|-----------|
| `docs/monitor-v2/qa-report.md` | 수동 QA 결과 보고서 — 3×3 브라우저×뷰포트 매트릭스, 체크리스트 항목별 결과, PASS/FAIL 판정, 비고 | 신규 |

## 진입점 (Entry Points)

N/A — `domain=test` (비-UI Task). 신규 라우터·메뉴 배선 없음.

## 주요 구조

- **qa-report.md 문서 구조**: 헤더 → 환경 정보 → 3×3 매트릭스 요약 표 → 항목별 상세 체크리스트 → 메모리 측정 결과 → 종합 판정
- **매트릭스 셀 (9개)**: `{Chrome, Safari, Firefox} × {1440px, 1024px, 390px}` — 각 셀에 PASS/FAIL/SKIP 기록
- **체크 항목 6종**: ① 레이아웃 ② 애니메이션 ③ 드로어 ESC 닫힘 ④ 필터 칩 ⑤ auto-refresh 토글 ⑥ `prefers-reduced-motion` 시 애니메이션 중단
- **메모리 측정 항목**: 초기 Heap 크기, 5분 후 Heap 크기, 증가량(MB), TRD §10 기준(≤50MB 증가) 만족 여부
- **골든 경로 시나리오**: `/dev-team` 실행 중 대시보드 열기 → WP 펼치기 → pane expand → ESC 닫기 — 이 순서를 전 브라우저에서 반드시 실행

## 데이터 흐름

실행 중인 모니터 서버(port 7321) → 브라우저 수동 접근 → 체크리스트 항목 확인 → 결과 qa-report.md에 기록

## 설계 결정 (대안이 있는 경우만)

- **결정**: Playwright 자동화 없이 순수 수동 QA로 진행
- **대안**: Playwright MCP로 3개 브라우저 자동 스크린샷 취득 + 시각적 diff
- **근거**: 이 Task의 요구사항이 "체크리스트 기반 수동 QA"로 명시되어 있고, `prefers-reduced-motion` 에뮬레이션·메모리 프로파일링 등 일부 항목은 DevTools 직접 조작이 필요하여 완전 자동화에 제약이 있음

- **결정**: DevTools Responsive 모드로 뷰포트 에뮬레이션
- **대안**: 실제 물리 기기(iPhone, 태블릿) 사용
- **근거**: 물리 기기 환경 의존성 없이 3개 뷰포트를 단일 머신에서 재현 가능; 레이아웃 깨짐 여부는 DevTools Responsive로 충분히 검증 가능

## 선행 조건

- TSK-02-01, TSK-02-02, TSK-02-03 (CSS·JS 구현), TSK-03-01, TSK-03-02 (접근성·모션 미디어쿼리 구현) 완료 필수
- `scripts/monitor-launcher.py --port 7321 --docs docs` 정상 기동 확인
- Chrome / Safari / Firefox 각 최신 버전 설치
- macOS 기준: 시스템 환경설정 → 접근성 → 디스플레이 → "움직임 줄이기" 토글 또는 Chrome DevTools → Rendering → "Emulate CSS media feature prefers-reduced-motion" 사용 가능

## 리스크

- **HIGH**: Safari는 DevTools Responsive 모드 지원이 제한적 — 뷰포트 에뮬레이션 방법이 다를 수 있음. Safari에서는 실 창 크기 조절로 대체
- **MEDIUM**: `conic-gradient` CSS가 구형 Safari에서 깨지는 알려진 리스크 (TRD §12) — 폴백 가로 막대 렌더링 확인 필요
- **MEDIUM**: Firefox DevTools의 Responsive 모드는 touch event 에뮬레이션이 Chrome과 다름 — 탭/포커스 동작 차이 주의
- **LOW**: Chrome DevTools Performance의 `performance.memory` API는 다른 브라우저에서 미지원 — 메모리 측정은 Chrome 전용으로 진행하고 qa-report에 명시

## QA 체크리스트

> 아래 항목은 각 브라우저(Chrome/Safari/Firefox) × 뷰포트(1440px/1024px/390px) 셀에서 모두 확인한다. 개별 셀 결과는 qa-report.md 매트릭스에 기록하고, 여기서는 항목의 pass 기준을 정의한다.

### 레이아웃

- [ ] 1440px: 좌(60%) / 우(40%) 2컬럼 레이아웃이 유지되고, WP 카드·KPI 카드·Live Activity·Phase Timeline이 모두 표시된다
- [ ] 1024px: 2컬럼 레이아웃이 유지되거나 단일 컬럼으로 자연스럽게 축소되며 콘텐츠가 잘리거나 가로 스크롤이 발생하지 않는다
- [ ] 390px: 단일 컬럼으로 전환되고 모든 섹션이 수직 스택으로 표시, 텍스트 오버플로·잘림·겹침 없음

### 애니메이션

- [ ] Running 상태 태스크의 pulse 애니메이션이 3개 브라우저 모두에서 동작한다
- [ ] Live Activity에 새 이벤트 도착 시 fade-in 효과가 동작한다
- [ ] 필터 칩 클릭 시 리스트 DOM 전환이 부드럽게 동작한다 (깜빡임 없음)

### 드로어 ESC 닫힘

- [ ] 골든 경로: 대시보드에서 WP 카드 펼치기 → pane expand([show]) 클릭 → 드로어 열림 확인 → ESC 키 입력 → 드로어가 닫히고 트리거 요소로 포커스 복귀
- [ ] 드로어 열림 시 `role="dialog"` `aria-modal="true"` 속성 존재 (DevTools Elements 탭 확인)
- [ ] 드로어 열림 시 포커스가 `.drawer-close` 버튼으로 이동 (Tab으로 이동 가능)

### 필터 칩

- [ ] `[All]` → `[Running]` 클릭 시 Running 태스크만 표시, 서버 요청 없이 즉시 DOM 필터링
- [ ] `[Failed]` 클릭 시 실패 태스크만 표시
- [ ] `[Bypass]` 클릭 시 우회된 태스크만 표시
- [ ] 필터 칩 선택 상태에서 auto-refresh가 발생해도 필터 선택이 유지된다

### auto-refresh 토글

- [ ] `[◐ auto]` 버튼 클릭 시 부분 fetch 중단, 버튼 상태가 "off"로 시각적으로 변경
- [ ] 토글 off 상태에서 5초가 지나도 DOM이 갱신되지 않음 (Network 탭에서 /api/state 요청 없음 확인)
- [ ] 토글 다시 켜면 fetch 재개, 버튼 상태가 "on"으로 복귀

### prefers-reduced-motion

- [ ] DevTools → Rendering → "Emulate CSS prefers-reduced-motion: reduce" 활성화 후 pulse·fade·transition 애니메이션이 모두 정지됨
- [ ] 애니메이션 중단 후에도 레이아웃·콘텐츠·기능(필터, 드로어, 토글)은 정상 동작

### 메모리 (Chrome 전용)

- [ ] Chrome DevTools → Performance → Memory 5분 이상 레코딩 후 JS Heap 증가량 ≤ 50MB (TRD §10 기준)
- [ ] 5분 레코딩 동안 명시적 메모리 누수 패턴(지속적 단조 증가 없이 GC 후 회수) 확인

### 골든 경로 종합

- [ ] `/dev-team` 실행 중 `http://localhost:7321` 접속 → KPI 카드 표시 → WP 카드 펼치기(`<details>`) → Running 태스크 row의 `[show]` 클릭 → 드로어에 pane 출력(2초 폴링) 표시 → ESC 닫기 — 이 시퀀스가 Chrome/Safari/Firefox 3개 브라우저에서 모두 동작
