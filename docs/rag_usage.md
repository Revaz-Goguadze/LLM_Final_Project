# How the Two RAG Layers Work

## Primary RAG (Codebase)
- Source: your project code (only `.py` files).
- Chunking: functions/classes via AST.
- Index: ChromaDB (semantic vectors) + BM25 (keyword).
- Use: retrieve relevant code blocks for the current diff + query.

## Secondary RAG (Python Best Practices / Docs)
- Source: documentation files in `docs/` (e.g. `python_best_practices.md`).
- Chunking: Markdown sections by heading.
- Index: ChromaDB + BM25 (separate collection).
- Use: retrieve best-practice guidance related to the diff + query.

## Combined Context
During `analyze`, the system builds one prompt with:
1) user query (optional)
2) codebase RAG context (primary)
3) docs/best-practices RAG context (secondary, optional)
4) git diff

## Commands
1) Index codebase:
`python /home/Zura/LLM_Final_Project/main.py index --path /home/Zura/LLM_Final_Project`

2) Index docs (secondary RAG):
`python /home/Zura/LLM_Final_Project/main.py index-docs --path /home/Zura/LLM_Final_Project/docs`

3) Analyze:
`python /home/Zura/LLM_Final_Project/main.py analyze --unstaged --query "check for logic bugs"`

Optional flags:
- `--use-docs-rag/--no-use-docs-rag` to toggle secondary RAG
- `--show-context` to print RAG query/context
- `--context-out /path/to/context.txt` to save context

Offline mode:
- Set `EMBEDDING_MODE=local` to avoid downloading the default embedding model.
