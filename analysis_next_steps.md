# Analysis and Roadmap (Updated 2026-01-19)

## Goals and Intended Scope
- Dual-RAG code review system: Git diff + codebase context + docs/best practices.
- Multi-LLM grading with judge aggregation.
- Optional fix loop: GenerateFix -> ApplyFix -> Verify with bounded retries.
- Quantitative evaluation on a labeled dataset.

## Current Stage (Implementation Reality)
- Core RAG and grading are implemented and wired through CLI.
- Docs indexing and retrieval are unified in CLI and evaluator via `docs_indexer.py` + `rag_builder.py`.
- Fix loop has guardrails: actionable validation, no-op detection, retry logic, patch vs replace handling, and rollback safety.
- Report filtering validates severity/confidence, changed-line alignment, file existence, and evidence matching.
- Evaluation is wired into the CLI (`main.py evaluate`) and produces summary metrics.

## Latest Analysis Run
- Command: `python main.py analyze --last-commit`
- Result: 1 consolidated issue (SECURITY, high) claiming an empty-fix risk in `codereview/agent.py`.
- Assessment: Likely false positive because empty-fix and no-op checks already exist. The report still surfaces it, indicating prompt + evidence alignment remains noisy.

## Remaining Gaps / Risks
- Fix loop still relies on single-step generation without a strict fix schema validator or patch dry-run.
- Grader and judge JSON parsing can still fail in edge cases (observed in evaluation runs).
- Docs pipeline duplication remains in codebase (`docs_rag.py`) and internal docs are out of date.
- Evaluation is split between `evaluation_runner.py` and `main.py evaluate` (outputs overlap but are not consolidated).
- Tests: pytest collects zero tests; coverage requirements remain unmet.
- Repo hygiene: `.chroma/`, `.bm25/`, and cache artifacts are committed; decide if they should be ignored.

## Roadmap (High-Level)
1) Fix loop accuracy and determinism
2) Report quality and prompt alignment
3) Evaluation consolidation and metrics stability
4) Tests and coverage for critical paths
5) Documentation alignment and repo hygiene

## Detailed Next Steps

### Fix Loop Reliability (Highest Priority)
- Add a strict fix payload validator (format, file, line range, replacement/patch presence).
- Add a patch dry-run check before mutation (e.g., `git apply --check`) and fail fast on invalid patches.
- Record each attempt: issue id, prompt, payload, apply result, verify output.
- Add targeted unit tests for `CodeFixer` (patch apply, line replace, rollback).

### Report Quality and Evidence Integrity
- Tighten prompt constraints to require evidence that matches an exact diff line or file line.
- Add a post-filter logic sanity step to suppress issues that contradict explicit guards.
- Maintain a small regression set of false positives/negatives to track prompt changes.

### Evaluation Consolidation
- Choose a single evaluation entry point (prefer `main.py evaluate`) and deprecate the other runner.
- Add robust JSON parsing with retry/fallback for judge output.
- Normalize metrics outputs into one location and format.

### Testing and Coverage
- Add unit tests for `ReportGenerator.filter_report`, `GitAnalyzer.get_diffs`, and `ReActAgent._validate_issue`.
- Add a minimal integration test that stubs grader outputs and runs `analyze` on a fixture diff.

### Docs and Hygiene
- Update `codereview/AGENTS.md` and `plan.md` to reflect the current docs pipeline.
- Decide whether index artifacts should stay versioned; if not, add to `.gitignore` and document rebuild steps.

## Current Stage Summary
- The system is in a more stable Phase 4: fix loop guardrails and report validation exist, but accuracy is still constrained by prompt noise and sparse tests.
- The next best gains come from stricter fix validation, stronger evidence alignment, and consolidated evaluation with reliable parsing.
