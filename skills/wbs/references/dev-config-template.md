# Dev Config 템플릿

`skills/wbs/SKILL.md`가 WBS 생성 시 헤더 블록과 첫 번째 WP 사이에 삽입하는 `## Dev Config` 섹션의 기본 템플릿. TRD의 기술 스택 정보를 참조하여 값을 채우고, 추론할 수 없는 항목은 사용자에게 확인한다.

- `fullstack` domain은 unit/e2e 명령이 있는 모든 domain을 순차 실행 (fail-fast)
- `-` = 해당 테스트 N/A (해당 domain에는 그 유형의 테스트가 없음)
- `Cleanup Processes`는 테스트 실행 후 정리할 프로세스 이름(node, vitest 등). Dev Config 로딩 단에서 `run-test.py`가 사용한다

```markdown
## Dev Config

### Domains
| domain | description | unit-test | e2e-test |
|--------|-------------|-----------|----------|
| backend | Server API | `your-unit-test-cmd` | `your-e2e-test-cmd` |
| frontend | Client UI | `your-unit-test-cmd` | `your-e2e-test-cmd` |
| database | Data layer | - | - |
| fullstack | Full stack | - | - |

### Design Guidance
| domain | architecture |
|--------|-------------|
| backend | Your backend architecture description |
| frontend | Your frontend architecture description |

### Cleanup Processes
node, vitest
```
