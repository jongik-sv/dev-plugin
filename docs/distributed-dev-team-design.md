# Distributed Dev-Team 설계

> 여러 머신에서 `/dev-team`의 WP를 분산 실행하여 개발 속도를 높인다.

## 핵심 원칙

- Python stdlib만 사용 (기존 원칙 유지)
- 기존 로컬 dev-team 로직 변경 최소화
- **HTTP 시그널 서버 + 주기적 싱크**로 머신 간 통신
- SSH는 워커 실행 시 **1회성**으로만 사용 (지속 연결 아님)

---

## 토폴로지

```
                    ┌─────────────────────────┐
                    │     Master Machine      │
                    │                         │
                    │  signal-server.py :9876  │◄── 프로젝트별 시그널 저장소
                    │  distributed-coord.py   │◄── WP 분배 + SSH 실행 + 모니터링 + 머지
                    │                         │
                    └────┬──────┬──────┬──────┘
                 SSH(1회) │      │      │
            ┌────────────┘      │      └────────────┐
            ▼                   ▼                    ▼
   ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
   │   Worker A      │ │   Worker B      │ │   Worker C      │
   │                 │ │                 │ │                 │
   │ signal-sync.py  │ │ signal-sync.py  │ │ signal-sync.py  │
   │   (daemon)      │ │   (daemon)      │ │   (daemon)      │
   │                 │ │                 │ │                 │
   │ tmux: dev-team  │ │ tmux: dev-team  │ │ tmux: dev-team  │
   │  (동적 할당)     │ │  (동적 할당)     │ │  (동적 할당)     │
   └─────────────────┘ └─────────────────┘ └─────────────────┘
         │ ▲                 │ ▲                 │ ▲
         └─┼── HTTP GET/POST ─┼─────────────────┼─┘
           └────── to Master ──┘                 │
                signal-server ◄──────────────────┘
```

**통신 방향 정리:**
- Master → Worker: SSH (1회, 실행 시에만)
- Worker → Master: HTTP (주기적 시그널 싱크)
- Worker ↔ Worker: **직접 통신 없음** (모든 시그널은 Master 경유)

**Master도 워커가 될 수 있다.** Master 머신에서 signal-server.py를 실행하면서 동시에 signal-sync.py + dev-team을 띄우면 된다. sync 대상이 `localhost:9876`이 되어 네트워크 지연 없이 동작하며, SSH 접속도 불필요하다. config의 workers 목록에 `"host": "localhost"`로 추가하면 코디네이터가 SSH 대신 로컬 실행으로 분기한다.

---

## 컴포넌트

### 1. signal-server.py (Master)

프로젝트별 시그널 저장 + **WP 동적 할당**을 담당하는 경량 HTTP 서버.

```python
# 자료구조
projects = {
    "my-app": {
        # 시그널 저장소
        "signals": {
            "TSK-01-01": {"event": "done", "machine": "worker-a", "at": "...", "message": "..."},
            "TSK-01-03": {"event": "failed", "machine": "worker-a", "at": "...", "message": "..."},
        },

        # WP 할당 큐
        "wp_queue": ["WP-03", "WP-04", "WP-05"],          # 아직 할당 안 된 WP
        "wp_assigned": {                                     # 현재 할당 중
            "WP-01": {"worker": "master",   "assigned_at": "..."},
            "WP-02": {"worker": "worker-a", "assigned_at": "..."},
        },
        "wp_completed": {                                    # 완료된 WP
            # "WP-01": {"worker": "master", "completed_at": "..."}
        },

        # 워커 상태
        "workers": {
            "master":   {"last_heartbeat": "...", "current_wp": "WP-01"},
            "worker-a": {"last_heartbeat": "...", "current_wp": "WP-02"},
            "worker-b": {"last_heartbeat": "...", "current_wp": null},
        },
    }
}
```

**API:**

