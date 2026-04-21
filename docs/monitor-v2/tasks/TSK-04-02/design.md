# TSK-04-02: 브라우저 수동 QA (Chrome / Safari / Firefox × 3 뷰포트) - 설계

## 요구사항 확인

- Chrome / Safari / Firefox 3개 브라우저 × 1440px / 1024px / 390px 3개 뷰포트 = **9개 조합(3×3 매트릭스)** 전체를 수동으로 확인한다.
- 각 조합에서 레이아웃 · 애니메이션 · 드로어 ESC 닫힘 · 필터 칩 · auto-refresh 토글 · `prefers-reduced-motion` 동작을 체크한다.
- 결과는 `docs/monitor-v2/qa-report.md` (v1 형식)에 기록한다. 전체 PASS 또는 실패 항목 명시가 acceptance 조건이다.

## 타겟 앱

- **경로**: N/A (단일 앱, 코드 파일 신규 작성 없음)
- **근거**: 이 Task는 기존 구현(monitor-server.py + prototype.html)을 브라우저에서 수동 검증하는 QA Task이며 별도 앱 경로가 없다.

## 구현 방향

이 Task는 **코드 구현이 아닌 수동 QA 절차 설계**이다.

1. QA를 위한 **체크리스트 매트릭스(3 브라우저 × 3 뷰포트 × 13 체크 항목)** 를 이 design.md에 정의한다.
2. QA 실행자는 `python3 scripts/monitor-launcher.py --port 7321 --docs docs`로 서버를 기동한 뒤 각 브라우저·뷰포트 조합을 순서대로 확인한다.
3. 결과를 `docs/monitor-v2/qa-report.md`에 v1 형식 표로 기록한다.
4. Chrome에서 5분+ 폴링 후 DevTools Performance 탭으로 JS Heap 증가량(목표 ≤ 50MB)을 측정한다.

## 파일 계획

| 파일 경로 | 역할 | 신규/수정 |
|-----------|------|-----------|
| `docs/monitor-v2/qa-report.md` | 3×3 매트릭스 QA 결과 기록 (v1 형식) | 신규 |

> 코드 파일 신규 작성 없음. `qa-report.md` 가 유일한 산출물이다.

## 진입점 (Entry Points)

N/A — domain=test, UI Task 아님.

## 주요 구조

### 서버 기동 절차

```
python3 scripts/monitor-launcher.py --port 7321 --docs docs
# → http://localhost:7321 에서 대시보드 확인
```

### 3×3 QA 매트릭스 체크 항목 정의

| ID  | 체크 항목 | 비고 |
|-----|-----------|------|
| C01 | 레이아웃 깨짐 없음 — KPI 카드 / WP 카드 / Live Activity / Timeline 정상 렌더 | sticky 헤더 포함 |
| C02 | 390px: 단일 컬럼 레이아웃, 요소 잘림 없음 | 모바일 컷 |
| C03 | 1024px: 2컬럼 WP 카드 또는 1컬럼 허용 | 태블릿 컷 |
| C04 | 1440px: 최대 레이아웃 정상 | 데스크탑 컷 |
| C05 | 필터 칩(`All / Running / Failed / Done / Pending`) 클릭 시 WP/Task 목록 필터링 동작 | |
| C06 | auto-refresh 토글 OFF → 폴링 중단, ON → 폴링 재개 | Network 탭 확인 |
| C07 | WP 카드 클릭 → Task 목록 펼침/접힘(`<details>` accordion) | |
| C08 | pane expand 버튼 클릭 → 드로어(side drawer) 열림 | |
| C09 | 드로어 ESC 키 → 닫힘 (focus가 트리거 버튼으로 복귀) | |
| C10 | 드로어 X 버튼 → 닫힘 | |
| C11 | `prefers-reduced-motion: reduce` 시 pulse·fade·transition 중단 | DevTools 시뮬레이션 |
| C12 | 5분+ 폴링 후 JS Heap 증가량 ≤ 50MB (Chrome Performance 탭) | Chrome 전용 |
| C13 | KPI 카드 `aria-label` 텍스트가 DevTools Accessibility 탭에서 확인됨 | |

### prefers-reduced-motion 시뮬레이션 방법 (브라우저별)

| 브라우저 | 활성화 경로 |
|----------|-------------|
| Chrome | DevTools → Rendering 탭 → "Emulate CSS media feature prefers-reduced-motion" → reduce |
| Safari | 개발자 도구 → 반응 → prefers-reduced-motion: reduce (또는 macOS 시스템 설정 → 손쉬운 사용 → 모션 줄이기) |
| Firefox | about:config → `ui.prefersReducedMotion` = 1 |

### qa-report.md v1 형식 정의

