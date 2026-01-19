# Project Goals, Specification, Implementation Status, and Gaps

## 1. Project Goals (Why This Exists)
- Provide a **Cursor-like code review tool** that analyzes git diffs and surfaces high-confidence bugs and bad practices.
- Use **Dual-RAG** (codebase + best-practice docs) to improve context and precision.
- Use **multi-LLM grading** (specialists + judge) to reduce false positives.
- Support an **agentic fix loop** that proposes, applies, verifies, and rolls back fixes safely.
- Provide **quantitative evaluation** (precision/recall/fix success) on labeled datasets.

## 2. High-Level Functional Specification

### 2.1 Input/Output
- **Input**
  - Git diffs: staged, unstaged, or last commit.
  - Optional user query for targeted analysis.
  - Optional dataset for evaluation.
- **Output**
  - JSON report of consolidated issues.
  - Markdown report of the same issues.
  - Evaluation metrics JSON and optional plots.

### 2.2 Core Pipeline Stages
1) **Diff Extraction**
   - Identify changed files and produce a diff text for analysis.
2) **RAG Context Retrieval**
   - **Codebase RAG**: retrieve relevant code chunks from indexed repository.
   - **Docs RAG**: retrieve best-practice guidance from indexed docs.
3) **Multi-LLM Grading**
   - Three graders (security, logic, performance) analyze the diff + context.
   - Judge consolidates high-confidence, critical/high issues.
4) **Report Generation**
   - Filter report for severity, confidence, diff alignment, and evidence validity.
   - Save JSON + Markdown.
5) **Fix Loop (Optional)**
   - Validate issue, generate fix, apply patch/replace, verify, rollback if needed.
6) **Evaluation (Optional)**
   - Compute precision/recall/fix-rate on labeled dataset.

## 3. Detailed Specifications

### 3.1 Diff Extraction
- Source: `GitAnalyzer.get_diffs()`
- Inputs: staged/unstaged/last_commit toggles
- Output: `GitDiff` with diff texts + changed files list
- Hard requirements:
  - Must return a diff even if only unstaged/staged exist.
  - Must produce consistent file paths for downstream matching.

### 3.2 Code RAG
- Indexer: `CodebaseIndexer.index_directory()`
- Chunking: Python AST-based chunking with fallback for non-Python.
- Retriever: `HybridRetriever.search()` using semantic + BM25 + HyDE.
- Output: list of text chunks + metadata (file path, line range, type).

### 3.3 Docs RAG
- Indexer: `DocsIndexer.index_directory()`
- Retriever: `HybridRetriever` over docs collection and BM25 index.
- Output: best-practice guidance snippets with metadata.

### 3.4 Multi-LLM Grading
- Roles: security / logic / performance
- Inputs: diff + RAG context
- Output: JSON payload per grader with structured issues.
- Judge consolidates into `FinalReport`.
- Strict JSON expectations; robust parsing with fallback and coercion.

### 3.5 Report Filtering
- Enforce:
  - Severity critical/high only.
  - Confidence >= 0.8.
  - Issues must map to **changed lines** in diff.
  - Evidence must exist in file or diff.
- Save both JSON and Markdown outputs.

### 3.6 Fix Loop (Agentic)
- Preconditions:
  - `issue.location.file` exists.
  - `issue.location.line` in range.
  - Evidence string found (if provided).
- Fix payload must be JSON and **validated**:
  - `format` in {`patch`, `replace`}.
  - For patch: `git apply --check` succeeds before apply.
  - For replace: valid line range + non-empty replacement.
- No-op detection: skip if proposed replacement is identical.
- Retry logic with bounded attempts, rollback on failure.

### 3.7 Evaluation
- Dataset format: list of cases (`diff`, `query`, `expected_issues`).
- Metrics: precision, recall, fix_rate, per-model breakdown.
- Output JSON metrics summary.

## 4. Current Implementation Status

### 4.1 Implemented
- Diff extraction (`codereview/git_analyzer.py`).
- Codebase indexing + chunking (Python AST) (`codereview/indexer.py`, `codereview/chunker.py`).
- HybridRetriever with semantic + BM25 + HyDE (`codereview/retriever.py`).
- Docs indexing via `docs_indexer.py` and retrieval in CLI + evaluator.
- Graders + judge with robust JSON parsing and coercion (`codereview/grader.py`).
- Report filtering enforcing severity/confidence/diff evidence (`codereview/report_generator.py`).
- Fix loop guardrails: payload validation, no-op detection, patch dry-run, rollback (`codereview/agent.py`, `codereview/fixer.py`).
- CLI commands: index, index_docs, analyze, fix, evaluate (`main.py`).
- Evaluation runner consolidated to `EvaluationRunner`.
- Tests added for:
  - Report filter
  - Fixer line-based replacement
  - Fix loop payload validation
  - Tool routing in fix loop
  - Minimal analyze integration

### 4.2 Partially Implemented
- ReAct agent multi-step tool routing exists but is **lightweight**; no explicit tool state machine.
- Fix loop handles single-file changes well; **multi-file patch handling** remains shallow.
- Evaluation dataset exists but precision/recall metrics need tuning and coverage.

### 4.3 Not Implemented
- Tree-sitter for non-Python AST chunking.
- Full tool-based ReAct loop with explicit action planning/trajectory logging.
- True multi-file fix transactions (atomic rollback across multiple files).
- Rich evaluation plots integrated into CLI.
- More extensive unit tests for retriever and grader behavior.

## 5. Gaps and Risks (Detailed)

### 5.1 Fix Loop Accuracy and Safety
- Missing multi-file transactional safety.
- Limited tool routing: no explicit action plan or retries based on tool outputs.
- Fix payload schema still allows replacements that are not evidence-aligned.

### 5.2 Report Quality
- Some false positives remain; evidence/diff alignment helps but not complete.
- Grader prompts still allow occasional hallucinations.

### 5.3 Evaluation Reliability
- Two datasets exist but single canonical pipeline is still evolving.
- Metrics do not yet track false-positive reasons or report alignment errors.

### 5.4 Docs and Knowledge Drift
- Some internal docs can still drift from code reality.
- Docs RAG quality depends heavily on docs corpus coverage.

### 5.5 Testing Gaps
- Tests are still minimal for core LLM behaviors (hard to unit test).
- No tests for patch apply failure path or multi-file rollback.

## 6. Recommended Next Steps (Short-Term)
1) **Fix Loop Transactions**
   - Implement multi-file atomic apply + rollback.
   - Log attempt artifacts for debugging.
2) **Evidence Alignment Enforcement**
   - Require patch/replacement to include evidence location or diff hunk.
3) **Prompt Tightening**
   - Force graders to only cite exact diff lines for evidence.
4) **Evaluation Extensions**
   - Track error categories and confidence calibration.
5) **Test Coverage**
   - Add tests for patch apply failure, retry behavior, and multi-file rollback.

## 7. Notes for Stronger Planning Model
- The system is already functional end-to-end for single-file fixes but needs rigor for multi-file safety and evidence alignment.
- Most leverage comes from: stricter fix schema + improved RAG context + evaluation instrumentation.