| Method | Path | 설명 |
|--------|------|------|
| `POST` | `/api/{project}/signal` | 시그널 등록 |
| `GET` | `/api/{project}/signals` | 프로젝트 전체 시그널 조회 |
| `GET` | `/api/{project}/status` | 진행 현황 (워커별 상태 + 큐 상태) |
| `POST` | `/api/{project}/register` | 워커 등록 |
| `POST` | `/api/{project}/heartbeat` | 워커 생존 신호 |
| `GET` | `/api/{project}/assign/{worker}` | **다음 WP 할당 요청** |
| `POST` | `/api/{project}/complete/{wp-id}` | **WP 완료 보고 → 다음 WP 자동 할당** |

**GET /api/{project}/assign/{worker}** — 워커가 다음 할 일을 요청
```json
// Response (할당 가능)
{"wp": "WP-03", "tasks": ["TSK-03-01", "TSK-03-02", "TSK-03-03"]}

// Response (남은 WP 없음)
{"wp": null, "reason": "all_assigned"}

// Response (전부 완료)
{"wp": null, "reason": "all_done"}
```

서버는 `wp_queue`에서 하나를 꺼내 해당 워커에 할당하고, `wp_assigned`로 이동시킨다. 의존성 순서(`dep-analysis.py` 결과)를 고려하여 현재 실행 가능한 WP만 할당한다.

**POST /api/{project}/complete/{wp-id}** — WP 완료 보고
```json
// Request
{"worker": "worker-a"}

// Response (다음 WP 있음)
{"ok": true, "next": {"wp": "WP-04", "tasks": ["TSK-04-01", "TSK-04-02"]}}

// Response (더 없음)
{"ok": true, "next": null}
```

`wp_assigned` → `wp_completed`로 이동시키고, 큐에 남은 WP가 있으면 바로 할당하여 응답에 포함한다.

**POST /api/{project}/signal**
```json
// Request
{"id": "TSK-01-03", "event": "done", "machine": "worker-a", "message": "test: 5/5, commit: abc123"}

// Response
{"ok": true}
```

**GET /api/{project}/signals**
```json
// Response
{
  "TSK-01-01": {"event": "done", "machine": "worker-a", "at": "..."},
  "TSK-01-03": {"event": "done", "machine": "worker-a", "at": "..."},
  "TSK-02-01": {"event": "failed", "machine": "worker-b", "at": "..."}
}
```

**GET /api/{project}/status**
```json
// Response
{
  "workers": {
    "master":   {"current_wp": "WP-01", "completed": ["WP-03"], "last_heartbeat": "...", "alive": true},
    "worker-a": {"current_wp": "WP-02", "completed": [],        "last_heartbeat": "...", "alive": true},
    "worker-b": {"current_wp": null,    "completed": [],        "last_heartbeat": "...", "alive": true}
  },
  "queue": {"pending": ["WP-04", "WP-05"], "assigned": ["WP-01", "WP-02"], "completed": ["WP-03"]},
  "signals": {"TSK-01-01": {"event": "done", ...}, ...},
  "progress": {"done": 5, "failed": 1, "bypassed": 0, "total": 15}
}
```

**특성:**
- `http.server` + `threading` 기반, stdlib만 사용
- 인메모리 저장 (재시작 시 유실) + 선택적 JSON 파일 백업 (`--persist state.json`)
- 포트 1개만 사용 (기본 9876)
- WP 큐에 대한 접근은 `threading.Lock`으로 보호 (동시 할당 요청 시 중복 방지)

---

### 2. signal-sync.py (Worker)

로컬 시그널 디렉토리 ↔ Master HTTP 서버 간 **양방향 주기적 싱크** 데몬.

```
signal-sync.py --server http://master:9876 --project my-app --signal-dir /tmp/claude-signals/my-app --interval 10
```

**싱크 루프 (매 interval초):**

