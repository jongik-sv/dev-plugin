# PRD — dev-plugin 웹 모니터링 도구

**문서 버전:** 0.1 (초안)
**작성일:** 2026-04-20
**대상 플러그인:** `dev` (dev-plugin)
**상태:** Draft

---

## 1. 배경 및 문제 정의

`dev-plugin`의 스킬(`/dev`, `/feat`, `/dev-team`, `/team-mode`, `/agent-pool`)은 WBS 기반·Feature 기반 TDD 개발 사이클을 자동화한다. 작업이 진행되는 동안 발생하는 상태 정보는 이미 파일로 존재한다:

- **상태 파일**: `docs/tasks/{TSK-ID}/state.json`, `docs/features/{name}/state.json`
- **시그널 파일**: `${TMPDIR}/claude-signals/{PROJECT}/*.running|*.done|*.failed|*.bypassed`
- **팀 에이전트 실시간 출력**: tmux window/pane
- **서브에이전트 진행 상태**: `${TMPDIR}/agent-pool-signals-*/` 내 슬롯 시그널

그러나 현재 사용자는 이 정보를 **파편화된 파일과 tmux 창을 직접 순회**하며 확인해야 하며, 다음의 불편이 있다:

1. WP 다수가 병렬로 도는 `/dev-team` 실행 중 전체 진행률을 한 눈에 볼 수 없다.
2. 어떤 Task가 현재 `[dd]/[im]/[ts]/[xx]` 중 어느 phase에 있는지, 재시도·에스컬레이션이 몇 번 일어났는지 파악하려면 state.json을 일일이 열어야 한다.
3. 팀 에이전트(tmux pane)의 실시간 출력은 tmux 창을 직접 띄워야만 확인 가능하며, 원격/브라우저 뷰가 불가능하다.
4. 서브에이전트(agent-pool)의 슬롯 점유 상태 역시 시그널 디렉터리를 수동 스캔해야 한다.

## 2. 목표

**하나의 슬래시 커맨드로 로컬 웹 대시보드를 기동**하여, 브라우저에서 dev-plugin 작업의 진행 상황·phase 이력·tmux pane 실시간 출력을 통합 모니터링한다.

### 2.1 Success Criteria

- [ ] `python3` 외 **추가 설치 0건** (pip 패키지·프론트엔드 빌드 없음)
- [ ] 스킬 실행 중 **LLM 토큰 소비 0** (서버는 순수 Python 프로세스, Claude는 최초 기동 시 1회만 호출)
- [ ] **단일 명령 1초 이내**에 HTTP 서버 기동 + 접속 URL 출력
- [ ] 주요 화면 3종(대시보드 / WP 상세 / pane 출력)에서 수동 새로고침 없이 진행 상황 갱신
- [ ] macOS / Linux / WSL2 / Windows(psmux) 네 환경에서 동일 동작

### 2.2 Non-Goals

- 서브에이전트(agent-pool의 Agent tool 기반 워커)의 **대화 내용 캡처** — 부모 Claude 세션 내부에서 실행되므로 외부에서 stdout 캡처 불가. 시그널 상태만 제공한다.
- 원격 접속 / 인증 / HTTPS — **localhost 전용**.
- 과거 이력 아카이빙·차트화·알림 — 현재 상태 스냅샷에만 집중한다.
- 사용자 조작(작업 재시작·중단 등)을 대시보드에서 수행하는 기능 — **읽기 전용**.

## 3. 사용자 및 시나리오

### 3.1 Primary User

`/dev-team` 또는 `/feat`을 실행해놓고 장시간 실행되는 병렬 개발을 감독하는 개발자.

### 3.2 주요 시나리오

**S1. 전체 진행률 확인**
사용자가 `/dev-team WP-01`로 5개 Task 병렬 개발을 시작 → 별도 터미널에서 `/dev-monitor` → 브라우저에서 각 Task의 현재 phase와 완료 개수 확인.

**S2. 실패 원인 추적**
어떤 Task가 `[ts]` phase에서 실패했을 때, 대시보드에서 해당 WP의 tmux pane 출력을 클릭하여 최근 500라인 확인 → 재시도(Sonnet→Opus 에스컬레이션) 이력을 `phase_history` 섹션에서 확인.