```markdown
# QA Report — Monitor v2

**작성일**: YYYY-MM-DD
**서버**: http://localhost:7321
**버전**: (git commit hash)

## 3×3 매트릭스

| 항목 | Chrome 1440 | Chrome 1024 | Chrome 390 | Safari 1440 | Safari 1024 | Safari 390 | Firefox 1440 | Firefox 1024 | Firefox 390 |
|------|:-----------:|:-----------:|:----------:|:-----------:|:-----------:|:----------:|:------------:|:------------:|:-----------:|
| C01 레이아웃 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| C02 390px 컬럼 | — | — | ✅ | — | — | ✅ | — | — | ✅ |
| C03 1024px 컬럼 | — | ✅ | — | — | ✅ | — | — | ✅ | — |
| C04 1440px 레이아웃 | ✅ | — | — | ✅ | — | — | ✅ | — | — |
| C05 필터 칩 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| C06 auto-refresh | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| C07 WP accordion | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| C08 드로어 열기 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| C09 ESC 닫기 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| C10 X 버튼 닫기 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| C11 reduced-motion | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| C13 aria-label | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

## 골든 경로 시나리오

> `/dev-team` 실행 중 대시보드 열기 → WP 펼치기 → pane expand → ESC 닫기

| 브라우저 | 결과 |
|----------|------|
| Chrome   | ✅ PASS |
| Safari   | ✅ PASS |
| Firefox  | ✅ PASS |

## prefers-reduced-motion

| 브라우저 | 시뮬레이션 방법 | 결과 |
|----------|----------------|------|
| Chrome   | DevTools Rendering → prefers-reduced-motion: reduce | ✅ |
| Safari   | macOS 손쉬운 사용 → 모션 줄이기 | ✅ |
| Firefox  | about:config → ui.prefersReducedMotion=1 | ✅ |

## 메모리 측정 (Chrome 전용, C12)

| 구간 | JS Heap | 증가량 |
|------|---------|--------|
| 0 min | X MB | — |
| 5 min | X MB | X MB |

**결론**: ≤50MB 목표 충족 / 미충족

## 실패 항목

| 항목 | 브라우저 | 뷰포트 | 증상 | 재현 절차 |
|------|----------|--------|------|-----------|
| (없음 또는 상세 기록) | | | | |

## 최종 판정

- [ ] 전체 PASS
- [ ] 조건부 PASS (실패 항목 위 표에 기록)
- [ ] FAIL
```

## 데이터 흐름

입력: `http://localhost:7321` (monitor-server.py 렌더 결과) → 처리: QA 실행자 수동 브라우저 조작 → 출력: `docs/monitor-v2/qa-report.md` (결과 기록)

## 설계 결정 (대안이 있는 경우만)

- **결정**: qa-report.md 포맷을 Markdown 표(3×3 매트릭스) + 골든 경로 + prefers-reduced-motion + 메모리 + 실패 항목 + 최종 판정 6파트로 구성
- **대안**: JSON 구조화 결과 파일
- **근거**: Markdown은 git diff가 용이하고 human-readable이며 자동화 파이프라인이 없으므로 JSON 오버엔지니어링.

## 선행 조건

- TSK-02-01, TSK-02-02, TSK-02-03: `monitor-server.py` 렌더링 레이어 구현 완료
- TSK-03-01, TSK-03-02: 반응형 + 접근성(`prefers-reduced-motion`) 미디어 쿼리 구현 완료
- `python3 scripts/monitor-launcher.py --port 7321 --docs docs` 정상 기동 가능

## 리스크

- **HIGH**: 선행 Task(TSK-02-x, TSK-03-x)가 미완료인 경우 QA 대상이 없어 실행 불가 — depends 메타데이터로 관리.
- **MEDIUM**: Safari는 macOS 전용이므로 Linux/Windows 환경에서는 Safari QA 생략 가능 — qa-report.md에 "N/A (플랫폼 미지원)" 기록.
- **MEDIUM**: `prefers-reduced-motion` 시뮬레이션 방법이 브라우저마다 달라 실수 가능 — 설계에 브라우저별 활성화 경로 명시.
- **LOW**: Chrome DevTools Performance 탭의 메모리 수치는 탭 개수/확장 프로그램에 따라 변동 있음 — 클린 프로필로 측정 권장.

## QA 체크리스트

- [ ] 9개 브라우저×뷰포트 조합(3×3 매트릭스) 전체에서 레이아웃 깨짐 없이 렌더링됨
- [ ] 필터 칩(All / Running / Failed / Done / Pending) 각 상태에서 목록이 올바르게 필터링됨
- [ ] auto-refresh 토글 OFF 시 `/api/state` 폴링 중단, ON 시 재개 (Network 탭에서 확인)
- [ ] WP 카드 클릭 시 Task 목록 펼침/접힘 accordion 동작
- [ ] pane expand 버튼 클릭 시 side drawer가 정상 열림
- [ ] ESC 키로 드로어가 닫히며 focus가 트리거 버튼으로 복귀
- [ ] X 버튼으로 드로어 닫힘
- [ ] Chrome/Safari/Firefox 3개 브라우저에서 `prefers-reduced-motion: reduce` 시뮬레이션 시 pulse·fade·transition 중단 확인
- [ ] Chrome에서 5분+ 폴링 후 JS Heap 증가량 ≤ 50MB
- [ ] KPI 카드 `aria-label` 텍스트가 DevTools Accessibility 탭에서 확인됨
- [ ] 골든 경로(대시보드 열기 → WP 펼치기 → pane expand → ESC 닫기)가 Chrome / Safari / Firefox 전체에서 성공
- [ ] `docs/monitor-v2/qa-report.md`가 v1 형식(3×3 매트릭스 + 골든 경로 + prefers-reduced-motion + 메모리 + 최종 판정 섹션 포함)으로 생성됨
