# CodeReview AI — Roadmap & Delivery Milestones (No-Timeline)

This roadmap is ordered by **dependency** and **risk reduction**, not by dates.

## Milestone 0 — Repo hygiene & alignment
**Goal:** Make the project predictable for other agents/contributors.

Deliverables:
- Single source of truth for config (env + optional YAML) and model IDs
- Remove/mark deprecated modules (`codereview/docs_rag.py`) or clearly document their status
- Ensure CLI flags match docs (or update docs)
- Add a `CONTRIBUTING.md` (coding standards, testing commands)

Acceptance criteria:
- `python -m pip install -r requirements.txt` succeeds on a clean env
- `python main.py --help` documents all commands and flags
- `docs/` reflects actual behavior

## Milestone 1 — Multi-file transactional fix loop
**Goal:** Fix loop is safe for real-world diffs that touch multiple files.

Deliverables:
- Determine touched files for a patch (parse unified diff headers)
- Snapshot *all* touched files before applying any patch/replacement
- Apply patch/replace; if verification fails, rollback all touched files
- Ensure rollback works even if git is unavailable (file snapshot fallback)

Acceptance criteria:
- Unit test: multi-file patch → verification fails → all files restored byte-for-byte
- Unit test: patch check fails → no files modified

## Milestone 2 — Evidence-aligned fixes
**Goal:** Prevent “correct-looking but wrong-location” fixes.

Deliverables:
- Extend fix schema to require one of:
  - `target_hunk` (diff hunk header + local context), OR
  - `before_context` (exact text to match) + `after_context` (replacement)
- Enforce that the fix touches:
  - The same file(s) as the reported issue, AND
  - A line range that overlaps changed lines (unless explicitly allowed)

Acceptance criteria:
- Unit tests for:
  - Rejecting fixes that modify unrelated files
  - Rejecting replacements that do not match evidence/changed lines

## Milestone 3 — Real agent/state machine + trajectory logging
**Goal:** Make the fix loop debuggable and deterministic.

Deliverables:
- Explicit state machine:
  - VALIDATE_ISSUE → BUILD_CONTEXT → GENERATE_FIX → VALIDATE_FIX → APPLY → VERIFY → DONE/RETRY/FAIL
- Persist a `runs/<run_id>/` folder with:
  - prompts, LLM outputs, normalized payload, patch/replacement, verification output
- Implement bounded retries with strategy:
  - Attempt 1: normal
  - Attempt 2: add verification output + widen context
  - Attempt 3: force patch format

Acceptance criteria:
- Integration test: failing fix attempts generate run artifacts
- Re-running a run with the saved payload reproduces the same apply/verify result

## Milestone 4 — Non-Python chunking (tree-sitter)
**Goal:** Better retrieval for JS/TS/other languages.

Deliverables:
- Tree-sitter based chunker for:
  - JavaScript / TypeScript (minimum)
- File-type routing:
  - `.py` → AST
  - `.js/.ts/.tsx/.jsx` → tree-sitter
  - fallback → whole file

Acceptance criteria:
- Unit tests chunk boundaries on small fixtures
- Indexer includes those files and retrieval returns them

## Milestone 5 — Evaluation expansion + plots integrated into CLI
**Goal:** Make evaluation output “assignment-grade” and product-useful.

Deliverables:
- Metrics: add F1, per-category metrics, false-positive taxonomy
- Save:
  - `evaluation/results_summary.json`
  - `evaluation/results_details.json`
- Generate plots (matplotlib) under `evaluation/plots/`:
  - precision/recall/F1 bar
  - per-category found vs expected
  - per-role model comparison
  - confidence calibration curve

Acceptance criteria:
- `python main.py evaluate ...` produces plots and JSON
- `visualize_results.py` either works or is removed/replaced with the new pipeline

## Milestone 6 — Quality hardening
Deliverables:
- Add tests for:
  - patch apply failure
  - rollback on verify failure
  - report filtering alignment to changed lines
  - retriever scoring stability
- Add CI config (GitHub Actions) to run unit tests

Acceptance criteria:
- Tests run in CI and pass
