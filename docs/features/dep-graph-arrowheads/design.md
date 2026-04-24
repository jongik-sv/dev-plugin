# dep-graph-arrowheads - 설계

## 요구사항 확인
- dev-monitor 대시보드의 Task Dependency Graph에서 일부 엣지(가장자리 방향)에 삼각형 화살표 머리(arrowhead)가 표시되지 않는 버그를 수정한다.
- 모든 엣지에 일관되게 삼각형 머리를 표시하여, 의존 방향(source → target)을 시각적으로 즉시 식별할 수 있어야 한다.
- 수정 대상은 `skills/dev-monitor/vendor/graph-client.js`의 cytoscape 엣지 스타일 정의다.

## 타겟 앱
- **경로**: N/A (단일 앱)
- **근거**: dev-plugin 단일 저장소. `skills/dev-monitor/vendor/graph-client.js`가 직접 수정 대상이다.

## 근본 원인 분석

### 현재 구현 (graph-client.js lines 372-385)

```js
{
  selector: "edge",
  style: {
    "width": "data(width)",          // 일반 엣지=1, 크리티컬=3
    "line-color": "data(color)",
    "target-arrow-color": "data(color)",
    "target-arrow-shape": "triangle",
    "curve-style": "bezier",
  },
},
```

### 특정된 결함

**결함 1 — `arrow-scale` 누락 (주원인)**

cytoscape.js에서 `target-arrow-shape: triangle`만 지정하면 화살표 크기는 기본값(1.0 × line-width)이 적용된다. `width: 1`인 일반 엣지의 경우 화살표 머리가 1px 크기로 렌더링되어, zoom 수준·화면 해상도·dagre 레이아웃 결과에 따라 사실상 보이지 않거나 다른 요소에 가려진다. 이것이 "가장자리 엣지에서만 안 보인다"는 현상의 직접 원인이다: 그래프 가장자리(외곽) 노드 사이의 엣지는 상대적으로 길고, 레이아웃 상 끝단이 viewport 밖이거나 anti-aliasing이 안 먹히는 위치에 오면 작은 arrowhead가 소실된다.

**결함 2 — `target-arrow-color`가 `data(color)`에 묶여 있음**

`_addEdge()`에서 엣지에 `color` 필드를 명시적으로 설정하지만(`ed.is_critical ? COLOR.edge_critical : COLOR.edge_default`), delta 갱신 경로에서 엣지 color를 갱신하는 로직이 없다(기존 엣지는 applyDelta가 삭제 후 재추가하지 않고 그냥 keep). `data(color)` 값이 undefined가 될 경우 cytoscape는 화살표를 투명 또는 기본 검정으로 렌더링하여 어두운 배경 대시보드에서 보이지 않는다.

**결함 3 — `curve-style: bezier` + 짧은 엣지에서의 마커 클리핑**

bezier 곡선에서 start/end control point가 edge 노드 범위 내로 클리핑될 경우, cytoscape 내부에서 `target-endpoint`가 노드 경계 안쪽에 위치하게 되어 화살표 머리가 노드 HTML 레이블 아래에 가려진다. 특히 `nodeHtmlLabel` 플러그인이 DOM overlay를 추가하므로 z-index 충돌로 화살표가 시각적으로 덮인다.

## 구현 방향

1. cytoscape 엣지 스타일에 `"arrow-scale": 2` (또는 `2.5`)를 추가하여 화살표 크기를 line-width에 독립적으로 고정한다. 이 값은 일반 엣지(width=1)와 크리티컬 엣지(width=3) 모두에 충분한 크기로 설정한다.
2. `"target-arrow-color": "data(color)"` 대신 고정 색상(`#475569` 기본, `#ef4444` 크리티컬)을 엣지별 selector로 분리하거나, `data(color)` 기반을 유지하되 기본값 fallback을 보장하는 방식으로 수정한다. 가장 단순한 해결책은 일반/크리티컬 엣지를 selector로 분리하는 것이다.
3. 노드 HTML 레이블 overlay에 의한 arrowhead 가림 문제는 `"target-distance-from-node": 4`를 추가하여 엣지 끝점을 노드 경계에서 일정 거리 떨어뜨린다.

## 파일 계획

| 파일 경로 | 역할 | 신규/수정 |
|-----------|------|-----------|
| `skills/dev-monitor/vendor/graph-client.js` | cytoscape 엣지 스타일 정의 수정 (`arrow-scale`, `target-distance-from-node` 추가, color fallback 보장) | 수정 |

## 진입점 (Entry Points)

이 feature는 신규 페이지나 라우트 추가 없이 기존 대시보드(dep-graph 섹션)의 렌더링 수정이다. 사용자 진입 경로는 "dev-monitor 대시보드 접속 → Dependency Graph 섹션 확인"이며, URL/라우터 파일 추가는 해당 없다.

