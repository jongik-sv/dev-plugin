## 할일
- 의존성 그래프에서 방향을 나타내는 삼각형 머리가 없는 선이 있어
- WP의 작업에 대해서도 스피너가 돌아야지.




## 좀 있다 할일
- future-upgrade-plan.md, idea.md 업데이트 : 다른 컴퓨터에 각각 개발하는 방안(분산 개발, 다른 구독 요금)
- 사용량 모니터링하여 부하 조절 기능
- 모니터 스킬 최적화 : 중복, 불합리 코드/프롬프트 제거




## 완료
- e2e 테스트 추가
- 반복으로 토큰 폭탄이 날 수 있는 문제 예방을 위한 스킬 검토
- WP 단위 코드 리뷰 (merge 전 품질 게이트) 추가
- codex:review 사용 문서, 코드 모두 맞는 명령어 사용
- 스킬 의존성 사전 체크 (tmux, jq, git — 이미 각 진입점에서 체크 구현됨)
- cross-platform-migration
- 설계부터 의존관계는 문제가 있음, 시간오래 걸리는 설계(대기중인 태스크에 한해서)는 먼저 진행해도 될것 같음
- feat 명령어 추가(wbs 없이 처리하는 명령어)
- 테스트 실패로 개발이 멈추어버리는 경우 → `--on-fail` 3모드 구현: `strict`(중단), `bypass`(에스컬레이션→임시완료, 기본값), `fast`(즉시 임시완료). state.json `bypassed: true` + dep-analysis 의존성 충족 판정. 향후 MCP/CLI로 이슈 전달 예정
- 디자인이 너무 안좋아졌어. 샘플로 제공된 것을 참고해서 개선해줘
- 문제점 wbs를 워크트리는 보지 않고 docs 밑의 폴더만 감시를 하면 실제 워크트리에서 보이는 태스크는 전혀 알수가 없음
- 자동으로 refresh를 하기에 작업 패키지를 접어도 의미가 없음. refresh 하면 다시 펼쳐진 상태로 되어 있음. 이를 해결할 방법은? --ultrathink
- 여러 워크트리에서 작업하다가 합칠 경우 유독 충돌이 많고 이를 해결하기 위해 토큰 소모가 크다. 해결 방법은? --ultrathink
- 순차 개발 기능이 있으면 좋겠다.
- 순차 dev-team 모드 : WP 별로 순차 실행, 워크 트리를 사용하지 않음 

- Task의 툴팁 위치 조정(Task 바로 위, 툴팁 디자인 개선도 필요)
- Task 선택 시 EXPAND 버튼 처럼 확장 되며 WBS의 Task 내용, 진행현황 확인
- WP 폭 크기 조절(지금 너무 큼, 실시간활동, 팀에이전트, 서브에이전트 있는 항목인 오른쪽을 더 키워야 함)
- 팀 에이전트 각 항목의 높이를 지금의 2배로 보이게 요청
- 의존성 그래프에서 failed와 크리티컬 패스의 색상이 동일해서 구분이 안감, 크리티컬 패스는 배경색을 댜르게 조정, 
- 작업 패키지, 의존성 그래프의 각 태스크에 현재 각 작업단계를 알 수 있도록 배지, 현재 작업중이면 배지에 스피너 추가
- 수행중 LLM의 실수를 CLAUDE.md 에 적어서 실수를 반복하지 않는 기능
- wbs 스킬에서 의존관게 없고 단독으로 작업가능한 feature 는 WP가 아닌 단독 feature로 등록하고 dev-team 에서 /feat 스킬을 사용하여 실행 할 수 있도록 한다.

