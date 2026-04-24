# Feature: monitor-skill-optimization

## 요구사항

모니터 스킬(dev-monitor)의 코드와 프롬프트에서 **중복·불합리 지점을 제거**한다. 아키텍처 변경은 범위 밖이고, monitor-v5 WBS가 놓고 간 정리 잔여물만 치운다.

### 범위 A — Dead code 제거

- `scripts/monitor_server/core.py:171` 주변의 `_t()` 첫 정의 블록 삭제. Python 후방 정의 규칙으로 `core.py:1269`의 재정의에 의해 죽은 코드. 모든 호출부(4084, 4092, 4098, 5211, 5217, 5220, 5221, 5223)는 1269 바인딩.
  - 삭제 전 171 블록 내 식별자 grep. 해당 블록 외부에서 참조되는 심볼이 있으면 1269 블록 앞으로 이주.

### 범위 B — Launcher ↔ Server 정리

| # | 항목 | 파일:라인 | 처리 |
|---|------|-----------|------|
| B1 | PID 파일 포맷 불일치 | `monitor-server.py:224-225` vs `monitor-launcher.py:185-186` | server도 JSON으로 통일. 스키마 `{"pid": int, "port": int, "project_root": str}`. 기존 평문 PID 파일과의 하위호환은 `read_pid_record()`가 이미 담당. |
| B2 | `stop_server_by_project()` vs `stop_server(port)` 95% 중복 | `monitor-launcher.py:207-249` | 단일 `stop_server(*, project=None, port=None)`로 병합. |
| B3 | `read_pid()` 래퍼 | `monitor-launcher.py:92-100` | 호출부 전수 치환 후 래퍼 삭제. |
| B4 | 플랫폼 분기 자체 구현 | `monitor-launcher.py:162-182` | `scripts/_platform.py:IS_WINDOWS` 재사용. |
| B5 | 과한 try/except `setattr` | `monitor-server.py:110-113` | 위에서 `hasattr` 검증됨 — 예외 블록 제거. |
| B6 | 과한 try/except `unlink(missing_ok=True)` 후 OSError | `monitor-server.py:189-191` | `missing_ok`로 이미 안전 — try/except 제거. |
| B7 | `signal.signal()` silent swallow | `monitor-server.py:203-206` | 최소 stderr 경고 한 줄. |

**제외**: `--no-tmux` 플래그(검증 결과 정상 동작), `project_key()` 충돌(2^48 공간에서 실사용 non-issue).

### 범위 C — SKILL.md 프롬프트 슬림

- **C1**: `skills/dev-monitor/SKILL.md` L19–26(인자 파싱 표) + L48–66(플로우 상세에서 PORT/DOCS/ACTION 추출 재설명) → L48–66 재설명은 "§0 인자 참조" 한 줄로 치환.
- **C2**: L77–86 응답 확인 섹션의 curl/Python wrapper 정당화 문단 → `scripts/http-probe.py`로 수행한다는 1~2줄로 축약.

**유지**: YAML 프런트매터(`name`, `description` NL 트리거), monitor-v5 TSK-05-02 제약 "≤200줄"(현재 86줄, 여유 충분).

## 배경 / 맥락

- monitor-v5 WBS가 `monitor-server.py` 6937줄 모놀리스를 `scripts/monitor_server/` 패키지로 분할하고 모든 15 Task를 `[xx]` 완료 처리.
- 분할 후에도 `core.py`가 7731줄로 재-팽창한 상태. 본 feat는 **구조 변경 없이** 리모델링 잔해만 제거한다.
- core.py 분할과 인라인 CSS/JS 외부화는 별도 WBS로 분리 — 인라인 상수는 `get_static_bundle()`(core.py:2574)에서 서빙되는 live source-of-truth임을 확인.

## 도메인

backend

## 진입점 (Entry Points)

N/A (UI 없음, 백엔드/인프라/문서 정리 feat)

## 비고

- 작업 순서: **A → B(launcher → server 순) → C**. B1(JSON 포맷)은 server가 최종 consumer이므로 launcher 기존 JSON 쓰기 유지, server만 조정.
- 테스트: `pytest tests/monitor_server/` + 기동/정지 smoke + `/static/style.css` `/static/app.js` 응답 200 확인.
- 크로스 플랫폼: `_platform.IS_WINDOWS` False 분기가 `start_new_session=True`를 여전히 전달하는지 단위 확인. Windows 실기 검증은 본 feat 범위 밖.
- 전 범위에서 회귀 없음을 최우선 — 의심 변경은 되돌리고 재검토.
