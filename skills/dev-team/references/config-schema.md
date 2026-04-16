# wp-setup.py config JSON 스키마

`{TEMP_DIR}/wp-setup-config.json`을 Write 도구로 작성한다:

```json
{
  "project_name": "{PROJECT_NAME}",
  "window_suffix": "{WINDOW_SUFFIX}",
  "temp_dir": "{TEMP_DIR}",
  "shared_signal_dir": "{SHARED_SIGNAL_DIR}",
  "docs_dir": "{DOCS_DIR}",
  "wbs_path": "{DOCS_DIR}/wbs.md",
  "session": "{SESSION}",
  "model_override": "{MODEL_OVERRIDE}",
  "worker_model": "{WORKER_MODEL}",
  "wp_leader_model": "{WP_LEADER_MODEL}",
  "plugin_root": "{PLUGIN_ROOT}",
  "on_fail": "{ON_FAIL}",
  "wps": [
    {
      "wp_id": "WP-01",
      "team_size": {TEAM_SIZE},
      "tasks": ["TSK-01-01", "TSK-01-02"],
      "execution_plan": "Level 0: TSK-01-01 (즉시)\nLevel 1: TSK-01-02 (TSK-01-01 의존)"
    }
  ]
}
```

## 필드 설명

| 필드 | 값 |
|------|-----|
| `project_name` | `$(basename "$(pwd)")` |
| `plugin_root` | 이 플러그인의 루트 디렉토리 (`${CLAUDE_PLUGIN_ROOT}` 또는 절대 경로) |
| `model_override` | `--model opus` 지정 시 `"opus"`, 미지정 시 빈 문자열 `""` |
| `wps[].tasks` | 해당 WP의 모든 TSK-ID 배열 (`[xx]` 포함 — 스크립트가 자동 필터링) |
| `on_fail` | 테스트 실패 시 동작 모드: `strict`/`bypass`/`fast` (기본값: `bypass`) |
| `wps[].execution_plan` | 2단계에서 산출한 레벨별 실행 계획 텍스트 |
