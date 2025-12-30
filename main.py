import os
import typer
from rich import print
from codereview.git_analyzer import GitAnalyzer
from codereview.indexer import CodebaseIndexer
from codereview.retriever import HybridRetriever
from codereview.grader import MultiLLMGrader
from codereview.report_generator import ReportGenerator
from codereview.config import MODEL_GRADER_SECURITY, MODEL_GRADER_LOGIC, MODEL_GRADER_PERF

app = typer.Typer()

@app.command()
def index(path: str = "."):
    """Index the codebase."""
    print(f"[bold blue]Indexing codebase at {path}...[/bold blue]")
    indexer = CodebaseIndexer()
    indexer.index_directory(path)
    print("[bold green]Indexing complete![/bold green]")

@app.command()
def analyze(staged: bool = False, unstaged: bool = False, last_commit: bool = False):
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

    # 2. RAG Context (Optional: find relevant code related to diff)
    # For now, we analyze the diff content directly as the primary context
    
    # 3. Multi-LLM Grading
    grader = MultiLLMGrader()
    print("Calling Grader 1 (Security)...")
    r1 = grader.grade_with_model("security", MODEL_GRADER_SECURITY, target_diff)
    
    print("Calling Grader 2 (Logic)...")
    r2 = grader.grade_with_model("logic", MODEL_GRADER_LOGIC, target_diff)
    
    print("Calling Grader 3 (Performance)...")
    r3 = grader.grade_with_model("performance", MODEL_GRADER_PERF, target_diff)
    
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

if __name__ == "__main__":
    app()