```
┌─ Upload (로컬 → 서버) ────────────────────────────────────┐
│ 1. 로컬 시그널 디렉토리 스캔                                │
│ 2. 새로운 .done / .failed / .bypassed 파일 감지            │
│ 3. POST /api/{project}/signal 로 서버에 등록               │
│ 4. 업로드 완료 마커 기록 (중복 방지)                         │
└───────────────────────────────────────────────────────────┘

┌─ Download (서버 → 로컬) ──────────────────────────────────┐
│ 1. GET /api/{project}/signals 로 전체 시그널 목록 조회      │
│ 2. 로컬에 없는 시그널 파일을 로컬 디렉토리에 생성            │
│    (기존 signal-helper.py와 동일한 파일 형식)               │
│ 3. 자기 머신이 생성한 시그널은 스킵 (이미 로컬에 있음)       │
└───────────────────────────────────────────────────────────┘
```

**핵심: 기존 signal-helper.py는 변경 없음.** sync가 어댑터 역할을 하여, 로컬 DDTR 로직은 분산 실행인지 로컬 실행인지 모른다.

**중복 방지:**
- 업로드: `.synced` 마커 파일 또는 내부 set으로 이미 올린 시그널 추적
- 다운로드: 로컬 파일 존재 여부로 판단 (이미 있으면 스킵)

**장애 내성:**
- 서버 연결 실패 시 경고 로그 + 다음 주기에 재시도
- 로컬 작업은 서버 장애와 무관하게 계속 진행 (의존 없는 Task)
- 서버 복구 시 밀린 시그널 자동 동기화

---

### 워커 루프 (각 워커의 실행 흐름)

워커는 tmux 세션 안에서 **할당 → 실행 → 완료 → 다음 할당** 루프를 반복한다.

```
워커 시작 (tmux 세션 내)
  │
  ├─ signal-sync.py 백그라운드 시작
  │
  └─ 루프:
      ├─ GET /api/{project}/assign/{worker-name}
      │   ├─ wp: "WP-03" → 할당 받음
      │   └─ wp: null     → 할 일 없음 → 종료
      │
      ├─ git worktree 생성 + /dev-team {WP-ID} 실행
      │   (기존 로컬 dev-team 방식 그대로)
      │
      ├─ WP 완료
      │   ├─ git push origin dev/{WP-branch}
      │   └─ POST /api/{project}/complete/{WP-ID}
      │       ├─ next: "WP-05" → 루프 계속
      │       └─ next: null    → 루프 종료
      │
      └─ 반복
```

빨리 끝나는 워커가 자동으로 다음 WP를 가져가므로, 구독 여유가 많은 계정이 자연스럽게 더 많은 일을 처리한다.

---

### 3. distributed-coord.py (Master)

전체 분산 실행을 오케스트레이션하는 코디네이터.

**실행 순서:**

```
Phase 1: 준비
  ├─ WBS 분석 (wbs-parse.py) → 전체 WP 목록 + Task 의존성
  ├─ signal-server.py 시작 (백그라운드)
  └─ 서버에 WP 큐 등록 (전체 WP를 의존성 순서대로 enqueue)

Phase 2: 워커 실행
  └─ 각 워커 머신에 대해:
      ├─ host=localhost → SSH 생략, 로컬에서 직접 실행
      ├─ host=원격     → SSH 접속 → git clone/pull
      ├─ signal-sync.py 시작 (백그라운드 데몬)
      ├─ tmux 세션 생성: `tmux new -d -s {worker-name}`
      │   (이미 존재하면 resume — `tmux has-session -t {worker-name}`)
      └─ 세션 내에서 워커 루프 시작 (할당 → 실행 → 완료 → 다음 할당)

Phase 3: 모니터링
  └─ 주기적으로:
      ├─ GET /api/{project}/status 조회 (큐 상태 + 시그널 기반 진행률)
      ├─ SSH → `tmux has-session -t {worker-name}` (세션 생존 확인)
      ├─ 워커 장애 감지 시 해당 WP를 큐에 반환
      └─ 완료된 WP는 early merge 트리거

Phase 4: 머지 + 정리
  ├─ 각 워커의 WP 브랜치를 remote에서 pull
  ├─ 순차 merge (충돌 시 수동 개입 안내)
  ├─ SSH → `tmux kill-session -t {worker-name}` (세션 정리)
  └─ 워커 signal-sync 종료
```

---

## 시그널 흐름 (Cross-WP 의존성)

