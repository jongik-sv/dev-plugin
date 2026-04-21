# TSK-01-05: pane 캡처 엔드포인트 - 테스트 보고서

## 실행 요약

| 구분        | 통과 | 실패 | 합계 |
|-------------|------|------|------|
| 단위 테스트 | 43   | 0    | 43   |
| E2E 테스트  | 0    | 0    | 0    |
| 합계        | 43   | 0    | 43   |

**결과: test.fail + BLOCKER** — E2E 서버 미기동으로 UI 항목 검증 불가

---

## 단위 테스트 결과

**실행 명령:**
```bash
python3 -m unittest scripts.test_monitor_pane -v
```

**결과: 모두 통과 (43/43 ✅)**

### 테스트 케이스 분류

#### PaneCapturePayloadTests (10/10 pass)
- `test_target_functions_are_defined` ✅ — 함수 존재 확인
- `test_normal_returns_expected_fields` ✅ — dict 반환 구조
- `test_invalid_pane_id_raises_value_error` ✅ — 정규식 위반 → ValueError
- `test_empty_pane_id_raises_value_error` ✅ — 빈 문자열
- `test_empty_capture_yields_empty_lines_list` ✅ — 빈 출력
- `test_small_output_not_truncated` ✅ — truncation 미적용 (500줄 미만)
- `test_truncates_to_max_lines_and_records_original_count` ✅ — truncation 적용 (500줄 초과)
- `test_error_field_is_none_on_success` ✅ — 성공 경로 error field
- `test_capture_failure_message_appears_in_lines` ✅ — stderr 원문 포함
- `test_file_not_found_error_maps_to_tmux_unavailable` ✅ — FileNotFoundError 처리

#### HandlePaneHtmlTests (6/6 pass)
- `test_success_returns_200_html_with_utf8` ✅ — HTTP 200 + Content-Type
- `test_invalid_pane_id_returns_400_html` ✅ — 정규식 위반 → 400 (acceptance 2)
- `test_nonexistent_pane_returns_200_with_capture_failed_message` ✅ — 존재 안함 → 200 + error msg (acceptance 1)
- `test_tmux_not_installed_returns_200_with_error` ✅ — tmux 부재
- `test_handler_falls_back_to_default_max_lines_when_server_missing_attr` ✅ — 기본값 fallback
- `test_cache_control_no_store` ✅ — Cache-Control 헤더

#### RenderPaneHtmlTests (10/10 pass)
- `test_doctype_present` ✅
- `test_contains_pre_with_data_pane_and_lines` ✅
- `test_footer_contains_captured_at` ✅
- `test_inline_script_exactly_once` ✅
- `test_back_link_present` ✅
- `test_xss_payload_escaped_in_pre` ✅ — XSS 이스케이프 (acceptance 4)
- `test_xss_pane_id_escaped_in_data_attr` ✅
- `test_no_external_resource_loading` ✅
- `test_error_payload_renders_capture_failed_message` ✅
- `test_no_meta_refresh` ✅

#### RenderPaneJsonTests (2/2 pass)
- `test_includes_all_required_fields` ✅ — 모든 필드 동반
- `test_line_count_present_on_error_path` ✅ — 에러 경로에서도 line_count (acceptance 3)

#### PanePathPrefixTests (6/6 pass)
- `test_pane_html_path_matches` ✅
- `test_api_pane_path_matches` ✅
- `test_api_pane_path_with_query_matches` ✅
- `test_pane_html_does_not_match_api_pane` ✅ — 순서 보장 (overbroad 방지)
- `test_bare_prefixes_still_match` ✅
- `test_url_double_encoding_normalizes_via_unquote` ✅

#### HandlePaneJsonTests (9/9 pass)
- JSON 응답 구조 및 헤더 검증

---

## E2E 테스트 상태

**BLOCKER — 서버 미기동**

### 1-7단계 실행 결과

