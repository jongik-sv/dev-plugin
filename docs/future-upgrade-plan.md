# 중장기 업그레이드 계획 — dev-plugin 분산 실행 레이어

> 이 문서는 **`/Users/jji/project/hani/docs/overlord-model-design.md`의 Phase 1.5 모델을 dev-plugin CLI로 실현하는 참조 구현**이다. hani가 조직 비유·PMT 엔티티·봇 역할의 SoT(Source of Truth)이고, 본 문서는 CLI 레이어(tmux·signal·git·DDTR)의 구현 설계만 담당한다. **hani 문서와 충돌 시 hani가 우선한다.**
>
> 두 축으로 구성:
> - **Part A — 실행 레이어**: PMT 실행 평면 + Office 안의 Overlord(= 1 프로젝트 전담 AI 팀원) / WP 리더 / 작업자를 dev-plugin 스크립트로 구현
> - **Part B — 분산 모니터링**: 여러 Office의 `/dev-monitor`를 통합 뷰로 집약 (hani SCR-31 §12.6 봇 상세 슬라이드 패널의 하위 데이터 레이어)

## 0. 배경 시나리오 (hani 용어)

- **회사(PMT)**가 여러 **사무실(Office = 컴퓨터)** 위에서 **AI 팀원(Overlord)** 을 띄우고, 각 AI 팀원이 자기 프로젝트 1개를 전담 실행한다. 프로젝트 내부는 **WP(Work Package) 단위 window**로 쪼개고, 각 window는 **WP 리더 1명 + 작업자(worker) N명**으로 구성된다.
- **1 Overlord = 1 프로젝트.** AI 팀원 한 명이 프로젝트 한 개를 맡는다. 더 많은 프로젝트를 동시 진행하려면 Overlord 수를 늘린다.
- **쿼터 경계 = Office 단위.** 한 Office에서 돌아가는 모든 Overlord는 그 Office의 Claude Code 구독 1개를 공유. 쿼터 병렬화는 Office를 늘려야만 가능 (`overlord-model-design.md` §6·§7).
- **한 Office 안에 Overlord 여러 개 가능** (hani §7.1 수직 스케일아웃). 각 Overlord는 서로 다른 프로젝트를 담당하며, DDTR I/O·git push 대기 시간을 다른 Overlord가 LLM 호출로 메워 동시성이 자연스럽게 올라간다. 쿼터는 공유되므로 rate limit 걸리면 함께 느려짐.
- 빨리 끝나는 Overlord는 종료되고, PMT가 여유가 생긴 Office에 다음 프로젝트를 새 Overlord로 spawn.
- PMT 실행 평면(`pmt-shim` 프로세스)은 **DDTR을 실행하지 않는다** (`overlord-model-design.md` §2.6). Master 컴퓨터에 물리 자원을 쓰려면 `host: localhost` 형태로 **별도 Office**를 등록하고 거기에 Overlord를 올린다 (구독은 그 Office에 로그인된 계정 공유).

## 0.1 4계층 다이어그램 (hani §2.3과 1:1)

```
[L0] Host Agent (사무실 관리자)
  │   Phase 1.5 기준: 호스트의 sshd 자체(신규 코드 0줄, host-agent-options.md 안 1)
  │   구현 장기: dev-plugin의 signal-sync.py 데몬으로 승계
  │   책임: 같은 Office 내 N개 Overlord의 lifecycle, PMT 명령 수신, 프로비저닝 집행
  │
[L1] Overlord (= AI 팀원 1명 = 1 프로젝트 전담)
  │   dev-plugin 구현: tmux session(이름 = overlord-{project-id})
  │   자기 프로젝트의 WBS를 WP 단위로 분해해 내부 오케스트레이션
  │   프로젝트 리더 역할 겸임. 4개 도구만 사용(tmux·sqlite·vault·webhook)
  │   같은 Office에 여러 Overlord(= 여러 프로젝트) 공존 가능, 구독 공유
  │
  ├─ window: WP-01   ← 프로젝트 워크트리(또는 WP 워크트리)에서 열림
  │   [L2] WP 리더 pane (1명, 필수)
  │        dev-plugin 구현: 기존 /dev-team WP Leader pane
  │        dep-analysis + Task 의존성 순 분배 + WP 단위 머지 조율
  │   [L3] 작업자(worker) pane (최소 1명)
  │        dev-plugin 구현: 기존 /dev-team worker pane
  │        PMT가 설정한 수만큼 spawn
  │        Task 1건씩 DDTR 사이클 실행
  │
  ├─ window: WP-02
  │   └─ ...
  │
  └─ window: WP-NN
```

**핵심 규칙** (hani §2 Invariants — 전 Phase에서 불변):

1. **Overlord 1개 = 정확히 1 프로젝트** (= AI 팀원 1명 = tmux 세션 1개).
2. **Overlord가 자기 프로젝트의 팀리더 역할을 겸임** — 별도 "프로젝트 리더" 세션·pane은 존재하지 않음.
3. 각 WP window는 프로젝트 워크트리(또는 WP 워크트리)에서 열린다.
4. 1 WP window = 정확히 1 WP 리더.
5. 1 WP window = 최소 1 작업자.
6. 작업자 수의 단일 진실은 PMT.
7. 프로젝트 ↔ Office 매핑은 **동적** (PMT가 운영 중 이관 가능 — 이관 = 이전 Overlord 해체 + 수신 Office에 새 Overlord spawn).
8. Office(컴퓨터)마다 Host Agent 1개. 1 Host Agent가 여러 Overlord를 동시 관리.

---

## 1. 어휘·계층 매핑 표

| dev-plugin 표현 | hani 모델 용어 | 계층 | 비고 |
|---|---|---|---|
| Master 프로세스 (`pmt-shim.py` + `pmt-coord.py`) | **PMT 실행 평면** | 중앙 | Phase 1.5엔 pmt-shim이 PMT DB의 경량 대리. 장기적으론 hani PMT DB(`Office`, `Overlord`, `Project`, `ProjectSlot`, `BotInstance` 테이블)가 SoT (`overlord-model-design.md` §14). |
| 호스트(컴퓨터) | **Office (사무실)** | 호스트 | 구독 1개 공유. hani ERD `Office` 엔티티. |
| `signal-sync.py` 데몬 | **Host Agent (L0)** | 호스트 데몬 | Phase 1.5 기준은 sshd 그 자체(`host-agent-options.md` 안 1). dev-plugin의 signal-sync는 Phase 3+ 안 3/안 4 단계 구현체. 한 Office의 여러 Overlord를 관리. |
| Overlord tmux 세션 (`overlord-{project-id}` 등) | **Overlord (L1, AI 팀원)** | 메인 세션 | 1 세션 = 1 프로젝트. hani ERD `Overlord.project_id` UNIQUE 제약. |
| 프로젝트 내부 WP 스케줄 | Overlord가 자기 프로젝트의 WP를 window로 여는 **내부 오케스트레이션** | L1 내부 | PMT는 프로젝트 단위로 Overlord를 배정, WP/Task는 Overlord 자기 내부에서 해결. |
| WP Leader pane | **WP 리더 (L2)** | window 첫 pane | 자기 WP의 Task 의존성 순 분배, WP 단위 완료/실패 Overlord에 보고. |
| worker pane | **작업자 (L3)** | pane | Task 1건 실행 단위. PMT `ProjectSlot` row 1개에 대응. |
| 단일 WBS의 WP 의존 그래프 | 프로젝트 **내부** 의존 그래프 | L1 관할 | 프로젝트 간 의존은 hani가 금지(§2·§10). 필요하면 PMT 상위에서 수동 관리. |
| `worker-bootstrap.py` | **프로비저닝 집행기**(`overlord-model-design.md` §11) | L0 집행 | Phase 1.5는 PMT가 SSH로 직접 실행, dev-plugin 스크립트는 그 구현체. |
| `distributed-config.json` | **PMT 운영 설정 일부** | 설정 | `offices[] / projects[]` 구조 (Overlord는 project×office 할당의 런타임 엔티티로 파생). |

