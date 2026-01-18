import typer
from rich import print
from codereview.git_analyzer import GitAnalyzer
from codereview.indexer import CodebaseIndexer
from codereview.retriever import HybridRetriever
from codereview.docs_indexer import DocsIndexer
from codereview.grader import MultiLLMGrader
from codereview.report_generator import ReportGenerator
from codereview.config import (
    MODEL_GRADER_SECURITY,
    MODEL_GRADER_LOGIC,
    MODEL_GRADER_PERF,
    DOCS_DB_COLLECTION,
    DOCS_BM25_INDEX_PATH,
)
from codereview.rag_builder import (
    build_rag_query,
    build_context_block,
    build_analysis_input,
    truncate_text,
)
from codereview.evaluator import EvaluationRunner

app = typer.Typer()

@app.command()
def index(path: str = ".", bm25: bool = True):
    """Index the codebase."""
    print(f"[bold blue]Indexing codebase at {path}...[/bold blue]")
    indexer = CodebaseIndexer()
    indexer.index_directory(path, build_bm25=bm25)
    print("[bold green]Indexing complete![/bold green]")

@app.command()
def index_docs(path: str = "docs", bm25: bool = True):
    """Index documentation for secondary RAG."""
    print(f"[bold blue]Indexing docs at {path}...[/bold blue]")
    indexer = DocsIndexer()
    indexer.index_directory(path, build_bm25=bm25)
    print("[bold green]Docs indexing complete![/bold green]")

@app.command()
def analyze(
    staged: bool = False,
    unstaged: bool = False,
    last_commit: bool = False,
    query: str | None = None,
    use_rag: bool = True,
    top_k: int = 6,
    docs_top_k: int = 4,
    use_docs_rag: bool = True,
    show_context: bool = False,
    context_out: str | None = None,
):
    """Analyze changes for bugs and bad practices."""
    print("[bold blue]Starting analysis...[/bold blue]")
    
    # 1. Extract Diffs
    analyzer = GitAnalyzer()
    diffs = analyzer.get_diffs()
    
    target_diff = ""
    if staged: target_diff = diffs.staged
    elif unstaged: target_diff = diffs.unstaged
    elif last_commit: target_diff = diffs.last_commit
    else:
        # Default to unstaged or staged
        target_diff = diffs.unstaged or diffs.staged
        
    if not target_diff:
        print("[yellow]No diff found to analyze.[/yellow]")
        return

    rag_context = None
    if use_rag:
        retriever = HybridRetriever()
        rag_query = build_rag_query(query, target_diff)
        if rag_query:
            rag_results = retriever.search(rag_query, n_results=top_k)
            code_context = build_context_block(rag_results)

            docs_context = ""
            if use_docs_rag:
                docs_retriever = HybridRetriever(
                    collection=DOCS_DB_COLLECTION,
                    bm25_index_path=DOCS_BM25_INDEX_PATH,
                )
                docs_results = docs_retriever.search(rag_query, n_results=docs_top_k)
                docs_context = build_context_block(docs_results) if docs_results else ""

            parts = []
            if code_context:
                parts.append("Codebase context:\n" + code_context)
            if docs_context:
                parts.append("Python docs/best practices:\n" + docs_context)
            rag_context = "\n\n".join(parts) if parts else None
            if show_context:
                print("[bold]RAG query:[/bold]")
                print(truncate_text(rag_query))
                if rag_context:
                    print("[bold]RAG context (truncated):[/bold]")
                    print(truncate_text(rag_context))
            if context_out and rag_context:
                with open(context_out, "w", encoding="utf-8") as f:
                    f.write(rag_context)

    # 3. Multi-LLM Grading
    grader = MultiLLMGrader()
    analysis_input = build_analysis_input(query, target_diff, rag_context)
    print("Calling Grader 1 (Security)...")
    r1 = grader.grade_with_model("security", MODEL_GRADER_SECURITY, analysis_input)
    
    print("Calling Grader 2 (Logic)...")
    r2 = grader.grade_with_model("logic", MODEL_GRADER_LOGIC, analysis_input)
    
    print("Calling Grader 3 (Performance)...")
    r3 = grader.grade_with_model("performance", MODEL_GRADER_PERF, analysis_input)
    
    # 4. Final Judgment
    print("Calling Final Judge...")
    final_report = grader.judge([r1, r2, r3])
    
    # 5. Generate Report
    ReportGenerator.save_report(final_report, "bug_report.json")
    print("[bold green]Analysis complete! Report saved to bug_report.md[/bold green]")
    
    # 6. Print Summary
    print("\n[bold]Consolidated Issues:[/bold]")
    for issue in final_report.consolidated_issues:
        severity_color = {"critical": "red", "high": "orange1", "medium": "yellow", "low": "green"}.get(issue.severity.lower(), "white")
        print(f"[{severity_color}]- {issue.type.upper()} ({issue.severity}): {issue.description}[/{severity_color}]")

@app.command()
def fix(issue_id: int):
    """Fix a specific issue by ID from the last report."""
    import json
    from codereview.agent import ReActAgent
    from codereview.models import BugIssue
    
    try:
        with open("bug_report.json", "r") as f:
            report_data = json.load(f)
        
        issues = report_data.get("consolidated_issues", [])
        if not issues or issue_id >= len(issues):
            print(f"[red]Issue ID {issue_id} not found.[/red]")
            return
        
        issue = BugIssue(**issues[issue_id])
        agent = ReActAgent()
        agent.solve_issue(issue)
    except FileNotFoundError:
        print("[red]No bug report found. Run 'analyze' first.[/red]")

@app.command()
def evaluate(
    dataset: str,
    use_rag: bool = True,
    top_k: int = 6,
    docs_top_k: int = 4,
    use_docs_rag: bool = True,
    output: str = "eval_report.json",
):
    """Evaluate model quality on a labeled dataset."""
    runner = EvaluationRunner(
        use_rag=use_rag,
        top_k=top_k,
        docs_top_k=docs_top_k,
        use_docs_rag=use_docs_rag,
    )
    results = runner.run(dataset)
    ReportGenerator.save_report(results, output)
    print(f"[bold green]Evaluation complete! Report saved to {output}[/bold green]")

if __name__ == "__main__":
    app()
