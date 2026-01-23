#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

if [[ ! -d ".venv" ]]; then
  python -m venv .venv
  .venv/bin/pip install -r requirements.txt
fi

: "${OPENAI_TIMEOUT:=45}"

rm -rf .vector_store .bm25

.venv/bin/python main.py index --path sample
.venv/bin/python main.py index-docs --path docs
.venv/bin/python main.py analyze --path sample --query "review sample code for security, logic, and performance issues"

ISSUE_COUNT=$(python -c "import json; d=json.load(open('bug_report.json')); print(len(d.get('consolidated_issues', [])))" 2>/dev/null || echo "0")
echo "Found $ISSUE_COUNT issues to fix"

for i in $(seq 0 $((ISSUE_COUNT - 1))); do
  echo "=== Fixing issue $i ==="
  .venv/bin/python main.py fix "$i" || echo "Failed to fix issue $i, continuing..."
done

echo "=== Done: attempted to fix $ISSUE_COUNT issues ==="
