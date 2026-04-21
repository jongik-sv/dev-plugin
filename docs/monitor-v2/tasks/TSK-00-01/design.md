# TSK-00-01: 정적 HTML 프로토타입 작성 - 설계

## 요구사항 확인
- 단일 HTML 파일(`docs/monitor-v2/prototype.html`)에 인라인 CSS + 인라인 JS만 사용하며 외부 CDN/폰트/스크립트를 전혀 포함하지 않는 독립 프로토타입을 만든다.
- 태스크 10건·WP 3개·phase history 20건·tmux pane 3개의 목업 데이터로 PRD §4.4 와이어프레임(좌 60%/우 40%) 레이아웃을 1440px 뷰포트에서 스크롤 없이 렌더한다.
- `[expand ↗]` 버튼 클릭 시 우측 사이드 드로어가 슬라이드 인되고 ESC로 닫히는 최소 JS 상호작용을 포함한다.

## 타겟 앱
- **경로**: N/A (단일 앱 — 빌드 없는 정적 HTML 파일)
- **근거**: 이 Task의 산출물은 프로젝트 루트 하위 `docs/monitor-v2/prototype.html` 한 파일이며 앱/패키지 구조가 없다.

## 구현 방향
- `<!DOCTYPE html>` 단일 파일에 `<style>` 블록(CSS 변수 + flex/grid/conic-gradient)과 `<script>` 블록(드로어 제어 50줄 이내)을 인라인으로 삽입한다.
- 레이아웃 골격: sticky 헤더 → KPI 5장 행 + 필터 칩 → `main` 2단(`left 60%` / `right 40%`).
- 좌: WP 3개 카드(도넛 conic-gradient + progress bar + 태스크 row 리스트). 우: Live Activity 피드 + Phase Timeline SVG + Team Agents(pane inline preview + expand 버튼).
- 드로어는 `position: fixed; right: -640px` → `right: 0` 슬라이드 트랜지션. backdrop 오버레이로 닫기 지원.
- 모든 시각화(도넛, 스파크라인, 타임라인)는 `conic-gradient` 또는 인라인 `<svg>`로 구현 — 외부 차트 라이브러리 사용 금지.

## 파일 계획

**경로 기준:** 모든 파일 경로는 **프로젝트 루트 기준**으로 작성한다.

| 파일 경로 | 역할 | 신규/수정 |
|-----------|------|-----------|
| `docs/monitor-v2/prototype.html` | 목업 데이터 하드코딩 정적 프로토타입 — 레이아웃·색·애니메이션 검증용 단일 HTML 산출물 | 신규 |

> UI Task이나 `entry-point=library` 성격으로 라우터/메뉴 파일 수정이 없다. 이 파일 자체가 브라우저에서 직접 열리는 독립 산출물이다.

## 진입점 (Entry Points)

이 Task는 `domain=frontend`이나 `entry-point=library`로 분류된 독립 정적 파일 산출물이다. 라우터에 등록하거나 사이드바 메뉴를 수정하는 방식이 아니라, 브라우저에서 직접 파일을 열어 진입한다.

- **사용자 진입 경로**: 파일 탐색기 또는 터미널에서 `open docs/monitor-v2/prototype.html` (macOS) / `xdg-open docs/monitor-v2/prototype.html` (Linux) 실행 → 브라우저에서 로컬 파일로 열림
- **URL / 라우트**: `file:///…/docs/monitor-v2/prototype.html` (로컬 파일 URL). 서버 라우팅 불필요.
- **수정할 라우터 파일**: 없음 — 독립 파일이므로 라우터 배선 불필요
- **수정할 메뉴·네비게이션 파일**: 없음 — 독립 파일이므로 메뉴 배선 불필요
- **연결 확인 방법**: `docs/monitor-v2/prototype.html`을 브라우저에서 열어 KPI 5장 + WP 3개 카드가 스크롤 없이 표시되고 `[expand ↗]` 클릭 시 드로어가 열리는지 육안 확인

## 주요 구조

| 구조 이름 | 책임 |
|-----------|------|
| `MOCK_DATA` (JS const 객체) | 태스크 10건·WP 3개·phase history 20건·pane 3개 목업 데이터 정의 |
| `renderKPI()` (JS 함수) | MOCK_DATA에서 Running/Failed/Bypass/Done/Pending 카운트 계산 후 KPI 카드 5장 DOM 생성 |
| `renderWPCard(wp)` (JS 함수) | 단일 WP 데이터를 받아 도넛(conic-gradient CSS 변수) + progress bar + 태스크 row 리스트 렌더 |
| `renderTimeline(tasks)` (JS 함수) | phase_history를 SVG `<rect>`로 변환하여 Phase Timeline 인라인 렌더 |
| `Drawer` (JS 모듈 패턴) | `open(paneId)` / `close()` 메서드, ESC 키 이벤트 바인딩, backdrop 클릭 처리 |

## 데이터 흐름

`MOCK_DATA` (하드코딩 JS 상수) → `DOMContentLoaded` 이벤트 핸들러에서 각 render 함수 호출 → 정적 DOM 조작으로 초기 렌더 완료 → 사용자 클릭(expand/필터 칩/ESC)에 따라 Drawer·필터 클래스 토글

## 설계 결정 (대안이 있는 경우만)

