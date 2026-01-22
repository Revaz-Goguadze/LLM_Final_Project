# LLM Code Review Platform

Multi-LLM Agentic Code Reviewer using Dual-RAG (codebase + docs) to analyze git diffs for security, logic, and performance issues.

## Architecture

- **Dual-RAG**: Primary RAG retrieves relevant code; Secondary RAG retrieves best practices
- **Multi-LLM Ensemble**: Three specialized graders (security, logic, performance) + final judge
- **RRF Hybrid Retrieval**: Reciprocal Rank Fusion combines semantic + BM25 + HyDE results
- **ReAct Agent**: Issue validation and fix generation with verification loop

## Quick Start

### 1. Install dependencies

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Set API keys

Create `.env` file:
```
OPENROUTER_API_KEY=your_openrouter_key_here
```

### 3. Index codebase for RAG

```bash
# Index current project
python main.py index .

# Index specific folder
python main.py index --path sample

# Index docs for best practices RAG
python main.py index-docs --path docs
```

### 4. Analyze changes

```bash
# Analyze unstaged changes
python main.py analyze --unstaged

# Analyze last commit
python main.py analyze --last-commit

# Analyze a folder without git
python main.py analyze --path sample --query "review for security issues"
```

### 5. Fix issues

```bash
# List issues from last analysis
python main.py list

# Fix specific issue by ID
python main.py fix <issue_id>
```

### 6. Evaluate

```bash
# Run evaluation with single/multi/both modes
python main.py evaluate evaluation/dataset.jsonl --mode both

# Modes: single (baseline), multi (full pipeline), both (with improvement metric)
```

## Demo Script

Complete end-to-end demo:

```bash
# 1. Setup and index
python main.py index .
python main.py index-docs docs

# 2. Make a sample change (with intentional bug)
cat > sample/bad_code.py << 'EOF'
def divide(a, b):
    return a / b  # No zero division check

result = divide(10, 0)
print(result)
EOF

git add sample/bad_code.py

# 3. Analyze changes
python main.py analyze --staged --query "check for logic bugs"

# 4. List and fix issues
python main.py list
python main.py fix 0  # Fix first issue

# 5. Run evaluation
python main.py evaluate evaluation/dataset.jsonl --mode both
```

## Project Structure

```
.
├── main.py               # CLI entry (typer): index, index-docs, analyze, fix
├── codereview/           # Core package: RAG, grading, agent
├── evaluation/           # Ground truth samples + runner
├── docs/                 # Best practices MD files indexed by DocsRAG
├── tests/                # Integration and component tests
├── sample/               # Sample code for testing
├── .vector_store/        # ChromaDB persistent storage
├── .bm25/                # BM25 lexical index
└── config/               # YAML configuration files
```

## Configuration

Edit `codereview/config.py` to customize:
- LLM models for each grader role
- RAG retrieval parameters (top_k, alpha)
- Fix loop retry limits
- Verification commands

## Metrics

The evaluation system tracks:
- **Precision**: TP / (TP + FP)
- **Recall**: TP / (TP + FN)
- **F1 Score**: 2 * (precision * recall) / (precision + recall)
- **Fix Rate**: Percentage of issues with valid fixes
- **Multi-LLM Improvement**: (multi_f1 - single_f1) / single_f1

## License

MIT License - See LICENSE file for details
