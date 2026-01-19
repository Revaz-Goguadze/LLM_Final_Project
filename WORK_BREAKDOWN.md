# CodeReview AI — Work Breakdown for an Implementation Agent

This breakdown is optimized for an autonomous coding agent: **small tasks**, **clear files to touch**, and **testable acceptance criteria**.

## Epic A — CLI + config alignment

### Task A1 — Consolidate configuration
**Files:** `codereview/config.py`, `config/example.yaml`, `main.py`

Requirements:
- Support configuration precedence:
  1. CLI flags
  2. YAML config (optional)
  3. env vars
  4. defaults
- All model IDs must be settable without editing code.

Acceptance:
- Running `python main.py analyze ...` uses the configured model IDs.

### Task A2 — Expand CLI flags to match docs
**Files:** `main.py`, `docs/rag_usage.md`

Requirements:
- Add flags:
  - `--use-rag/--no-use-rag`
  - `--use-docs-rag/--no-use-docs-rag`
  - `--top-k`, `--docs-top-k`
  - `--show-context`
  - `--context-out <path>`

Acceptance:
- Flags appear in `--help` and work.

---

## Epic B — Multi-file transactional fix loop

### Task B1 — Identify patch-touched files
**Files:** new `codereview/diff_utils.py`, tests

Requirements:
- Parse unified diff text and return a list of touched file paths.

Acceptance:
- Unit test: given a multi-file diff, function returns both files.

### Task B2 — Snapshot all touched files
**Files:** `codereview/fixer.py`

Requirements:
- Before applying patch/replace, capture pre-image of every touched file.
- Store in memory and optionally on disk under `runs/<run_id>/snapshots/`.

Acceptance:
- Unit test: after snapshot, modifying file and calling rollback restores.

### Task B3 — Atomic apply + verify + rollback
**Files:** `codereview/agent.py`, `codereview/fixer.py`, tests

Requirements:
- Apply fix.
- If verification fails, rollback all touched files.
- If verification passes, clear backups.

Acceptance:
- Integration test: multi-file patch + failing verification → all restored.

---

## Epic C — Evidence-aligned fixes

### Task C1 — Extend fix payload schema
**Files:** `codereview/agent.py` (payload validation), docs

Requirements:
- Require at least one of:
  - `before_context` (exact string to match) OR
  - `hunk_header` + `hunk_context`
- Reject fixes that cannot be matched in file content.

Acceptance:
- Unit tests cover accept/reject cases.

### Task C2 — Restrict to changed lines
**Files:** `codereview/report_generator.py`, `codereview/agent.py`

Requirements:
- If the issue was derived from diff-changed line(s), enforce overlap.
- Allow override only with explicit flag (e.g., `--allow-outside-diff`).

Acceptance:
- Unit test: reject a fix that changes an unrelated part of the file.

---

## Epic D — Agent state machine + logging

### Task D1 — Add run directory logging
**Files:** `codereview/agent.py`

Requirements:
- Create `runs/<run_id>/`.
- Write:
  - `issue.json`
  - `context.txt`
  - `attempt_<n>_prompt.txt`
  - `attempt_<n>_raw_llm.txt`
  - `attempt_<n>_payload.json`
  - `attempt_<n>_verification.txt`

Acceptance:
- After running `fix`, directory exists with the above.

### Task D2 — Make the agent an explicit state machine
**Files:** new `codereview/agent_state.py`, update `agent.py`

Requirements:
- State enum and transition rules.
- Deterministic retry strategy.

Acceptance:
- Tests validate that repeated identical fix is detected and stops.

---

## Epic E — Non-Python chunking

### Task E1 — Add tree-sitter chunker (JS/TS)
**Files:** `codereview/chunker.py`, `requirements.txt`, tests

Requirements:
- Use tree-sitter to identify function/class boundaries.
- Preserve start/end lines.

Acceptance:
- Unit test chunking `.js` fixture returns expected chunk count.

### Task E2 — Indexer includes non-Python files
**Files:** `codereview/indexer.py`

Requirements:
- Index `.js/.ts/.tsx/.jsx` files.

Acceptance:
- A fixture project indexes those files and retrieval returns them.

---

## Epic F — Evaluation plots integrated

### Task F1 — Expand metrics and save detailed results
**Files:** `codereview/evaluator.py`

Requirements:
- Add F1.
- Track per-category metrics.
- Save `evaluation/results_details.json`.

Acceptance:
- Evaluate produces both summary and details.

### Task F2 — Generate plots
**Files:** new `codereview/eval_plots.py` or `visualize_results.py` replacement

Requirements:
- Produce plots into `evaluation/plots/`.

Acceptance:
- Evaluate command produces PNGs.

