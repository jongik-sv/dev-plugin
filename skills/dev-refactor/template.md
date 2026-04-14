# {TSK-ID}: 리팩토링 내역

## 변경 사항

| 파일 | 변경 내용 (요약) | 적용 기법 (콤마 구분) |
|------|-----------------|----------------------|
| path/to/file-a.ts | 중복 검증 로직을 공용 함수로 추출 | Extract Method, Remove Duplication |
| path/to/file-b.ts | 예약어와 충돌하는 변수명 개선 | Rename |
| path/to/file-c.ts | 100줄짜리 함수 3단계로 분리 | Extract Method |

적용 기법 예: Extract Method, Inline, Rename, Remove Duplication, Replace Magic Number, Simplify Conditional, Introduce Parameter Object 등. 변경 없음이면 표 대신 "변경 없음(기존 코드가 이미 충분히 정돈됨)" 한 줄로 대체.

## 테스트 확인
- 결과: PASS / FAIL
- 실행 명령: (사용한 테스트 명령)
- (실패 시 되돌린 범위 기재 — 부분 되돌림 금지, 항상 전체 되돌림)

## 비고
- 케이스 분류 (SKILL.md 단계 3 참조): A (성공) / B (rollback 후 통과) / C (pre-existing regression 의심)
- (그 외 특이사항, 없으면 생략)
