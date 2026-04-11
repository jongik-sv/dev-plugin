# Default Dev Config

이 파일은 **feat 모드에서 프로젝트에 `wbs.md` Dev Config도 없고 `{feat_dir}/dev-config.md` 로컬 오버라이드도 없을 때** 사용되는 최종 fallback 값이다.

## Fallback 우선순위

1. `{feat_dir}/dev-config.md` — Feature별 로컬 오버라이드 (있으면 이것만 사용)
2. `{docs_dir}/wbs.md`의 `## Dev Config` 섹션 — 프로젝트 공용 설정
3. 이 파일 — 전역 기본값

feat 모드에서 프로젝트 관습을 커스터마이즈하려면 위 1번 또는 2번에 아래 구조로 작성한다. 로컬 오버라이드 (`{feat_dir}/dev-config.md`) 는 파일 전체가 Dev Config 섹션으로 해석되므로 아래와 동일한 `## Dev Config` 섹션 하나로만 구성한다.

## Dev Config

### Domains
| domain | description | unit-test | e2e-test |
|--------|-------------|-----------|----------|
| default | 단일 도메인 프로젝트 기본값 | - | - |
| backend | 서버 API / 비즈니스 로직 | - | - |
| frontend | 클라이언트 UI | - | - |

### Design Guidance
| domain | architecture |
|--------|-------------|
| default | 단일 책임 원칙, 의존성 역전, 명확한 계층 분리를 우선한다. 기존 코드 패턴이 있으면 그것을 따른다. 테스트 가능한 경계를 명시적으로 정의한다. |
| backend | 라우트/컨트롤러 → 서비스 → 리포지토리 계층. 비즈니스 로직은 서비스 계층에 집중. 외부 의존성은 인터페이스로 추상화. |
| frontend | 표현(presentational)과 컨테이너(container) 관심사 분리. 상태 관리와 렌더링 분리. 불필요한 전역 상태 회피. |

### Quality Commands
| name | command |
|------|---------|
| lint | - |
| typecheck | - |
| coverage | - |

### Cleanup Processes

