# LLM Code Review Platform

## Overview

Multi-LLM Agentic Code Reviewer using Dual-RAG (codebase + docs) to analyze git diffs for security, logic, and performance issues. Python CLI tool with OpenRouter-based grading ensemble and automated fix verification.

## Structure

```
./
├── main.py               # CLI entry (typer): index, index-docs, analyze, fix
├── codereview/           # Core package: RAG, grading, agent (22 files)
├── evaluation/           # Ground truth samples + runner for precision/recall
├── docs/                 # Best practices MD files indexed by DocsRAG
├── tests/                # Integration and component tests (7 files)
├── sample/               # Sample code for testing
├── .vector_store/        # ChromaDB persistent storage
├── .bm25/                # BM25 lexical index
└── config/               # YAML configuration files
```

## Key Locations

| Task | Location |
|------|----------|
| Add CLI command | `main.py` |
| Change LLM models | `codereview/config.py` |
| Modify grading prompts | `codereview/grader.py` - `_get_grading_prompt()` |
| Add new issue type | `codereview/models.py` - Pydantic schemas |
| Improve code chunking | `codereview/chunker.py` - AST-based for Python |
| Add best practice docs | `docs/*.md` - Auto-indexed by DocsRAG |
| Add test samples | `evaluation/samples/{category}/` - Update ground_truth.json |

## Tech Stack

- **Vector Store**: ChromaDB with sentence-transformers embeddings
- **LLM Provider**: OpenRouter (primary) + Gemini (fallback)
- **Models**: Mixtral Devstral-2512 (free tier)
- **Code Parsing**: tree-sitter for AST chunking
- **CLI Framework**: typer with rich output
- **Retrieval**: Hybrid (semantic vector + BM25 lexical, α=0.6)

## Commands

```bash
# Setup
pip install -r requirements.txt
cp .env.example .env  # Add OPENROUTER_API_KEY

# Index codebase for RAG
python main.py index .
python main.py index-docs docs/

# Analyze changes
python main.py analyze --staged
python main.py analyze --last-commit

# Auto-fix issue
python main.py fix <issue_id>

# Evaluate accuracy
python main.py evaluate
```

## Conventions

- **Relative imports only** in `codereview/` package
- **Pydantic models** for all data contracts (`models.py`)
- **OpenRouter gateway** for all LLM calls (not direct OpenAI)
- **Type hints** required for function signatures
- **Early returns** to reduce nesting

## Architecture

- **Dual-RAG**: Primary RAG retrieves relevant code; Secondary RAG retrieves best practices
- **Multi-LLM Ensemble**: Three specialized graders (security, logic, performance) + final judge
- **Strict Filtering**: Only reports issues with ≥85% confidence
- **ReAct Agent**: Issue validation and fix generation with verification loop

## Known TODOs

- HybridRetriever BM25 integration partially complete
- Tree-sitter support for JS/TS files planned
- ReActAgent and CodeFixer are partial implementations
- `.vector_store/` and `.bm25/` should be gitignored

## Anti-Patterns to Avoid

- **Bare `except:`** - use specific exceptions (existing violations in chunker.py:80, git_analyzer.py:25)
- **Direct OpenAI client** - must use OpenRouter base_url
- **Hardcoded secrets** - use .env for API keys
