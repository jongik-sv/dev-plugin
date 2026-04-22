# Feature: monitor-port-per-project

## 요구사항

dev-monitor 서버가 프로젝트별로 다른 포트를 사용하도록 수정. 같은 프로젝트(동일 project-root) 내에서는 하나의 포트로 idempotent하게 재사용되고, 다른 프로젝트에서 기동하면 자동으로 다른 포트를 할당받아 동시 실행 가능해야 함. 현재는 PID 파일이 포트 기준(dev-monitor-{port}.pid)이라 기본 포트 7321이 한 프로젝트에 점유되면 다른 프로젝트에서 기동이 막힘.

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