---

# Part A. 실행 레이어 설계

## A1. 핵심 원칙

- Python stdlib만 사용 (기존 dev 플러그인 원칙 유지).
- 기존 로컬 dev-team 로직 변경 최소화 (`signal-helper.py`·DDTR 스킬 무수정 — sync가 어댑터 역할).
- **HTTP 시그널 서버(`pmt-shim`) + 주기적 싱크**로 머신 간 통신.
- SSH는 Overlord spawn·프로비저닝 때 **1회성**으로만 사용 (`host-agent-options.md` 안 1).
- **PMT는 프로젝트 단위로 Office에 Overlord를 할당**하고, WP/Task 할당은 Overlord가 자기 세션 내부에서 처리.
- **PMT 실행 평면은 DDTR을 실행하지 않는다** (hani §2.6 — Overlord는 자기 라이프사이클 관리 안 함, PMT는 L1에 간섭 안 함).
- **쿼터 경계 = Office 단위** — 같은 Office의 Overlord들은 동일 구독 공유.
- **hani 4계층 불변 규칙(§2) 준수** — 본 문서 어떤 설계 결정도 §2 규칙을 깨지 않는다.
- 시그널은 **git에 넣지 않는다** — git은 코드/브랜치 동기화 전용, 시그널은 HTTP 채널.

## A2. 현재 한계점

| 구성요소 | 현재 (단일 Office·단일 Overlord) | 분산 시 문제 |
|---|---|---|
| 시그널 파일 | 로컬 `/tmp/claude-signals/` | 다른 Office에서 보이지 않음 |
| Git worktree | 로컬 `.claude/worktrees/` | 다른 Office에 없음 |
| tmux 제어 | `tmux send-keys` (로컬 IPC) | 원격 Office의 tmux 제어 불가 |

세 가지 모두 "**로컬 파일/IPC 가정**" 위에 있어, Office 경계를 넘으려면 별도 레이어가 필요 — Part A 전체가 이 문제를 푸는 설계.

## A3. 분배 계층 — 두 층으로 분리

hani 모델은 **프로젝트(PMT→Office 경계)** 와 **WP/Task(Overlord 내부 경계)** 의 분배를 다른 주체가 처리한다.

### A3.1 PMT → Office: **프로젝트 단위** Overlord spawn 결정

```
PMT(pmt-shim 큐)          Office B (acc-b 공유)             Office C (acc-c)
─────────────             ─────────────────────            ──────────────────
프로젝트 대기열:           Overlord α (project: my-app:backend)   Overlord γ (project: another-app)
  my-app:backend     ──►   └─ WP windows (WP-01, WP-02, ...)     └─ WP windows
  my-app:frontend          
  another-app              Overlord β (project: my-app:frontend)
                           └─ WP windows
```

- **PMT는 어느 프로젝트를 어느 Office에 배정할지를 결정**하고, 해당 Office의 Host Agent(sshd)를 통해 새 Overlord tmux 세션을 spawn한다 (`overlord-model-design.md` §4 Overlord 책임).
- 각 Overlord는 1 프로젝트 전담. 프로젝트가 끝나면 그 Overlord는 종료되고, PMT가 다음 프로젝트를 필요 시 같은 Office에 새 Overlord로 spawn.
- Office × 구독 쿼터에 여유가 많을수록 그 Office가 자연스럽게 더 많은 프로젝트를 받음 (Overlord 인스턴스 수 증가).
- 프로젝트 **재할당**(예: Office B가 너무 바쁨 → 미시작 프로젝트 하나를 Office C로)은 hani §10 동적 구조조정 그대로 — **이전 Overlord 안전 종료 + 수신 Office 새 Overlord spawn**, Task 단위 원자성 + git remote 경유.

### A3.2 Overlord 내부: **WP 의존 affinity + 균등 분배**

Overlord(L1)는 자기 프로젝트의 WBS를 읽어 WP 단위 window를 생성하고, 각 WP 내부에서 WP 리더가 작업자들에게 Task를 분배한다. 기존 `/dev-team` 내부 로직 그대로:

```
Overlord가 하는 일:
1. dep-analysis.py로 WP 의존 그래프 → 약연결 컴포넌트(WCC) 분해
2. 팀원 수(PMT) × WCC affinity 계산 → window 수 결정
3. 각 window에 WP 리더 + 작업자 spawn
4. WCC 고갈 시 독립 WP로 work-steal (같은 프로젝트 내)

WP 리더가 하는 일 (window 내부):
1. 자기 WP의 Task 목록 추출
2. 의존성 순으로 작업자에게 Task 분배
3. WP 완료 시 Overlord에 보고
```

**프로젝트 경계를 넘는 WP steal은 없다** — hani §2가 프로젝트 간 의존을 금지하므로 Cross-project WP 의존 시그널도 없음. 프로젝트를 다른 Office로 옮기고 싶으면 §10 동적 구조조정(Overlord kill + spawn)을 거침.

## A4. 시그널 채널 — `pmt-shim` HTTP 서버 (1차안)

PMT 실행 평면이 HTTP 서버를 띄우고, Host Agent(sshd)를 통해 bootstrap된 Overlord들이 REST로 자기 프로젝트 메타를 받아가고 시그널을 교환한다.

| 항목 | 값 |
|---|---|
| 프로토콜 | HTTP/JSON (`http.server` + `threading`, stdlib만) |
| 위치 | PMT 실행 평면 머신 (`pmt-shim.py :9876`) |
| 저장소 | 인메모리 + 선택적 JSON persist (`--persist state.json`) |
| 워커 측 | `signal-sync.py`가 Office ↔ 로컬 `/tmp/claude-signals/` 양방향 미러링. 기존 `signal-helper.py wait` 코드 무수정 |
| 통신 | PMT→Office SSH(1회/Overlord spawn 시), Office→PMT HTTP(주기), Overlord↔Overlord 직접 통신 없음 |