- **사용자 진입 경로**: dev-monitor 서버 기동(`python3 scripts/monitor-launcher.py`) → 브라우저에서 `http://localhost:7321` 접속 → "의존성 그래프 / Dependency Graph" 섹션 확인
- **URL / 라우트**: `http://localhost:7321` (기존 루트 경로, 변경 없음)
- **수정할 라우터 파일**: 해당 없음 (기존 라우트 변경 없음)
- **수정할 메뉴·네비게이션 파일**: 해당 없음 (메뉴 구조 변경 없음)
- **연결 확인 방법**: dev-monitor 서버 기동 후 대시보드 접속 → Dependency Graph 섹션에서 모든 엣지에 삼각형 화살표 머리가 표시되는지 시각적으로 확인

## 주요 구조

- **`init()` (line 332)**: cytoscape 인스턴스 생성. `style` 배열 내 edge selector 수정이 이루어지는 위치.
- **edge selector 스타일 객체 (lines 373-381)**: `selector: "edge"` 블록. `arrow-scale`와 `target-distance-from-node` 추가.
- **`_addEdge()` (line 129)**: 엣지 추가 시 color 데이터 설정. `target-arrow-color`를 data에서 직접 읽는 방식 유지 (기본값 보장 추가).
- **`.bottleneck` selector (lines 382-384)**: 참고용. edge 선택자 수정 시 이 selector 뒤에 추가 edge style이 필요하면 여기에 추가.

## 데이터 흐름

`/api/graph` 폴링 → `applyDelta(data)` → `_addEdge(ed)` (color, width data 설정) → cytoscape 렌더링 → 수정된 edge style로 `arrow-scale: 2` + `target-distance-from-node: 4` 적용 → 모든 엣지에 가시적 삼각형 arrowhead 표시.

## 설계 결정 (대안이 있는 경우만)

**결정 1 — `arrow-scale: 2` 전역 적용**
- **결정**: edge selector에 `"arrow-scale": 2` 단일 값을 전역 추가
- **대안**: 일반/크리티컬 엣지를 별도 selector로 분리하여 각각 다른 `arrow-scale` 지정
- **근거**: 단일 값으로 두 케이스 모두 커버 가능하며 코드 변경 최소화. 크리티컬 엣지는 `width: 3`으로 이미 강조되므로 arrowhead 크기 차별화 불필요.

**결정 2 — `target-distance-from-node: 4` 추가**
- **결정**: edge 끝점을 노드 경계에서 4px 띄워 HTML 레이블 overlay 하단에 arrowhead가 가리지 않도록 함
- **대안**: z-index 조정으로 arrowhead를 HTML 레이블 위에 렌더링
- **근거**: cytoscape-node-html-label 플러그인의 DOM overlay z-index를 건드리면 다른 인터랙션(click, hover)이 영향받을 수 있음. distance 옵션이 더 안전하고 예측 가능.

**결정 3 — `line-fill` 제외**
- **결정**: `line-fill` 속성은 수정하지 않음
- **대안**: `"line-fill": "solid"` 명시
- **근거**: bezier 엣지에서 기본값이 solid이며, 증상과 무관.

## 선행 조건
- 없음 (외부 라이브러리 버전 변경 불필요, cytoscape.min.js 교체 불필요)

## 리스크

- **LOW**: `arrow-scale: 2` 값이 노드가 밀집된 그래프에서 arrowhead끼리 겹쳐 보일 수 있음. 실제 사용 화면(노드 5~20개, LR rankDir)에서는 `rankSep: 120`이 충분한 간격을 제공하므로 문제 없을 것으로 판단.
- **LOW**: `target-distance-from-node: 4`이 너무 클 경우 화살표가 노드에서 멀어 보일 수 있음. 2~4 범위에서 조정 가능.
- **LOW**: cytoscape.min.js 버전(현재 2016-2024 Copyright)에 따라 `arrow-scale` 지원 여부가 달라질 수 있음. 현재 번들은 `arrow-scale`을 지원하는 v3.x 이상이므로 문제 없음.

## QA 체크리스트

- [ ] 일반 엣지(non-critical, width=1)에서 삼각형 arrowhead가 엣지 끝(target 노드 쪽)에 가시적으로 표시된다.
- [ ] 크리티컬 패스 엣지(critical, width=3, 빨간색)에서도 삼각형 arrowhead가 정상 표시된다.
- [ ] 그래프 가장자리(좌측 끝 / 우측 끝 / 상하 끝) 노드와 연결된 엣지에서도 arrowhead가 표시된다.
- [ ] zoom-out(ZOOM_MIN=0.7) 상태에서도 arrowhead가 육안으로 식별 가능하다.
- [ ] zoom-in(ZOOM_MAX=2.0) 상태에서 arrowhead가 노드 HTML 레이블에 가려지지 않는다.
- [ ] 필터 적용(TSK-05-02 `applyFilter`) 후 dim된 엣지의 arrowhead도 동일하게 dim 상태로 유지된다.
- [ ] 2초 폴링으로 그래프가 갱신된 후에도 arrowhead가 유지된다(delta 경로에서 arrow 소실 없음).
- [ ] (클릭 경로) dev-monitor 서버 기동 → `http://localhost:7321` 접속 → Dependency Graph 섹션에서 엣지의 arrowhead가 표시된다.
- [ ] (화면 렌더링) 노드가 1개 이상 있을 때 모든 의존 관계 엣지에 arrowhead가 렌더링되고 방향이 올바르다 (source→target).
