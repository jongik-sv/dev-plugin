# PRD — dev-plugin 웹 모니터링 도구 v2 (Visual Redesign)

**문서 버전:** 0.1 (초안)
**작성일:** 2026-04-21
**대상 플러그인:** `dev` (dev-plugin)
**선행 문서:** `docs/monitor/prd.md` (v1, 2026-04-20)
**상태:** Draft

---

## 1. 배경 및 문제 정의

v1(`/dev-monitor`, `scripts/monitor-server.py`)은 기능적으로는 완성되어 WBS·Feature·tmux pane·agent-pool 시그널을 통합 제공하지만, **UI가 비주얼적으로 빈약**하다는 피드백이 있다. 실측 기반 약점:

1. **정보 위계 없음** — 상단 요약/KPI 없이 섹션 리스트가 바로 나옴. 실패·진행 중 태스크를 찾으려면 스크롤 + 뱃지 스캔이 필요.
2. **페이지 전체 리프레시** — `<meta http-equiv="refresh">`로 N초마다 전체 재로드. 스크롤·`<details>` 펼침 상태 증발, 깜빡임 발생. (pane 페이지는 이미 부분 fetch 하고 있음 — 대시보드만 구식)
3. **섹션 시각적 차별 없음** — WBS / Features / Team / Subagents / Phases 모두 동일 패널. 중요도 구분 불가.
4. **진행률 시각화 없음** — WP별 완료율, 상태 분포를 한눈에 파악할 카드·도넛·바 없음.
5. **태스크 row 밀도** — 6컬럼 고정 그리드. 상태 색이 작은 뱃지 하나에만. Running 행이 눈에 안 띔.
6. **타임라인 없음** — phase_history가 문자열 `<li>` 리스트. 어느 WP가 언제 바빴는지, 어느 태스크가 장시간 걸리는지 한 눈에 파악 불가.
7. **아이콘 빈약** — emoji만 사용, 시각 요소 통일감 부족.

## 2. 목표

**단일 HTML 파일·인라인 CSS·No external CDN 원칙을 유지한 채, 대시보드를 "모니터링 대시보드답게" 재디자인**한다. 기존 v1의 데이터 수집·엔드포인트·스킬 커맨드는 최대한 재사용하고, 렌더링 레이어(`DASHBOARD_CSS` + `_section_*` 함수)만 교체한다.

### 2.1 Success Criteria

- [ ] v1과 동일하게 **추가 설치 0건** (pip 패키지·프론트엔드 빌드 없음)
- [ ] 외부 CDN/폰트/JS 로드 **0건** 유지 — 모든 자원 인라인
- [ ] 주요 정보(Running / Failed / Bypassed 태스크 수)를 **상단 KPI 카드에서 3초 이내** 식별 가능
- [ ] 리프레시 시 스크롤 위치·`<details>` 펼침 상태·필터 선택 **유지** (부분 fetch 도입)
- [ ] 기존 화면(v1) 대비 **정보 밀도 유지** — 스크롤 분량이 유의미하게 증가하지 않아야 함
- [ ] 반응형 — 데스크톱(≥1280px) / 태블릿(768~1279px) / 모바일(<768px) 세 구간에서 깨지지 않음
- [ ] macOS / Linux / WSL2 / Windows(psmux) 네 환경에서 동일 동작 (v1과 동일)

### 2.2 Non-Goals

- **차트 라이브러리 도입 금지** — Chart.js / D3 등 외부 번들 사용하지 않음. 모든 시각화는 CSS(`conic-gradient`, progress bar) + 인라인 SVG로 해결.
- **새로운 데이터 소스 추가 없음** — v1의 스캔 함수(`scan_tasks`, `scan_features`, `scan_signals`, `list_tmux_panes`, `capture_pane`)만 사용.
- **읽기 전용 원칙 유지** — 대시보드에서 작업 재시작/중단 등 조작 기능 추가 안 함.
- **인증/원격 접속 도입 안 함** — localhost 전용.
- **과거 이력 아카이빙·알림·이메일** — v1과 동일하게 현재 상태 스냅샷만.
- **다중 프로젝트 동시 감시** — 단일 프로젝트 범위 유지.

## 3. 사용자 및 시나리오

### 3.1 Primary User

