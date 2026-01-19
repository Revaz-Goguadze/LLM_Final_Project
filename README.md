# LLM Code Review Platform

This repository describes an MVP that uses multiple LLMs to evaluate code
changes, detect bugs, and optionally suggest fixes. It combines:

- Git diff + user query + indexed codebase context
- Primary RAG (codebase retrieval)
- Secondary RAG (framework docs + best practices)
- Multi-model evaluation with metrics (precision, recall, fix rate)
- Fix loop: GenerateFix -> ApplyFix -> Verify -> Retry/Stop

Start with the docs in `docs/` for architecture, pipeline, data schemas,
and evaluation setup.
See `docs/rag_usage.md` for how the two RAG layers work together.

## Quick Start
1) Install deps:
`pip install -r /home/Zura/LLM_Final_Project/requirements.txt`

2) Index codebase (builds vector + BM25 index):
`python /home/Zura/LLM_Final_Project/main.py index --path /home/Zura/LLM_Final_Project`

3) Index docs for secondary RAG (Python best practices):
`python /home/Zura/LLM_Final_Project/main.py index-docs --path /home/Zura/LLM_Final_Project/docs`

4) Analyze with RAG context:
`python /home/Zura/LLM_Final_Project/main.py analyze --unstaged --query "check for logic bugs"`

5) Evaluate on labeled dataset:
`python /home/Zura/LLM_Final_Project/main.py evaluate --dataset /path/to/eval.jsonl`
