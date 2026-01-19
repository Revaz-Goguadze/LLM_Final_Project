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
├── retriever.py       # HybridRetriever: semantic search (BM25 TODO)
├── docs_rag.py        # DocsIndexer/Retriever: best practices RAG
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
ReActAgent.solve_issue() -> CodeFixer.apply_fix()
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

- All LLM responses parsed as JSON with regex extraction
- Grader prompts request strict JSON schema compliance
- ChromaDB collections: `codebase` (code), `best_practices_docs` (docs)
- Metadata always includes: file_path, name, type, start_line, end_line

## INCOMPLETE IMPLEMENTATIONS

| Component | Status | TODO |
|-----------|--------|------|
| ReActAgent | Stub | Multi-step reasoning loop |
| CodeFixer.apply_fix | Placeholder | Actual patch application |
| HybridRetriever | Semantic only | Add BM25 ranking |
| ASTChunker | Python only | Tree-sitter for JS/TS |
