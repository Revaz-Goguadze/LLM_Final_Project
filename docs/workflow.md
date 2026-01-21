# Workflow Guide

Purpose: run a review from diff to report in a repeatable way.

## Commands

```bash
python main.py index --path .
python main.py index-docs --path docs
python main.py analyze --unstaged --query "check for logic bugs"
python main.py analyze --path sample --query "review sample code for security, logic, and performance issues"
```

## Analyze Steps

1) Select diff (staged/unstaged/last commit)
2) Build RAG query from:
   - user query
   - file paths in the diff
   - added/removed diff lines
3) Retrieve code + docs context
4) Grade with security/logic/performance models
5) Judge and write reports

## Outputs

- `bug_report.json` (machine-readable)
- `bug_report.md` (human-readable)

## Optional Fix Loop

```bash
python main.py fix <issue_id>
```

- snapshot → apply → verify → rollback on failure

## Operations

### Environment Variables
- `OPENROUTER_API_KEY`: required for LLM calls
- `OPENAI_API_KEY`: required for OpenAI embeddings (no torch)
- `OPENROUTER_TIMEOUT`: request timeout in seconds (default 60)
- `EMBEDDING_MODE`: `openai` or `local`

### Troubleshooting
- "Collection does not exist": run `python main.py index` and `python main.py index-docs`
- Slow graders: increase `OPENROUTER_TIMEOUT`
- Missing issues: verify diff is non-empty and a query is provided