**S3. Bypass 발생 확인**
MAX_ESCALATION 초과로 bypass 처리된 Task를 대시보드에서 🟡 아이콘으로 식별 → `bypassed_reason` 필드와 함께 표시.

## 4. 기능 요구사항

### 4.1 기동 인터페이스

- **슬래시 커맨드**: `/dev-monitor [--port PORT] [--docs DIR]`
  - `--port`: 기본 `7321`
  - `--docs`: 기본 `docs` (대상 프로젝트의 docs 루트)
- 커맨드 실행 시 동작:
  1. `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/monitor-server.py` 를 백그라운드로 기동 (detach)
  2. `http://localhost:{PORT}` URL을 사용자에게 출력
  3. 이미 같은 포트에서 기동 중이면 기존 프로세스 재사용 안내
- **종료**: 별도 커맨드 없이 프로세스 kill (PID 파일 `${TMPDIR}/dev-monitor-{port}.pid`)

### 4.2 데이터 소스 및 스캔 규칙

| 소스 | 경로 | 스캔 주기 |
|------|------|-----------|
| WBS Task 상태 | `{docs}/tasks/*/state.json` | HTTP 요청 시 on-demand |
| Feature 상태 | `{docs}/features/*/state.json` | HTTP 요청 시 on-demand |
| 공유 시그널 | `${TMPDIR}/claude-signals/{PROJECT}/*` | HTTP 요청 시 on-demand |
| Agent-pool 시그널 | `${TMPDIR}/agent-pool-signals-*/*` | HTTP 요청 시 on-demand |
| tmux/psmux pane 목록 | `tmux list-panes -a -F ...` | HTTP 요청 시 on-demand |
| tmux/psmux pane 출력 | `tmux capture-pane -t {id} -p -S -500` | pane 상세 요청 시만 |

**원칙**: 서버는 상태를 메모리에 보관하지 않는다. 매 HTTP 요청마다 파일·tmux를 새로 읽어 렌더링하여 **데이터 불일치 리스크를 제거**한다.

### 4.3 HTTP 엔드포인트

| 메서드 | 경로 | 응답 | 용도 |
|--------|------|------|------|
| GET | `/` | HTML | 메인 대시보드 (Task/Feature 트리 + 시그널 요약) |
| GET | `/api/state` | JSON | 프로그램 연동용 전체 스냅샷 |
| GET | `/pane/{pane_id}` | HTML(`<pre>`) | 지정 tmux pane의 최근 500라인 캡처 |
| GET | `/api/pane/{pane_id}` | JSON `{lines, captured_at}` | pane 캡처 JSON 버전 |

### 4.4 대시보드 UI

- **단일 HTML 페이지**, 인라인 CSS, 의존 프레임워크 0건
- `<meta http-equiv="refresh" content="3">` 로 3초마다 전체 갱신 (pane 상세 영역은 2초 fetch)
- 섹션 구성:
  1. **헤더**: 프로젝트명·기동 시각·스캔 대상 경로
  2. **WBS 섹션**: Task 트리 (WP → Task). 각 Task 행에 상태 배지, 경과 시간, 재시도 카운트, bypass 아이콘
  3. **Feature 섹션**: 동일 포맷
  4. **Team 에이전트 섹션**: tmux window 목록 (WP 이름으로 필터) → 펼치면 pane 리스트 → 각 pane "show output" 버튼
  5. **Subagent 섹션**: agent-pool 슬롯별 상태 (running / done / failed) + 현재 task ID. "외부 캡처 불가" 안내 문구 명시
  6. **phase_history 최근 N건** (기본 10건): bypass·에스컬레이션 흔적을 한 눈에

### 4.5 상태 표시 규칙

| 상태 | 배지 | 색상 |
|------|------|------|
| `[dd]` Design 완료 | 🔵 DESIGN | blue |
| `[im]` Build 완료 | 🟣 BUILD | purple |
| `[ts]` Test 완료 | 🟢 TEST | green |
| `[xx]` Refactor 완료 | ✅ DONE | gray |
| `.running` 시그널 존재 | 🟠 RUNNING | orange (pulse) |
| `.failed` 시그널 존재 | 🔴 FAILED | red |
| `bypassed: true` | 🟡 BYPASSED | yellow |

## 5. 비기능 요구사항

### 5.1 Constraints