### 토폴로지

```
                    ┌─────────────────────────┐
                    │     PMT Host Machine     │
                    │    (실행 평면 전용)       │
                    │                         │
                    │  pmt-shim.py :9876       │◄── 프로젝트 큐 + 시그널 저장소
                    │  pmt-coord.py           │◄── SSH 부트스트랩 + 모니터링 + 머지 조율
                    │                         │
                    │  (DDTR 실행 안 함)        │
                    └────┬──────┬──────┬──────┘
                 SSH(1회) │      │      │
            ┌────────────┘      │      └────────────┐
            ▼                   ▼                    ▼
   ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
   │   Office B       │ │   Office C       │ │   Office D       │
   │   acc-b 공유      │ │   acc-c 전용     │ │   acc-d 전용     │
   │                  │ │                  │ │                  │
   │ signal-sync.py  │ │ signal-sync.py  │ │ signal-sync.py  │
   │   (L0, Phase 3+) │ │                  │ │                  │
   │                  │ │                  │ │                  │
   │ Overlord α       │ │ Overlord γ       │ │ Overlord δ       │
   │ (project A)      │ │ (project C)      │ │ (project E)      │
   │                  │ │                  │ │                  │
   │ Overlord β       │ │                  │ │                  │
   │ (project B)      │ │                  │ │                  │
   └─────────────────┘ └─────────────────┘ └─────────────────┘
         │ ▲                 │ ▲                 │ ▲
         └─┼── HTTP GET/POST ─┼─────────────────┼─┘
           └─────── to PMT ───┘
```

> **PMT Host Machine에 Overlord를 두고 싶다면** `host: localhost` Office 엔트리를 추가. PMT 프로세스는 DDTR을 실행하지 않지만, 같은 컴퓨터에서 별개 tmux 세션으로 Overlord를 띄울 수 있음. 그 Overlord들은 해당 컴퓨터의 구독을 공유.

### 왜 HTTP인가

- 기존 `signal-helper.py`의 파일 원자성 가정 유지 — Overlord는 로컬 미러만 봄.
- Python stdlib만 사용 (외부 인프라 0).
- SSH 터널·직결·역터널 모두 동일 코드로 동작 → NAT/방화벽 흡수.
- hani Phase 3+에서 인증/HTTPS 추가 가능 (토큰 auth).

### 대안 (필요시)

| 방식 | 언제 검토 | 단점 |
|---|---|---|
| **Redis/Valkey pub/sub** | 시그널 트래픽이 초당 수십~수백 건이고 진짜 실시간 push가 필요할 때 | 외부 서비스 운영 부담 |
| **객체 스토리지(S3 등) write-once** | 이미 클라우드 스토리지가 있고 인바운드 HTTP가 어려울 때 | 폴링 latency, eventual consistency |

> ⚠️ **검토하지 않는 방식**
> - **git remote** — 커밋 노이즈·push 충돌·수십 초 지연.
> - **NFS/SMB/sshfs** — `create→rename→check` 원자성 없음 (CLAUDE.md "SHARED_SIGNAL_DIR는 로컬 디스크" 제약).

## A5. 컴포넌트 상세

### A5.1 `pmt-shim.py` (PMT 실행 평면 대리)

**hani 계층**: PMT 실행 평면 (중앙)
**hani 엔티티 대응**: `Project` ↔ `Office` 배정, `Overlord` 1 row lifecycle, `ProjectSlot` 관리, `BotInstance` 생명주기 (Phase 1.5 경량 대리; 장기적으로 hani PMT DB로 이관).

프로젝트 대기열 + **Office당 Overlord 1:1 런타임 매핑**을 담당하는 경량 HTTP 서버.

**자료구조 (in-memory)**

```python
state = {
    "projects": {
        "my-app:backend":  {"status":"queued",   "assigned_office": None, "overlord_id": None},
        "my-app:frontend": {"status":"running",  "assigned_office": "office-b", "overlord_id": "overlord-frontend"},
        "another-app":     {"status":"done",     "assigned_office": "office-c", "overlord_id": None, "terminated_at": "..."},
    },
    "offices": {
        "office-b": {"host":"192.168.1.101", "subscription": "acc-b", "alive": True, "active_overlords": ["overlord-frontend"]},
        "office-c": {"host":"192.168.1.102", "subscription": "acc-c", "alive": True, "active_overlords": []},
    },
    "overlords": {
        # 런타임 Overlord 인스턴스 (1 Overlord = 1 Project)
        "overlord-frontend": {"office":"office-b", "project":"my-app:frontend", "status":"RUNNING", "started_at":"..."},
    },
    "signals": {
        # 프로젝트:Task 네임스페이스 — 프로젝트 내부 WP/Task 의존 시그널만
        "my-app:frontend/TSK-01-01": {"event":"done", "overlord":"overlord-frontend", "at":"..."},
    },
}
```

**API**

| Method | Path | 설명 |
|---|---|---|
| `POST` | `/api/offices/{office}/register` | Office + Host Agent 등록 |
| `POST` | `/api/overlords/{overlord}/heartbeat` | Overlord 생존 신호 |
| `GET` | `/api/overlords/{overlord}/project` | 자기에게 할당된 프로젝트 메타 조회 (WBS 경로, 작업자 수 등) |
| `POST` | `/api/projects/{p}/complete` | 프로젝트 완료 보고 → Overlord 종료 처리 |
| `POST` | `/api/projects/{p}/signal` | 프로젝트 내부 WP/Task 시그널 등록 |
| `GET` | `/api/projects/{p}/signals` | 해당 프로젝트 시그널 조회 (signal-sync 다운로드용) |
| `POST` | `/api/offices/{office}/spawn` | pmt-coord가 호출 — 대기 큐에서 프로젝트 하나 pop → 해당 Office에 Overlord spawn 명령 |
| `GET` | `/api/status` | 전체 진행 현황 (Office × Overlord × Project 롤업) |

**`GET /api/overlords/{overlord}/project`** 응답

```json
// Overlord spawn 직후 자기 할당 프로젝트 조회
{
  "project": "my-app:backend",
  "git_clone_url": "git@github.com:org/my-app.git",
  "wbs_path": "docs/backend/wbs.md",
  "team_size": 3,
  "repo_path_hint": "~/projects/my-app"
}

// 이미 종료되어야 하는 Overlord (이관/취소)
{"project": null, "reason": "terminated"}
```

스케줄링: pmt-coord가 큐를 감시하다가 Office별 쿼터/부하를 고려해 다음 프로젝트를 꺼내고, 해당 Office에 SSH로 Overlord tmux 세션을 spawn한다. spawn된 Overlord는 환경변수/초기 prompt로 자기 `OVERLORD_ID`를 받아 위 API를 호출한다.

