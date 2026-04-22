# TSK-01-03: pane 상세 페이지 URL 인코딩 버그 수정 - 설계

## 요구사항 확인
- 브라우저가 `%` 문자를 `%25`로 자동 재인코딩하여 `/pane/%250` 요청이 오는 문제를 해결한다.
- 링크 생성 측(`_render_pane_row`)에서 `urllib.parse.quote(pane_id, safe="")`로 URL-encode하고, 라우터 측(`do_GET`)에서 `urllib.parse.unquote`로 디코딩 후 `_PANE_ID_RE` 검증을 수행한다.
- 기존 `_PANE_ID_RE` 정규식(`^%\d+$`)은 변경하지 않으며, 디코딩 후 검증이므로 기존 패턴 그대로 유효하다.

## 타겟 앱
- **경로**: N/A (단일 앱 — `scripts/monitor-server.py` 단일 파일 구조)
- **근거**: dev-monitor는 모노레포 없이 `scripts/` 디렉토리의 단일 Python 파일 서버 구조다.

## 구현 방향
- `scripts/monitor-server.py`의 2개 지점을 수정한다.
- **렌더 측 수정**: `_render_pane_row` 함수(~2183번째 줄)에서 `/pane/` href를 생성할 때 `pane_id_raw`에 `urllib.parse.quote(pane_id_raw, safe="")`를 적용하여 `%0` → `%250`으로 인코딩된 href를 생성한다. `data-pane-expand` 속성의 JS fetch에는 이미 `encodeURIComponent`가 적용되므로 raw 값 유지.
- **라우터 측 수정**: `do_GET`에서 `/pane/` 경로와 `/api/pane/` 경로의 pane_id 추출 직후(3696, 3699번째 줄 근처) `urllib.parse.unquote`를 적용하여 `%250` → `%0`으로 복원한 뒤 `_handle_pane_html`/`_handle_pane_api`로 전달한다.
- `urllib.parse` import에 `unquote`, `quote`를 추가한다(현재 `urlsplit`만 임포트).

## 파일 계획

**경로 기준:** 모든 파일 경로는 프로젝트 루트 기준으로 작성한다.

| 파일 경로 | 역할 | 신규/수정 |
|-----------|------|-----------|
| `scripts/monitor-server.py` | URL 인코딩/디코딩 2개 지점 수정 + import 추가 | 수정 |
| `scripts/test_monitor_pane.py` | `test_pane_route_decodes_percent_encoded`, `test_pane_link_quotes_pane_id` 테스트 추가 | 수정 |

## 진입점 (Entry Points)

N/A — `domain=backend`이므로 UI 진입점 항목 불필요.

## 주요 구조

- **`_render_pane_row(pane, preview_lines)`** (`scripts/monitor-server.py` ~2149): pane HTML row 렌더러. `/pane/` href에 `quote(pane_id_raw, safe="")`를 적용하도록 수정한다. `data-pane-expand`는 JS가 `encodeURIComponent`로 처리하므로 raw `pane_id_raw` 유지.
- **`do_GET(self)`** (`scripts/monitor-server.py` ~3688): HTTP GET 라우터. pane_id 추출(3696, 3699번째 줄) 직후 `unquote(pane_id)`를 호출하여 핸들러로 전달한다.
- **`_pane_capture_payload(pane_id, ...)`** (`scripts/monitor-server.py` ~3225): pane_id 유효성 검증(`_PANE_ID_RE.fullmatch`) — 변경 없음. unquote 후 `%0` 형태가 되면 기존 정규식이 그대로 매칭한다.
- **`capture_pane(pane_id)`** (`scripts/monitor-server.py` ~270): tmux subprocess 호출 — 변경 없음. 이미 정상 `%\d+` pane_id를 받는다고 가정.
- **`urllib.parse` import** (41번째 줄): `urlsplit` 외에 `unquote`, `quote` 추가.

## 데이터 흐름