```
시나리오: Worker B의 TSK-03-01이 Worker A의 TSK-01-03에 의존

Worker A                          Master                          Worker B
─────────                         ──────                          ─────────
TSK-01-03 완료
  │
  ├─ signal-helper.py done
  │   → /tmp/.../TSK-01-03.done (로컬)
  │
  ├─ signal-sync.py (다음 주기)
  │   → POST /api/my-app/signal
  │     {id: TSK-01-03, event: done}
  │                                 │
  │                                 ├─ 시그널 저장
  │                                 │
  │                                 │                signal-sync.py (다음 주기)
  │                                 │                  → GET /api/my-app/signals
  │                                 │◄─────────────────│
  │                                 │                  │
  │                                 │──────────────────►
  │                                 │  {TSK-01-03: done, ...}
  │                                 │                  │
  │                                 │          로컬에 TSK-01-03.done 없음 감지
  │                                 │            → touch /tmp/.../TSK-01-03.done
  │                                 │                  │
  │                                 │          signal-helper.py wait 감지!
  │                                 │            → TSK-03-01 실행 시작
```

**최대 지연**: sync interval × 2 (업로드 1주기 + 다운로드 1주기)
- interval=10초 → 최대 20초 지연
- DDTR 사이클 대비 무시할 수 있는 수준

---

## 설정

### distributed-config.json

```json
{
  "project_id": "my-app",
  "wbs_path": "docs/wbs.md",
  "docs_dir": "docs",
  "git_remote": "origin",

  "signal_server": {
    "port": 9876,
    "persist": true
  },

  "sync_interval": 10,

  "workers": [
    {
      "name": "master",
      "host": "localhost",
      "team_size": 3,
      "repo_path": "~/project/my-app"
    },
    {
      "name": "worker-a",
      "host": "192.168.1.101",
      "user": "dev",
      "ssh_key": "~/.ssh/id_ed25519",
      "team_size": 3,
      "repo_path": "~/project/my-app"
    },
    {
      "name": "worker-b",
      "host": "192.168.1.102",
      "user": "dev",
      "team_size": 2,
      "repo_path": "~/project/my-app"
    }
  ],

  "merge": {
    "strategy": "sequential",
    "early_merge": true
  }
}
```

**분산 실행의 핵심 동기:** 서로 다른 Claude 구독 계정(Max 등)을 병렬로 활용하여 단일 계정의 rate limit/용량 한계를 넘기는 것. 각 워커 = 각각의 구독 계정.

**필수 전제 (사람이 직접):**
- Master → Worker SSH 접속 가능 (키 기반, 비밀번호 없음)
- 각 워커 → Master HTTP 접속 가능 (포트 1개)
- **각 워커에 고유한 Claude 구독 계정으로 `claude login` 완료** (계정 공유 아님)
- 공유 git remote (GitHub/GitLab 등) + 각 머신에서 접근 가능

**자동화 가능 (worker-bootstrap.py):**
- Python 3, git, tmux 설치
- git clone / git pull
- dev plugin 설치

---

## 워커 부트스트랩

### worker-bootstrap.py (Master에서 실행)

SSH만 설정되어 있으면 나머지를 자동으로 준비하는 스크립트.

```
python3 scripts/worker-bootstrap.py distributed-config.json
```

**워커별 처리 흐름:**

```
1. SSH 접속 테스트
   └─ 실패 시 해당 워커 스킵 + 에러 리포트

2. OS / 패키지 매니저 감지
   ├─ uname -s → Linux / Darwin
   ├─ Linux: apt (Debian/Ubuntu) / yum (RHEL/CentOS) / pacman (Arch)
   └─ Darwin: brew

3. 필수 소프트웨어 설치 (없는 것만)
   ├─ python3  → apt install python3 / brew install python3 / ...
   ├─ git      → apt install git / ...
   └─ tmux     → apt install tmux / ...

4. claude CLI 확인 (설치 + 구독 계정 로그인은 사람이 사전에 완료)
   ├─ which claude → 없으면 에러 + 해당 워커 스킵
   ├─ claude --version → 버전 기록
   └─ 인증 안 됨 → 에러 리포트 ("해당 머신에서 claude login 필요")

5. 프로젝트 repo
   ├─ repo_path 존재? → git pull
   └─ 없음? → git clone {git_remote} {repo_path}

7. dev plugin 설치
   └─ claude '/plugin install dev@dev-tools' (또는 로컬 경로)

8. 준비 완료 확인
   └─ 체크리스트 출력:
      ✅ python3 3.11.2
      ✅ git 2.43.0
      ✅ tmux 3.4
      ✅ claude 1.2.3 (구독 계정: user-a@example.com)
      ✅ repo ~/project/my-app (branch: main, clean)
      ✅ dev plugin installed
```

