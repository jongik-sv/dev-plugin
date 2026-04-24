# Feature: monitor-server-perf

## 요구사항

내부 시그널·서버 측 부하 요소 제거 (모니터 성능 보강). 코드 감사 결과 서버측 비용이 클라이언트 폴링과 곱셈으로 작용하는 핫스팟 다수 발견. (a) monitor-server.py /api/graph가 명시적 no in-memory caching — 매 요청마다 os.walk(claude-signals/) + glob(agent-pool-signals-*) + Path.glob(*/state.json) 전수 스캔 + subprocess.run(sys.executable, dep-analysis.py, --graph-stats) 새 Python 인터프리터 fork. 10.6 req/s x 콜드 스타트 ~80-150ms = 단일 페이지가 코어 1개 거의 점유. ThreadingHTTPServer라 동시 다중 탭이면 fork도 N배. (b) scan_signals()는 캐시 없이 매번 전체 트리 os.walk — 시그널 파일 5개여도 전 프로젝트 dir stat. (c) 대시보드 HTML이 --refresh-seconds default=3 meta-refresh로 3초마다 풀 페이지 리로드 + JS가 별도로 /api/graph 폴링 -> 이중 부하. (d) signal-helper.py wait-running은 2초 폴링 — dev-team 워커 16개 동시면 8 stat/s. (e) leader-watchdog.py는 WP당 1개 데몬이 30초마다 tmux display-message + tmux list-windows 2회 호출 — WP 4개면 tmux 서버에 분당 16회. 개선 우선순위: (1) /api/graph 1초 TTL 메모이즈 + ETag/304, (2) dep-analysis.py를 subprocess가 아닌 import로 인프로세스 호출, (3) scan_signals() 1초 TTL 메모이즈, (4) meta-refresh 제거 후 JS 단일 폴링으로 일원화, (5) watchdog tmux 호출을 list-windows -F 한 번으로 통합. 주의: dev/WP-02-monitor-v5 머지가 monitor-server.py를 monitor_server/ 패키지로 분리 — 머지 마무리하면서 위 캐시·디바운스를 같이 넣지 않으면 분리된 코드가 동일 핫스팟을 그대로 이관. 회귀 방지: /api/graph p95 응답시간 + subprocess fork 횟수/분 메트릭 노출 + 헤드리스 1분 측정에 추가.

## 배경 / 맥락

(선택: 이 기능이 필요한 이유, 관련 이슈, 영향 범위 등)

## 도메인

(backend | frontend | fullstack | database — Dev Config의 domains 중 하나. 비워두면 dev-design이 판단)

## 진입점 (Entry Points)

> UI가 있는 Feature(fullstack/frontend)는 **필수**. 백엔드/인프라 Feature는 `N/A`로 남긴다.

- 사용자 진입 경로: (예: `로그인 후 → 사이드바 '설정' → '프로필'` 클릭 플로우)
- URL / 라우트: (예: `/settings/profile`)
- 수정할 라우터 파일: (예: `apps/web/src/app/settings/profile/page.tsx`)
- 수정할 메뉴·네비게이션 파일: (예: `apps/web/src/components/Sidebar.tsx`의 `navItems` 배열)

## 비고

(선택: 제약사항, 의존성, 주의사항 등)
