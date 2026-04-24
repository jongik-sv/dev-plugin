# FR-08 스코프 확정 문서

**Task**: TSK-05-02 — `skills/dev-monitor/` 중복 문서 정리 (조사 선행)
**조사 일자**: 2026-04-24
**조사자**: dev-build 자동 조사

---

## 1. grep 조사 결과

```
grep -rn "monitor-launcher|monitor-server|dev-monitor" skills/dev-monitor/
```

### 조사 원문 (전체)

```
skills/dev-monitor/SKILL.md:2:  name: dev-monitor
skills/dev-monitor/SKILL.md:3:  description: "개발 활동 모니터링 대시보드 서버를 기동한다. 키워드: 모니터링, 대시보드, monitor, dashboard, ..."
skills/dev-monitor/SKILL.md:6:  # /dev-monitor — 개발 활동 모니터링 대시보드
skills/dev-monitor/SKILL.md:32: "$(python3 -c 'import sys; print(sys.executable)')" "${CLAUDE_PLUGIN_ROOT}/scripts/monitor-launcher.py" \
skills/dev-monitor/SKILL.md:58: 5. **JSON PID 파일 기록**: `${TMPDIR}/dev-monitor-{project_hash}.pid` → `{"pid": N, "port": N}`
skills/dev-monitor/SKILL.md:61: 로그는 `${TMPDIR}/dev-monitor-{project_hash}.log`에 append된다.
skills/dev-monitor/SKILL.md:65: 각 프로젝트는 고유한 해시 기반 PID 파일(`dev-monitor-{hash}.pid`)을 가지므로 ...
```

**결과 요약**: `skills/dev-monitor/` 내 파일에서 키워드가 발견된 파일은 `SKILL.md` 1개뿐이다.

---

## 2. 파일 목록 + 줄 수

| 파일 경로 | 줄 수 | 비고 |
|-----------|-------|------|
| `skills/dev-monitor/SKILL.md` | **86줄** | 유일한 마크다운 문서 |
| `skills/dev-monitor/vendor/cytoscape.min.js` | — | JS 벤더 라이브러리 (변경 금지) |
| `skills/dev-monitor/vendor/cytoscape-dagre.min.js` | — | JS 벤더 라이브러리 (변경 금지) |
| `skills/dev-monitor/vendor/cytoscape-node-html-label.min.js` | — | JS 벤더 라이브러리 (변경 금지) |
| `skills/dev-monitor/vendor/dagre.min.js` | — | JS 벤더 라이브러리 (변경 금지) |
| `skills/dev-monitor/vendor/graph-client.js` | — | JS 클라이언트 코드 (변경 금지) |

**`skills/dev-monitor/references/` 디렉토리**: **존재하지 않음** → 해당 파일 정리 작업 불필요(no-op).

---

## 3. 중복 문장 카운트 분석

### SKILL.md vs monitor-launcher.py 중복

`SKILL.md`의 `## 1. 기동 플로우 / ### 플로우 상세 (ACTION=start)` 섹션(48~66줄)은 `scripts/monitor-launcher.py` 상단 docstring과 기술 내용이 중복된다.

| SKILL.md 줄/내용 | 중복 위치 | 중복 여부 |
|------------------|-----------|-----------|
| 줄 52: "PID 파일 존재 + 프로세스 생존 → URL 재출력 후 종료" | `monitor-launcher.py` L10 | 중복 |
| 줄 53: "7321~7399 범위 자동 탐색" | `monitor-launcher.py` L11 | 중복 |
| 줄 55: "subprocess.Popen detach" | `monitor-launcher.py` L13 | 중복 |
| 줄 58: "JSON PID 파일 기록" | `monitor-launcher.py` L15, L44, L184 | 중복 |
| 줄 61: "로그 파일 경로" | `monitor-launcher.py` L49 | 중복 |
| 줄 65: "프로젝트별 독립 실행" 설명 | `monitor-launcher.py` 전반 | 중복 |

**중복 문장 카운트**: 약 6~7문장이 `monitor-launcher.py` docstring/주석과 동일한 내용.

### 결론

- 중복 블록은 `## 1. 기동 플로우 / ### 플로우 상세 (ACTION=start)` 및 `#### 프로젝트별 독립 실행` 섹션에 집중됨 (약 20줄)
- **그러나 현재 SKILL.md는 이미 86줄로 목표값 ≤ 200줄을 충분히 만족한다.**
- AC-FR08-b의 절댓값 기준(≤ 200줄)은 현 상태로 통과됨

---

## 4. 정리 범위 결론

### 정리 필요 여부

| 항목 | 결론 |
|------|------|
| `SKILL.md` 줄 수 (현재 86줄) | 목표 ≤ 200줄 **이미 달성** — 추가 삭제 불필요 |
| `skills/dev-monitor/references/*.md` | 디렉토리 **없음** — 작업 없음(no-op) |
| `scripts/monitor-server.py` docstring | **변경 금지** (정리 범위 밖) |
| `docs/monitor-v1/`~`docs/monitor-v4/` | **변경 금지** (역사적 보존) |

### 최종 판정

**SKILL.md 추가 정리 불필요.**

현재 SKILL.md(86줄)는 이미 목표치 이하이므로, PRD §8 "조사 후 범위 한정 선행" 제약에 따라 본 조사 문서에서 **추가 정리 작업 없음**으로 범위를 확정한다.

신규 작성 파일:
- `scripts/test_dev_monitor_skill_md.py` — AC-FR08-a/b/d 자동 검증
- `scripts/test_dev_monitor_trigger.py` — AC-FR08-c 자동 검증

구버전 docs 파일 수 기준값 (AC-FR08-d 검증용):

| 디렉토리 | 파일 수 (조사 시점) |
|----------|---------------------|
| `docs/monitor/` (v1에 해당) | 77 |
| `docs/monitor-v2/` | 82 |
| `docs/monitor-v3/` | 111 |
| `docs/monitor-v4/` | 93 |
