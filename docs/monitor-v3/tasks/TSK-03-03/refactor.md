# TSK-03-03: 리팩토링 내역

## 변경 사항

| 파일 | 변경 내용 (요약) | 적용 기법 (콤마 구분) |
|------|-----------------|----------------------|
| `scripts/monitor-server.py` | `_handle_static` 내 중첩 `_send_404` 로컬 함수를 모듈 레벨 `_send_plain_404`로 추출; `_route_not_found`의 중복 응답 블록 제거 후 `_send_plain_404` 위임; `plugin_root` 조회를 기존 `_server_attr` 헬퍼로 대체 | Extract Method, Remove Duplication |

### 세부 변경 내용

1. **`_send_plain_404(handler)` 모듈 레벨 추출** (Static file route helpers 섹션 상단)
   - `_handle_static` 내부에 있던 중첩 `def _send_404()` 클로저를 모듈 레벨 공유 함수로 추출.
   - 기존에는 `_handle_static`과 `_route_not_found`가 동일한 404 응답 코드 4줄을 독립적으로 갖고 있었음.

2. **`_route_not_found` 중복 제거**
   - `_route_not_found`의 body/send_response/send_header/end_headers/write 5줄을 `_send_plain_404(self)` 단일 호출로 교체.

3. **`plugin_root` 조회를 `_server_attr` 헬퍼 통일**
   - 기존: `getattr(getattr(handler, "server", None), "plugin_root", None) or _resolve_plugin_root()`
   - 변경: `_server_attr(handler, "plugin_root") or _resolve_plugin_root()`
   - 코드베이스 전반에서 이미 사용 중인 `_server_attr` 헬퍼(line 3721)를 재사용하여 defensive getattr 패턴의 일관성 확보.

## 테스트 확인
- 결과: PASS
- 실행 명령: `python3 -m unittest scripts/test_monitor_static.py -v`
- 통과: 34/34 (재시도 없음)

## 비고
- 케이스 분류: A (성공) — 리팩토링 변경 적용 후 테스트 통과.
- 동작 변경 없음: 모든 외부 HTTP 응답(상태 코드, 헤더, 본문)은 리팩토링 전후 동일.
- `_send_plain_404` 위치를 Static file route helpers 섹션 최상단에 배치하여 의존 관계가 명확하게 드러나도록 함.