**특성**

- 인메모리 + `--persist`로 JSON 백업.
- 프로젝트 큐 접근은 `threading.Lock`으로 보호 (중복 할당 방지).
- 포트 1개 (기본 9876).
- 자신은 DDTR 실행하지 않아 Claude 구독 쿼터 무소모.

### A5.2 `signal-sync.py` (Host Agent 구현 — Phase 3+)

**hani 계층**: L0 Host Agent
**Phase 1.5**에선 호스트의 sshd가 L0 역할을 함 (`host-agent-options.md` 안 1). signal-sync는 **Phase 3+ 비동기·NAT 환경 필요 시** 등장하는 데몬으로, 안 3(tmux 폴링) / 안 4(bash 데몬)의 Python 구현체. **한 Office의 여러 Overlord를 동시에 서비스**한다.

로컬 `/tmp/claude-signals/{project}/...` ↔ PMT shim 서버 간 **양방향 주기적 싱크**.

```bash
signal-sync.py \
  --pmt http://pmt-host:9876 \
  --office office-b \
  --signal-root /tmp/claude-signals \
  --interval 10
```

**싱크 루프 (매 interval초)**

```
Upload (로컬 → PMT):
  1. signal-root 하위 프로젝트 디렉토리 스캔 (이 Office의 모든 Overlord의 시그널)
  2. 새로운 .done / .failed / .bypassed 감지
  3. POST /api/projects/{p}/signal 로 등록
  4. .synced 마커로 중복 방지

Download (PMT → 로컬):
  1. 이 Office에서 실행 중인 각 Overlord의 프로젝트에 대해
     GET /api/projects/{p}/signals 조회
  2. 로컬에 없는 시그널 파일 생성 (기존 signal-helper.py 포맷 그대로)
  3. 자기 Office 생성 시그널은 스킵
```

**핵심: `signal-helper.py`는 변경 없음.** sync가 어댑터 역할을 해서, DDTR 로직은 분산 여부를 모른다.

**Phase 1.5에서의 대체** — SSH-only일 때는 signal-sync 데몬 없이 PMT가 직접 SSH로 Office의 시그널 디렉토리를 rsync하거나, 더 간단히 단일 호스트 구성(모든 프로젝트가 같은 Office의 Overlord들). NAT/다중 Office가 필요해지는 순간이 signal-sync 도입 시점.

### A5.3 `overlord-loop.py` (L1 Overlord의 주 루프)

**hani 계층**: L1 Overlord (AI 팀원)
**hani 엔티티**: `Overlord` 1 row (프로젝트 1개 전담)

Overlord tmux 세션 안에서 도는 **프로젝트 메타 조회 → WP 분해 → window 생성 → 진행 모니터링 → 프로젝트 완료** 루프. **1 프로젝트 전담이므로 "다음 프로젝트 할당" 단계가 없다.** 프로젝트 완료 시 자기 세션을 정리하고 종료.

```
Overlord 세션 시작 (tmux new -s overlord-{project-id})
  │   환경변수: OVERLORD_ID={project-id}, PMT_URL=http://pmt-host:9876
  │
  ├─ (Phase 3+) 로컬 signal-sync.py 데몬이 이미 기동 중이면 재사용
  │
  └─ 메인 루프:
      ├─ GET /api/overlords/{OVERLORD_ID}/project
      │   └─ WBS 경로, team_size, git URL 등 획득
      │
      ├─ 프로비저닝 확인 (overlord-model-design.md §11)
      │   ├─ repo_path 존재? → git pull
      │   └─ 없음? → git clone {git_clone_url} {repo_path}
      │
      ├─ WBS 로딩 + WP 분해
      │   ├─ wbs-parse.py로 WP 목록 추출
      │   ├─ dep-analysis.py로 WP 의존 그래프 → WCC 분해
      │   └─ team_size × WCC affinity로 window 수 결정
      │
      ├─ 각 WP에 대해:
      │   ├─ tmux new-window -n {wp-id} -c {project-worktree-or-wp-worktree}
      │   ├─ 첫 pane에 WP 리더 prompt 주입 (ddtr-prompt-template)
      │   └─ 추가 pane 생성 (team_size만큼) + 작업자 prompt 주입
      │
      ├─ 모니터링 (capture-pane 폴링 / 시그널 파일 감시)
      │   ├─ WP 완료 시 overlord가 조기 머지 가능 여부 판단
      │   └─ WP 실패 시 에스컬레이션 로직
      │
      ├─ 프로젝트 완료 (모든 WP 완료 + main 브랜치 머지)
      │   ├─ git push origin {project-branch}
      │   ├─ POST /api/projects/{p}/complete
      │   └─ tmux kill-session -t {OVERLORD_ID} (자기 세션 종료)
      │
      └─ 종료
```

Overlord는 WP 내부 Task에 직접 개입하지 않는다 (hani §4). WP 단위 완료/실패만 감지하고 PMT에 보고.

### A5.4 `pmt-coord.py` (PMT 실행 평면 오케스트레이터)

**hani 계층**: PMT 실행 평면 (중앙)
**hani 엔티티**: `Office` 등록, `Overlord` spawn/kill, `Project` 할당

전체 분산 실행을 조율하는 마스터 스크립트. `/dev-team --distributed distributed-config.json`이 이 스크립트를 호출.

```
Phase 1: 준비
  ├─ config.json 파싱 → offices[] + projects[] 등록
  ├─ pmt-shim.py 시작 (백그라운드 daemon)
  └─ 프로젝트 큐 초기화 (priority/weight 적용)

Phase 2: Overlord spawn (hani §9.5 Overlord 신설)
  └─ 큐가 빌 때까지 반복:
      ├─ 큐에서 프로젝트 하나 pop (priority 순)
      ├─ 배정 Office 결정 (config assigned_office 또는 부하 기반 자동 선택)
      ├─ host=localhost → SSH 생략, 로컬 tmux
      ├─ host=원격     → SSH 접속 → worker-bootstrap.py 실행 (프로비저닝 §11)
      ├─ ssh {office} "tmux new -d -s overlord-{project-id} 'claude'"
      ├─ ssh {office} "tmux send-keys ... overlord-loop.py ... Enter"
      │                (OVERLORD_ID={project-id}, PMT_URL 주입)
      └─ (Phase 3+) signal-sync.py 기동 (이미 Office에 있으면 skip)

Phase 3: 모니터링
  └─ 주기적으로:
      ├─ GET /api/status (큐 + 시그널 진행률 + Overlord heartbeat)
      ├─ ssh {office} "tmux has-session -t {overlord-id}" (생존 확인)
      ├─ Overlord 장애 → 프로젝트를 큐 맨 앞으로 되돌림 → 다른 Office에 새 Overlord spawn
      └─ 완료된 프로젝트는 early merge 트리거

Phase 4: 머지 + 정리
  ├─ 각 프로젝트 브랜치를 remote에서 pull
  ├─ 프로젝트별 독립 순차 merge (충돌 시 수동 개입)
  ├─ 완료된 Overlord는 자기 세션을 스스로 종료 (overlord-loop 마지막 단계)
  └─ signal-sync 종료
```

