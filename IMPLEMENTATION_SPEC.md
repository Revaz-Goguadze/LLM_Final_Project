# CodeReview AI — Implementation Specification

**Purpose:** This document turns the existing project materials (`project.pdf`, `project_spec_gaps.md`, and the current repository) into an implementable, agent-ready specification.

## 0. Context and current state

### 0.1 What exists today
The repository already implements an end-to-end MVP that can:
- Extract git diffs (staged / unstaged / last commit)
- Index a Python codebase into **ChromaDB** + build a **BM25** index
- Index documentation (best-practice markdown) into a separate Chroma collection + BM25
- Run **three LLM graders** (security / logic / performance) + a **judge** that consolidates issues
- Filter issues to those that are severity **high/critical**, confidence ≥ **0.8**, and aligned to **changed diff lines**
- Emit **JSON + Markdown** reports
- Optionally run a fix loop: generate fix → apply → verify → rollback on failure
- Run evaluation on a labeled dataset and compute precision/recall/fix-rate

### 0.2 Known gaps / incomplete items (must-fix to be “fully implemented”)
These are the highest-leverage missing pieces, based on the current repo + `project_spec_gaps.md`:
1. **Multi-file fix transactions** (atomic apply + atomic rollback across multiple files)
2. **Stricter evidence alignment for fixes** (ensure replacement/patch targets the exact diff hunk / changed lines)
3. **A real agentic tool/state machine** (explicit plan/trajectory logging, deterministic retries)
4. **Non-Python chunking support** (tree-sitter or similar)
5. **Evaluation enhancements** (error categories, calibration, plots integrated into CLI)
6. **Hardening & consistency** (docs drift, redundant modules, richer tests)

This spec defines the “target system” and acceptance criteria for those missing pieces.

---

## 1. Product definition

### 1.1 One-sentence goal
A **Cursor-like** code review tool that analyzes **git diffs**, retrieves relevant context from the **codebase + best-practice docs (Dual-RAG)**, uses a **multi-LLM grading + judge** pattern to reduce false positives, and can optionally run a **safe fix loop** with verification and rollback.

### 1.2 Primary user workflows

#### Workflow A — Analyze changes
1. Developer changes code locally.
2. Runs `analyze` on staged/unstaged/last_commit changes.
3. Tool retrieves code + docs context (Dual-RAG).
4. Three graders analyze; judge consolidates.
5. Tool writes `bug_report.json` + `bug_report.md`.

#### Workflow B — Fix a specific issue
1. Developer chooses an issue index/ID from the last report.
2. Runs `fix <issue_id>`.
3. Tool validates issue location + evidence.
4. Agent generates fix payload (patch or replace).
5. Tool applies fix, runs verification command (tests/lint), and rolls back on failure.

#### Workflow C — Evaluate quality on labeled dataset
1. Developer runs `evaluate --dataset <path>`.
2. Tool runs analysis per case, computes precision/recall/fix-rate.
3. Tool saves results JSON and plots.

### 1.3 Scope boundaries (explicit)
In scope for “full implementation”:
- CLI-first product
- Python-first; optional extension to JS/TS via tree-sitter
- Local persistent Chroma DB
- OpenRouter/Gemini-based model calling
- Safe local patching (no remote PR integration)

Out of scope (for now):
- Hosting as a web service
- IDE plugin UX
- Automatic PR commenting
- Running arbitrary project-specific build pipelines beyond configurable `VERIFY_COMMAND`

---

## 2. Functional requirements

### 2.1 CLI requirements

#### Commands
- `index --path <repo_root>`
  - Builds codebase vector index + BM25 index.
- `index-docs --path <docs_dir>`
  - Builds docs vector index + BM25 index.
- `analyze [--staged|--unstaged|--last-commit] [--query "..."]`
  - Runs Dual-RAG + multi-LLM grading + judge.
- `fix <issue_id> [--dry-run] [--no-verify] [--max-attempts N]`
  - Runs fix loop for a chosen issue.
- `evaluate --dataset <path> [--use-rag/--no-use-rag] [--use-docs-rag/--no-use-docs-rag] [--out-dir evaluation]`
  - Runs evaluation and produces plots.

#### Required outputs
- `bug_report.json` (machine-readable)
- `bug_report.md` (human-readable)
- `evaluation/results_summary.json`
- `evaluation/results_details.json` (per-case + per-model details)
- `evaluation/plots/*.png`

