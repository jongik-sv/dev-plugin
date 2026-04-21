# TSK-01-07: 리팩토링 내역

## 변경 사항

| 파일 | 변경 내용 (요약) | 적용 기법 (콤마 구분) |
|------|-----------------|----------------------|
| `scripts/test_monitor_e2e.py` | `import json as _json` (3곳)와 `import urllib.parse` (1곳)를 메서드 내부 로컬 import에서 모듈 상단 top-level import로 이동 | Remove Duplication |

적용 범위: `test_monitor_e2e.py` 전체 파일. TSK-01-07 신규 추가 클래스 `FeatureSectionE2ETests._api_state()`의 `import json as _json` 제거가 직접 대상이나, 동일 패턴이 기존 `PaneCaptureEndpointTests`의 두 메서드에도 존재하여 파일 수준에서 일괄 정리.

`scripts/monitor-server.py` 및 `scripts/test_monitor_scan.py`: TSK-01-07 범위 코드(`ScanFeaturesEdgeCaseTests`, `scan_features`, `_section_features`, `_build_state_snapshot.features`)는 이미 충분히 정돈됨. 변경 없음.

## 테스트 확인

- 결과: PASS
- 실행 명령: `python3 -m unittest discover -s scripts -p "test_monitor*.py" -v`
- 전체 256 tests, 0 failures, 16 skipped (E2E — 서버 미기동 시 skipUnless 정상 동작)

## 비고

- 케이스 분류: A (성공) — 리팩토링 변경 적용 후 단위 테스트 통과.
- `import json`과 `import urllib.parse`를 top-level로 올려 PEP 8 표준 스타일을 따르고 메서드 호출마다 반복되는 로컬 import를 제거했다. 동작 변경 없음.
- `scripts/monitor-server.py`와 `scripts/test_monitor_scan.py`의 신규 코드는 네이밍·분기·중복 모두 문제 없어 추가 변경 불필요.
