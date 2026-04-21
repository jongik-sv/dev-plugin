# TSK-01-01: 테스트 결과

## 결과: FAIL

## 실행 요약

| 구분 | 통과 | 실패 | 합계 |
|------|------|------|------|
| 단위 테스트 | 318 | 1 | 319 |
| E2E 테스트 | 0 | 0 | 0 |

## 정적 검증 (Dev Config에 정의된 경우만)

| 구분 | 결과 | 비고 |
|------|------|------|
| lint (py_compile) | pass | 스크립트 컴파일 성공 |
| typecheck | N/A | Dev Config에 정의되지 않음 |

## 단위 테스트 실패 상세

**실패 테스트**: `test_monitor_server_bootstrap.TestMainFunctionality.test_server_attributes_injected`

```
test_server_attributes_injected (test_monitor_server_bootstrap.TestMainFunctionality)
server.project_root, docs_dir 등 속성이 서버 인스턴스에 주입된다.
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/Users/jji/project/dev-plugin/.claude/worktrees/WP-01-monitor-v2/scripts/test_monitor_server_bootstrap.py", line 306, in test_server_attributes_injected
    self.assertIsNotNone(server)
AssertionError: unexpectedly None
```

**원인**: _ServerContext의 server 인스턴스 캡처 메커니즘이 null을 반환함. ThreadingMonitorServer.__init__을 패치하는 과정에서 server_holder 리스트가 채워지지 않은 상태로 _server 속성 접근.

**영향**: 서버 속성 주입 테스트 1건만 실패. 다른 318건의 유닛 테스트는 모두 통과하였음.

## E2E 테스트

단위 테스트 실패로 인해 E2E 테스트를 건너뜀 (dev-test 절차 "단위 실패 시 E2E skip").

## QA 체크리스트 판정

| # | 항목 | 결과 | 비고 |
|---|------|------|------|
| 1 | `python3 -m py_compile scripts/monitor-server.py` 통과 | pass | 컴파일 성공 |
| 2 | CSS 문자열 라인 수 ≤ 400 | unverified | E2E 실행 미진행 |
| 3 | @supports fallback 포함 | unverified | E2E 실행 미진행 |
| 4 | v1 CSS 변수 15개 존재 | unverified | E2E 실행 미진행 |
| 5 | KPI 카드 상태별 스타일 | unverified | E2E 실행 미진행 |
| 6 | 필터 칩 aria-pressed 스타일 | unverified | E2E 실행 미진행 |
| 7 | .page 2단 레이아웃 | unverified | E2E 실행 미진행 |
| 8 | 미디어 쿼리 1279px 전환 | unverified | E2E 실행 미진행 |
| 9 | 미디어 쿼리 767px 블록 | unverified | E2E 실행 미진행 |
| 10 | prefers-reduced-motion 블록 | unverified | E2E 실행 미진행 |
| 11 | timeline SVG 클래스 정의 | unverified | E2E 실행 미진행 |
| 12 | 드로어 기본 너비 640px | unverified | E2E 실행 미진행 |
| 13 | 드로어 모바일 100vw 전환 | unverified | E2E 실행 미진행 |
| 14 | task-row position relative | unverified | E2E 실행 미진행 |
| 15 | running 애니메이션 연결 | unverified | E2E 실행 미진행 |
| 16 | (클릭 경로) sticky 헤더 고정 | unverified | E2E 실행 미진행 |
| 17 | (화면 렌더링) KPI·칩·레이아웃 | unverified | E2E 실행 미진행 |

## 재시도 이력

첫 실행에서 단위 테스트 1건 실패. 캡처 메커니즘 이슈로 인한 테스트 프레임워크 문제.

## 비고

- 단위 테스트 실패율 0.3% (318/319 통과)
- 대부분의 monitor-server 기능(렌더, 라우팅, 신호 처리, tmux 통합, 상태 스캔)이 정상 작동함을 확인
- 해당 테스트는 test_monitor_server_bootstrap.py의 내부 _ServerContext 유틸리티 문제로 보임
- E2E 테스트는 단위 테스트 성공 후 재시도 시 실행 예정