### 2.2 Diff extraction requirements
- Must support:
  - `staged`: `git diff --cached`
  - `unstaged`: `git diff`
  - `last_commit`: `git diff HEAD~1 HEAD` (empty on initial commit)
- Must produce:
  - `GitDiff` object: `{staged, unstaged, last_commit, changed_files}`
- Must normalize file paths to match repo-relative paths (consistent with diff headers: `+++ b/<path>`).

### 2.3 Dual-RAG requirements

#### Codebase RAG (Primary)
- Inputs: query built from `(user_query + diff snippet + file paths)`
- Indexing:
  - Chunk by AST (function/class), fallback to module
  - Store metadata: `file_path`, `name`, `type`, `start_line`, `end_line`
- Retrieval:
  - Hybrid ranking = semantic + BM25 (+ HyDE semantic)
  - Return top-K chunks for prompt context

#### Docs RAG (Secondary)
- Inputs: same rag query
- Indexing:
  - Chunk markdown docs by headings
  - Store metadata with `file_path`, `section_id` (and optional title)
- Retrieval:
  - Same HybridRetriever but separate collection + BM25 index path

#### Token budget and formatting
- Build a single “context block” used by graders.
- Enforce max chars / tokens by truncation:
  - Code context block max ~5000 chars
  - Doc context block max ~5000 chars
  - Diff snippet max ~2000 chars in query
- All chunks must include a header with file path + line range.

### 2.4 Multi-LLM grading requirements
- Roles: `security`, `logic`, `performance`
- Each grader must return strict JSON matching **GraderReport**.
- Judge must return strict JSON matching **FinalReport**.
- Confidence constraints:
  - Graders should only output issues with confidence ≥ 0.85
  - Judge filters to severity ∈ {high, critical} and confidence ≥ 0.8
- Evidence constraints:
  - Each issue must include evidence as an exact diff line or exact file excerpt.
  - Evidence must be present in the diff or file content.

### 2.5 Report filtering requirements
A consolidated issue is retained only if:
- severity in {high, critical}
- confidence ≥ 0.8
- `issue.location.file` exists in repo
- file appears in the diff (if diff contains identifiable files)
- `issue.location.line` is one of the changed `+` lines in the diff
- evidence string appears in file content or diff

### 2.6 Fix loop requirements (agentic)
Fix loop must be safe, bounded, and reproducible.

#### Preconditions
Before generating or applying a fix:
- file exists
- issue line is in range
- if evidence provided, evidence must exist in file OR in diff hunk

#### Fix payload schema (strict)
Agent must output JSON only, one of:

**Patch mode:**
```json
{ "format": "patch", "patch": "diff --git a/... b/...\n..." }
```

**Replace mode:**
```json
{ "format": "replace", "start_line": 10, "end_line": 12, "replacement": "..." }
```

Constraints:
- For patch: `git apply --check` must succeed before apply
- For replace: range must be valid; replacement must not be empty; preserve indentation
- No-op detection: if replacement equals current content for that range, reject and retry

#### Verification
- Default: run `VERIFY_COMMAND` (env var, default `pytest`)
- Must capture stdout+stderr
- Must time out (e.g., 60s)

#### Rollback
- Must rollback **all modified files** from the attempt (see Multi-file Transactions).

---

## 3. Non-functional requirements

### 3.1 Reliability and safety
- Never apply a patch that fails `git apply --check`
- Never write outside repository root
- Never modify files not referenced by the patch/issue unless explicitly allowed
- Must rollback on verification failure
- Must be deterministic in retries (bounded attempts)

### 3.2 Observability
- Every analyze/fix/evaluate run must produce an artifact folder:
  - `runs/<run_id>/config.json`
  - `runs/<run_id>/inputs/diff.txt`
  - `runs/<run_id>/prompts/*.txt`
  - `runs/<run_id>/responses/*.json`
  - `runs/<run_id>/fix_attempts/<attempt_n>/*`

### 3.3 Performance
- Indexing should skip common heavy dirs: `.git`, `.chroma`, `.bm25`, `venv`, `node_modules`, `__pycache__`.
- Should support incremental re-indexing of only changed files.

---

## 4. Data models and schemas

### 4.1 Canonical Pydantic models
Target models (align to current `codereview/models.py`, but tighten types):

- `CodeLocation`
  - `file: str` (repo-relative)
  - `line: int | null`
  - `function: str | null`