```
e2e-server.py 호출:
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/e2e-server.py start \
  --cmd "python3 scripts/monitor-server.py --port 7321 --docs docs" \
  --url "http://localhost:7321" --timeout 120
```

**응답:**
```json
{
  "status": "server_crashed",
  "url": "http://localhost:7321",
  "exit_code": 0,
  "elapsed": 2.0,
  "log_tail": [
    "monitor-server.py: HTTP bootstrap not yet wired (TSK-01-01 pending)."
  ]
}
```

### 근본 원인

`scripts/monitor-server.py` line 1556-1559:
```python
# TSK-01-01 will replace this block with argparse + HTTPServer bootstrap.
if __name__ == "__main__":
    sys.stderr.write(
        "monitor-server.py: HTTP bootstrap not yet wired (TSK-01-01 pending).\n"
    )
```

**분류:** Pre-existing (Task 범위 밖)
- TSK-01-05의 핸들러(`_render_pane`, `_api_pane`, `_pane_capture_payload`)는 완전히 구현됨
- HTTP 부트스트랩(argparse, HTTPServer 기동)은 TSK-01-01 책임
- dev-test SKILL.md Step 1-7 Step C에서 서버 기동 실패 → Phase 즉시 종료

### QA 체크리스트 — E2E 항목

| 항목 | 상태 | 사유 |
|------|------|------|
| (클릭 경로) 대시보드 → Team → [show output] 클릭 | unverified | 서버 미기동 |
| (화면 렌더링) `<pre class="pane-capture">` + 2초 fetch | unverified | 서버 미기동 |

---

## QA 체크리스트 최종 판정

### 단위 테스트로 검증 (모두 pass)

- ✅ (정상) `_pane_capture_payload("%1")` 반환 구조 및 필드
- ✅ (정상) `_render_pane("%1")` HTML 구조, 백링크, 인라인 JS
- ✅ (정상) `_api_pane("%1")` JSON 필드 + `line_count` 동반
- ✅ (에러) 정규식 위반 → 400
- ✅ (에러) 존재 안함 pane → 200 + error msg (acceptance 1)
- ✅ (에러) JSON 응답에 `line_count` (acceptance 3)
- ✅ (엣지) ANSI escape 제거 (TSK-01-03 위임)
- ✅ (엣지) truncation (500줄 경계)
- ✅ (보안) XSS 이스케이프 (`</pre><script>alert(1)</script>`)
- ✅ (보안) 외부 리소스 로딩 0건 (정규식 검사, acceptance 4)
- ✅ (보안) subprocess 호출 0건 (TSK-01-03 위임)
- ✅ (보안) FileNotFoundError → 200 + "tmux not available"
- ✅ (통합) 라우트 매칭 순서 (`/api/pane/` 우선)
- ✅ (통합) double-encoding 정규화 (`%251` → `%1`)

### E2E 필수 항목 (미검증)

- ⛔ (클릭 경로) 실제 대시보드 링크 클릭
- ⛔ (화면 렌더링) 브라우저 렌더 + 2초 fetch 동작 확인

---

## 정적 검증 (Step 2.5)

**Lint 실행:**
```bash
python3 -m py_compile scripts/monitor-server.py
```

**결과:** ✅ 통과 (문법 에러 없음)

---

## 최종 판정

**상태: test.fail**

### 사유

**BLOCKER — 서버 부트스트랩 미구현**

dev-test SKILL.md Step 1-7 Step C에 따라:
- 서버 기동 실패(`status: server_crashed`)
- 분류: Pre-existing (Task 범위 밖, TSK-01-01 pending)
- 조치: Phase 즉시 종료, 재시도 대상 아님

### 권장 조치

1. **TSK-01-01 완료** — HTTP 부트스트랩 구현
2. **TSK-01-05 재실행** — `/dev TSK-01-05`

단위 테스트는 모두 통과했으므로, 서버 부트스트랩 완료 후 E2E 재실행만 필요.

---

**생성일시:** 2026-04-21  
**Task:** TSK-01-05  
**Domain:** fullstack  
**Source:** WBS
