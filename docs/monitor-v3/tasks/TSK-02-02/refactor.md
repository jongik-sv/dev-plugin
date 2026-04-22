# TSK-02-02: 리팩토링 내역

## 변경 사항

| 파일 | 변경 내용 (요약) | 적용 기법 (콤마 구분) |
|------|-----------------|----------------------|
| `scripts/monitor-server.py` | lang 정규화 로직 `_normalize_lang()` 헬퍼로 추출 — `_t()`, `render_dashboard()`, `_route_root()` 3곳에 중복된 `if lang not in _I18N: lang = "ko"` 패턴을 단일 함수로 통합 | Extract Method, Remove Duplication |

**상세:**
- `_normalize_lang(lang: str) -> str` 순수 함수를 `_I18N` 상수 직후 (line 68)에 추가.
- `_t()` 내부의 `_I18N.get(lang) or _I18N["ko"]` fallback 로직을 `_I18N[_normalize_lang(lang)]` 1줄로 단순화.
- `render_dashboard()` 내 3줄 정규화 블록(`if lang not in _I18N: lang = "ko"`)을 `lang = _normalize_lang(lang)` 1줄로 교체.
- `_route_root()` 내 동일한 2줄 패턴을 `_normalize_lang(...)` 인라인 호출로 교체.

## 테스트 확인
- 결과: PASS
- 실행 명령: `python3 -m pytest -q scripts/test_monitor_render.py -k "section_title or lang or i18n or normalize"`
- 25/25 통과. `test_section_titles_korean_default`, `test_section_titles_english_with_lang_en` 포함 전체 i18n 관련 테스트 통과 확인.

## 비고
- 케이스 분류: **A (성공)** — 리팩토링 변경 적용 후 단위 테스트 전체 통과.
- `scripts/` 전체 테스트(`pytest -q scripts/`)에서 pre-existing 실패(TSK-02-02와 무관한 다른 Task 영역)가 존재하나, 리팩토링 전후 실패 목록 비교 결과 새로 실패한 테스트 0건 확인. 회귀 없음.
