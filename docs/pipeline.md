# Pipeline Details

## 1) Inputs
- Git diff (per commit or PR)
- User query (task-specific question)
- Indexed codebase (chunked + metadata)

## 2) Indexing
- Parse code into AST where possible.
- Chunk by function/class or logical block.
- Metadata: file path, language, symbol name, commit hash.

## 3) Retrieval
- RAG #1: codebase chunks (semantic + keyword).
- RAG #2: docs and best practices (React, backend, etc).
- Merge and de-duplicate contexts with a token budget.

## 4) LLM Analysis
- Run multiple models in parallel.
- Each model returns:
  - issues[] with severity and evidence
  - confidence score
  - suggested fix (optional)

## 5) Aggregation
- Normalize scores and rank issues.
- Merge duplicates by file path + line range + message.
- Produce a final report.

## 6) Fix Loop (optional)
- GenerateFix -> ApplyFix -> Verify
- Verification: run tests or static checks.
- Stop after N attempts or when clean.

