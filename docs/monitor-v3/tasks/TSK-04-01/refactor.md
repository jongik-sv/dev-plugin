# TSK-04-01: 리팩토링 내역

## 변경 사항

| 파일 | 변경 내용 (요약) | 적용 기법 |
|------|-----------------|-----------|
| `scripts/test_monitor_static.py` | 두 클래스(`TestHandleStatic`, `TestNodeHtmlLabelStaticRoute`)에 중복 정의된 vendor dir setup 로직을 모듈 레벨 `_make_vendor_dir()` 헬퍼로 추출 | Extract Method, Remove Duplication |
| `scripts/test_monitor_static.py` | `TestHandleStatic.test_static_route_whitelist_allows_vendor_js` 검증 대상을 4종 → 5종으로 정확히 수정 (TSK-04-01 이후 whitelist 항목 수 반영) | 명세 일치 수정 |
| `scripts/test_monitor_static.py` | `TestIsStaticPath.test_whitelist_constant_has_four_entries` 메서드명을 `test_whitelist_constant_has_five_entries`로 수정 (메서드명이 내부 단언 `assertEqual(len, 5)`과 불일치하던 오류 수정) | Rename |
| `scripts/test_monitor_static.py` | `TestDepGraphScriptLoadOrder._import_server_mod()` 불필요한 단계 제거 — `_get_section_html` 내에서 `_mod`를 직접 참조 | Inline |

`scripts/monitor-server.py`의 구현 코드(`_STATIC_WHITELIST`, `_section_dep_graph`, `_is_static_path`, `_handle_static`)는 이미 충분히 정돈된 상태로 변경 없음.

## 테스트 확인
- 결과: PASS
- 실행 명령: `python3 -m unittest scripts.test_monitor_static -v`
- 결과: 48/48 OK (0 failures, 0 errors)
- 정적 검증: `python3 -m py_compile scripts/monitor-server.py scripts/dep-analysis.py` → OK

## 비고
- 케이스 분류: A (리팩토링 성공 — 변경 적용 후 테스트 통과)
- 구현 파일(`monitor-server.py`)은 리팩토링 불필요. 테스트 파일에서 Extract Method + Rename + Inline 3가지 기법을 적용하여 중복 제거 및 명세 일치성 향상.
- `test_whitelist_constant_has_four_entries` 메서드명 오류는 TSK-04-01 빌드 시점에 수정되지 않은 채 남아있던 naming drift — 리팩토링에서 수정.
