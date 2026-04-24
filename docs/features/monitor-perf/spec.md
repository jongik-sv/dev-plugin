# Feature: monitor-perf

## 요구사항

모니터 성능 최적화 — 단일 monitor 페이지가 GPU 38%·WindowServer 18%·Terminal 14%·monitor 폴링 10.6 req/s를 잡아먹음 (브라우저 탭 닫으면 GPU 0%·폴링 0/s로 즉시 회수). 원인: /api/graph 폴링이 ~100ms 간격 + 매 폴링마다 SVG 전체 재구성으로 추정. 개선 방향: ① 폴링 주기 5~10초로 늘리거나 SSE/WebSocket push 전환, ② 그래프 diff 갱신(변경 노드만 업데이트), ③ document.visibilityState === 'hidden'이면 폴링 정지·감속, ④ /api/graph ETag/304 캐싱으로 미변경 시 redraw 스킵, ⑤ monitor-server.py(~5600줄) 인라인 HTML/CSS/JS의 will-change·transform: translateZ(0) 등 GPU 레이어 남용 감사. 회귀 방지: 폴링 빈도·GPU util 회귀 테스트(헤드리스 브라우저로 1분 측정).

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