- `BugIssue`
  - `id: str` (stable identifier; see below)
  - `severity: "critical"|"high"|"medium"|"low"`
  - `type: "security"|"logic"|"performance"|"style"`
  - `location: CodeLocation`
  - `description: str`
  - `evidence: str`
  - `suggested_fix: str`
  - `confidence: float (0..1)`

- `GraderReport`
  - `grader_id: str`
  - `issues: BugIssue[]`
  - `best_practices_violations: BestPracticeViolation[]`
  - `overall_score: float (0..10)`
  - `summary: str`

- `FinalReport`
  - `winner_assessment: str | null`
  - `consolidated_issues: BugIssue[]`
  - `overall_health_score: float (0..10)`
  - `summary: str`

- `GitDiff`
  - `staged: str`
  - `unstaged: str`
  - `last_commit: str`
  - `changed_files: str[]`

### 4.2 Issue IDs (required for “full” implementation)
The system should assign a stable `BugIssue.id` so “fix issue X” remains valid across formats.

Proposed ID format:
- `sha1(<file>|<line>|<type>|<description>)[:10]`

Also maintain report-local index for UX:
- `issue_index` (0..N-1) in markdown output

---

## 5. Detailed pipeline specifications

### 5.1 Analyze pipeline

#### Inputs
- diff selector: staged / unstaged / last_commit / default
- optional user query string

#### Steps
1. `GitAnalyzer.get_diffs()` → choose target diff
2. Build `rag_query` using:
   - user query (if provided)
   - file list extracted from diff
   - diff snippet containing only +/- lines (excluding headers)
3. `HybridRetriever.search(rag_query)` on codebase index → `code_chunks`
4. `HybridRetriever.search(rag_query)` on docs index → `doc_chunks`
5. Build combined prompt input:
   - user query
   - code context block
   - docs context block
   - full git diff
6. Run graders:
   - security grader model
   - logic grader model
   - performance grader model
7. Run judge:
   - consolidate, dedupe, enforce severity/confidence
8. Filter final report by diff alignment + evidence validation
9. Save `bug_report.json` and `bug_report.md`

#### Acceptance criteria
- If no diff is found, analyze exits cleanly.
- If RAG retrieval fails, analysis still runs with diff-only context.
- Output is always valid JSON.

### 5.2 Retrieval algorithm

#### BM25
- Tokenization should split snake_case + camelCase and lowercase.
- Persist BM25 index to `.bm25/index.pkl` (and docs index separately).

#### Semantic
- Use Chroma `query_texts=[query]`.

#### HyDE
- If OpenRouter key present:
  - Generate short hypothetical code snippet from query
  - Run semantic search using that snippet

#### Hybrid merge
- Normalize semantic and bm25 scores to 0..1
- `score = alpha*semantic + (1-alpha)*bm25` (alpha default 0.6)

#### Improvement: diff-aware filtering (recommended)
When diff file list exists, prefer results whose `file_path` is in the diff files.
Implementation options:
- Post-filter rerank boost +0.1 if file is in diff
- Or use Chroma `where` filter if metadata stored supports it

---

## 6. Fix loop and agent specification

### 6.1 Tool/state machine (required upgrade)
Replace the current “lightweight” loop with an explicit state machine.

#### States
- `VALIDATE_ISSUE`
- `BUILD_CONTEXT`
- `GENERATE_FIX`
- `VALIDATE_FIX`
- `APPLY_FIX`
- `VERIFY`
- `ROLLBACK`
- `SUCCESS`
- `FAIL`

#### Actions/tools
- `READ_FILE(file, line, radius)`
- `SEARCH_CODE(query, top_k)`
- `READ_DOCS(query, top_k)`
- `APPLY_PATCH(patch)`
- `APPLY_REPLACE(file, start_line, end_line, replacement)`
- `RUN_VERIFY(command)`
- `ROLLBACK(transaction_id)`

#### Trajectory logging
Persist a JSON log per attempt:
```json
{
  "issue_id": "...",
  "attempt": 1,
  "steps": [
    {"state":"BUILD_CONTEXT", "actions":["READ_FILE","READ_DOCS"], "notes":"..."},
    {"state":"GENERATE_FIX", "model":"...", "prompt_path":"...", "response_path":"..."}
  ]
}
```

### 6.2 Multi-file transaction system (required)
Current rollback is single-file; must be atomic.