v1과 동일 — `/dev-team` 또는 `/feat`을 실행해놓고 장시간 병렬 개발을 감독하는 개발자.

### 3.2 주요 시나리오 (v2 기준)

**S1. 한눈에 진행률 확인 (신규)**
대시보드 상단 KPI 카드 5장(Running / Failed / Bypassed / Done / Pending)만 보고 현재 전체 건강 상태를 3초 내 판단.

**S2. 병목 식별 (신규)**
우측 Phase Timeline에서 가로 막대가 긴 태스크 발견 → 해당 row 클릭하여 tmux pane 출력 확인. 기존 v1에서는 phase_history를 스크롤로 읽어야 했음.

**S3. Bypass/Failed만 필터링 (신규)**
상단 필터 칩에서 `[Failed]`나 `[Bypass]`를 눌러 리스트를 즉시 축소 (클라이언트 사이드 필터링 — 서버 호출 없음).

**S4. 장시간 모니터링 시 상태 유지 (신규)**
페이지 부분 fetch로 리프레시해도 사용자가 펼쳐둔 WP `<details>`·스크롤 위치·활성 필터가 유지됨.

**S5. 실행 중인 에이전트 출력 관찰 (신규)**
사용자가 대시보드를 떠나지 않고, 실행 중인 tmux pane의 출력을 인라인 preview(마지막 3줄) 또는 사이드 드로어(최근 500줄 + 2초 폴링)로 확인. v1에서는 별도 페이지(`/pane/{id}`)로 이동해야 했음.

## 4. 기능 요구사항

### 4.1 기동 인터페이스 (v1 변경 없음)

- 슬래시 커맨드: `/dev-monitor [--port PORT] [--docs DIR] [--stop] [--status]`
- PID 파일 관리, detach 기동, 포트 충돌 안내 — v1 그대로.

### 4.2 데이터 소스 (v1 변경 없음)

v1 PRD §4.2 그대로 계승. 서버는 상태를 메모리에 보관하지 않고, 매 HTTP 요청마다 파일·tmux를 새로 읽음.

### 4.3 HTTP 엔드포인트 (v1 + 0개 확장)

| 메서드 | 경로 | 응답 | 상태 |
|--------|------|------|------|
| GET | `/` | HTML | v1 유지 — 내부 렌더 함수만 v2로 교체 |
| GET | `/api/state` | JSON | v1 유지 — 클라이언트 부분 fetch에서 재사용 |
| GET | `/pane/{pane_id}` | HTML | v1 유지 |
| GET | `/api/pane/{pane_id}` | JSON | v1 유지 |

v2에서 **새 엔드포인트는 추가하지 않는다**. `/api/state`가 이미 전체 스냅샷을 JSON으로 제공하므로, 프론트의 부분 fetch는 이것을 재사용한다.

### 4.4 대시보드 UI — 레이아웃

데스크톱(≥1280px) 기준 와이어프레임:

```
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│  ●  dev-plugin Monitor         project: /path/to/repo        ⟳ 5s  [◐ auto-refresh]      │  ← sticky 헤더
├──────────────────────────────────────────────────────────────────────────────────────────┤
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐                         │
│  │ RUNNING │  │ FAILED  │  │ BYPASS  │  │  DONE   │  │ PENDING │   [All][Run][Fail][Byp] │
│  │   3 🟠  │  │   1 🔴  │  │   2 🟡  │  │  24 ✅  │  │   6 ⚪  │                         │
│  │ ▁▃▅█▃▁  │  │ ▁▁▁▁▃▁  │  │ ▁▁▃▁▁▁  │  │ ▅█▇▆█▇  │  │ ▃▃▂▂▁▁  │                         │
│  └─────────┘  └─────────┘  └─────────┘  └─────────┘  └─────────┘                         │
├────────────────────────────────────────┬─────────────────────────────────────────────────┤
│  WORK PACKAGES                         │  LIVE ACTIVITY                                  │
│  ┌──────────────────────────────────┐  │  ┌───────────────────────────────────────────┐  │
│  │ WP-01 monitor             8/10   │  │  │ 11:09:22  TSK-03-02   ts.ok     67s       │  │
│  │   ╭──────────╮  ████████░░ 80%   │  │  │ 11:08:55  TSK-03-02   ts.fail   12s   ⚠   │  │
│  │   │ ◜◝  80%  │  ● 6 done         │  │  │ 11:08:40  TSK-01-08   xx.ok     4s        │  │
│  │   │ ◟◞       │  ○ 2 running      │  │  │ ...                                       │  │
│  │   ╰──────────╯  ◐ 1 pending      │  │  └───────────────────────────────────────────┘  │
│  │                 × 1 failed       │  │                                                 │
│  ├──────────────────────────────────┤  │  PHASE TIMELINE                (last 60 min)    │
│  │ WP-02 wbs-tools           4/6    │  │  ┌───────────────────────────────────────────┐  │
│  │   ╭──────────╮  █████░░░░░ 66%   │  │  │ TSK-01-07 │▓▓▓ dd │▓▓▓▓▓▓ im │▓ ts │▓ xx │  │
│  │   ╰──────────╯                   │  │  │ TSK-01-08 │▓ dd  │▓▓▓▓ im  │▓ ts │▓ xx   │  │
│  └──────────────────────────────────┘  │  │ TSK-02-03 │▓▓ dd │▓▓▓ im  │░ ts-fail │▓ ts│  │
│                                        │  │         10:15    10:30    10:45     11:00 │  │
│  ▼ WP-01 monitor  (펼침)               │  └───────────────────────────────────────────┘  │
│  │ ▌TSK-01-07 ● done   build-dash    │  │                                                 │
│  │ ▌TSK-01-08 ● done   defect-fix    │  │  TEAM AGENTS (tmux)                             │
│  │ ▌TSK-01-09 ○ running design…      │  │  dev-WP-01  %2  claude  pid 48121  [show]      │
│  │ ▌TSK-01-10 × failed im 2nd fail   │  │  dev-WP-01  %3  claude  pid 48122  [show]      │
│  │ ▌TSK-01-11 ◐ pending              │  │                                                 │
│  ▶ WP-02 wbs-tools  (접힘)             │  │  SUBAGENTS (agent-pool)                         │
│  ▶ WP-03 monitor-docs  (접힘)          │  │  pool/slot-1  ● running  TSK-A  2s ago       │  │
│                                        │  │  pool/slot-2  ✓ done     TSK-B  12s ago      │  │
│  FEATURES                              │  │                                                 │
│  │ ▌feat-login  ○ running            │  │                                                 │
│  │ ▌feat-i18n   ● done               │  │                                                 │
└────────────────────────────────────────┴─────────────────────────────────────────────────┘
     좌측(60%): 계층 구조                           우측(40%): 라이브 + 보조 정보
```

### 4.5 UI 구성 요소 상세

#### 4.5.1 헤더 (sticky)

- **로고 dot**: 서버 기동 상태 컬러 점 (녹색 = 정상, 회색 = 스캔 중)
- **제목**: `dev-plugin Monitor`
- **프로젝트 경로**: `project_root` 표시 (말줄임)
- **새로고침 주기 라벨**: `⟳ 5s` — 주기 표시
- **auto-refresh 토글**: `[◐ auto]` 버튼. 끄면 부분 fetch 중단, 사용자가 수동 새로고침 시만 갱신

#### 4.5.2 KPI 카드 5장

| 카드 | 카운트 기준 | 색상 |
|------|-------------|------|
| RUNNING | `.running` 시그널이 있는 태스크+피처 | orange (pulse) |
| FAILED | `.failed` 시그널이 있거나 `state.json.last.event`가 `*.fail`인 항목 | red |
| BYPASS | `state.json.bypassed: true` | yellow |
| DONE | `status == [xx]` | green |
| PENDING | 그 외 (미착수/진행 중인 중간 phase) | light-gray |

- 각 카드에 **최근 10분 활동 스파크라인** (SVG `<polyline>`): `phase_history`의 해당 상태 이벤트 수를 1분 버킷으로 집계.
- 카드 우측에 **필터 칩 4개**: `[All] [Running] [Failed] [Bypass]`. 선택 시 하단 WP/Feature 리스트를 클라이언트 사이드 DOM 숨김/표시로 필터링 (서버 호출 없음).

#### 4.5.3 좌측 — Work Packages

