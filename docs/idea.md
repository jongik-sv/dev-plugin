# 아이디어 모음

## 원격 모니터링 (SSH 기반 dev-team 감시)

### 배경

- 컨트롤러 머신 **A**가 SSH로 여러 워커 머신(**B, C, D, E, F**)에 접속해 각각 `/dev-team`을 실행시키는 분산 개발 시나리오.
- 각 워커 머신에서 `/dev-monitor`가 기동되어도 현재는 `127.0.0.1`에만 바인딩되어 외부에서 직접 접근 불가 (`scripts/monitor-server.py:6917`, PRD §4.1).
- 인증 없이 tmux pane 출력·WBS 상태·파일 내용을 평문 서빙하므로 `0.0.0.0` 오픈은 금지되어 있음.

### 단일 원격 머신 — SSH 포트 포워딩

가장 단순하고 안전한 방법. 코드 변경 없음.

```bash
# A에서 B로 접속할 때
ssh -L 7321:127.0.0.1:7321 user@B
```

A의 브라우저에서 `http://localhost:7321` → SSH 터널을 타고 B의 로컬 대시보드에 접속.

### 다중 원격 머신 — 머신별 포트 매핑

N대의 워커를 동시에 보려면 "N개 머신 × 1개 터널"로 **포트만 다르게** 포워딩.

`~/.ssh/config` 예시:

```sshconfig
Host dev-b
    HostName b.example
    LocalForward 7321 127.0.0.1:7321
Host dev-c
    HostName c.example
    LocalForward 7322 127.0.0.1:7321
Host dev-d
    HostName d.example
    LocalForward 7323 127.0.0.1:7321
Host dev-e
    HostName e.example
    LocalForward 7324 127.0.0.1:7321
Host dev-f
    HostName f.example
    LocalForward 7325 127.0.0.1:7321
```

- A의 브라우저에서 `localhost:7321 ~ 7325`를 탭으로 열면 각 머신 대시보드 확인 가능.
- `autossh`로 터널을 재연결 유지하면 더 안정적.
- 모든 워커의 monitor 포트가 같아도(7321) A 측 로컬 포트만 다르게 잡으면 충돌 없음.

### 한 머신에서 여러 프로젝트 운영 (dev-c에 P1, P2 동시 실행)

**가능함 — 코드 변경 불필요.** `monitor-launcher.py`가 이미 이 시나리오를 전제로 설계되어 있음:

- **PID 파일이 프로젝트 경로 해시 기반** (`dev-monitor-{project_hash}.pid`) — 프로젝트마다 별도 인스턴스로 인식 (`scripts/monitor-launcher.py:43`).
- **포트 자동 탐색 7321~7399** — 첫 프로젝트가 7321을 잡으면 두 번째는 7322로 자동 할당 (`scripts/monitor-launcher.py:119`).

dev-c에서 두 프로젝트를 각각 `/dev-monitor`로 띄우면 자동으로:
```
P1 → http://127.0.0.1:7321
P2 → http://127.0.0.1:7322
```

A에서 보려면 터널만 추가:

```sshconfig
Host dev-c
    HostName c.example
    LocalForward 7322 127.0.0.1:7321   # dev-c의 P1
    LocalForward 7323 127.0.0.1:7322   # dev-c의 P2
Host dev-d
    HostName d.example
    LocalForward 7324 127.0.0.1:7321   # dev-d의 P1
    # ...
```

즉 **머신 × 프로젝트 조합마다 A 측 로컬 포트 하나씩** 할당. N대 × M프로젝트 = N×M 탭이 되므로 이쯤이면 랜딩 페이지/aggregator 가치가 급격히 커짐.

**운용 팁:**
- A 측 로컬 포트는 7321부터 쓰지 말고 별도 범위(예: 17321~)를 할당해 두면 A 자체에서 `/dev-monitor`를 돌려도 충돌 안 남.
- `/dev-monitor --status`로 머신별로 어떤 프로젝트가 어떤 포트에 붙었는지 확인 후 A 측 매핑 테이블을 관리.

### 트레이드오프

**현 상태의 한계:** 탭 N개를 왔다갔다 해야 함. 통합 뷰 부재.

**개선 옵션 (비용 오름차순):**

1. **플릿 랜딩 페이지 (가장 저렴)**
   - A에 정적 HTML 한 장 — 각 머신 포트로의 링크 + 헬스 뱃지(연결 여부, 마지막 업데이트 시각)만 표시.
   - 각 대시보드 자체는 터널로 그대로 열림.
   - 순수 HTML/fetch 폴링으로 충분. 신규 스킬 1개로 감당 가능.

2. **Aggregator 대시보드 (중간 비용)**
   - A가 각 터널 포트의 상태를 읽어 병합 렌더링.
   - 머신별 WP/Task 진행률을 한 화면에 그리드로 집약.
   - **선행 작업 필요:** 현재 `monitor-server.py`는 HTML 모놀리스(~5600줄)라 기계가 읽을 수 있는 JSON 엔드포인트가 없음. `/api/status.json` 같은 구조화 출력 추가 후 aggregator가 그 위에 얹히는 구조.

3. **Push 기반 중앙 수집 (가장 비쌈)**
   - 각 워커가 A로 상태를 push. state.json 스크래핑 → 스트리밍.
   - 방화벽/NAT 환경에서 SSH 역터널 조합 필요. 아키텍처 변경 규모 큼.

