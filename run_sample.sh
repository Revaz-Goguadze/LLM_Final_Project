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

# Get issues sorted by line DESC (bottom-up) to prevent line shift problems
# When fixing multiple issues, start from bottom of file so earlier fixes don't shift later line numbers
ISSUE_ORDER=$(python -c "
import json
d = json.load(open('bug_report.json'))
issues = d.get('consolidated_issues', [])
# Sort by (file, line) descending - fix bottom of each file first
indexed = [(i, iss.get('file',''), iss.get('line',0)) for i, iss in enumerate(issues)]
indexed.sort(key=lambda x: (x[1], -x[2]))  # file ASC, line DESC
print(' '.join(str(i) for i, _, _ in indexed))
" 2>/dev/null || echo "")

ISSUE_COUNT=$(echo "$ISSUE_ORDER" | wc -w | tr -d ' ')
echo "Found $ISSUE_COUNT issues to fix (bottom-up order: $ISSUE_ORDER)"

for i in $ISSUE_ORDER; do
  echo "=== Fixing issue $i ==="
  .venv/bin/python main.py fix "$i" || echo "Failed to fix issue $i, continuing..."
done

echo "=== Done: attempted to fix $ISSUE_COUNT issues ==="