- 각 WP가 독립 카드. 카드 상단에 **도넛 차트** (CSS `conic-gradient`로 구현) + 가로 **progress bar**.
- 상태별 카운트: `● done / ○ running / ◐ pending / × failed / 🟡 bypass`.
- 카드 아래로 `<details>` 펼쳤을 때 v1의 6컬럼 row를 재사용하되, **상태별 4px 좌측 컬러 바**(`▌`) 추가. Running row는 얇은 애니메이션 라인 오버레이.

#### 4.5.4 좌측 — Features

- WBS 외 독립 Feature를 별도 카드에 평면 리스트로. WP 그룹핑 없음 (v1 동일).

#### 4.5.5 우측 상단 — Live Activity

- `phase_history`의 최신 N개 이벤트(기본 20개), 타임스탬프 내림차순.
- auto-scroll + 새 이벤트 fade-in.
- 이벤트 포맷: `HH:MM:SS  TSK-ID  event(ok/fail)  elapsed  [⚠ if fail]`.
- 상태 칩 색상은 KPI 카드와 동일 팔레트.

#### 4.5.6 우측 중단 — Phase Timeline

- 태스크 ID × 시간축 가로 스트립, 인라인 SVG 렌더.
- 각 phase 구간을 `dd/im/ts/xx` 색으로 채움. 실패 구간은 반투명 + 빗금 패턴, bypass는 🟡 엔드 마커.
- 시간축 라벨: 현재 시점 기준 최근 60분 (x-axis는 5분 간격 tick).
- 태스크 수가 많으면 세로 스크롤.

#### 4.5.7 우측 하단 — Team Agents / Subagents

- v1의 Team / Subagents 섹션을 우측 보조 영역으로 이동.
- tmux pane 목록 — **각 pane row에 마지막 3줄 인라인 preview + [expand ↗] 버튼** (v2 신규).
- `[expand ↗]` 클릭 시 §4.5.8의 사이드 드로어 오픈.
- agent-pool 슬롯 목록 — 외부 stdout 캡처 불가 (v1 문구 유지), preview·드로어 대상 아님.

```
  TEAM AGENTS (tmux)
  ┌──────────────────────────────────────────────────┐
  │ dev-WP-01  %2  claude  pid 48121    [expand ↗]   │
  │   ╭──────────────────────────────────────────╮   │
  │   │ > starting build phase                   │   │
  │   │ > 5 passed, 2 failed                     │   │
  │   │ > retrying with opus (escalation 1/2)    │   │
  │   ╰──────────────────────────────────────────╯   │
  │ dev-WP-01  %3  claude  pid 48122    [expand ↗]   │
  │   ...                                            │
  └──────────────────────────────────────────────────┘
```

#### 4.5.8 실행 출력 뷰어 (Side Drawer) — 신규

**트리거**: Team Agents 섹션의 `[expand ↗]` 버튼 또는 pane row 클릭, 혹은 단축키 `o`.

**레이아웃**: 우측에서 슬라이드 인하는 드로어 (데스크톱 기준 너비 640px, 태블릿·모바일은 전체 화면 모달).

```
 ┌─── PANE OUTPUT: dev-WP-01 %2 (claude, pid 48121) ────────── [✕] ──┐
 │  TSK-01-09 · build phase · elapsed 4m 22s           ⏸ pause │ ⟳   │
 │ ──────────────────────────────────────────────────────────────── │
 │  > claude-code: starting build phase                              │
 │  > applying design from docs/tasks/TSK-01-09/design.md            │
 │  > writing src/monitor/dashboard.tsx                              │
 │  > running npm test                                               │
 │  > 5 passed, 2 failed                                             │
 │  > retrying with opus (escalation 1/2)                            │
 │  ...                                                              │
 │                                                                   │
 │  ▼ live  •  2s refresh  •  captured at 11:09:22                   │
 └───────────────────────────────────────────────────────────────────┘
```

