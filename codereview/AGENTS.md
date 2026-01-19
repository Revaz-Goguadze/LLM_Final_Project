# CODEREVIEW PACKAGE

Core AI/RAG logic for code analysis and automated repair.

## STRUCTURE

```
codereview/
├── config.py          # API keys, model IDs, ChromaDB path
├── models.py          # Pydantic: BugIssue, GraderReport, FinalReport, GitDiff
├── grader.py          # MultiLLMGrader: 3 specialists + judge
├── agent.py           # ReActAgent: orchestrates fix workflow
├── fixer.py           # CodeFixer: applies patches, runs pytest
├── git_analyzer.py    # GitAnalyzer: extracts staged/unstaged/commit diffs
├── indexer.py         # CodebaseIndexer: chunks + stores in ChromaDB
├── chunker.py         # ASTChunker: Python AST-based code splitting
├── retriever.py       # HybridRetriever: semantic + BM25 + HyDE
├── docs_indexer.py    # DocsIndexer: best practices RAG
├── rag_builder.py     # RAG prompt/context assembly helpers
└── report_generator.py# Saves FinalReport to JSON/MD
```

## DATA FLOW

```
GitAnalyzer.get_diffs() -> GitDiff
    |
    v
HybridRetriever.search() -> Code context
DocsRetriever.search() -> Best practices
    |
    v
MultiLLMGrader.grade_with_model() x3 -> [GraderReport]
    |
    v
MultiLLMGrader.judge() -> FinalReport
    |
    v
ReActAgent.solve_issue() -> CodeFixer.apply_fix_with_content()
```

## WHERE TO LOOK

| Task | File | Function/Class |
|------|------|----------------|
| Add grader role | `grader.py` | `_get_grading_prompt()` prompts dict |
| Change model | `config.py` | MODEL_GRADER_* constants |
| New data field | `models.py` | Pydantic BaseModel classes |
| Chunk non-Python | `chunker.py` | `_simple_chunk()` or add tree-sitter |
| Custom embedding | `indexer.py` | Replace `DefaultEmbeddingFunction()` |

## CONVENTIONS

- LLM responses parsed as JSON with multi-candidate fallback and coercion
- Grader prompts request strict JSON schema compliance
- ChromaDB collections: `codebase` (code), `docs` (docs)
- Metadata always includes: file_path, name, type, start_line, end_line

## INCOMPLETE IMPLEMENTATIONS

| Component | Status | TODO |
|-----------|--------|------|
| ReActAgent | Partial | Multi-step reasoning loop + tool routing |
| ASTChunker | Python only | Tree-sitter for JS/TS |