### 설정 파일 확장

```json
{
  "workers": [
    {
      "name": "worker-a",
      "host": "192.168.1.101",
      "user": "dev",
      "ssh_key": "~/.ssh/id_ed25519",
      "team_size": 3,
      "repo_path": "~/project/my-app",
      "git_clone_url": "git@github.com:org/my-app.git"
    }
  ]
}
```

`git_clone_url`은 워커에 repo가 없을 때 자동 clone에 사용. 이미 있으면 `git pull`만 수행.

### Claude 인증 전략

**각 워커 = 각각의 Claude 구독 계정.** 분산 실행의 목적이 여러 구독의 용량을 병렬 활용하는 것이므로, 인증은 공유하지 않는다.

각 워커 머신에서 사람이 직접 `claude login`을 1회 수행한다. OAuth 토큰은 macOS Keychain(`Claude Safe Storage`)에 저장되며 머신/계정에 바인딩되어 복사 불가.

**bootstrap에서의 처리:**
1. `which claude` → 설치 여부 확인
2. `claude --version` → 버전 확인
3. 인증 안 됨 → 에러 리포트 (사람이 직접 해결)

```
⚠️ worker-a: claude 인증 안 됨
   → 해당 머신에서 직접 실행: claude login
   → 사용할 구독 계정으로 로그인
```

### 사람이 반드시 직접 해야 하는 것

| 항목 | 이유 | 시점 |
|------|------|------|
| Worker SSH 설정 | 보안 — 키 교환은 수동 확인 필요 | 최초 1회 |
| Git remote 인증 | SSH key 또는 token, 머신별 설정 | 최초 1회 |
| `claude login` | 워커마다 고유 구독 계정으로 인증 | 최초 1회 |

이 세 가지만 각 워커에서 1회 설정하면, `worker-bootstrap.py`가 소프트웨어 설치 + repo 준비 + 플러그인 설치를 전부 자동 처리한다.

---

## 기존 코드 변경 범위

### 변경 없음

| 파일 | 이유 |
|------|------|
| `signal-helper.py` | sync가 어댑터 역할, 로컬 파일 인터페이스 유지 |
| `wbs-transition.py` | state.json은 각 워커 로컬에서 관리 |
| `wbs-parse.py` | WBS 파싱 로직 불변 |
| `dep-analysis.py` | 의존성 분석 로직 불변 |
| `dev-design/build/test/refactor` | DDTR 스킬 불변 |
| `team-mode`, `agent-pool` | 로컬 병렬 엔진 불변 |

### 변경

| 파일 | 변경 내용 |
|------|----------|
| `dev-team SKILL.md` | `--distributed config.json` 모드 분기 추가 |
| `wp-setup.py` | 원격 워커용 설정 생성 옵션 (선택적) |

### 신규

| 파일 | 역할 |
|------|------|
| `scripts/signal-server.py` | HTTP 시그널 서버 + WP 큐 관리 (Master) |
| `scripts/signal-sync.py` | 양방향 시그널 싱크 데몬 (Worker) |
| `scripts/worker-loop.py` | 할당 → 실행 → 완료 → 다음 할당 루프 (Worker) |
| `scripts/distributed-coord.py` | 분산 코디네이터 (Master) |
| `scripts/worker-bootstrap.py` | 워커 자동 환경 구성 (Master에서 실행) |