#### Transaction design
- Create `FixTransaction` object:
  - `id`
  - `touched_files: list[str]`
  - `backups: dict[file->content]` OR `git stash ref`
  - `patch_text` or `replace_ops`
  - `created_at`

#### Patch transaction
1. Parse patch to identify touched files (from `diff --git a/X b/X`).
2. Snapshot content of every touched file (pre-apply) into transaction.
3. Run `git apply --check`.
4. Apply patch.
5. On verification failure: restore all touched files from backup.

#### Replace transaction
1. Snapshot file(s).
2. Apply replacements.
3. Verify.
4. Rollback restore all touched files.

#### Acceptance criteria
- If patch touches N files and verification fails, all N revert to pre-state.
- No partial application persists.

### 6.3 Evidence/diff alignment for fixes (required)
Enhance fix validation so the agent cannot “fix” unrelated code.

Rules:
- For replace:
  - `start_line..end_line` must overlap changed diff lines OR be within the same diff hunk as the issue line.
- For patch:
  - Patch hunks must apply only to files present in diff (unless user overrides)

Implementation:
- Use parsed diff hunks from `ReportGenerator._parse_changed_lines()` plus a `parse_hunks()` helper that records contiguous ranges.

---

## 7. Evaluation specification

### 7.1 Dataset format
Support JSON array or JSONL.

Each case:
```json
{
  "id": "case-001",
  "diff": "...",
  "query": "optional",
  "expected_issues": [
    {"type":"security", "file":"path.py", "line": 42, "keyword":"sql"}
  ]
}
```

### 7.2 Matching rules
- If expected.type present → must match
- If expected.file present → must match
- If expected.line present and predicted.line present → within ±3 lines
- If expected.keyword present → keyword appears in (description+evidence)

### 7.3 Metrics
Compute:
- Precision = TP / (TP+FP)
- Recall = TP / (TP+FN)
- F1 = 2PR/(P+R)
- Fix rate = (# matched predicted issues with non-empty suggested_fix) / TP

Also compute:
- Per-grader metrics (security/logic/perf) before judge
- Judge metrics (final consolidated)
- Category metrics (by expected type)
- Multi-LLM improvement vs baseline single-model run

### 7.4 Required plots (integrated)
Generate and save:
- `precision_recall_f1.png`
- `performance_by_category.png`
- `per_model_comparison.png`
- `rag_vs_no_rag.png`
- `confidence_calibration.png` (if confidence usable)

Acceptance criteria:
- `evaluate` produces JSON outputs + plots in a single run.

---

## 8. Language support and chunking

### 8.1 Python (must)
- Use `ast.parse`.
- Chunk `FunctionDef`, `AsyncFunctionDef`, `ClassDef`.
- Capture `start_line` and `end_line`.
- If node missing `end_lineno`, approximate end by next node start or EOF.

### 8.2 JavaScript/TypeScript (should)
- Use tree-sitter for parsing.
- Chunk functions/classes/exports.
- Fallback: split by fixed line windows (e.g., 200 lines) if parsing fails.

---

## 9. Hardening tasks (repo hygiene)

### 9.1 Remove/mark deprecated modules
- `codereview/docs_rag.py` appears redundant with `codereview/docs_indexer.py` and should be removed or clearly marked deprecated.

### 9.2 Config unification
- Support a YAML config (like `config/example.yaml`) for:
  - model IDs per role
  - top_k settings
  - alpha weights
  - verify command
- Precedence order:
  1) CLI flags
  2) YAML
  3) env vars
  4) defaults

### 9.3 Consistent docs
- Ensure `docs/rag_usage.md` matches actual CLI flags.

---

## 10. Test plan and acceptance criteria

### 10.1 Unit tests (minimum)
- Diff parsing → changed line mapping
- RAG query builder → includes file list + diff snippet
- Fix payload validation
- Patch apply failure path
- Multi-file rollback restores all files
- Docs indexing splits by headings

### 10.2 Integration tests
- `analyze` on a small temp git repo with a known diff
- `fix` in a temp repo with a failing verification, ensuring rollback
- `evaluate` on a tiny dataset producing correct metrics

### 10.3 Definition of Done (project-level)
- `index`, `index-docs`, `analyze`, `fix`, `evaluate` all work end-to-end
- Fix loop is atomic across multi-file changes
- Evaluation outputs plots + metrics
- Docs match behavior
- Tests cover key failure paths