### A5.5 `worker-bootstrap.py` (프로비저닝 집행기)

**hani 계층**: L0 프로비저닝 (현재 Phase 1.5는 PMT가 SSH로 직접 실행, 이 스크립트는 그 구현체)
**참조**: `overlord-model-design.md` §11

SSH만 설정돼 있으면 나머지 자동.

```bash
python3 scripts/worker-bootstrap.py distributed-config.json
```

처리 흐름:

```
1. SSH 접속 테스트
2. OS/패키지 매니저 감지 → python3/git/tmux 없는 것만 설치
3. claude CLI 확인 (사람이 미리 login 필수; §11.3 안전 조건)
4. 각 프로젝트 repo 폴더 확인
   ├─ 존재 + origin 일치 → git pull
   ├─ 존재 + origin 불일치 → 충돌, PMT에 "사용자 확인 필요" 보고
   └─ 없음 → git clone (§11.2 clone 분기)
5. dev plugin 설치 (claude '/plugin install dev@dev-tools')
6. 체크리스트 출력 + PMT에 성공/실패 보고
```

**사람이 직접 하는 것**

| 항목 | 이유 |
|---|---|
| SSH 키 교환 | 보안 — 키 페어 수동 확인 |
| Git 인증 | SSH key / PAT, Office별 설정 |
| `claude login` (Office마다 1회) | OAuth 토큰이 macOS Keychain에 바인딩되어 복사 불가. Office = 1 구독 계정 |

## A6. 시그널 흐름 (프로젝트 내부 Cross-WP 의존)

```
시나리오: 프로젝트 my-app:backend 내부에서 TSK-03-01이 TSK-01-03에 의존.
         두 Task는 모두 Overlord α의 같은 세션의 각각 다른 WP window에서 처리되므로
         로컬 signal-helper로 해소.

Overlord α (Office B, 프로젝트 my-app:backend 전담)
────────────────────────────────────────────────
TSK-01-03을 담당하는 WP 윈도우의 작업자 pane 완료
  │
  └─ signal-helper.py done
      → /tmp/claude-signals/my-app:backend/TSK-01-03.done
  ↓
다른 WP 윈도우의 작업자(TSK-03-01 담당)가
signal-helper.py wait로 대기 → 즉시 감지 → 실행 시작
```

**Cross-Office 시그널은 현재 설계에 없음** — hani가 **프로젝트 간 의존을 금지**하므로, 다른 Office의 시그널을 기다릴 일이 없다. Office 간 통신은 다음 2가지뿐:

1. PMT → Overlord: 프로젝트 메타 조회 응답 (HTTP pull)
2. Overlord → PMT: 프로젝트 완료 보고 + 상태 heartbeat (HTTP)

프로젝트가 Office 간 이관되는 경우(hani §10)는 이전 Overlord 종료 + 수신 Office 새 Overlord spawn — 시그널 동기화가 아닌 **세션 lifecycle**로 처리된다. 코드는 git remote를 경유.

## A7. 설정 — `distributed-config.json`

```json
{
  "pmt_shim": {
    "port": 9876,
    "persist": "~/.dev-plugin/pmt-state.json"
  },

  "sync_interval": 10,

  "offices": [
    {"id": "office-b",      "host": "192.168.1.101", "user": "dev", "ssh_key": "~/.ssh/id_ed25519", "subscription_account": "acc-b", "max_concurrent_overlords": 3},
    {"id": "office-c",      "host": "192.168.1.102", "user": "dev", "subscription_account": "acc-c", "max_concurrent_overlords": 2},
    {"id": "office-master", "host": "localhost",                    "subscription_account": "acc-master", "max_concurrent_overlords": 1}
  ],

  "projects": [
    {"id": "my-app:backend",  "git_clone_url": "git@github.com:org/my-app.git", "branch_base": "main", "wbs_path": "docs/backend/wbs.md",  "assigned_office": "office-b", "team_size": 3, "priority": 1, "repo_path": "~/projects/my-app"},
    {"id": "my-app:frontend", "git_clone_url": "git@github.com:org/my-app.git", "branch_base": "main", "wbs_path": "docs/frontend/wbs.md", "assigned_office": null,       "team_size": 2, "priority": 1, "repo_path": "~/projects/my-app"},
    {"id": "another-app",     "git_clone_url": "git@github.com:org/another.git","branch_base": "main", "wbs_path": "docs/wbs.md",          "assigned_office": null,       "team_size": 2, "priority": 2, "repo_path": "~/projects/another-app"}
  ],

  "merge": {
    "strategy": "sequential",
    "early_merge": true
  }
}
```

**스키마 규칙**

- `offices[]`의 `subscription_account`는 그 호스트에 `claude login`된 계정 식별자 (메타 정보; 구독 경계 확인용).
- `offices[].max_concurrent_overlords`는 그 Office에서 동시에 돌릴 수 있는 Overlord 수 상한 (= 동시 진행 프로젝트 수 상한). 수직 스케일아웃의 운영 레버.
- `projects[].assigned_office`는 선택. `null`이면 pmt-coord가 런타임에 부하 기반 자동 선택 (가장 여유 있는 Office).
- `projects[].team_size`는 hani "작업자 수의 단일 진실은 PMT" 규칙에 따라 PMT가 정함 (이 설정값이 초기 SoT).
- 프로젝트 ID 규칙: `project-name` 또는 `project-name:subproject-name` (서브프로젝트는 `docs/{sub}/wbs.md` 기반).
- **`overlords[]` 배열이 없다** — Overlord는 project × office 런타임 엔티티로 pmt-shim이 spawn 시점에 생성. 세션 ID는 `overlord-{project-id}` 규약.

## A8. tmux 세션 관리

### 명명 규칙

| 단위 | tmux 대상 | 이름 |
|---|---|---|
| L1 Overlord | session | `overlord-{project-id}` (예: `overlord-my-app-backend`) |
| L2 WP 윈도우 | window | `{wp-id}` (예: `WP-01`) |
| L2 WP 리더 | 해당 window의 첫 pane | — |
| L3 작업자 | 같은 window의 추가 pane | — |

### 라이프사이클 (hani §9.5 Overlord 신설/해체)

