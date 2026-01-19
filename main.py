import os
import typer
from rich import print
import json
from codereview.git_analyzer import GitAnalyzer
from codereview.indexer import CodebaseIndexer
from codereview.retriever import HybridRetriever
from codereview.docs_indexer import DocsIndexer
from codereview.grader import MultiLLMGrader
from codereview.report_generator import ReportGenerator
from codereview.rag_builder import build_rag_query, build_context_block, build_analysis_input
from codereview.evaluator import EvaluationRunner
from codereview.eval_plots import generate_plots
from codereview.config import (
    MODEL_GRADER_SECURITY,
    MODEL_GRADER_LOGIC,
    MODEL_GRADER_PERF,
    DOCS_DB_COLLECTION,
    DOCS_BM25_INDEX_PATH,
)

app = typer.Typer()

@app.command()
def index(path: str = "."):
    """Index the codebase (Code RAG)."""
    print(f"[bold blue]Indexing codebase at {path}...[/bold blue]")
    indexer = CodebaseIndexer()
    indexer.index_directory(path)
    print("[bold green]Codebase indexing complete![/bold green]")

@app.command()
def index_docs(path: str = "docs"):
    """Index best practices documentation (Documentation RAG)."""
    print(f"[bold blue]Indexing documentation at {path}...[/bold blue]")
    indexer = DocsIndexer()
    indexer.index_directory(path)
    print("[bold green]Documentation indexing complete![/bold green]")

@app.command()
def analyze(
    staged: bool = False,
    unstaged: bool = False,
    last_commit: bool = False,
    query: str = None,
    use_rag: bool = typer.Option(True, "--use-rag/--no-use-rag"),
    use_docs_rag: bool = typer.Option(True, "--use-docs-rag/--no-use-docs-rag"),
    top_k: int = typer.Option(5, "--top-k"),
    docs_top_k: int = typer.Option(5, "--docs-top-k"),
    show_context: bool = typer.Option(False, "--show-context"),
    context_out: str = typer.Option(None, "--context-out"),
):
    """Analyze changes for bugs and bad practices."""
    print("[bold blue]Starting analysis...[/bold blue]")
    
    # 1. Extract Diffs
    analyzer = GitAnalyzer()
    diffs = analyzer.get_diffs()
    
    target_diff = ""
    diff_type = "changes"
    if staged: 
        target_diff = diffs.staged
        diff_type = "staged changes"
    elif unstaged: 
        target_diff = diffs.unstaged
        diff_type = "unstaged changes"
    elif last_commit: 
        target_diff = diffs.last_commit
        diff_type = "last commit"
    else:
        # Default to unstaged or staged
        target_diff = diffs.unstaged or diffs.staged
        diff_type = "current changes"
        
    if not target_diff:
        print("[yellow]No diff found to analyze.[/yellow]")
        return

    print(f"[blue]Analyzing {diff_type}...[/blue]")

    rag_query = build_rag_query(query, target_diff)
    if not rag_query:
        rag_query = target_diff[:2000]

    # 2. RAG #1: Code Context - Find relevant code from indexed codebase
    code_context = ""
    if use_rag:
        print("[blue]RAG #1: Retrieving related code from indexed codebase...[/blue]")
        try:
            code_retriever = HybridRetriever()
            related_chunks = code_retriever.search(rag_query, n_results=top_k)
            code_context = build_context_block(related_chunks)
            print(f"[green]Found {len(related_chunks)} related code chunks.[/green]")
        except Exception as e:
            print(f"[yellow]Warning: Code RAG failed: {e}[/yellow]")
    
    # 3. RAG #2: Documentation Context - Find relevant best practices
    docs_context = ""
    if use_docs_rag:
        print("[blue]RAG #2: Retrieving best practices from documentation...[/blue]")
        try:
            docs_retriever = HybridRetriever(
                collection=DOCS_DB_COLLECTION,
                bm25_index_path=DOCS_BM25_INDEX_PATH,
            )
            related_docs = docs_retriever.search(rag_query, n_results=docs_top_k)
            docs_context = build_context_block(related_docs) if related_docs else ""
            print(f"[green]Found {len(related_docs)} relevant best practices.[/green]")
        except Exception as e:
            print(f"[yellow]Warning: Docs RAG failed: {e}[/yellow]")
    
    # 4. Combine all contexts for comprehensive analysis
    combined_context = "\n\n".join(
        part for part in [code_context, docs_context] if part
    )
    full_context = build_analysis_input(query, target_diff, combined_context or None)
    if show_context:
        print("\n[bold]Context Preview:[/bold]\n")
        print(full_context)
    if context_out:
        with open(context_out, "w", encoding="utf-8") as f:
            f.write(full_context)
    
    # 4. Multi-LLM Grading with full context
    grader = MultiLLMGrader()
    print("Calling Grader 1 (Security)...")
    r1 = grader.grade_with_model("security", MODEL_GRADER_SECURITY, full_context)
    
    print("Calling Grader 2 (Logic)...")
    r2 = grader.grade_with_model("logic", MODEL_GRADER_LOGIC, full_context)
    
    print("Calling Grader 3 (Performance)...")
    r3 = grader.grade_with_model("performance", MODEL_GRADER_PERF, full_context)
    
    # 5. Final Judgment
    print("Calling Final Judge...")
    final_report = grader.judge([r1, r2, r3])
    final_report = ReportGenerator.filter_report(final_report, target_diff)
    
    # 6. Generate Report
    ReportGenerator.save_report(final_report, "bug_report.json")
    with open("bug_report_meta.json", "w", encoding="utf-8") as f:
        json.dump({"diff_type": diff_type, "diff_text": target_diff}, f, indent=2)
    print("[bold green]Analysis complete! Report saved to bug_report.md[/bold green]")
    
    # 7. Print Summary
    print("\n[bold]Consolidated Issues:[/bold]")
    for issue in final_report.consolidated_issues:
        severity_color = {"critical": "red", "high": "orange1", "medium": "yellow", "low": "green"}.get(issue.severity.lower(), "white")
        print(f"[{severity_color}]- {issue.type.upper()} ({issue.severity}): {issue.description}[/{severity_color}]")