- **언어/런타임**: Python 3.8+ 표준 라이브러리만 (`http.server`, `json`, `subprocess`, `pathlib`, `urllib`)
- **의존성**: pip 패키지 금지. 기존 플러그인 관례 준수 (`CLAUDE.md` → "Python 3 standard library only — no pip dependencies")
- **토큰 소비**: 최초 기동 명령 외 Claude 호출 없음. 이후 모든 갱신은 브라우저 ↔ 로컬 HTTP 서버 간에만 발생.
- **파일 I/O**: 읽기 전용. 어떤 state.json·wbs.md·signal 파일도 수정·삭제하지 않는다.

### 5.2 플랫폼 호환성

- tmux pane 캡처는 `scripts/_platform.py` 를 통해 tmux/psmux 공통 경로 처리
- 임시 디렉터리는 `tempfile.gettempdir()` 결과 사용 (macOS `$TMPDIR`, Linux `/tmp`, Windows `%TEMP%`)
- Windows 환경에서는 `sys.executable` 사용, `python3` 하드코딩 금지

### 5.3 실패 모드

| 상황 | 동작 |
|------|------|
| tmux 미설치 | Team 에이전트 섹션에 "tmux not available" 안내, 다른 섹션은 정상 |
| state.json JSON 파싱 실패 | 해당 Task만 ⚠️ 로 표시 후 raw 내용 링크 |
| 포트 충돌 | 기동 실패 메시지 + `--port` 옵션 안내 |
| pane 캡처 실패 | "capture failed: {stderr}" 표시, 대시보드는 계속 동작 |

## 6. 파일 구조 변경안

```
dev-plugin/
├── scripts/
│   └── monitor-server.py          # 신규 — 단일 파일 HTTP 서버 (~300 LOC)
└── skills/
    └── dev-monitor/                # 신규 스킬 디렉터리
        └── SKILL.md                # /dev-monitor 커맨드 정의
```

추가 수정:
- `.claude-plugin/plugin.json`: 스킬 목록에 `dev-monitor` 추가
- `README.md`: 스킬 테이블에 `/dev-monitor` 한 줄 추가
- `CLAUDE.md` 헬퍼 스크립트 테이블에 `monitor-server.py` 항목 추가

## 7. 구현 단계 (제안)

1. **P1** — `scripts/monitor-server.py` 단일 파일 작성
   - `/`, `/api/state`, `/pane/{id}`, `/api/pane/{id}` 네 엔드포인트
   - 데이터 수집 함수: `scan_tasks()`, `scan_features()`, `scan_signals()`, `list_tmux_panes()`, `capture_pane()`
   - HTML 렌더링: 인라인 CSS + 자동 새로고침
2. **P2** — `skills/dev-monitor/SKILL.md` 작성
   - `$ARGUMENTS` 파싱 (`--port`, `--docs`)
   - 백그라운드 기동 + PID 파일 관리 + 중복 기동 방지
3. **P3** — 문서 갱신 (`README.md`, `CLAUDE.md`, `plugin.json`)
4. **P4** — 수동 QA
   - `/dev-team` 실행 중 대시보드 열어 모든 섹션 동작 확인
   - `/feat`, `/agent-pool` 각각 단독 실행 시나리오 확인
   - Windows(psmux) 환경에서 pane 캡처 동작 확인

## 8. 열린 질문 / 의사결정 필요

- [ ] 대시보드 자동 새로고침 간격 기본값: 3초 vs 5초
- [ ] pane 캡처 라인 수 기본값: 500 vs 1000
- [ ] `/dev-monitor` 종료 명령(`/dev-monitor stop`)을 스킬로 제공할지, 사용자가 직접 `kill` 할지
- [ ] `/api/state` 응답에 최근 `phase_history` 엔트리를 몇 개까지 포함할지 (기본 10)
- [ ] 다중 프로젝트 지원 여부 — 초기엔 **단일 프로젝트(현재 CWD)** 만 지원, 여러 프로젝트 감시는 추후 과제

## 9. 참고

- 플러그인 루트: `/Users/jji/project/dev-plugin`
- 상태 머신 정의: `references/state-machine.json`
- 시그널 프로토콜: `references/signal-protocol.md`
- 플랫폼 유틸: `scripts/_platform.py`
