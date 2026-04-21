# TSK-01-01: 리팩토링 내역

## 변경 사항

| 파일 | 변경 내용 (요약) | 적용 기법 |
|------|-----------------|-----------|
| `scripts/monitor-server.py` | `:root`에 `--font-mono` CSS custom property 추가 | Extract Variable (CSS) |
| `scripts/monitor-server.py` | `ol.phase-list li`의 하드코딩된 `font-family: "SFMono-Regular", Consolas, monospace` → `var(--font-mono)` | Remove Duplication |
| `scripts/monitor-server.py` | `.task-row .id`의 동일 폰트 선언 → `var(--font-mono)` | Remove Duplication |
| `scripts/monitor-server.py` | `.task-row .elapsed, .task-row .retry`의 동일 폰트 선언 → `var(--font-mono)` | Remove Duplication |
| `scripts/monitor-server.py` | `.pane-preview`의 동일 폰트 선언 → `var(--font-mono)` | Remove Duplication |

**변경 요약**: `DASHBOARD_CSS` 내에서 `"SFMono-Regular", Consolas, monospace` 폰트 스택이 4개 셀렉터에 동일하게 하드코딩되어 있었다. `:root`에 `--font-mono` CSS 변수를 추가하고 4곳을 `var(--font-mono)`로 일괄 교체하여 중복을 제거했다. CSS 라인 수: 262 → 263줄 (변수 선언 1줄 추가, 3줄 단축 상쇄 후 순 +1줄). v1 CSS 변수 15개 및 모든 기능 클래스는 그대로 보존.

## 테스트 확인

- 결과: PASS
- 실행 명령: `python3 -m unittest discover scripts/ -v`
- 통과 수: 319 tests, 0 failures, 5 skipped (skipped는 E2E 서버 연결 테스트로 정상)
- `python3 -m py_compile scripts/monitor-server.py`: PASS

## 비고

- 케이스 분류: **(A) 리팩토링 성공** — 변경 적용 후 테스트 통과.
- CSS 라인 수 263줄 (400줄 상한 내, 여유 137줄).
- `--font-mono` 변수는 v1 CSS 변수 네이밍 컨벤션(`--`접두사)을 따르며, 이후 Task(TSK-01-02~06)에서 추가되는 CSS에서도 동일 변수를 재사용할 수 있다.