@app.command()
def fix(issue_id: int):
    """Fix a specific issue by ID from the last report."""
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
        diff_text = None
        try:
            with open("bug_report_meta.json", "r", encoding="utf-8") as f:
                meta = json.load(f)
                diff_text = meta.get("diff_text")
        except FileNotFoundError:
            diff_text = None
        agent.solve_issue(issue, diff_text=diff_text)
    except FileNotFoundError:
        print("[red]No bug report found. Run 'analyze' first.[/red]")

@app.command()
def evaluate(
    dataset_path: str,
    use_rag: bool = typer.Option(True, "--use-rag/--no-use-rag"),
    use_docs_rag: bool = typer.Option(True, "--use-docs-rag/--no-use-docs-rag"),
    top_k: int = typer.Option(6, "--top-k"),
    docs_top_k: int = typer.Option(4, "--docs-top-k"),
):
    """Run evaluation on a labeled dataset."""
    runner = EvaluationRunner(
        use_rag=use_rag, use_docs_rag=use_docs_rag, top_k=top_k, docs_top_k=docs_top_k
    )
    results = runner.run(dataset_path)
    os.makedirs("evaluation", exist_ok=True)
    with open("evaluation/results_summary.json", "w", encoding="utf-8") as f:
        json.dump(
            {
                "precision": results["precision"],
                "recall": results["recall"],
                "f1": results["f1"],
                "fix_rate": results["fix_rate"],
                "totals": results["totals"],
            },
            f,
            indent=2,
        )
    with open("evaluation/results_details.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    generate_plots(results, "evaluation/plots")
    print("[bold green]Evaluation complete! Results saved to evaluation/results_summary.json[/bold green]")
    print(f"Precision: {results['precision']:.2f}")
    print(f"Recall: {results['recall']:.2f}")
    print(f"F1: {results['f1']:.2f}")
    print(f"Fix rate: {results['fix_rate']:.2f}")

if __name__ == "__main__":
    app()
