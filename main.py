import os
import typer
from rich import print
import json
from codereview.git_analyzer import GitAnalyzer
from codereview.grader import MultiLLMGrader
from codereview.report_generator import ReportGenerator
from codereview.rag_builder import (
    build_rag_query,
    build_context_block,
    build_analysis_input,
)
from codereview.config import (
    MODEL_GRADER_SECURITY,
    MODEL_GRADER_LOGIC,
    MODEL_GRADER_PERF,
    DOCS_DB_COLLECTION,
    DOCS_BM25_INDEX_PATH,
)

app = typer.Typer()


def _read_target_files(path: str) -> list[str]:
    paths: list[str] = []
    if os.path.isdir(path):
        for root, dirs, files in os.walk(os.path.abspath(path)):
            parts = [part for part in root.split(os.sep) if part]
            if any(part.startswith(".") for part in parts):
                continue
            if "venv" in root or "__pycache__" in root or "node_modules" in root:
                continue
            for file in files:
                if file.endswith((".py", ".js", ".jsx", ".ts", ".tsx")):
                    paths.append(os.path.join(root, file))
    elif os.path.isfile(path):
        paths.append(os.path.abspath(path))
    return paths


def _build_snapshot(paths: list[str], max_chars: int = 2000) -> str:
    blocks = []
    for file_path in paths:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception:
            continue
        content = content[:max_chars]
        blocks.append(f"FILE: {file_path}\n{content}")
    return "\n\n".join(blocks)


@app.command()
def index(path: str = "."):
    """Index the codebase (Code RAG)."""
    from codereview.indexer import CodebaseIndexer

    print(f"[bold blue]Indexing codebase at {path}...[/bold blue]")
    indexer = CodebaseIndexer()
    indexer.index_directory(path)
    print("[bold green]Codebase indexing complete![/bold green]")


@app.command()
def index_docs(path: str = "docs"):
    """Index best practices documentation (Documentation RAG)."""
    from codereview.docs_indexer import DocsIndexer

    print(f"[bold blue]Indexing documentation at {path}...[/bold blue]")
    indexer = DocsIndexer()
    indexer.index_directory(path)
    print("[bold green]Documentation indexing complete![/bold green]")