**상세 요구**:
- 드로어 상단: pane 메타(window, index, pid) + 태스크 연결(해당 pane이 현재 처리 중인 TSK-ID, phase, elapsed) + [✕] 닫기 · [⏸ pause] 폴링 정지 · [⟳] 수동 새로고침
- 본문: `<pre>` 영역, 최대 500줄 (v1과 동일), 새 줄은 하단에 append + auto-scroll (사용자가 스크롤 업하면 auto-scroll 일시 정지)
- 푸터: live 상태·폴링 주기·마지막 캡처 시각
- 닫기 방법: [✕] 버튼 · `ESC` 키 · 드로어 바깥 backdrop 클릭
- 데이터 소스: `/api/pane/{pane_id}` (v1 엔드포인트 그대로 재사용, 신규 엔드포인트 없음)
- 다중 동시 열기 **불가** (단일 드로어) — 다른 pane의 expand 클릭 시 현재 드로어를 해당 pane으로 교체
- 드로어가 열려있을 때 대시보드 본체의 부분 fetch는 계속 동작 (둘은 독립 폴링)

### 4.6 상태 표시 규칙 (v1 승계 + 시각화 강화)

| 상태 | 뱃지 | 색상 | v2 추가 요소 |
|------|------|------|---------------|
| `[dd]` Design | 🔵 DESIGN | blue | — |
| `[im]` Build | 🟣 BUILD | purple | — |
| `[ts]` Test | 🟢 TEST | green | — |
| `[xx]` Done | ✅ DONE | gray | WP 도넛에서 100% 회색 영역 |
| `.running` | 🟠 RUNNING | orange (pulse) | row 얇은 애니메이션 바, KPI 카드 맥동 |
| `.failed` / `*.fail` | 🔴 FAILED | red | row 좌측 바 강조, 타임라인에 빗금 패턴 |
| `bypassed: true` | 🟡 BYPASSED | yellow | 타임라인 엔드 마커 🟡, row 플래그 아이콘 |

### 4.7 반응형

- **≥1280px**: 2단 (좌 60% WP/Feature / 우 40% Live+Timeline+Team+Subagent).
- **768~1279px**: 1단으로 접힘. 순서 = KPI → WP → Features → Activity → Timeline → Team → Subagent.
- **<768px**: KPI 카드 가로 스크롤, Phase Timeline 기본 접힘(사용자가 토글). 도넛 대신 숫자만.

### 4.8 부분 fetch 프로토콜

1. 초기 HTML 렌더 시 서버가 전체 상태를 SSR.
2. 클라이언트가 `setInterval`로 N초마다 `GET /api/state` 호출.
3. 응답 JSON을 기존 DOM과 diff해서 **변경된 섹션만 innerHTML 교체**.
4. `<details open>` 펼침 상태, 스크롤 위치, 필터 칩 선택은 data-attribute로 보존.
5. auto-refresh 토글 OFF 시 `clearInterval`.

**No framework**: 바닐라 JS, fetch + `document.querySelector`만 사용. 번들 크기 제한을 위해 JS 총량 200줄 이내 목표.

## 5. 비기능 요구사항

### 5.1 Constraints (v1 승계)

- **언어/런타임**: Python 3.8+ 표준 라이브러리만
- **의존성**: pip 패키지 금지, 외부 CDN/폰트/JS 금지 (v1과 동일)
- **파일 I/O**: 읽기 전용

### 5.2 코드 규모 제한

- `DASHBOARD_CSS` 인라인 분량 ≤ **400줄** (v1 ~63줄에서 증가하되, 상한 고정)
- `_section_*` 렌더 함수 합계 ≤ **600줄**
- 클라이언트 사이드 JS ≤ **200줄**
- 서버 핸들러/데이터 수집 로직은 v1 그대로, 변경 없음

### 5.3 접근성

- 색상 대비 WCAG AA 준수 (GitHub 다크 팔레트 기준 이미 대체로 만족)
- KPI 카드·필터 칩은 keyboard focusable (`tabindex`, `aria-pressed`)
- 스파크라인·타임라인 SVG에 `<title>` 태그로 스크린리더 보조 텍스트 제공
- 애니메이션(pulse, fade-in)은 `prefers-reduced-motion: reduce` 존중

### 5.4 성능

- 초기 페이지 로드 1MB 이내 (이미지·폰트 없음이므로 자연스럽게 만족)
- `/api/state` 응답 크기: 태스크 100건 기준 100KB 이내
- 부분 fetch 주기 기본 5초, 최소 2초

## 6. 파일 구조 변경안

```
dev-plugin/
├── scripts/
│   └── monitor-server.py          # 수정 — DASHBOARD_CSS + _section_* 함수 재작성
└── docs/
    └── monitor-v2/                 # 신규 — v2 설계/QA 아티팩트
        ├── prd.md                  # 본 문서
        ├── trd.md                  # (후속) 기술 설계
        └── wbs.md                  # (후속) 작업 분해
```