```
┌─ Overlord spawn (AI 팀원 출근 = 프로젝트 시작) ───────────────┐
│ ssh {office.host} "                                           │
│   tmux has-session -t overlord-{project-id} 2>/dev/null && \  │
│     echo 'RESUME' || tmux new -d -s overlord-{project-id}     │
│ "                                                             │
│ ssh {office.host} "                                           │
│   tmux send-keys -t overlord-{project-id} \                   │
│     'python3 scripts/overlord-loop.py \                       │
│        --pmt http://pmt-host:9876 \                           │
│        --overlord overlord-{project-id} \                     │
│        --office {office.id}' Enter                            │
│ "                                                             │
└───────────────────────────────────────────────────────────────┘

┌─ 생존 확인 ─────────────────────────────────────────────────┐
│ ssh {office.host} "tmux has-session -t overlord-{project-id}"│
│   exit 0 = Overlord 유지, exit 1 = Overlord 사망              │
│   → pmt-coord가 프로젝트를 큐로 되돌려 다른 Office에 재spawn  │
└───────────────────────────────────────────────────────────────┘

┌─ Overlord kill (AI 팀원 퇴근 = 프로젝트 완료 또는 이관) ─────┐
│ 정상 완료 (overlord-loop 스스로 종료):                         │
│   1. 모든 WP 완료 + git push origin {project-branch}           │
│   2. POST /api/projects/{p}/complete                           │
│   3. tmux kill-session -t overlord-{project-id} (자체 종료)   │
│                                                               │
│ 강제 이관 (PMT 명령):                                          │
│   1. overlord-loop에 SIGTERM 시그널 → 현재 Task 안전 종료     │
│   2. commit/push 완료 대기                                      │
│   3. ssh {office.host} "tmux kill-session -t overlord-{id}"  │
│   4. PMT가 hani `Overlord.status = TERMINATED` 갱신            │
│   5. 다른 Office에 새 Overlord spawn (위 spawn 흐름 반복)     │
└───────────────────────────────────────────────────────────────┘
```

### localhost Office

`office-master`처럼 `host: localhost`인 Office는 SSH 없이 로컬 쉘에서 동일 명령. PMT 프로세스와는 **별개 tmux 세션**이고, DDTR 실행은 그 Office에 로그인된 계정의 구독을 사용. PMT 프로세스 자체는 여전히 DDTR 없음.

### Resume

pmt-coord 재시작 시:

```
각 활성 Overlord 기록에 대해:
  ssh {office} "tmux has-session -t overlord-{project-id}"
  ├─ 존재 → 이미 실행 중, pmt-shim의 projects[].status로 진행 상황 복원
  └─ 없음 → pmt-shim의 마지막 상태 판단
           ├─ status=running이고 완료 시그널 있음 → 완료 처리
           └─ 미완료 → 프로젝트를 큐 맨 앞으로 되돌려 재spawn
```

## A9. 실행 예시

### 자동 (pmt-coord 사용)

```bash
# 1. 설정 파일 준비
vi distributed-config.json

# 2. PMT 실행 평면 기동 (= /dev-team --distributed)
claude '/dev-team --distributed distributed-config.json'

# 내부:
#   pmt-shim.py :9876 기동 → 프로젝트 큐 등록
#   worker-bootstrap.py로 각 Office에 프로젝트 repo 준비 + SSH 세팅 검증
#   큐가 빌 때까지:
#     큐에서 프로젝트 pop → 부하 여유 있는 Office 선택 → Overlord spawn
#     ssh office-b → tmux new -d -s overlord-my-app-backend  → overlord-loop.py
#     ssh office-b → tmux new -d -s overlord-my-app-frontend → overlord-loop.py  (같은 Office 다수 Overlord)
#     ssh office-c → tmux new -d -s overlord-another-app     → overlord-loop.py
#   모니터링 루프 시작
#
# 각 Overlord는 자기 프로젝트의 WBS를 WP 단위 window로 분해하여 내부 병렬 수행
# 프로젝트 끝나면 Overlord가 자체 종료 → pmt-coord가 큐에서 다음 프로젝트를 새 Overlord로 spawn
# PMT 프로세스는 DDTR 실행 안 함 → PMT 머신의 Claude 계정 쿼터 보존
```

### 수동 (pmt-coord 없이)

```bash
# PMT 머신: shim 서버 기동
python3 scripts/pmt-shim.py --config distributed-config.json --port 9876 &

# Office B에 프로젝트 하나 Overlord로 직접 띄우기
ssh dev@192.168.1.101 "tmux new -d -s overlord-my-app-backend"
ssh dev@192.168.1.101 "tmux send-keys -t overlord-my-app-backend '
  cd ~/projects/my-app && \
  python3 scripts/overlord-loop.py \
    --pmt http://pmt-host:9876 \
    --overlord overlord-my-app-backend \
    --office office-b
' Enter"

# 상태 확인
curl http://localhost:9876/api/status | jq
```

## A10. 머지 전략 (hani §10 정합)

### Sequential Merge (기본)

```
각 Overlord (프로젝트 완료 시):
  overlord-loop 마지막 단계에서 git push origin {project-branch}
  → POST /api/projects/{p}/complete

PMT(pmt-coord):
  프로젝트 단위로 독립 머지
  ├─ git fetch origin
  ├─ git merge origin/{project-branch}  (충돌 시 수동 개입)
  └─ hani §10.3 핸드오버 절차 따름 ("코드는 git remote 경유")
```

### 프로젝트 이관 (hani §10 동적 구조조정)

```
"Office B가 너무 바쁨 → my-app:frontend를 Office C로 이관"

1. Office B의 Overlord α(프로젝트 my-app:frontend 담당):
   진행 중 Task commit/push → overlord-loop 안전 종료 → tmux 세션 종료
2. PMT: Overlord α row를 TERMINATED, my-app:frontend.assigned_office = office-c (원자적)
3. pmt-coord: ssh office-c → tmux new -d -s overlord-my-app-frontend → overlord-loop.py
4. Office C의 새 Overlord α': git pull → WP window 재구성 → 작업 재개
```

- 진행 중 Task는 원자 단위로 마치고 이관 — "중간에 끊지 않는다".
- double ownership은 PMT가 막는다 (hani §10.3) — 이전 Overlord가 종료 보고를 올린 뒤에야 수신 Office 새 Overlord를 spawn한다.

## A11. 에러 처리

| 상황 | 대응 |
|---|---|
| Overlord 장애 (heartbeat 중단) | pmt-coord가 감지 → 해당 프로젝트를 큐 맨 앞으로 되돌림 → 부하 여유 있는 다른 Office에 새 Overlord spawn (hani §10). Office도 같이 죽었으면 그 Office의 모든 Overlord 프로젝트를 일괄 재spawn |
| WP/Task 실패 | 기존 bypass 메커니즘 그대로. signal-sync가 `.failed`/`.bypassed`도 PMT에 전파 |
| 네트워크 단절 | Overlord 로컬 작업 계속, 프로젝트 내부 시그널은 로컬에서 해소. 복구 시 밀린 시그널 자동 동기화 |
| pmt-shim 재시작 | `--persist`로 JSON 백업 → 재시작 시 복원 |
| Git 충돌 | 프로젝트 단위 분리로 대부분 회피. 발생 시 pmt-coord가 수동 해결 안내 |
| 프로비저닝 충돌 (폴더 존재, origin 불일치) | hani §11.3 "사용자 확인 없이 진행 금지" → PMT에 리포트 |
| Office의 max_concurrent_overlords 초과 요청 | pmt-coord가 대기; 빈 슬롯 생기면 spawn |