```
[링크 생성]
pane_id_raw ("%0")
  → quote(pane_id_raw, safe="") → "%250"
  → href="/pane/%250" 렌더링

[라우터 처리]
브라우저 요청 GET /pane/%2525  (브라우저가 %250의 %를 재인코딩)
  실제 HTTP 수신: GET /pane/%250   (HTTP 경로 레벨에서 %25→%)
  path 추출 후 pane_id = "%250"
  → unquote("%250") → "%0"
  → _PANE_ID_RE.fullmatch("%0") → pass
  → capture_pane("%0") → 200 응답
```

> 참고: 브라우저 동작 — `href="/pane/%250"` 링크를 클릭하면 브라우저가 `%25`를 리터럴 `%`로 인식하지 않고 이미 인코딩된 것으로 처리하여 `/pane/%250`이 HTTP 요청으로 전달된다. 따라서 서버는 `%250`을 unquote하면 `%0`을 얻는다.

## 설계 결정 (대안이 있는 경우만)

- **결정**: 라우터 `do_GET` 내 pane_id 추출 직후에 `unquote` 적용
- **대안**: `_handle_pane_html`/`_handle_pane_api` 함수 내부에서 `unquote` 적용
- **근거**: 라우터에서 1회 처리하면 HTML/API 두 핸들러 모두를 커버하며 중복을 피한다. 함수 시그니처 변경 없이 기존 단위 테스트(`_handle_pane_html`, `_handle_pane_api` 직접 호출 테스트)에서는 이미 디코딩된 pane_id가 전달되던 기존 계약이 유지된다.

- **결정**: `_render_pane_row`에서 `href="/pane/{quote(pane_id_raw, safe="")}"` 적용, `data-pane-expand`에는 raw 값 유지
- **대안**: `data-pane-expand`도 quote 적용
- **근거**: `data-pane-expand`는 JS가 `encodeURIComponent(paneId)`로 fetch URL을 구성하므로(3173번째 줄 `_PANE_JS`) 이미 올바르게 처리된다. raw 값을 유지해야 JS encodeURIComponent가 정확히 동작한다.

## 선행 조건
- 없음 (`_PANE_ID_RE`, `capture_pane`, 라우터 구조 모두 이미 존재)

## 리스크

- **LOW**: `urllib.parse.unquote`를 이미 URL-decoded된 pane_id에 한 번 더 적용할 경우 `%` 자체를 포함하는 엣지 케이스가 있을 수 있으나, tmux pane_id 형식은 `^%\d+$`로 한정되어 있어 실제 충돌 없음.
- **LOW**: `do_GET` 내 unquote 추가로 인해 기존 `_handle_pane_html`/`_handle_pane_api` 직접 호출 단위 테스트에는 영향 없음(이미 디코딩된 값 전달 패턴 유지). 단, 통합 경로(서버 요청 시뮬레이션) 테스트는 새 동작 기준으로 검증 필요.

## QA 체크리스트

- [ ] `GET /pane/%250` 요청 시 `capture_pane`에 `%0`이 전달되어 200 응답이 반환된다 (`test_pane_route_decodes_percent_encoded`)
- [ ] `_render_pane_row` 가 생성한 HTML의 `/pane/` href에 `%25`가 포함된다 (pane_id=`%0` 기준) (`test_pane_link_quotes_pane_id`)
- [ ] `GET /pane/%251` 요청 시 `capture_pane`에 `%1`이 전달된다 (다른 ID에도 동일 동작 확인)
- [ ] `GET /api/pane/%250` 요청 시 동일하게 `%0`으로 디코딩되어 JSON 200 응답 반환
- [ ] 잘못된 입력 `GET /pane/%25xx` 는 unquote 후 `%xx`가 되어 `_PANE_ID_RE` 불일치 → 400 반환
- [ ] 빈 pane_id `GET /pane/` 는 unquote 후에도 빈 문자열 → 400 반환 (regression)
- [ ] `_render_pane_row` 내 `data-pane-expand` 속성은 raw `pane_id` 유지 (JS encodeURIComponent 의존)
- [ ] `python3 -m py_compile scripts/monitor-server.py` 오류 없음
- [ ] 기존 `test_monitor_pane.py` 전체 테스트 regression 없이 통과
- [ ] 기존 `pytest -q scripts/` 전체 regression 없이 통과