**기존 파일 삭제 없음**. `scripts/monitor-server.py`의 렌더링 레이어만 in-place 교체.

스킬 커맨드(`/dev-monitor`)·엔드포인트 경로·PID 파일·로그 위치는 모두 v1 그대로. 사용자 입장에서 업그레이드 후 명령어 변경 없음.

## 7. 마이그레이션 전략

- **단일 파일 교체**: `/dev-monitor`를 재실행하면 새 렌더가 적용된다. 다운그레이드도 이전 커밋으로 되돌리면 됨.
- **이전 URL·Bookmarks 호환**: `/`, `/api/state`, `/pane/{id}`, `/api/pane/{id}` 경로 유지.
- **브라우저 캐시**: 인라인 CSS/JS라 별도 캐시 무효화 불필요.

## 8. 구현 단계 (제안)

1. **P1 — 정적 프로토타입 (~1일)**
   - `docs/monitor-v2/prototype.html` — 목업 데이터 하드코딩한 단일 HTML 파일
   - 레이아웃·색·애니메이션 확인용 (서버 통합 전)
2. **P2 — CSS/렌더 레이어 교체 (~2일)**
   - `DASHBOARD_CSS` 교체
   - `_section_header`를 KPI 카드 + 필터 칩 포함으로 확장
   - `_section_wbs`를 WP 카드(도넛+progress) 형태로 재작성
   - Live Activity·Phase Timeline 렌더 함수 신규 추가
3. **P3 — 부분 fetch JS 추가 (~0.5일)**
   - `setInterval` + `fetch('/api/state')` + DOM diff
   - `<details>` 펼침 상태·스크롤·필터 보존 로직
4. **P4 — 반응형 + 접근성 (~0.5일)**
   - 미디어 쿼리, `prefers-reduced-motion`, `aria-*` 태그
5. **P5 — QA (~0.5일)**
   - v1 시나리오 회귀 (`/dev-team`, `/feat`, `/agent-pool` 단독 실행)
   - macOS/Linux/WSL2/Windows(psmux) 4개 환경 Smoke test

총 ~4.5일 예상.

## 9. 열린 질문 / 의사결정 필요

- [ ] 실행 출력 뷰어: 사이드 드로어(640px) vs 대시보드 하단 고정 패널(높이 30%) vs 풀스크린 모달? (와이어프레임은 드로어 기준)
- [ ] pane row 인라인 preview 라인 수: **3줄** vs **5줄** vs **끄기 옵션**?
- [ ] KPI 카드 스파크라인 시간창: 최근 **10분** vs **1시간**? (데이터 밀도와 스파크라인 가독성 트레이드오프)
- [ ] Phase Timeline 시간축: 최근 **60분** 고정 vs 확대/축소 가능? (후자는 복잡도↑)
- [ ] 필터 칩 기본값: `[All]` vs `[Running+Failed]`? (장시간 모니터링 시 "문제 있는 것만 보기"가 주 사용 패턴이라면 후자)
- [ ] 도넛 차트: WP별로만? vs 상단 전역 도넛도 추가? (상단 KPI와 중복일 수 있음)
- [ ] Phase Timeline에 bypass 마커 노출 위치: 이벤트 시점 vs 태스크 row 끝? (v2 와이어프레임은 row 끝 🟡 기준)
- [ ] 정적 프로토타입(P1) 생성 여부: 시간 절약하고 바로 P2로? vs 먼저 프로토타입 검토 후 진행?
- [ ] v2를 **재명명 없이 v1 자리에 덮어쓰기** vs **`monitor-v2` 디렉터리에 병행 운영** 후 전환? (문서는 monitor-v2 기준으로 작성, 코드는 in-place 교체 기본 가정)

## 10. 참고

- 선행 PRD: `docs/monitor/prd.md` (v1, 2026-04-20)
- v1 구현: `scripts/monitor-server.py` (1852줄)
- v1 스킬: `skills/dev-monitor/SKILL.md`
- 상태 머신 정의: `references/state-machine.json`
- 시그널 프로토콜: `references/signal-protocol.md`
- 플랫폼 유틸: `scripts/_platform.py`