## A12. 기존 코드 변경 범위

### 변경 없음

| 파일 | 이유 |
|---|---|
| `signal-helper.py` | sync가 어댑터, 로컬 파일 인터페이스 유지 |
| `wbs-transition.py` | state.json은 Overlord 로컬에서 관리 |
| `wbs-parse.py` / `dep-analysis.py` | Overlord(L1)가 여전히 단일 WBS 기준 호출 |
| `dev-design/build/test/refactor` | DDTR 스킬 불변 |
| `team-mode`, `agent-pool` | 로컬 병렬 엔진 불변 |

### 변경

| 파일 | 변경 내용 |
|---|---|
| `dev-team` SKILL.md | `--distributed config.json` 모드 분기 추가 (→ pmt-coord 호출) |
| `wp-setup.py` | 원격 Overlord용 worktree/signal 경로 옵션 추가 (프로젝트 prefix 포함) |

### 신규 (구현은 v1에서 보류; 본 문서는 스펙 정의만)

| 파일 (권고) | hani 계층 | 역할 |
|---|---|---|
| `scripts/pmt-shim.py` | PMT 대리 | HTTP 서버 + 프로젝트 큐 + Overlord 런타임 매핑 + 시그널 저장소 |
| `scripts/signal-sync.py` | L0 (Phase 3+) | Office ↔ PMT 시그널 미러링 데몬 (Office당 1개, N Overlord 동시 서비스) |
| `scripts/overlord-loop.py` | L1 Overlord | 프로젝트 메타 조회 → WBS 분해 → WP window 생성 → 완료 시 자체 종료 |
| `scripts/pmt-coord.py` | PMT 실행 평면 | SSH 부트스트랩 + Overlord spawn/kill + 모니터링 + 머지 조율 |
| `scripts/worker-bootstrap.py` | L0 프로비저닝 | Office 환경 자동 구성 (§11) |

> **스크립트 이름은 권고.** v1 구현 시 확정.

## A13. 향후 확장 (hani Phase 2~3)

### Phase 2 — 구독 사용량 heartbeat

- 각 Overlord가 heartbeat에 남은 토큰/rate limit 상태 포함.
- rate limit에 걸린 Office는 자동으로 `max_concurrent_overlords` 일시 축소, 잔여 프로젝트는 다른 Office로 (hani §10 자동 이관).
- pmt-shim의 `/api/status`가 Office별 계정 사용량 노출 → SCR-31에서 시각화.

### Phase 2~3 — 사무실 간 프로젝트 이관

- `overlord-model-design.md` §10.4 cross-host 이동 구현.
- 수신 Office에서 프로비저닝(§11) 재실행, git remote 경유 코드 인계, 새 Overlord spawn.

### Phase 3+ — Host Agent 고도화

- `host-agent-options.md` 단계 진행: 안 1(SSH-only) → 안 3(tmux 폴링) → 안 4(bash 데몬) / 안 8(Tailscale+SSH).
- signal-sync.py가 이 시점부터 실제로 의미.

### Phase 3+ — pmt-shim 고도화

- WebSocket 업그레이드 (폴링 → push).
- 여러 PMT 프로젝트 동시 지원 (현재 API가 이미 프로젝트 네임스페이스 기반).
- HTTPS + API 토큰 인증 (공용 인터넷 노출 시).

---

# Part B. 분산 모니터링

## B1. 현재 제약

- `/dev-monitor`는 `127.0.0.1`에만 바인딩 (`scripts/monitor-server.py:6917`, PRD §4.1).
- 인증 없이 tmux pane 출력·WBS 상태·파일 내용을 평문 서빙 → `0.0.0.0` 오픈 절대 금지.
- 외부 접근은 **SSH 터널 필수**.

## B2. 단일 원격 — SSH 포트 포워딩 (코드 변경 0)

```bash
ssh -L 7321:127.0.0.1:7321 user@office-b
```

브라우저에서 `http://localhost:7321`.

## B3. 다중 원격 — Office별 포트 매핑

```sshconfig
Host office-b
    HostName 192.168.1.101
    LocalForward 7321 127.0.0.1:7321
Host office-c
    HostName 192.168.1.102
    LocalForward 7322 127.0.0.1:7321
Host office-d
    HostName 192.168.1.103
    LocalForward 7323 127.0.0.1:7321
```

- `autossh`로 터널 유지.

## B4. 한 Office에서 여러 Overlord(= 여러 프로젝트) 운영

`monitor-launcher.py`가 이미 이 시나리오 설계:

- PID 파일 프로젝트 경로 해시 기반 (`dev-monitor-{project_hash}.pid`, `monitor-launcher.py:43`).
- 포트 자동 탐색 7321~7399 (`monitor-launcher.py:119`).

한 Office × N Overlord(= N 프로젝트) = N개 포트가 로컬에 뜨고, 컨트롤러 측에서 로컬 포트만 다르게 터널링.

## B5. 트레이드오프와 통합 뷰 옵션 (비용 오름차순)

1. **플릿 랜딩 페이지** — 정적 HTML 링크 + 헬스 뱃지. 신규 스킬 1개로 충분.
2. **Aggregator 대시보드** — 각 터널 포트를 읽어 병합 렌더링. **선행: monitor-server JSON API 추출 필수** (현재 HTML 모놀리스).
3. **Push 기반 중앙 수집** — 각 Office가 Master로 push. NAT/방화벽 환경 필요 시.

> 💡 **Part A의 `pmt-shim /api/status`가 이미 풍부한 Office × Overlord × Project 상태를 노출한다.** 분산 실행을 v1로라도 돌리고 있으면 Aggregator는 monitor-server보다 pmt-shim을 풀링하는 편이 더 정확 (Overlord heartbeat·프로젝트 큐까지 포함).
>
> 💡 **hani SCR-31 §12.6 봇 상세 슬라이드 패널이 이 Aggregator의 UI 상위 계층**이다. dev-plugin monitor-server의 JSON API는 SCR-31 라이브 탭의 데이터 소스가 될 수 있다 (`bot-roles-design.md` §14.5, FR-203 PTY 스트림 참조).

## B6. 통합 뷰 구현 설계

### Phase 1 — JSON API 엔드포인트 추출 (~1일)

monitor-server에 구조화 라우트 **추가**:

```text
GET /api/v1/status   → { project, office_id, overlord_id, updated_at, uptime }
GET /api/v1/wbs      → [{ wp_id, tasks: [{ tsk_id, status, phase_start, ... }] }]
GET /api/v1/team     → [{ wp_id, leader_pane, workers: [...], signals: {...} }]
GET /api/v1/signals  → { done: [...], failed: [...], bypassed: [...], running: [...] }
GET /api/v1/health   → { ok: true, tmux: true, last_scan: "..." }
```

