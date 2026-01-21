# LLM Code Review Platform

This repository describes an MVP that uses multiple LLMs to evaluate code
changes, detect bugs, and optionally suggest fixes. It combines:

- Git diff + user query + indexed codebase context
- Primary RAG (codebase retrieval)
- Secondary RAG (framework docs + best practices)
- Multi-model evaluation with metrics (precision, recall, fix rate)
- Fix loop: GenerateFix -> ApplyFix -> Verify -> Retry/Stop

Start with the docs in `docs/README.md` for a structured map of the
architecture, workflow, data schemas, and evaluation setup.

## Quick Start
1) Install deps:
`pip install -r /home/Zura/LLM_Final_Project/requirements.txt`

2) Set API keys in `.env`:
```
OPENROUTER_API_KEY=your_openrouter_key
OPENAI_API_KEY=your_openai_key
```

## One-Command Run (analyze current changes)
```bash
MPLCONFIGDIR=/tmp OPENROUTER_TIMEOUT=45 python /home/Zura/LLM_Final_Project/main.py analyze --unstaged --query "review changes for security, logic, and performance issues"
```

## Analyze a Folder (no git diff)
```bash
MPLCONFIGDIR=/tmp OPENROUTER_TIMEOUT=45 python /home/Zura/LLM_Final_Project/main.py analyze --path sample --query "review sample code for security, logic, and performance issues"
```

## One-Command Script (sample run)
```bash
bash /home/Zura/LLM_Final_Project/run_sample.sh
```

## Full Run (index sample + analyze)
```bash
python /home/Zura/LLM_Final_Project/main.py index --path /home/Zura/LLM_Final_Project/sample
python /home/Zura/LLM_Final_Project/main.py index-docs --path /home/Zura/LLM_Final_Project/docs
python /home/Zura/LLM_Final_Project/main.py analyze --unstaged --query "review changes for security, logic, and performance issues"
```

## Embeddings (no torch)
This project uses OpenAI embeddings by default. Set:
```
OPENAI_API_KEY=your_openai_key
```

## Arch Linux Setup
```bash
sudo pacman -S --needed python python-pip
python -m venv .venv
.venv/bin/pip install -r requirements.txt
```

3) Index codebase (builds vector + BM25 index):
`python /home/Zura/LLM_Final_Project/main.py index --path /home/Zura/LLM_Final_Project`

4) Index docs for secondary RAG (Python best practices):
`python /home/Zura/LLM_Final_Project/main.py index-docs --path /home/Zura/LLM_Final_Project/docs`

5) Analyze with RAG context:
`python /home/Zura/LLM_Final_Project/main.py analyze --unstaged --query "check for logic bugs"`

6) Evaluate on labeled dataset:
`python /home/Zura/LLM_Final_Project/main.py evaluate --dataset /path/to/eval.jsonl`
