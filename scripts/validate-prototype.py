#!/usr/bin/env python3
"""정적 HTML 프로토타입 수용 기준 검증 스크립트 (TSK-00-01).

Usage: python3 scripts/validate-prototype.py [html_path]
Exit 0 = PASS, Exit 1 = FAIL
"""
import re
import sys

html_path = sys.argv[1] if len(sys.argv) > 1 else "docs/monitor-v2/prototype.html"

try:
    with open(html_path, encoding="utf-8") as f:
        content = f.read()
except FileNotFoundError:
    print(f"FAIL: {html_path} not found", file=sys.stderr)
    sys.exit(1)

errors = []

# 외부 자원 금지 (src/href에 http 또는 // 프로토콜)
for m in re.findall(r'(?:src|href)=["\'](https?://|//)[^"\']*', content):
    errors.append(f"External resource detected: {m}")

# 필수 구조 요소 존재 확인
required = {
    "conic-gradient": "conic-gradient (도넛 차트)",
    "polyline": "SVG polyline (스파크라인)",
    "<rect": "SVG rect (타임라인)",
    "drawer": "드로어 골격",
    "kpi": "KPI 카드",
    "DOMContentLoaded": "JS 초기화",
}
for kw, desc in required.items():
    if kw not in content:
        errors.append(f"Missing required element: {desc} ({kw!r})")

if errors:
    for err in errors:
        print(f"FAIL: {err}", file=sys.stderr)
    sys.exit(1)

print(f"PASS: {html_path} validation OK ({len(required)} checks, no external resources)")
