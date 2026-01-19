# Analysis and Roadmap

## Goals and Intended Scope
- Dual-RAG code review system: Git diff + codebase context + docs/best practices.
- Multi-LLM grading with judge aggregation.
- Optional fix loop: GenerateFix → ApplyFix → Verify with bounded retries.
- Quantitative evaluation on a labeled dataset.

## Current Stage (Implementation Reality vs Docs)
- Phase 1–3 largely implemented:
  - Git diff ingestion (`codereview/git_analyzer.py`), code indexing (`codereview/indexer.py`), AST chunking for Python (`codereview/chunker.py`).
  - Hybrid retrieval includes semantic + BM25 + HyDE (`codereview/retriever.py`, `codereview/bm25_index.py`).
  - Multi-LLM grading + judge and report output implemented (`codereview/grader.py`, `codereview/report_generator.py`, `main.py`).
- Phase 4 (fix loop) partially implemented:
  - ReActAgent is a single-step loop without tool selection or state (`codereview/agent.py`).
  - CodeFixer applies unified diff, substring replace, or line-based replacement; verification is pytest with fallback (`codereview/fixer.py`).
- Phase 5 (evaluation) partially implemented:
  - Two parallel evaluation paths exist: `evaluation_runner.py` (count-based) and `codereview/evaluator.py` (issue-matching). Not unified or wired to CLI.

## Key Mismatches / Risks
- Docs RAG is split into two implementations:
  - `codereview/docs_rag.py` (collection: `best_practices_docs`, DefaultEmbeddingFunction) used by `main.py`.
  - `codereview/docs_indexer.py` + `HybridRetriever` (collection: `docs`, embedding from `embeddings.py`) used by `codereview/evaluator.py`.
  - Result: indexing/search contexts don’t line up across CLI vs evaluation.
- Report accuracy issues in current `bug_report`:
  - “Hardcoded API keys” is misclassified; config loads from env but lacks validation.
  - “Empty fix applied” in `ReActAgent` is likely false; the code already checks `if not current_fix`.
  - Evidence strings aren’t guaranteed to match actual file content, which breaks fix application.
- Fix loop fragility:
  - Fix generation is one-shot with only local file context; doesn’t use retriever or docs.
  - Fix content can be empty/unchanged or poorly aligned to the line range; `_apply_line_based_fix` is heuristic.
  - `rollback` uses `git checkout` (can discard unrelated local changes).
- Documentation drift:
  - AGENTS.md says HybridRetriever is semantic-only; code already has BM25 + HyDE.
  - plan.md describes tree-sitter JS/TS; not implemented.
- Anti-patterns:
  - Bare `except:` in `chunker.py` and `git_analyzer.py` (explicitly called out in AGENTS.md).

## Roadmap (High-Level)
1) Stabilize fix loop accuracy (short-term focus)
2) Unify RAG and docs indexing
3) Improve report quality and validation
4) Consolidate evaluation pipeline and metrics
5) Harden reliability and hygiene

## Detailed Next-Steps Plan (Fix-Loop Improvement)

### Phase A — Fix Loop Reliability (Highest Priority)
- A1. Report-to-fix validation gate
  - Validate `location.file` exists, `line` is in range, and `evidence` is found in file before attempting fixes.
  - If validation fails, mark issue as non-actionable and skip or request user input.
- A2. Fix content hygiene
  - Reject empty or no-op fixes after whitespace normalization.
  - Detect if the proposed fix produces no diff and regenerate.
- A3. Context refresh per attempt
  - Re-read file context after each failed attempt (current loop reuses stale context).
  - Optionally pull extra context from RAG when evidence mismatch occurs.
- A4. Safer apply strategies
  - Prefer unified diff generation for multi-line fixes; fallback to line-based replace only when evidence matches.
  - Ensure line-based replacement handles insertions/deletions (replacement length is currently fixed).
- A5. Verification + rollback safety
  - Use `git restore -- <file>` (or stash) to avoid wiping unrelated edits.
  - Ensure `VERIFY_COMMAND` is documented and configurable for repos.

### Phase B — Improve Fix Generation (Quality and Determinism)
- B1. Add tool-like “READ_FILE” and “SEARCH_CODE” steps
  - Use `HybridRetriever` for additional context when evidence doesn’t match or issue spans multiple files.
- B2. Prompt changes for patch format
  - Ask LLM to output a minimal unified diff or explicit “before → after” block.
  - Enforce JSON output for fix with fields: `file`, `start_line`, `end_line`, `replacement`.
- B3. Track repeated failures
  - If two attempts return identical fixes or errors, stop early and report.

## System-Wide Alignment Plan

### Phase C — RAG and Docs Indexing Unification
- Pick one docs indexing pipeline:
  - Option 1: retire `docs_rag.py` and use `docs_indexer.py` + `HybridRetriever` everywhere.
  - Option 2: standardize on `docs_rag.py` and update evaluator accordingly.
- Align collection names (`DOCS_DB_COLLECTION`) and embedding functions.
- Ensure `index_docs` populates the same collection that evaluation uses.

### Phase D — Report Quality and Evidence Integrity
- Post-process model output:
  - Drop issues whose evidence isn’t found in the file/diff.
  - Normalize issue types (security vs configuration vs best-practice).
  - Enforce “changed lines only” constraint using diff parsing.
- Tune prompts to reduce hallucinations:
  - Require evidence to be an exact line from the diff or file.
  - Require `location.file` to be one of the changed files.

### Phase E — Evaluation Consolidation
- Add a single evaluation entry point:
  - Use `codereview/evaluator.py` scoring and wire it into CLI.
  - Retire or clearly separate `evaluation_runner.py`.
- Standardize dataset format (prefer structured expected issues vs count-only).
- Generate consistent JSON + chart outputs from one runner.

### Phase F — Hygiene / Reliability
- Replace bare `except:` with explicit exception types.
- Add env var validation with clear error messages in `config.py`.
- Add `.gitignore` for `.chroma/`, `.bm25/`, caches (prevent index bloat in repo).

## Current Stage Summary
- The project is effectively late Phase 3 / early Phase 4: multi-LLM grading + RAG works, evaluation dataset exists, fix loop exists but lacks guardrails and alignment with report quality.
- The highest immediate value is improving report accuracy and fix-loop robustness, because current report issues are inconsistent with actual code.