### 보안 관점

- SSH 포트 포워딩은 기존 SSH 인증·암호화 체계를 그대로 재사용 → 추가 인증 구현 불필요.
- `0.0.0.0` 바인딩은 같은 네트워크의 누구나 열람 가능해지므로 절대 금지 유지.
- 향후 `/dev-monitor`에 `--bind` 옵션을 PRD 제약 내에서 추가한다면 `::1`(IPv6 loopback) 정도까지만 열고, LAN 노출은 불가.

### 통합 뷰 구현 설계 (Aggregator 대시보드)

핵심 원칙: **두 단계로 쪼갠다.** 현재 `monitor-server.py`는 ~5600줄 HTML 모놀리스라 직접 통합 뷰를 얹으면 HTML 스크래핑이 되어버려 UI 변경마다 깨짐. 반드시 JSON API를 먼저 분리.

#### Phase 1 — JSON API 엔드포인트 추출 (~1일, 가장 중요)

기존 HTML은 그대로 두고, 같은 서버에 구조화된 JSON 라우트를 **추가**:

```
GET /api/v1/status          → { project, machine_id, updated_at, uptime }
GET /api/v1/wbs             → [{ wp_id, tasks: [{ tsk_id, status, phase_start, ... }] }]
GET /api/v1/team            → [{ wp_id, leader_pane, workers: [...], signals: {...} }]
GET /api/v1/signals         → { done: [...], failed: [...], bypassed: [...], running: [...] }
GET /api/v1/health          → { ok: true, tmux: true, last_scan: "..." }
```

**중요한 설계 원칙:** 기존 HTML 렌더링 함수가 **JSON 수집 함수를 호출한 뒤 HTML로 변환**하는 구조로 리팩토링. 수집 로직을 두 번 구현하면 금세 drift 발생. 기존 monitor 로직 중 `_scan_*`, `_collect_*` 함수를 찾아 JSON 직렬화 계층을 얇게 씌우는 식.

부수 효과 — JSON API가 생기면 통합 뷰 외에도 재사용처 多:
- `/dev-monitor` CLI 서브커맨드 (`--status --json`)
- 외부 Slack/Grafana 연동
- e2e 테스트 안정화 (HTML 파싱 대신 JSON 단언)

#### Phase 2 — Aggregator 스킬 `/dev-fleet-monitor` (~2~3일)

A에서 도는 새 스킬. 구조:

```
skills/dev-fleet-monitor/
  SKILL.md
  fleet-config.example.yaml     # 머신 × 프로젝트 × 포트 매핑
scripts/
  fleet-server.py               # HTTP 서버 (Phase 1의 JSON을 풀링)
  fleet-launcher.py             # 기존 monitor-launcher.py와 동일 패턴
```

`fleet-config.yaml` 예시:
```yaml
instances:
  - label: "B / main-product"
    url: http://127.0.0.1:7321
  - label: "C / P1"
    url: http://127.0.0.1:7322
  - label: "C / P2"
    url: http://127.0.0.1:7323
refresh_seconds: 5
```

`fleet-server.py`가 하는 일:
1. 주기적으로 각 `url + /api/v1/status`, `/api/v1/wbs`, `/api/v1/team`을 풀링 (동시 요청)
2. 연결 실패 / stale / OK 세 가지 상태 뱃지 유지
3. 집계된 그리드 HTML 렌더링 (행=인스턴스, 열=WP 진행도)
4. 드릴다운 링크는 원본 대시보드(`http://127.0.0.1:7322` 등)로 점프

#### 기술 선택지

- **SSE (Server-Sent Events) vs 폴링**: Phase 2는 단순 폴링으로 시작. SSE는 Phase 3.
- **인증**: A 로컬에서만 도는 서버라 기존 monitor처럼 `127.0.0.1` 바인딩으로 충분.
- **타임아웃**: 각 인스턴스 호출에 2~3초 타임아웃, 실패하면 "disconnected" 뱃지.

#### 비용 비교

| 항목 | 비용 | 얻는 것 |
|---|---|---|
| **Phase 1만** | 낮음 (~1일) | CLI·외부 연동·Aggregator 기반 확보. UX는 그대로 |
| **Phase 1 + 2** | 중간 (~4일) | 진짜 통합 뷰 완성 |
| **HTML 스크래핑으로 바로 Phase 2** | 빠름 (~2일) | 단기엔 빠르지만 monitor UI 바뀌면 깨짐 — 비추천 |
| **Push 기반** | 높음 | NAT/방화벽 돌파는 좋지만 아키텍처 변경 큼 — 현 단계 불필요 |

#### 추천 실행 순서

**Phase 1을 먼저.** JSON API는 통합 뷰 외에도 가치가 많으므로 sunk cost가 아님. Phase 2는 Phase 1이 끝난 뒤 실제로 N×M 탭 관리가 고통스러워질 때 착수해도 늦지 않음.

### 관련 문서

- `docs/todo.md` — "future-upgrade-plan 업데이트 : 다른 컴퓨터에 각각 개발하는 방안(분산 개발, 다른 구독 요금)"
- `docs/distributed-dev-team-design.md` — 분산 개발 설계 문서
- `docs/future-upgrade-plan.md` — 중장기 업그레이드 계획
