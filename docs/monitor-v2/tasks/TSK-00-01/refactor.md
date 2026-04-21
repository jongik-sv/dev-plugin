# TSK-00-01: 리팩토링 내역

## 변경 사항

| 파일 | 변경 내용 (요약) | 적용 기법 |
|------|-----------------|-----------|
| `docs/monitor-v2/prototype.html` | `eventClass()` 함수의 불필요한 `|| ev === 'refactor.ok'` 중복 조건 제거 (`ev.indexOf('.ok') >= 0`로 이미 처리됨) | Remove Duplication |
| `docs/monitor-v2/prototype.html` | CSS `.pane-preview`, `.drawer-full-output`의 하드코딩 `#0d1117` → `var(--bg)` 교체 | Replace Magic Number |
| `docs/monitor-v2/prototype.html` | `renderActivityFeed()` 인라인 스타일(`color:var(--text3);font-family:ui-monospace,monospace;font-size:11px;`) → CSS 클래스 `.activity-tsk` 추출 | Extract Class, Remove Duplication |
| `docs/monitor-v2/prototype.html` | `renderWPCard()` 반복 패턴 `total ? (x/total)*100 : 0` → `toPct(count, total)` 헬퍼 함수로 추출 | Extract Method |
| `docs/monitor-v2/prototype.html` | `renderWPCard()` 반복 패턴 `tasks.filter(function(t){ return t.status===st; }).length` → `countByStatus(tasks, status)` 헬퍼 함수로 추출 | Extract Method |

## 테스트 확인

- 결과: PASS
- 실행 명령: `python3 scripts/validate-prototype.py docs/monitor-v2/prototype.html`
- 단위 테스트: N/A (frontend domain, 정적 파일)

## 비고

- 케이스 분류: A (성공) — 리팩토링 변경 적용 후 E2E 검증 통과
- `eventClass()` 수정: `refactor.ok`는 `.ok` 서픽스를 포함하므로 첫 번째 조건(`indexOf('.ok') >= 0`)에서 이미 처리됨. `|| ev === 'refactor.ok'`는 도달 불가 코드였음
- CSS variable 통일: `--bg` 변수가 `:root`에 `#0d1117`로 정의되어 있어 시각적 변화 없이 동작 보존
- 새 헬퍼 함수 `countByStatus`, `toPct`는 `renderWPCard` 위에 배치하여 사용 전 선언 순서를 명확히 함
