# Decisions Log 템플릿

`decisions.md`는 LLM이 모호한 상황에서 자율적으로 내린 결정을 사후 감사 가능한 형태로 보존하는 append-only 로그다. dev-plugin의 모든 phase 스킬(`dev-design`, `dev-build`, `dev-test`, `dev-refactor`, `wbs`, `feat`, `dev-team` merge)은 비자명한 결정을 할 때 이 로그에 entry를 append한다.

## 위치 규약

| 범위 | 경로 |
|---|---|
| WBS Task | `docs/tasks/{TSK-ID}/decisions.md` |
| Feature | `docs/features/{name}/decisions.md` |
| 프로젝트 전역 (PRD auto-resolve 등) | `docs/decisions.md` |

## 파일 헤더

```markdown
# Decisions Log — {scope-label}

> Append-only audit trail of autonomous decisions made during DDTR/feat/wbs cycles.
> Edit prior entries forbidden — record reversals as new entries instead.
```

## Entry 스키마

```markdown
## D-{NNN} ({UTC ISO timestamp})
- **Phase**: design | build | test | refactor | wbs | feat-intake | prd-resolve | dev-team-merge | wbs-resolve
- **Decision needed**: <모호했던 점 / 누락된 사양>
- **Decision made**: <실제 채택한 결정>
- **Rationale**: <PRD/TRD/유사 코드/도메인 규약 등 근거>
- **Reversible**: yes | no    (선택)
- **Source**: <파일:라인 또는 commit SHA — 근거 증거>    (선택)
```

## 호출 규약

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/decision-log.py append \
  --target docs/tasks/TSK-04-02 \
  --phase design \
  --decision-needed "캐시 만료 정책 PRD 미명시" \
  --decision-made "TTL 5분 + LRU 100 entries" \
  --rationale "TRD §4.1 메모리 200MB 상한 + 메모리 캐시 컨벤션(monitor-server.py:1245)" \
  --reversible yes \
  --source "docs/TRD.md:78"
```

## 비자명한 결정 판별 휴리스틱

다음 중 **하나라도** 해당하면 `decisions.md`에 기록한다:

1. PRD/TRD/spec에 명시되지 않은 항목을 가정으로 채워야 한다
2. 같은 요구를 만족하는 둘 이상의 구현 방식 중 하나를 선택해야 한다
3. 요구가 모순되거나 모호해서 한쪽으로 해석을 고정해야 한다
4. 라이브러리·프레임워크·런타임 선택 자유도가 있다
5. 에러 처리·타임아웃·리트라이·캐시 등 정책 파라미터를 정해야 한다
6. 모델 선택, 의존성 해석, 스코프 추정 같은 운영 결정을 한다

다음은 기록 **불필요**하다:

- PRD/TRD에 명시된 사항을 그대로 따르는 경우
- 코딩 스타일·변수명·줄바꿈 같은 미시 결정
- 단일 정답이 자명한 경우 (e.g., 1+1 결과)

## 결정 번복 / 정정

기존 entry를 수정하지 않는다. 대신 새 entry를 추가하면서 `Decision needed`에 "D-NNN 번복"을 명시하고 `Rationale`에 번복 사유를 기록한다.

```markdown
## D-007 (2026-04-29T03:00:00Z)
- **Phase**: refactor
- **Decision needed**: D-003 캐시 TTL 5분 결정 번복 검토
- **Decision made**: TTL 30초 + LRU 200 entries로 변경
- **Rationale**: 통합 테스트에서 5분 TTL 시 stale read 비율 18% — TRD §4.3 (1% 이하) 위반
- **Reversible**: yes
- **Source**: docs/tasks/TSK-04-02/test-report.md:integration_stale_read
```

## 검증

phase 종료 verification footer 작성 시 함께 호출한다:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/decision-log.py validate \
  --target docs/tasks/TSK-04-02
```

`{"ok": false, ...}` 응답이 오면 phase 종료를 차단하고 errors 항목을 수정한다.
