# Feature: monitor-redesign

## 요구사항

디자인 샘플 /Users/jji/project/dev-plugin/dev-plugin Monitor.html를 참고하여 http://localhost:7322/?subproject=monitor-v3 대시보드 개선: Task States/Work Packages/Live Activity 카드 디자인을 샘플과 동일하게 맞추고, 컴포넌트 폭/배치를 재조정하며, 한국어/영어 언어 토글을 복원. 실제 브라우저(Chrome MCP)와 디자인 HTML을 비교하면서 작업.

## 배경 / 맥락

(선택: 이 기능이 필요한 이유, 관련 이슈, 영향 범위 등)

## 도메인

frontend

## 진입점 (Entry Points)

- 사용자 진입 경로: `python scripts/monitor-launcher.py` → 브라우저에서 http://localhost:7322/?subproject=monitor-v3 접속
- URL / 라우트: `http://localhost:7322/?subproject={SUBPROJECT}`
- 수정할 라우터 파일: `scripts/monitor-server.py` (HTML/CSS/JS를 Python 문자열로 inline 제공)
- 수정할 메뉴·네비게이션 파일: N/A (SPA 단일 페이지)

## 참조 디자인

- **디자인 샘플**: `/Users/jji/project/dev-plugin/dev-plugin Monitor.html`
- **현재 구현**: `scripts/monitor-server.py` (render_dashboard)

## 개선 항목

1. **레이아웃/폭 (최우선)** — 현재 페이지는 **오른쪽에 넓은 빈 공간**이 발생. 샘플처럼 화면 폭을 제대로 활용하도록 container max-width 확대, 카드 그리드를 가로 방향으로 채워 배치. 샘플 HTML의 grid 구조를 그대로 복제.
2. **Task States 카드** — 샘플과 동일한 카드 스타일 (pill 배지, 색상, 그라데이션, 카운트 타이포그래피)
3. **Work Packages 카드** — 동일 디자인 규칙 적용 (헤더, 진행률 바, 타임라인)
4. **Live Activity** — 동일 디자인 규칙 적용 (타임스탬프, 아이콘, 레이아웃)
5. **언어 토글** — 한국어/영어 전환 UI 복원 (헤더 우측 상단)

## 비고

- 렌더링은 Python 문자열 템플릿이므로 HTML/CSS/JS 변경은 `render_dashboard` 함수 내부 수정으로 이뤄짐
- 테스트: `scripts/test_monitor_render.py`, `scripts/test_monitor_kpi.py` 기존 구조 계약을 깨지 않으면서 추가 테스트 작성
- 검증: Chrome MCP로 실제 브라우저 렌더링을 스크린샷으로 확인하며 디자인 샘플과 대조

## 불변 영역 (건드리지 않을 것)

- **서브프로젝트 선택 UI** — 현재 구현된 서브프로젝트 선택(드롭다운/리스트) 영역은 **그대로 유지**. 디자인/동작/위치 모두 변경 금지.
