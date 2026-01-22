# PROJECT KNOWLEDGE BASE

**Generated:** 2026-01-18
**Commit:** a101e64
**Branch:** main

## OVERVIEW

Multi-LLM Agentic Code Reviewer using Dual-RAG (codebase + docs) to analyze git diffs for security, logic, and performance issues. Python CLI tool with OpenRouter-based grading ensemble and automated fix verification.

## STRUCTURE

```
./
├── main.py               # CLI entry (typer): index, index_docs, analyze, fix
├── codereview/           # Core package: RAG, grading, agent
├── evaluation/           # Ground truth samples + runner for precision/recall
├── docs/                 # Best practices MD files indexed by DocsRAG
├── diagrams/             # Architecture visuals (mermaid, PNG)
├── .chroma/              # ChromaDB persistent storage (gitignore candidate)
├── evaluation_runner.py  # Runs graders against samples, outputs metrics
└── visualize_results.py  # Generates performance plots
```

## WHERE TO LOOK

| Task | Location | Notes |
|------|----------|-------|
| Add CLI command | `main.py` | Uses typer app |
| Change LLM models | `codereview/config.py` | OpenRouter model IDs |
| Modify grading prompts | `codereview/grader.py` | `_get_grading_prompt()` |
| Add new issue type | `codereview/models.py` | Pydantic schemas |
| Improve code chunking | `codereview/chunker.py` | AST-based, Python only |
| Add best practice docs | `docs/*.md` | Auto-indexed by DocsRAG |
| Add test samples | `evaluation/samples/{category}/` | Update ground_truth.json |

## CONVENTIONS

- **Relative imports only** in `codereview/` package
- **Pydantic models** for all data contracts (`models.py`)
- **OpenRouter gateway** for all LLM calls (not direct OpenAI)
- **ChromaDB DefaultEmbeddingFunction** (sentence-transformers)
- **AST chunking** for Python; whole-file fallback for others

## ANTI-PATTERNS (THIS PROJECT)

- **Bare `except:`** - use specific exceptions (violations exist in chunker.py:80, git_analyzer.py:25)
- **Hardcoded secrets** - use .env (buggy_sample.py is intentional test case)
- **Direct OpenAI client** - must use OpenRouter base_url
- **pytest not in requirements.txt** - add if implementing tests/

## COMMANDS

```bash
# Setup
pip install -r requirements.txt
cp .env.example .env  # Add GEMINI_API_KEY (+ OPENAI_API_KEY if using OpenAI embeddings)

# Index codebase for RAG
python main.py index .
python main.py index-docs docs/

# Analyze changes
python main.py analyze --staged
python main.py analyze --last-commit

# Auto-fix issue
python main.py fix <issue_id>

# Evaluate accuracy
python evaluation_runner.py
python visualize_results.py
```

## NOTES

- `tests/` directory exists but is empty - pytest mentioned in plan.md but not implemented
- ReActAgent and CodeFixer are partial implementations (TODO markers)
- HybridRetriever currently semantic-only (BM25 TODO)
- Tree-sitter support for JS/TS planned but not implemented
- `.chroma/` persists vectors locally - consider .gitignore
