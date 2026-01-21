# Architecture Overview

Purpose: analyze git diffs using dual-RAG (code + docs) and a multi-LLM grading pipeline.

## Components

1) CLI (`main.py`)
   - commands: index, index-docs, analyze, fix, evaluate

2) Code RAG
   - indexer: `codereview/indexer.py`
   - chunker: `codereview/chunker.py`
   - storage: ChromaDB + BM25

3) Docs RAG
   - indexer: `codereview/docs_indexer.py`
   - sources: `docs/*.md`

4) Graders + Judge
   - graders: `codereview/grader.py` (security/logic/performance)
   - judge: consolidate + filter

5) Fix Loop (optional)
   - agent: `codereview/agent.py`
   - patch apply/rollback: `codereview/fixer.py`

## Data Flow

1) Select diff (staged/unstaged/last commit)
2) Build RAG query (user query + file paths + diff snippet)
3) Retrieve code chunks
4) Retrieve docs chunks
5) Combine context + diff into a single prompt
6) Grade with multiple LLMs
7) Judge outputs report (`bug_report.json`, `bug_report.md`)

## Storage

- Local vector store persists embeddings under `.vector_store/`
- BM25 stores lexical retrieval scores
- Embeddings are generated via OpenAI (no local torch)
