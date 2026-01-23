#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

DEMO_MODE=0
if [[ "${1:-}" == "--demo" ]]; then
  DEMO_MODE=1
fi
export DEMO_MODE

if [[ ! -d ".venv" ]]; then
  python -m venv .venv
  .venv/bin/pip install -r requirements.txt
fi

: "${RESET_SAMPLE:=1}"
if [[ "$RESET_SAMPLE" == "1" ]]; then
  git restore -- sample >/dev/null 2>&1 || true
fi

: "${OPENAI_TIMEOUT:=45}"

rm -rf .vector_store .bm25

.venv/bin/python main.py index --path sample
.venv/bin/python main.py index-docs --path docs
.venv/bin/python - <<'PY'
import json
import os
import subprocess

QUERY = "review sample code for security, logic, and performance issues"
demo_mode = os.getenv("DEMO_MODE", "0") == "1"

subprocess.run(
    [".venv/bin/python", "main.py", "analyze", "--path", "sample", "--query", QUERY]
    + (["--demo"] if demo_mode else []),
    check=False,
)

if not os.path.exists("bug_report.json"):
    raise SystemExit(0)

with open("bug_report.json", "r", encoding="utf-8") as f:
    report = json.load(f)

issues = report.get("consolidated_issues", [])
for idx in range(len(issues)):
    subprocess.run([".venv/bin/python", "main.py", "fix", str(idx)], check=False)
PY
