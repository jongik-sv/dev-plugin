# Feature: dep-graph-arrowheads

## 요구사항

dev-monitor 대시보드의 **의존성 그래프(Task Dependency Graph)** 에서 엣지(Task → Task) 일부가 **방향을 나타내는 삼각형 화살표 머리(arrowhead) 없이 평범한 선**으로 렌더링된다. 모든 엣지에 일관되게 삼각형 머리를 표시해 의존 방향을 시각적으로 즉시 식별할 수 있도록 수정한다.

## 배경 / 맥락

- 증상: 사용자 제공 스크린샷에서 `TSK-01-01 → TSK-02-01` 등 중앙부 엣지는 삼각형 머리가 보이지만, 화면 가장자리로 이어지는 일부 엣지(왼쪽·오른쪽·아래쪽)에는 머리가 없다.
- 영향 범위: `scripts/monitor-server.py` 내 의존성 그래프 렌더링 (SVG/Canvas — `<marker>` 정의 또는 화살표 삼각형 draw 로직).
- 가설: SVG 마커가 특정 경로(직선 대각선 또는 짧은 길이 엣지)에만 누락되었거나, `marker-end` 속성 누락, 혹은 viewport 경계 클리핑 문제.

## 도메인

frontend

## 진입점 (Entry Points)

> UI가 있는 Feature(fullstack/frontend)는 **필수**. 백엔드/인프라 Feature는 `N/A`로 남긴다.

- 사용자 진입 경로: (예: `로그인 후 → 사이드바 '설정' → '프로필'` 클릭 플로우)
- URL / 라우트: (예: `/settings/profile`)
- 수정할 라우터 파일: (예: `apps/web/src/app/settings/profile/page.tsx`)
- 수정할 메뉴·네비게이션 파일: (예: `apps/web/src/components/Sidebar.tsx`의 `navItems` 배열)

## 비고

(선택: 제약사항, 의존성, 주의사항 등)
