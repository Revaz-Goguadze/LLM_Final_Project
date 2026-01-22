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
.venv/bin/python main.py fix 0
