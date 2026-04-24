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

## pytest 전체 결과 (`pytest -q scripts/`) — 2026-04-24 기준

| 항목 | 값 |
|------|-----|
| 실행 결과 | **exit 1 (41 failed)** |
| passed | 1739 |
| failed | 41 |
| skipped | 31 |
| 소요 시간 | ~30s |

### 실패 분류

| 분류 | 파일 | 개수 | 원인 |
|------|------|------|------|
| v5 새 기능 TDD Red | `test_monitor_filter_bar_e2e.py` | 25 | TSK-05-01 필터바 구현 전 Red 상태 (build TDD 정상) |
| v5 새 기능 TDD Red | `test_monitor_graph_filter_e2e.py` | 3 | TSK-05-02 graph domain/model 필드 미구현 (build TDD 정상) |
| v4 디자인 회귀 | `test_monitor_e2e.py` | 10 | v3 디자인 클래스 변경 (`sticky-hdr`→cmdbar, `page` div 제거) + Google Fonts preconnect 외부링크 |
| v4 기존 회귀 | `test_monitor_dep_graph_html.py` | 1 | `height:640px` 단순 검색 — 실제 구현 `clamp(640px, 78vh, 1400px)` (TSK-04-03) |
| v4 기존 회귀 | `test_monitor_render.py` | 2 | `height:640px` 단순 검색 + `running` 시그널 done 제외 버그 |

#### v4 기존 회귀 상세 (3개 — 코드 변경 0 제약으로 수정 불가)

| # | 테스트 | 실패 원인 |
|---|--------|-----------|
| 1 | `test_monitor_dep_graph_html.py::TestDepGraphCanvasHeight640::test_dep_graph_canvas_height_640` | `height:640px` 단순 검색 실패 — 실제 구현 `clamp(640px, 78vh, 1400px)` (TSK-04-03 responsive 구현 후 테스트 미갱신) |
| 2 | `test_monitor_render.py::KpiCountsTests::test_done_excludes_bypass_failed_running` | `.running` 시그널 task가 done 카운트에서 미제외 (1 != 0) |
| 3 | `test_monitor_render.py::DepGraphSectionEmbeddedTests::test_canvas_height_640px` | 동일 — `height:640px` 단순 검색 실패 |

## unit 테스트만 (`pytest -q scripts/` `--ignore` E2E 파일들) — v4 기준선

`test_monitor_e2e.py`, `test_monitor_filter_bar_e2e.py`, `test_monitor_graph_filter_e2e.py` 제외 시:

| 항목 | 값 |
|------|-----|
| passed | 1663 |
| failed | **3** (위 v4 기존 회귀 3개) |
| skipped | 25 |
| exit code | 1 |

> **판단**: v4 코드 자체의 단위 테스트 실패는 3개이며, 모두 TSK-04-03 구현 후 테스트 미갱신과 `.running` 시그널 done 계산 버그다. v5 S1에서 수정 대상으로 분류.

## E2E 테스트 (`python3 scripts/test_monitor_e2e.py`)

| 항목 | 값 |
|------|-----|
| 직접 실행 결과 | 10 failed, 69 passed, 2 skipped |
| 실패 원인 | v3 디자인 리팩터링 후 옛 클래스 단언 미갱신 (`sticky-hdr`, `page` div 등) + Google Fonts preconnect 외부링크 단언 |

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
