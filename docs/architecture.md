# Architecture Overview

## Goals
- Evaluate code diffs and detect bugs with multiple LLMs.
- Provide context from the codebase and relevant external docs.
- Support iterative fixes with verification.
- Measure model quality on a labeled test dataset.

## Components
1. Ingest
   - Git diff extractor
   - User query collector
   - Codebase indexer (parser + chunking)

2. Retrieval
   - Primary RAG: codebase chunks (ChromaDB or Qdrant)
   - Secondary RAG: framework docs + best practices

3. LLM Orchestration
   - Multi-model runner (Gemini + free OpenRouter models)
   - Prompt templates for analysis and fix generation
   - Aggregator for scores + final report

4. Evaluation
   - Labeled test dataset (known bugs)
   - Metrics: precision, recall, fix rate
   - Per-model dashboards and comparisons

5. Fix Loop (optional)
   - GenerateFix -> ApplyFix -> Verify
   - Retry with bounded attempts

## Data Flow Summary
Input: git diff + user query + codebase index
-> Retrieve code context (RAG #1)
-> Retrieve docs context (RAG #2)
-> LLM analysis (multiple models)
-> Aggregation + report
-> (optional) Fix loop and verification