**설계 원칙**: HTML 렌더링 함수가 JSON 수집 함수를 호출한 뒤 HTML로 변환 — 수집 로직 이중화 금지.

**재사용처**

- `/dev-monitor --status --json` CLI
- 외부 Slack/Grafana 연동
- e2e 테스트 안정화 (JSON 단언)
- **SCR-31 봇 상세 슬라이드 패널 라이브 탭 데이터 소스** (hani FR-203 PTY 스트림과 별개로 메타 JSON 제공)
- Part A pmt-shim API와 동일 스키마로 맞추면 Aggregator 코드 재사용

### Phase 2 — Aggregator 스킬 `/dev-fleet-monitor` (~2~3일)

```text
skills/dev-fleet-monitor/
  SKILL.md
  fleet-config.example.yaml
scripts/
  fleet-server.py               # HTTP 서버 (monitor 또는 pmt-shim 풀링)
  fleet-launcher.py             # monitor-launcher.py와 동일 패턴
```

`fleet-config.yaml`:

```yaml
instances:
  - label: "office-b / overlord-my-app-backend"
    url: http://127.0.0.1:7321
  - label: "office-b / overlord-my-app-frontend"
    url: http://127.0.0.1:7322
  - label: "office-c / overlord-another-app"
    url: http://127.0.0.1:7323
  - label: "pmt-shim (global)"
    url: http://127.0.0.1:9876
refresh_seconds: 5
```

### 비용 비교

| 항목 | 비용 | 얻는 것 |
|---|---|---|
| **Phase 1만** | 낮음 (~1일) | CLI·외부 연동·Aggregator·SCR-31 기반 확보 |
| **Phase 1 + 2** | 중간 (~4일) | 통합 그리드 뷰 완성 |
| HTML 스크래핑으로 Phase 2 | 빠름 (~2일) | UI 바뀌면 깨짐 — **비추천** |
| Push 기반 | 높음 | NAT/방화벽 돌파, 아키텍처 변경 큼 |

---

# Part C. 보안

- SSH 포트 포워딩은 기존 SSH 인증·암호화 재사용.
- `0.0.0.0` 바인딩 절대 금지 — 같은 네트워크 누구나 열람 가능.
- 향후 `/dev-monitor --bind` 옵션 추가해도 PRD 제약 내 `::1` 정도까지만.
- Part A의 pmt-shim은 v1에서 LAN/VPN 가정. 공용 인터넷 노출 시 HTTPS + `--auth-token` 필수 (Phase 3+).
- 각 Office의 Claude OAuth 토큰은 **머신 Keychain 바인딩** — Office 간 복사·공유 불가 (hani 설계 그대로).
- **모든 입출력은 감사 로그에 기록된다** (hani §2.6). dev-plugin 측 구현은 pmt-shim의 sqlite append-only + signal-sync 전송 기록으로 담당.
- Master 컴퓨터에 `office-master` 엔트리를 둘 때 그 Office의 Overlord들은 해당 컴퓨터의 Claude 계정 쿼터를 공유 (쿼터 경계 = Office). PMT 프로세스 자체는 DDTR 없음이라 쿼터 무소모.

---

# Part D. 실행 순서 (hani Phase 로드맵 정합)

| 순서 | 작업 | 대응 hani Phase | 이유 |
|---|---|---|---|
| 1 | **Part B Phase 1 — monitor JSON API 추출** | Phase 1 | sunk cost 아님. CLI/SCR-31/aggregator/e2e 모두에 재사용. ~1일. |
| 2 | **Part B5 옵션 1 — 플릿 랜딩 페이지** | Phase 1 | N×M 탭 관리 고통 완화. 정적 HTML 1장. |
| 3 | **Part A의 pmt-shim + SSH-only Host Agent 최소 구현** | **Phase 1.5 "Overlord 1 + 작업자 1"** | 사무실 1·Overlord 1(= 프로젝트 1)·WP 1·WP 리더 1·작업자 1 축소형부터 출발. `host-agent-options` 안 1. |
| 4 | **같은 Office에 Overlord 여러 개 동시 실행** | Phase 2 | hani §7.1 수직 스케일아웃 구현. |
| 5 | **Part B Phase 2 — Aggregator + SCR-31 연결** | Phase 2 | 1·3·4를 운영한 뒤 정말 그리드가 필요할 때. |
| 6 | **구독 사용량 heartbeat + 사무실 간 프로젝트 이관** | Phase 2~3 | hani §10.4 cross-host 구현. |
| 7 | **Host Agent 고도화 (안 3/4)** | Phase 3+ | NAT/비동기 환경 필요 시점. |

핵심 메시지: **"hani Phase 로드맵을 따라가며, dev-plugin은 그 각 Phase의 CLI 구현체를 공급한다."** 모니터링 JSON API를 먼저 뽑는 건 hani Phase 1에서도 쓸모가 있고, 실행 분산은 hani Phase 1.5부터 의미가 생긴다.

---

# 관련 문서

## hani SoT (본 문서는 이들을 구현하는 CLI 레이어)

- `/Users/jji/project/hani/docs/overlord-model-design.md` — **SoT**: 4계층(L0~L3), 8개 불변 규칙, 수직·수평 스케일아웃, 동적 구조조정(§10), 프로비저닝(§11), PMT 엔티티 매핑(§14). **1 Overlord = 1 프로젝트** 모델.
- `/Users/jji/project/hani/docs/bot-roles-design.md` — **SoT**: Overlord(AI 팀원)/WP 리더/작업자 역할 정의, 주변 봇 12종, architecture-diagram v0.7 기반.
- `/Users/jji/project/hani/docs/host-agent-options.md` — **SoT**: Host Agent(L0) 8가지 구현 안과 Phase별 추천 (§11).

## dev-plugin 내부 참조

- `CLAUDE.md` — Shared signal directory가 로컬 디스크여야 한다는 제약 (Part A4 NFS 경고 근거).
- `scripts/monitor-launcher.py:43,119` — PID/포트 자동 분리 (Part B4 근거).
- `scripts/monitor-server.py:6917` — `127.0.0.1` 바인딩 (Part B1 근거).
- `scripts/signal-helper.py` — Part A의 어댑터 패턴이 유지하려는 기존 인터페이스 (sync가 이 파일의 API를 감싼다).
- `scripts/wbs-parse.py`, `scripts/dep-analysis.py`, `scripts/wbs-transition.py` — Overlord(L1) 내부 로직에서 무수정 재사용.

## 계획 문서

- `/Users/jji/.claude/plans/fizzy-painting-swan.md` — 본 문서 재작성을 승인받은 플랜 (검증 체크리스트 포함).
