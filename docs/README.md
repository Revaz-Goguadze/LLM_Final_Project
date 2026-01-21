# Documentation Index

## Core Guides
- `docs/architecture.md`: system components and data flow
- `docs/workflow.md`: end-to-end usage and outputs
- `docs/pipeline.md`: concise pipeline summary

## Reference
- `docs/rag_usage.md`: query construction and dual-RAG behavior
- `docs/data-schemas.md`: report and issue schemas
- `docs/evaluation.md`: evaluation workflow
- `docs/evaluation_dataset.md`: dataset format and samples

## Best Practices (Docs RAG Sources)
- `docs/security_best_practices.md`
- `docs/logic_best_practices.md`
- `docs/performance_best_practices.md`
- `docs/python_best_practices.md`
- `docs/additional_best_practices.md`

## Final Project Checklist
- Run `python main.py index --path .`
- Run `python main.py index-docs --path docs`
- Run `python main.py analyze --unstaged --query "review changes for security, logic, and performance issues"`
- Verify `bug_report.json` and `bug_report.md` are generated
- Ensure `.env` is set with `OPENROUTER_API_KEY`