---

## tmux 세션 관리

### 명명 규칙

각 워커의 tmux 세션은 **워커 이름**으로 생성한다. 코디네이터가 SSH로 워커를 찾고 관리하는 유일한 핸들이다.

```
세션 이름: {worker-name}      예: worker-a, worker-b, master
```

### 라이프사이클

```
┌─ 실행 ─────────────────────────────────────────────────────┐
│ # 코디네이터가 SSH로 실행                                    │
│ ssh dev@192.168.1.101 "                                     │
│   tmux has-session -t worker-a 2>/dev/null && \             │
│     echo 'RESUME: session exists' || \                      │
│     tmux new -d -s worker-a                                 │
│ "                                                           │
│                                                             │
│ # 세션 내에서 signal-sync + 워커 루프 실행                    │
│ ssh dev@192.168.1.101 "                                     │
│   tmux send-keys -t worker-a \                              │
│     'python3 scripts/signal-sync.py ... &' Enter            │
│ "                                                           │
│ ssh dev@192.168.1.101 "                                     │
│   tmux send-keys -t worker-a \                              │
│     'cd ~/project/my-app && python3 scripts/worker-loop.py \│
│      --server http://master:9876 --project my-app \         │
│      --worker worker-a' Enter                               │
│ "                                                           │
│ # worker-loop.py가 서버에서 WP를 할당받아 dev-team 실행,     │
│ # 완료 후 다음 WP 요청을 반복한다                              │
└─────────────────────────────────────────────────────────────┘

┌─ 상태 확인 ─────────────────────────────────────────────────┐
│ # 세션 존재 여부 (생존 확인)                                  │
│ ssh dev@192.168.1.101 "tmux has-session -t worker-a"        │
│   → exit 0: 살아 있음                                        │
│   → exit 1: 세션 없음 (죽었거나 완료됨)                       │
│                                                             │
│ # 현재 세션 내용 캡처 (디버깅용)                               │
│ ssh dev@192.168.1.101 "tmux capture-pane -t worker-a -p"    │
└─────────────────────────────────────────────────────────────┘

┌─ 정리 ─────────────────────────────────────────────────────┐
│ # 완료 후 세션 종료                                          │
│ ssh dev@192.168.1.101 "tmux kill-session -t worker-a"       │
└─────────────────────────────────────────────────────────────┘
```

### localhost (Master = Worker)

Master 자신이 워커인 경우 SSH 없이 직접 tmux 명령 실행:

```bash
# Master 세션 안에서 새 세션을 detached로 생성
tmux new -d -s master
tmux send-keys -t master 'python3 scripts/signal-sync.py ... &' Enter
tmux send-keys -t master 'cd ~/project/my-app && claude ...' Enter
```

### Resume

코디네이터 재시작 시, 기존 워커 세션을 이름으로 찾아 상태를 복원한다:

```
각 워커에 대해:
  ssh {host} "tmux has-session -t {worker-name}"
  ├─ 존재 → 이미 실행 중, 시그널 서버에서 진행 상황 확인
  └─ 없음 → 시그널 서버의 마지막 상태로 판단
            ├─ WP 완료 시그널 있음 → 스킵
            └─ 미완료 → 세션 재생성 + dev-team 재실행 (state.json 기반 resume)
```

---

## 실행 예시

### Master에서 실행 (자동)

```bash
# 1. 설정 파일 준비
vi distributed-config.json

# 2. 분산 실행 시작
claude '/dev-team --distributed distributed-config.json'

# 내부적으로:
#   signal-server.py 시작 → :9876 + WP 큐 등록 (WP-01~WP-05)
#   tmux new -d -s master  → signal-sync + worker-loop (서버에서 WP 할당받아 실행)
#   ssh worker-a → tmux new -d -s worker-a → signal-sync + worker-loop
#   ssh worker-b → tmux new -d -s worker-b → signal-sync + worker-loop
#   모니터링 루프 시작
#
# 각 워커는 WP를 하나씩 받아 처리, 빨리 끝나는 워커가 다음 WP를 가져감
```