- `scripts/merge-wbs-status.py` 무한루프 버그 수정 — `_diff3_hunks()`의 외곽 `while i <= n` 루프가 base 끝(`i == n`) 위치에 ours/theirs 양쪽 trailing insert가 있을 때 `i`를 증가시키지 못해 `hunks` 리스트에 동일 청크를 무한 append → 메모리 폭증. 실측: `git merge --no-ff dev/WP-01-monitor-v5` 중 PID 8818이 31% CPU·physical footprint 29 GB·8분간 `.git/index.lock` 점유로 시스템 전체 멈춤. 수정안: changed 분기 내부에 "i가 진전되지 않았으면 break 또는 i+=1" 가드 추가 + `_lcs_matrix` 사이즈 한도(혹은 `difflib.SequenceMatcher` 대체) 검토. 회귀 방지: trailing-insert 양쪽 시나리오 단위 테스트 추가.
- 모니터 성능 최적화 — 단일 monitor 페이지가 GPU 38%·WindowServer 18%·Terminal 14%·monitor 폴링 10.6 req/s를 잡아먹음 (브라우저 탭 닫으면 GPU 0%·폴링 0/s로 즉시 회수). 원인: `/api/graph` 폴링이 ~100ms 간격 + 매 폴링마다 SVG 전체 재구성으로 추정. 개선 방향: ① 폴링 주기 5~10초로 늘리거나 SSE/WebSocket push 전환, ② 그래프 diff 갱신(변경 노드만 업데이트), ③ `document.visibilityState === 'hidden'`이면 폴링 정지·감속, ④ `/api/graph` ETag/304 캐싱으로 미변경 시 redraw 스킵, ⑤ `monitor-server.py(~5600줄)` 인라인 HTML/CSS/JS의 `will-change`·`transform: translateZ(0)` 등 GPU 레이어 남용 감사. 회귀 방지: 폴링 빈도·GPU util 회귀 테스트(헤드리스 브라우저로 1분 측정).
- 내부 시그널·서버 측 부하 요소 제거 (모니터 성능 보강) — 코드 감사 결과 서버측 비용이 클라이언트 폴링과 곱셈으로 작용하는 핫스팟 다수 발견. (a) `monitor-server.py:4882` `/api/graph`가 명시적 "no in-memory caching" — 매 요청마다 `os.walk(claude-signals/)` + `glob(agent-pool-signals-*)` + `Path.glob("*/state.json")` 전수 스캔 + **`subprocess.run([sys.executable, dep-analysis.py, --graph-stats])` 새 Python 인터프리터 fork**. 10.6 req/s × 콜드 스타트 ~80–150ms = 단일 페이지가 코어 1개 거의 점유. `ThreadingHTTPServer`(line 6080)라 동시 다중 탭이면 fork도 N배. (b) `scan_signals()`(line 249)는 캐시 없이 매번 전체 트리 `os.walk` — 시그널 파일 5개여도 전 프로젝트 dir stat. (c) 대시보드 HTML이 `--refresh-seconds default=3`(line 6113) meta-refresh로 **3초마다 풀 페이지 리로드** + JS가 별도로 `/api/graph` 폴링 → 이중 부하. (d) `signal-helper.py wait-running`은 2초 폴링(`signal-helper.py:197`) — dev-team 워커 16개 동시면 8 stat/s. (e) `leader-watchdog.py`는 WP당 1개 데몬이 30초마다 `tmux display-message` + `tmux list-windows` 2회 호출 — WP 4개면 tmux 서버에 분당 16회. 개선 우선순위: ① `/api/graph` 1초 TTL 메모이즈 + ETag/304(앞 항목 ④와 한 PR), ② `dep-analysis.py`를 subprocess가 아닌 `import`로 인프로세스 호출(이미 `sys.pycache_prefix` 설정해 둔 흔적 있음 — `monitor-server.py:34`), ③ `scan_signals()` 1초 TTL 메모이즈, ④ meta-refresh 제거 후 JS 단일 폴링으로 일원화, ⑤ watchdog tmux 호출을 `list-windows -F "#{window_name}|#{pane_dead}"` 한 번으로 통합. 주의: `dev/WP-02-monitor-v5` 머지가 `monitor-server.py`를 `monitor_server/` 패키지로 분리 중(현재 unmerged) — 머지 마무리하면서 위 캐시·디바운스를 같이 넣지 않으면 분리된 코드가 동일 핫스팟을 그대로 이관. 회귀 방지: `/api/graph` p95 응답시간 + subprocess fork 횟수/분 메트릭 노출 + 헤드리스 1분 측정에 추가.