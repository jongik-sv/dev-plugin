# Feature: wp-progress-spinner

## 요구사항

dev-monitor 대시보드에서 WP(Work Package) 단위의 **통합 작업(merge/integration)** 과 **WP 단위 테스트 실행** 중에는 해당 WP 카드 위치에 스피너가 돌아가야 한다. 이를 통해 WP가 현재 어떤 활동 상태인지 시각적으로 즉시 인지할 수 있어야 한다.

## 배경 / 맥락

- 현재 dev-monitor 대시보드(scripts/monitor_server/ + scripts/monitor_server/static/app.js)는 WP 카드에 Phase 배지(P0~P5)와 Task 요약만 표시한다.
- WP 리더가 (1) 여러 Task들을 머지하거나 (early merge / full merge) (2) WP 전체 단위 테스트를 돌리는 동안에는 시각적 진행 피드백이 없어, 사용자는 "지금 뭐 하는 중인지" 알기 어렵다.
- 기존 Phase 배지는 단계 전이만 나타내며, 실시간 "활동 중(busy)" 상태를 표현하지 못한다.
- Task 레벨(개별 DDTR) 스피너는 이번 Feature 범위 밖. **WP 레벨 활동**만 대상.

## 도메인

frontend

## 진입점 (Entry Points)

- 사용자 진입 경로: dev-monitor 대시보드 → WP 카드
- URL / 라우트: `http://localhost:{port}/` (monitor-server 루트)
- 수정할 라우터/렌더링 파일:
  - `scripts/monitor_server/static/app.js` (WP 카드 렌더링 + 상태 바인딩)
  - `scripts/monitor_server/static/style.css` (스피너 CSS 애니메이션)
  - `scripts/monitor_server/renderers/*` 또는 `scripts/monitor_server/core.py` (WP busy 상태를 API 응답에 포함)
- 상태 소스 후보:
  - WP 리더가 머지/통합 중일 때 남기는 시그널 또는 로그
  - WP 단위 테스트 실행 중일 때의 signal-helper / leader-watchdog 흔적
  - 기존 `state.json` / tmux pane snapshot에서 유도

## 비고

- Dev-monitor 서버는 폴링 기반(ETag 캐시). 스피너는 클라이언트 CSS 애니메이션이면 충분하므로 스트리밍은 불필요.
- WP 활동 종료 시(merge 완료 / 테스트 종료) 스피너는 즉시 사라져야 한다 (다음 폴링 사이클 내).
- 여러 WP가 동시에 병렬 활동 중일 수 있으므로 WP별 독립 상태.
- UI 회귀 방지: 기존 Phase 배지/Task 요약의 레이아웃을 깨뜨리지 않는다. layout-skeleton 테스트만 단언, 구체 색상값 단언 금지 (회귀 자석 방지).