**도넛 차트 구현:**
- **결정**: CSS `conic-gradient`로 `<div>` 원형 구현 (`background: conic-gradient(var(--done-color) var(--pct), #333 0)`)
- **대안**: 인라인 SVG `<circle>` stroke-dasharray 패턴
- **근거**: conic-gradient가 HTML 템플릿 문자열에서 CSS 변수 교체만으로 완성 가능하여 JS 계산량이 적고 제약 조건(conic-gradient 명시 사용)에 부합한다.

**스파크라인:**
- **결정**: SVG `<polyline>` (인라인, viewBox 고정 `0 0 60 20`)
- **대안**: CSS border-height 막대 배열
- **근거**: TRD 기술 스펙이 `SVG polyline(sparkline)` 사용을 명시하고 있다.

**Phase Timeline:**
- **결정**: SVG `<rect>` 블록, x 좌표 = (start - baseline) / 3600 × viewBox width 비례 계산
- **대안**: CSS flex bar (position absolute 오프셋)
- **근거**: TRD 기술 스펙이 `SVG rect(timeline)` 사용을 명시하고 있으며, SVG가 x/width 정밀 제어에 유리하다.

**필터 칩:**
- **결정**: 클라이언트 사이드 DOM 클래스 토글 (`data-status` 속성 기준 `display:none`), 서버 호출 없음
- **대안**: 서버 API 재요청 (정적 프로토타입이므로 불가)
- **근거**: 정적 파일이므로 서버가 없고, PRD §3.3 S3에도 클라이언트 사이드 필터링으로 명시.

## 선행 조건
- 없음 (독립 정적 산출물, 외부 의존 없음)

## 리스크

- **MEDIUM**: `conic-gradient` 다중 색상(done/running/failed 분할)은 3분할 계산이 필요한데 하나의 conic-gradient 문에 여러 stop을 정밀하게 지정해야 함 — 목업 데이터에서 소수점 각도가 어색하게 보일 수 있음. 완벽한 계산보다 근사값(정수 퍼센트)으로 충분.
- **MEDIUM**: 1440px 뷰포트에서 "스크롤 없이 KPI 5장 + WP 3개 카드가 모두 보이도록" 레이아웃 조정 시 WP 카드 높이가 가변적이어서 처음 배치에서 overflow가 발생할 수 있음 — `overflow-y: auto`를 좌측 패널에 적용하고 헤더/KPI 행의 고정 height를 사전에 측정하여 계산.
- **LOW**: ESC 키 이벤트 핸들러가 input focus 중 충돌 가능성 있으나 이 프로토타입에는 input이 없으므로 실질적 위험 없음.

## QA 체크리스트

- [ ] 브라우저(Chrome/Firefox 최신)에서 `prototype.html`을 로컬 파일로 열었을 때 외부 네트워크 요청이 0건이다 (DevTools Network 탭 확인)
- [ ] 1440px 뷰포트 기준 페이지를 열었을 때 스크롤 없이 KPI 카드 5장과 WP 3개 카드가 한 화면에 표시된다
- [ ] KPI 카드 영역에 Running(3) / Failed(1) / Bypass(2) / Done(4) / Pending(0) 수치가 목업 데이터와 일치하여 표시된다
- [ ] 좌측 WP 카드 3개에 각각 도넛 차트(conic-gradient)와 progress bar가 표시되며 WP별 완료율이 목업 데이터와 일치한다
- [ ] 필터 칩 `[All]`·`[Running]`·`[Failed]`·`[Bypass]` 클릭 시 서버 요청 없이 태스크 row가 즉시 필터링된다
- [ ] `[Running]` 필터 선택 시 running 상태가 아닌 태스크 row는 숨겨진다
- [ ] 우측 Live Activity 피드에 phase_history 이벤트가 타임스탬프 내림차순으로 표시된다
- [ ] Phase Timeline SVG에 `<rect>` 블록으로 각 태스크의 phase 구간이 표시되고 x축에 시간 레이블이 있다
- [ ] Team Agents 영역에 pane 3개가 표시되고 각 pane에 마지막 3줄 inline preview가 표시된다
- [ ] `[expand ↗]` 버튼 클릭 시 우측 사이드 드로어가 슬라이드 인 트랜지션과 함께 열린다
- [ ] 드로어가 열린 상태에서 ESC 키를 누르면 드로어가 닫힌다
- [ ] 드로어가 열린 상태에서 backdrop(드로어 바깥) 클릭 시 드로어가 닫힌다
- [ ] 데스크톱(1440px) 뷰포트에서 좌 60% / 우 40% 2단 레이아웃이 유지되며 콘텐츠가 겹치거나 밀리지 않는다
- [ ] HTML 파일 내 `<script src>`, `<link href>`, `<img src>` 등 외부 자원 참조 태그가 0건이다
- [ ] `[expand ↗]` 클릭 시 열린 드로어에 pane 식별 정보(window명, pane index, pid)가 표시된다

**fullstack/frontend Task 필수 항목 (E2E 테스트에서 검증 — dev-test reachability gate):**
- [ ] (클릭 경로) 메뉴/사이드바/버튼을 클릭하여 목표 페이지에 도달한다 (URL 직접 입력 금지) — 본 Task는 `entry-point=library`로 브라우저에서 직접 파일을 열며, `[expand ↗]` 버튼 클릭으로 드로어에 도달하는 클릭 경로를 검증한다
- [ ] (화면 렌더링) 핵심 UI 요소가 브라우저에서 실제 표시되고 기본 상호작용이 동작한다 — KPI 카드·WP 도넛·Phase Timeline·드로어가 1440px 뷰포트에서 정상 렌더되고 드로어 open/close 상호작용이 동작한다
