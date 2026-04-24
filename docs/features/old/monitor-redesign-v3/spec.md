# Feature: monitor-redesign-v3

## 요구사항

Apply new Claude-Design-generated monitor UI incrementally. Replace DASHBOARD_CSS with new design tokens/layout CSS from 'dev-plugin Monitor.html', then rewrite section renderers in stages: (1) shell+cmdbar+grid+section-heads, (2) WP cards with donut SVG + task rows (.trow), (3) right col (live-activity .arow, phase timeline .tl-track, team .pane + pane-preview, subagents .subs), (4) phase history table + drawer + JS (clock, filter chips, drawer open/close/Esc/focus-trap). Update scripts/test_monitor_render.py tests to match new markup. Source design: /Users/jji/project/dev-plugin/dev-plugin Monitor.html (2099 lines). Target: /Users/jji/project/dev-plugin/scripts/monitor-server.py.

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