### 수동 실행 (코디네이터 없이)

```bash
# Master: 시그널 서버 + WP 큐 초기화
python3 scripts/signal-server.py --port 9876 --wbs docs/wbs.md

# Master: 워커로도 참여 (tmux 세션: master)
tmux new -d -s master
tmux send-keys -t master '
  python3 scripts/signal-sync.py \
    --server http://localhost:9876 --project my-app \
    --signal-dir /tmp/claude-signals/my-app --machine master --interval 10 &
  python3 scripts/worker-loop.py \
    --server http://localhost:9876 --project my-app --worker master
' Enter

# Worker A: SSH로 접속하여 세션 생성 (tmux 세션: worker-a)
ssh dev@192.168.1.101 "tmux new -d -s worker-a"
ssh dev@192.168.1.101 "tmux send-keys -t worker-a '
  python3 scripts/signal-sync.py \
    --server http://master:9876 --project my-app \
    --signal-dir /tmp/claude-signals/my-app --machine worker-a --interval 10 &
  python3 scripts/worker-loop.py \
    --server http://master:9876 --project my-app --worker worker-a
' Enter"

# 상태 확인
ssh dev@192.168.1.101 "tmux has-session -t worker-a"  # exit 0 = 실행 중
curl http://localhost:9876/api/my-app/status           # 전체 진행 현황
```

---

## 머지 전략

### Sequential Merge (기본)

```
각 워커: WP 완료 → git push origin dev/{WP-branch}

Master (early merge 또는 전체 완료 후):
  git fetch origin
  git merge origin/dev/WP-01   # 충돌 없으면 자동
  git merge origin/dev/WP-02   # 충돌 시 수동 개입 안내
  ...
```

### PR 기반 Merge (선택)

```
각 워커: WP 완료 → git push + gh pr create
Master: PR 리뷰 + merge
```

**WBS 충돌 회피:**
- WP 단위로 Task를 분리하므로 `docs/tasks/{TSK-ID}/` 경로가 겹치지 않음
- `wbs.md` status 변경은 각 워크트리 내에서만 발생 → 머지 시 diff 영역이 다름
- 공통 소스 파일 충돌은 WP 간 의존성 설계 시점에 최소화

---

## 에러 처리

| 상황 | 대응 |
|------|------|
| 워커 장애 (heartbeat 중단) | Master가 감지 → 해당 WP를 `wp_assigned`에서 `wp_queue`로 반환. 다른 워커가 자동으로 가져감 |
| Task 실패 | 기존 bypass 메커니즘 그대로. signal-sync가 `.failed`/`.bypassed`도 서버에 전파 |
| 네트워크 단절 | 로컬 작업 계속 진행. 의존 Task만 대기. 복구 시 밀린 시그널 자동 동기화 |
| 시그널 서버 재시작 | `--persist` 옵션으로 JSON 파일에 주기적 백업. 재시작 시 복원 |
| Git 충돌 | WP 단위 분리로 대부분 회피. 발생 시 Master에서 수동 해결 안내 |

---

## 향후 확장 (v2)

### 구독 사용량 모니터링

- 각 워커가 heartbeat에 구독 사용량 정보 포함 (남은 토큰/요청 수, rate limit 상태)
- 구독 한도 소진된 워커는 자동으로 할당 요청을 중단, 잔여 WP는 다른 워커가 가져감
- status 대시보드에서 계정별 사용량 시각화
- (현재 v1의 동적 할당으로 자연스러운 밸런싱은 이미 동작 — 빨리 끝나는 워커가 더 가져감)

### 시그널 서버 고도화

- WebSocket 업그레이드 (폴링 → push 전환, 지연 0)
- 여러 프로젝트 동시 지원 (이미 API가 프로젝트별이므로 자연스럽게 확장)
- 대시보드 UI (status 엔드포인트 기반)

### 보안

- 현재는 같은 네트워크(LAN/VPN) 가정
- 공용 인터넷 사용 시: HTTPS + API key 인증 추가
- signal-server.py에 `--auth-token` 옵션
