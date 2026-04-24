# v4 기준선 (monitor-server-pre-v5)

TSK-00-01 결과 기록. v5 S1~S8 각 단계의 독립 rollback 기준점.

## 커밋 정보

| 항목 | 값 |
|------|-----|
| 커밋 SHA | `f1e7e7d7509675e8f579acf8282a4d3eafba4b9e` |
| 커밋 메시지 | `chore: DDTR 템플릿 stale .running 삭제 규칙 + idea/todo 업데이트` |
| 태그명 | `monitor-server-pre-v5` |
| 태그 방식 | lightweight tag |
| 태깅 일시 | 2026-04-24 |

## pytest 결과 (`pytest -q scripts/`)

| 항목 | 값 |
|------|-----|
| 실행 결과 | **exit 1 (3 failed)** |
| passed | 1689 |
| failed | 3 |
| skipped | 169 |
| 소요 시간 | 50.68s |

### 실패 목록 (v4 기존 미해결 회귀)

| # | 테스트 파일 | 테스트명 | 실패 원인 |
|---|-------------|----------|-----------|
| 1 | `test_monitor_dep_graph_html.py` | `TestDepGraphCanvasHeight640::test_dep_graph_canvas_height_640` | `height:640px` 문자열 단순 검색 — 실제 구현은 `height:clamp(640px, 78vh, 1400px)` (TSK-04-03 responsive 구현) |
| 2 | `test_monitor_render.py` | `KpiCountsTests::test_done_excludes_bypass_failed_running` | `.running` 시그널이 있는 task가 done 카운트에서 제외되어야 하나 미제외 (1 != 0) |
| 3 | `test_monitor_render.py` | `DepGraphSectionEmbeddedTests::test_canvas_height_640px` | 동일 원인 — `height:640px` 단순 문자열 검색 실패 |

> **판단**: 위 3개 실패는 v5 작업 이전부터 존재하던 v4 코드의 기존 회귀 테스트 오불일치. TSK-00-01 코드 변경 0 제약으로 수정 불가. v5 S1 시작 시 해결 대상으로 분류.

## E2E 테스트 (`scripts/test_monitor_e2e.py`)

| 항목 | 값 |
|------|-----|
| 실행 여부 | 미실행 |
| 사유 | unit pytest 3개 실패로 인해 E2E 실행 선행 조건 미충족 |

> design.md 리스크 섹션: "E2E 실패 시 원인을 baseline.md에 명시하고 pytest가 통과했다면 태그 생성 진행" — 본 경우 unit test 실패이므로 E2E 생략.

## 플러그인 캐시 확인

| 항목 | 값 |
|------|-----|
| 캐시 경로 | `~/.claude/plugins/marketplaces/dev-tools/` |
| 프로젝트 경로 | `/Users/jji/project/dev-plugin/` |
| 구조 | 독립 git 저장소 (별개 `.git/`) |
| monitor-server.py MD5 | `f360c1fc683e146b6713fc0c57d06940` (양쪽 동일) |
| 결과 | **일치 확인** — 핵심 파일 동일 상태 |

## 태그 검증

```bash
$ git tag --list monitor-server-pre-v5
monitor-server-pre-v5

$ git rev-list -n 1 monitor-server-pre-v5
f1e7e7d7509675e8f579acf8282a4d3eafba4b9e
```

## v5 rollback 절차

```bash
# v5 작업 중 S1~S8 임의 단계 rollback 시:
git revert --no-commit <commit-range>
# 또는:
git checkout monitor-server-pre-v5 -- scripts/monitor-server.py
```
