# WP 완료 전 브라우저 visible 검증 (brw-test)

WP 리더가 `wp-leader-cleanup.md` 단계 3(팀리더 완료 보고) **직전**에 수행한다. 헤드리스 측정만으로 완료 보고 금지 (사용자 지시, `feedback_e2e_browser_verify.md` 근거).

## 0. Pre-flight — 잔존 프로세스 정리 (필수)

Playwright MCP는 세션 간 Chrome 프로파일을 재사용하므로 이전 호출의 잔존 Chrome이 profile lock을 보유할 수 있다. 아래 cleanup을 **반드시 선행**한다:

```bash
pkill -f 'user-data-dir=.*mcp-chrome-' 2>/dev/null
sleep 2
```

> **증상**: 이 단계를 생략하면 `Error: Browser is already in use for /Users/.../mcp-chrome-<hash>, use --isolated to run multiple instances of the same browser` 실패 반복. 원인: MCP 서버가 다음 호출을 위해 Chrome을 살려두는 설계인데, 세션 간 graceful close 보장이 없음.

## 1. MCP 선택

| MCP | 사용 | 이유 |
|-----|------|------|
| `mcp__plugin_playwright_playwright__*` | ✅ | standalone Chrome, 이 환경에서 동작 확인 |
| `mcp__plugin_ecc_playwright__*` | ❌ | "Playwright MCP Bridge" 브라우저 확장 필요, 미설치 시 `Extension connection timeout` |

확장이 설치되어 있지 않은 기본 환경에서는 반드시 `plugin_playwright` 사용.

## 2. 검증 절차

각 구현 컴포넌트/페이지에 대해:

1. **dev 서버 기동** — 해당 패키지 디렉토리에서 `pnpm dev` 또는 관련 entry. 포트 기록.
2. **browser_navigate** — `http://localhost:{port}/{path}` 접속
3. **browser_take_screenshot** — `docs/tasks/{TSK-ID}/screenshots/brw-{컴포넌트}.png` 로 저장. `fullPage: true` 권장.
4. **browser_console_messages** (level: error) — 치명적 콘솔 에러 확인 (favicon 404 등 benign은 무시)
5. **browser_evaluate** — 스타일/레이아웃 진단:
   ```js
   () => ({
     stylesheetCount: document.styleSheets.length,
     rulesTotal: Array.from(document.styleSheets).reduce((n, s) => { try { return n + s.cssRules.length; } catch { return n; } }, 0),
     // 대상 루트 요소의 computed style 샘플
     rootComputed: (() => {
       const el = document.querySelector('{대상 루트 셀렉터}');
       if (!el) return null;
       const cs = getComputedStyle(el);
       return { display: cs.display, background: cs.backgroundColor, padding: cs.padding, height: cs.height };
     })(),
     // 외부 라이브러리(form-js/radix 등) CSS 로드 여부
     externalCssLoaded: Array.from(document.styleSheets).some(s => s.href && s.href.includes('form-js'))
   })
   ```
6. **화면 육안 판단** — 팀리더(사용자)가 screenshot 파일을 열어보는 것도 가능하도록 파일 경로를 signal에 기록.

## 3. 시그널 기록 포맷

`{WT_NAME}.done` 본문 특이사항 섹션에 다음 형식으로 한 줄 또는 블록:

```
brw-test: OK — {검증한 컴포넌트/페이지 목록} visible Playwright 확인 (docs/tasks/{TSK-ID}/screenshots/brw-*.png). styleSheets={n}, externalCssLoaded={true|false}. 콘솔 error={favicon 등 benign만|N건 발견 — 상세 후속}.
```

NG 판정(스타일 깨짐·콘솔 error 비-benign·컴포넌트 미렌더):
```
brw-test: NG — {문제 요약}. screenshot: {경로}. 복구 제안: {원인 가설}.
```

## 4. Post-flight — 정리

검증 완료 후 `mcp__plugin_playwright_playwright__browser_close`를 호출해 tab close. Chrome 프로세스 자체는 MCP가 유지하지만 다음 WP 리더의 Pre-flight cleanup에서 처리된다.
