# TSK-02-03: 리팩토링 내역

## 변경 사항

| 파일 | 변경 내용 (요약) | 적용 기법 |
|------|-----------------|-----------|
| `scripts/monitor-server.py` | `_DASHBOARD_JS` 내 `openDrawer`/`closeDrawer`의 backdrop+drawer DOM 조작 중복 제거 → `_setDrawerOpen(open)` 내부 헬퍼로 추출 | Extract Method, Remove Duplication |
| `scripts/monitor-server.py` | click 이벤트 위임의 `e.target.hasAttribute&&e.target.hasAttribute(...)` 반복 패턴 → `_hasAttr(el, attr)` 헬퍼로 추출, `e.target` 지역 변수 `t`로 중복 참조 제거 | Extract Method, Rename, Remove Duplication |

### 변경 상세

**`_setDrawerOpen(open)` 추출 (openDrawer/closeDrawer 중복 제거)**

- 리팩토링 전: `openDrawer`와 `closeDrawer` 각각에서 `document.querySelector('[data-drawer-backdrop]')`/`document.querySelector('[data-drawer]')` 두 번씩 쿼리 + `classList.add/remove('open')` + `removeAttribute/setAttribute('aria-hidden')` — 4줄 × 2 = 8줄 중복
- 리팩토링 후: `_setDrawerOpen(open)` 헬퍼가 두 요소를 배열로 순회하여 단일 로직으로 처리 → `openDrawer`/`closeDrawer` 각각 1줄 호출

**`_hasAttr(el, attr)` 추출 (click 위임 간결화)**

- 리팩토링 전: `e.target.hasAttribute&&e.target.hasAttribute('attr')` 패턴 3회 등장, `e.target` 직접 참조 반복
- 리팩토링 후: `_hasAttr(el, attr)` 헬퍼 + 지역 변수 `t = e.target` 도입으로 가독성 향상

**_DASHBOARD_JS 라인 수**: 125줄 → 126줄 (250줄 제한 준수)

## 테스트 확인

- 결과: PASS
- 실행 명령: `python3 -m unittest discover scripts/ -v`
- TSK-02-03 범위 (`test_monitor_drawer.py`) 46/46 통과
- 전체 351개 중 1건 실패 (`test_server_attributes_injected`): 리팩토링 전후 동일하게 실패하는 pre-existing 에러 (포트 점유 순서 의존성, TSK-02-03 범위 외)
- lint (`py_compile`): PASS

## 비고

- 케이스 분류: A (리팩토링 성공 — 변경 적용 후 테스트 통과)
- `test_server_attributes_injected` 실패는 `discover` 실행 시 타 테스트의 7321 포트 점유 잔존으로 인한 간헐적 실패이며, 리팩토링 전에도 동일하게 발생하는 pre-existing 에러임을 stash 비교로 확인함.