@app.command()
def analyze(
    staged: bool = False,
    unstaged: bool = False,
    last_commit: bool = False,
    path: str = None,
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

    target_diff = ""
    diff_type = "changes"
    if path:
        target_paths = _read_target_files(path)
        target_diff = _build_snapshot(target_paths)
        diff_type = f"files under {path}"
    else:
        # 1. Extract Diffs
        analyzer = GitAnalyzer()
        diffs = analyzer.get_diffs()

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
            from codereview.retriever import HybridRetriever

            code_retriever = HybridRetriever()
            related_chunks = code_retriever.search(rag_query, n_results=top_k)
            code_context = build_context_block(related_chunks)
            print(f"[green]Found {len(related_chunks)} related code chunks.[/green]")
            if not related_chunks:
                print(
                    "[yellow]No code chunks found. Rebuilding index and retrying...[/yellow]"
                )
                from codereview.indexer import CodebaseIndexer

                CodebaseIndexer().index_directory(path or os.getcwd())
                code_retriever = HybridRetriever()
                related_chunks = code_retriever.search(rag_query, n_results=top_k)
                code_context = build_context_block(related_chunks)
                print(
                    f"[green]Found {len(related_chunks)} related code chunks.[/green]"
                )
        except Exception as e:
            print(f"[yellow]Warning: Code RAG failed: {e}[/yellow]")
            if "Collection" in str(e) and "does not exist" in str(e):
                print("[yellow]Rebuilding code index and retrying...[/yellow]")
                from codereview.indexer import CodebaseIndexer

                CodebaseIndexer().index_directory(os.getcwd())
                try:
                    from codereview.retriever import HybridRetriever

                    code_retriever = HybridRetriever()
                    related_chunks = code_retriever.search(rag_query, n_results=top_k)
                    code_context = build_context_block(related_chunks)
                    print(
                        f"[green]Found {len(related_chunks)} related code chunks.[/green]"
                    )
                except Exception as retry_error:
                    print(
                        f"[yellow]Warning: Code RAG retry failed: {retry_error}[/yellow]"
                    )
            elif "list index out of range" in str(e):
                print("[yellow]Rebuilding code index and retrying...[/yellow]")
                from codereview.indexer import CodebaseIndexer

                CodebaseIndexer().index_directory(path or os.getcwd())
                try:
                    from codereview.retriever import HybridRetriever

                    code_retriever = HybridRetriever()
                    related_chunks = code_retriever.search(rag_query, n_results=top_k)
                    code_context = build_context_block(related_chunks)
                    print(
                        f"[green]Found {len(related_chunks)} related code chunks.[/green]"
                    )
                except Exception as retry_error:
                    print(
                        f"[yellow]Warning: Code RAG retry failed: {retry_error}[/yellow]"
                    )

    # 3. RAG #2: Documentation Context - Find relevant best practices
    docs_context = ""
    if use_docs_rag:
        print("[blue]RAG #2: Retrieving best practices from documentation...[/blue]")
        try:
            from codereview.retriever import HybridRetriever

            docs_retriever = HybridRetriever(
                collection=DOCS_DB_COLLECTION,
                bm25_index_path=DOCS_BM25_INDEX_PATH,
            )
            related_docs = docs_retriever.search(rag_query, n_results=docs_top_k)
            docs_context = build_context_block(related_docs) if related_docs else ""
            print(f"[green]Found {len(related_docs)} relevant best practices.[/green]")
            if not related_docs:
                print(
                    "[yellow]No docs found. Rebuilding docs index and retrying...[/yellow]"
                )
                from codereview.docs_indexer import DocsIndexer

                DocsIndexer().index_directory("docs")
                docs_retriever = HybridRetriever(
                    collection=DOCS_DB_COLLECTION,
                    bm25_index_path=DOCS_BM25_INDEX_PATH,
                )
                related_docs = docs_retriever.search(rag_query, n_results=docs_top_k)
                docs_context = build_context_block(related_docs) if related_docs else ""
                print(
                    f"[green]Found {len(related_docs)} relevant best practices.[/green]"
                )
        except Exception as e:
            print(f"[yellow]Warning: Docs RAG failed: {e}[/yellow]")
            if "Collection" in str(e) and "does not exist" in str(e):
                print("[yellow]Rebuilding docs index and retrying...[/yellow]")
                from codereview.docs_indexer import DocsIndexer

                DocsIndexer().index_directory("docs")
                try:
                    from codereview.retriever import HybridRetriever

                    docs_retriever = HybridRetriever(
                        collection=DOCS_DB_COLLECTION,
                        bm25_index_path=DOCS_BM25_INDEX_PATH,
                    )
                    related_docs = docs_retriever.search(
                        rag_query, n_results=docs_top_k
                    )
                    docs_context = (
                        build_context_block(related_docs) if related_docs else ""
                    )
                    print(
                        f"[green]Found {len(related_docs)} relevant best practices.[/green]"
                    )
                except Exception as retry_error:
                    print(
                        f"[yellow]Warning: Docs RAG retry failed: {retry_error}[/yellow]"
                    )
            elif "list index out of range" in str(e):
                print("[yellow]Rebuilding docs index and retrying...[/yellow]")
                from codereview.docs_indexer import DocsIndexer

                DocsIndexer().index_directory("docs")
                try:
                    from codereview.retriever import HybridRetriever

                    docs_retriever = HybridRetriever(
                        collection=DOCS_DB_COLLECTION,
                        bm25_index_path=DOCS_BM25_INDEX_PATH,
                    )
                    related_docs = docs_retriever.search(
                        rag_query, n_results=docs_top_k
                    )
                    docs_context = (
                        build_context_block(related_docs) if related_docs else ""
                    )
                    print(
                        f"[green]Found {len(related_docs)} relevant best practices.[/green]"
                    )
                except Exception as retry_error:
                    print(
                        f"[yellow]Warning: Docs RAG retry failed: {retry_error}[/yellow]"
                    )

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

    # 4. Multi-LLM Grading with full context (parallel for speed)
    grader = MultiLLMGrader()
    print("[blue]Running parallel grading (Security, Logic, Performance)...[/blue]")
    r1, r2, r3 = grader.grade_all_parallel(
        full_context,
        MODEL_GRADER_SECURITY,
        MODEL_GRADER_LOGIC,
        MODEL_GRADER_PERF,
    )

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
        severity_color = {
            "critical": "red",
            "high": "orange1",
            "medium": "yellow",
            "low": "green",
        }.get(issue.severity.lower(), "white")
        print(
            f"[{severity_color}]- {issue.type.upper()} ({issue.severity}): {issue.description}[/{severity_color}]"
        )


@app.command()
def fix(
    issue_id: int,
):
    """Fix a specific issue by ID from the last report."""
    from codereview.agent import ReActAgent
    from codereview.models import BugIssue

    print(f"[cyan]Loading issue {issue_id} from bug_report.json...[/cyan]")

    try:
        with open("bug_report.json", "r") as f:
            report_data = json.load(f)

        issues = report_data.get("consolidated_issues", [])
        if not issues or issue_id >= len(issues):
            print(
                f"[red]Issue ID {issue_id} not found. Available: 0-{len(issues) - 1}[/red]"
            )
            return

        issue = BugIssue(**issues[issue_id])
        print(f"[cyan]Issue: {issue.description[:80]}...[/cyan]")
        print(f"[cyan]File: {issue.location.file}:{issue.location.line}[/cyan]")

        agent = ReActAgent()
        diff_text = None
        try:
            with open("bug_report_meta.json", "r", encoding="utf-8") as f:
                meta = json.load(f)
                diff_text = meta.get("diff_text")
        except FileNotFoundError:
            diff_text = None

        success = agent.solve_issue(issue, diff_text=diff_text)
        if success:
            print("[bold green]Fix applied successfully![/bold green]")
        else:
            print("[bold red]Fix failed after all attempts.[/bold red]")
    except FileNotFoundError:
        print("[red]No bug report found. Run 'analyze' first.[/red]")


@app.command()
def evaluate(
    dataset_path: str,
    use_rag: bool = typer.Option(True, "--use-rag/--no-use-rag"),
    use_docs_rag: bool = typer.Option(True, "--use-docs-rag/--no-use-docs-rag"),
    top_k: int = typer.Option(6, "--top-k"),
    docs_top_k: int = typer.Option(4, "--docs-top-k"),
    mode: str = typer.Option(
        "both", "--mode", help="Evaluation mode: 'single', 'multi', or 'both'"
    ),
):
    """Run evaluation on a labeled dataset.

    Modes:
    - single: Logic grader only (baseline)
    - multi: All graders + judge (full pipeline)
    - both: Run both and compute improvement metric
    """
    from codereview.evaluator import EvaluationRunner, compute_multi_llm_improvement
    from codereview.eval_plots import generate_plots

    os.makedirs("evaluation", exist_ok=True)

    single_results = None
    multi_results = None

    # Run single mode if requested
    if mode in ("single", "both"):
        print("[yellow]Running single-model baseline evaluation...[/yellow]")
        single_runner = EvaluationRunner(
            use_rag=use_rag,
            use_docs_rag=use_docs_rag,
            top_k=top_k,
            docs_top_k=docs_top_k,
            mode="single",
        )
        single_results = single_runner.run(dataset_path)
        with open("evaluation/results_summary_single.json", "w", encoding="utf-8") as f:
            json.dump(single_results, f, indent=2)
        print(
            f"[cyan]Single mode - F1: {single_results['f1']:.2f}, Precision: {single_results['precision']:.2f}, Recall: {single_results['recall']:.2f}[/cyan]"
        )

    # Run multi mode if requested
    if mode in ("multi", "both"):
        print("[yellow]Running multi-model evaluation...[/yellow]")
        multi_runner = EvaluationRunner(
            use_rag=use_rag,
            use_docs_rag=use_docs_rag,
            top_k=top_k,
            docs_top_k=docs_top_k,
            mode="multi",
        )
        multi_results = multi_runner.run(dataset_path)
        with open("evaluation/results_summary_multi.json", "w", encoding="utf-8") as f:
            json.dump(multi_results, f, indent=2)
        generate_plots(multi_results, "evaluation/plots")
        print(
            f"[cyan]Multi mode - F1: {multi_results['f1']:.2f}, Precision: {multi_results['precision']:.2f}, Recall: {multi_results['recall']:.2f}[/cyan]"
        )

    # Compute improvement if both modes were run
    if mode == "both" and single_results and multi_results:
        improvement = compute_multi_llm_improvement(single_results, multi_results)
        with open("evaluation/improvement.json", "w", encoding="utf-8") as f:
            json.dump(improvement, f, indent=2)

        print(
            "\n[bold green]=== Multi-LLM Improvement vs Single Baseline ===[/bold green]"
        )
        print(
            f"F1 Improvement: {improvement['f1_improvement_pct']:+.1f}% (single: {improvement['single_f1']:.2f} -> multi: {improvement['multi_f1']:.2f})"
        )
        print(
            f"Precision Improvement: {improvement['precision_improvement_pct']:+.1f}%"
        )
        print(f"Recall Improvement: {improvement['recall_improvement_pct']:+.1f}%")
        print(f"Fix Rate Improvement: {improvement['fix_rate_improvement_pct']:+.1f}%")

        # Use multi results as primary summary
        results = multi_results
    elif single_results:
        results = single_results
    else:
        results = multi_results

    # Write legacy summary file for backward compatibility
    with open("evaluation/results_summary.json", "w", encoding="utf-8") as f:
        json.dump(
            {
                "mode": mode,
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

    print(
        "\n[bold green]Evaluation complete! Results saved to evaluation/[/bold green]"
    )
    print(f"Final Precision: {results['precision']:.2f}")
    print(f"Final Recall: {results['recall']:.2f}")
    print(f"Final F1: {results['f1']:.2f}")
    print(f"Final Fix rate: {results['fix_rate']:.2f}")


if __name__ == "__main__":
    app()
