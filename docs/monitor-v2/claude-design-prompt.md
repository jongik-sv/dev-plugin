# dev-plugin Monitor — 재디자인 요청

## 프로덕트
로컬 개발 오케스트레이션 모니터 (tmux pane + git worktree 병렬로 돌아가는
AI 에이전트들의 WBS/Task 실행 상태 대시보드). 단일 개발자가 옆 모니터에
띄워놓고 glance하는 용도. 뷰포트는 데스크톱 1440px 기본.

색·타이포·톤은 Claude Design에 맡김. **컴포넌트 구성과 배치만 명세.**

---

## 컴포넌트 명세

| # | ID | 이름 | 형태 | 보여주는 것 |
|---|------|------|------|-------------|
| 1 | `hdr` | Command Bar | sticky 얇은 수평 바 | 프로젝트 경로, 현재 시각, 리프레시 주기, auto-refresh 토글 버튼 |
| 2 | `kpi` | KPI Strip | 5등분 카드 열 | Running / Failed / Bypass / Done / Pending 각각의 숫자 + 최근 10분 스파크라인 |
| 3 | `kpi-chips` | Filter Chips | 둥근 버튼 4개 (KPI 바로 아래) | All / Running / Failed / Bypass — Task row 필터 |
| 4 | `wp-cards` | Work Package Cards | 카드 리스트 (세로 스택, WP별 1개) | WP-ID, 제목, 도넛(상태 비율), 진행률 바, 카운트 5종(●○◐×🟡), 접히는 Task 목록 |
| 5 | `features` | Features | 평면 Task row 리스트 | WP 없이 독립 Feature들의 Task (형태는 wp-cards 내부 Task row와 동일) |
| 6 | `live-activity` | Live Activity | 세로 ticker 리스트 | 최근 20건 phase 이벤트 (`HH:MM:SS TSK-XX-XX event [from]→[to] elapsed`) |
| 7 | `phase-timeline` | Phase Timeline | 가로 SVG 타임라인 | 행당 Task 하나, 현재-60분 → 현재 구간, phase별 색 segment + 5분 tick |
| 8 | `team` | Team Agents | pane row 리스트 | 각 tmux pane: ID, window/command, PID, 최근 3줄 preview, [show output], [expand] |
| 9 | `subagents` | Subagents | 뱃지 리스트 | agent-pool의 running/done/failed 시그널 |
| 10 | `phase-history` | Phase History | 번호 매긴 풀폭 리스트 (푸터) | 최근 10건 (`HH:MM:SSZ TSK-XX event [from]→[to] elapsed`) |
| 11 | `drawer` | Pane Drawer | 우측 슬라이드인 오버레이 (640px) | team 섹션의 [expand] 클릭 시 해당 pane의 스크롤백을 2초 폴링해 표시 |

### Task row 구조 (wp-cards / features 공통 하위 컴포넌트)
```
[상태 컬러 바 4px][TSK-ID][상태 뱃지][제목][경과][재시도][플래그]
```
상태: done / running / failed / bypass / pending — 각기 다른 시각 표현.

### WP 카드 구조
```
┌──────────────────────────────────────┐
│ [도넛]  WP-ID · WP 제목               │
│         progress bar                  │
│         ● N done ○ N running ...      │
│         ▸ Tasks (N) ← 클릭하면 펼침   │
│           └─ [Task row × N]           │
└──────────────────────────────────────┘
```

---

## 레이아웃 (1440px)

```
┌───────────────────────────────────────────────────────────────┐
│ 1. Command Bar (sticky top, 높이 48~56px)                     │
├───────────────────────────────────────────────────────────────┤
│ 2. KPI Strip (5등분, 높이 100~140px)                          │
│ 3. Filter Chips (KPI 바로 아래, 얇은 줄)                       │
├──────────────────────────────┬────────────────────────────────┤
│                              │                                │
│  4. WP Cards                 │  6. Live Activity              │
│     (세로 스택)              │     (세로 스크롤 20건)          │
│                              │                                │
│  5. Features                 │  7. Phase Timeline             │
│     (WP 없으면 empty)        │     (가로 SVG)                  │
│                              │                                │
│     좌측 3fr (~60%)          │  8. Team Agents                │
│                              │     (pane rows)                │
│                              │                                │
│                              │  9. Subagents                  │
│                              │                                │
│                              │     우측 2fr (~40%)            │
├──────────────────────────────┴────────────────────────────────┤
│ 10. Phase History (풀폭 푸터, 최근 10건)                       │
└───────────────────────────────────────────────────────────────┘

11. Drawer: team의 [expand] 클릭 시 우측에서 슬라이드인
    (화면 위에 오버레이, 너비 640px, Esc로 닫힘, 배경 클릭 시 닫힘)
```

### 반응형
- **1280px 미만**: 좌·우 2단 그리드를 1단 세로 스택으로 전환. WP Cards → Features → Live Activity → Phase Timeline → Team → Subagents 순서.
- **768px 미만**: KPI Strip 가로 스크롤 (scroll-snap), Drawer는 풀폭(100vw), Phase Timeline 기본 접힘.

---

## 인터랙션

- **Filter chips**: 클릭 시 `aria-pressed` 토글, 모든 Task row를 상태 기준으로 필터
- **auto-refresh 토글**: 클릭 시 5초 폴링 on/off
- **WP 카드의 `▸ Tasks (N)`**: `<details>`로 펼침/접힘
- **Team의 [expand] 버튼**: Pane Drawer 오픈 + 2초 폴링 시작
- **Drawer 닫기**: Esc / 배경 클릭 / × 버튼
- 서버는 5초마다 `data-section` 단위로 부분 DOM 교체 (전체 리로드 없음)

---

## 기술 제약 (변경 불가)

- **단일 HTML 문서** — 인라인 `<style>`, 인라인 `<script>`, 인라인 `<svg>`만
- **외부 CDN/폰트/스크립트 전부 금지** (Google Fonts, Tailwind, Chart.js 등)
- 시스템 폰트 스택만 사용
- 바닐라 JS만 (React/Vue 불가)
- 모든 interactive 요소에 다음 훅 보존:
  - `data-section="{id}"` (각 섹션 외곽 태그)
  - `data-filter="{all|running|failed|bypass}"` (칩)
  - `data-pane-expand="{pane_id}"` (expand 버튼)
  - `data-drawer` / `data-drawer-backdrop` / `data-drawer-title` /
    `data-drawer-meta` / `data-drawer-pre` / `data-drawer-close`
  - `.refresh-toggle` (auto 버튼)
  - `aria-*` 속성 (dialog·pressed·hidden·labelledby)

---

## 산출물
HTML 단일 파일 (`<!DOCTYPE html>` 부터 `</html>`까지). 목업 데이터 하드코딩
— 실제 서버 연동은 우리가 Python 렌더 함수에 이식.
