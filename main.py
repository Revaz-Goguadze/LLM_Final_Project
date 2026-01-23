import os
import typer
from rich import print
import json
from codereview.git_analyzer import GitAnalyzer
from codereview.grader import MultiLLMGrader
from codereview.report_generator import ReportGenerator
from codereview.rag_builder import build_rag_query, build_context_block, build_analysis_input
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

def _truncate_lines(lines: list[str], max_chars: int) -> list[str]:
    used = 0
    kept = []
    for line in lines:
        line_len = len(line) + 1
        if used + line_len > max_chars and kept:
            break
        kept.append(line)
        used += line_len
        if used >= max_chars:
            break
    return kept


def _build_snapshot(paths: list[str], max_chars: int = 2000) -> str:
    blocks = []
    cwd = os.getcwd()
    for file_path in paths:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.read().splitlines()
        except Exception:
            continue
        lines = _truncate_lines(lines, max_chars)
        rel_path = os.path.relpath(file_path, cwd)
        line_count = len(lines)
        if line_count == 0:
            continue
        header = [
            f"diff --git a/{rel_path} b/{rel_path}",
            f"--- a/{rel_path}",
            f"+++ b/{rel_path}",
            f"@@ -1,{line_count} +1,{line_count} @@",
        ]
        body = [f"+{line}" for line in lines]
        blocks.append("\n".join(header + body))
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
    changed_only: bool = typer.Option(False, "--changed-only"),
    base_ref: str = typer.Option("HEAD~1", "--base-ref"),
):
    """Analyze changes for bugs and bad practices."""
    print("[bold blue]Starting analysis...[/bold blue]")
    
    target_diff = ""
    diff_type = "changes"
    if changed_only:
        analyzer = GitAnalyzer()
        target_diff = analyzer.get_diff_against(base_ref)
        diff_type = f"changes since {base_ref}"
    elif path:
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

    changed_ranges = {}
    changed_files = []
    if changed_only and target_diff:
        from codereview.diff_utils import parse_changed_lines, lines_to_ranges
        from codereview.diff_utils import parse_unified_diff_files
        from codereview.config import DEMO_EXCLUDE_PREFIXES
        changed_lines = parse_changed_lines(target_diff)
        for file_path, lines in changed_lines.items():
            changed_ranges[file_path] = lines_to_ranges(lines)
        changed_files = parse_unified_diff_files(target_diff)
        if DEMO_EXCLUDE_PREFIXES:
            changed_files = [
                path
                for path in changed_files
                if not any(path.startswith(prefix) for prefix in DEMO_EXCLUDE_PREFIXES)
            ]

    rag_query = build_rag_query(query, target_diff)
    if not rag_query:
        rag_query = target_diff[:2000]

    # 2. RAG #1: Code Context - Find relevant code from indexed codebase
    code_context = ""
    if use_rag:
        print("[blue]RAG #1: Retrieving related code from indexed codebase...[/blue]")
        try:
            from codereview.retriever import HybridRetriever
            if changed_only and changed_files:
                from codereview.indexer import CodebaseIndexer
                indexer = CodebaseIndexer()
                for file_path in changed_files:
                    indexer.index_file(file_path)
            code_retriever = HybridRetriever()
            related_chunks = code_retriever.search(rag_query, n_results=top_k)
            code_context = build_context_block(related_chunks)
            print(f"[green]Found {len(related_chunks)} related code chunks.[/green]")
            if not related_chunks:
                print("[yellow]No code chunks found. Rebuilding index and retrying...[/yellow]")
                from codereview.indexer import CodebaseIndexer
                CodebaseIndexer().index_directory(path or os.getcwd())
                code_retriever = HybridRetriever()
                related_chunks = code_retriever.search(rag_query, n_results=top_k)
                code_context = build_context_block(related_chunks)
                print(f"[green]Found {len(related_chunks)} related code chunks.[/green]")
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
                    print(f"[green]Found {len(related_chunks)} related code chunks.[/green]")
                except Exception as retry_error:
                    print(f"[yellow]Warning: Code RAG retry failed: {retry_error}[/yellow]")
            elif "list index out of range" in str(e):
                print("[yellow]Rebuilding code index and retrying...[/yellow]")
                from codereview.indexer import CodebaseIndexer
                CodebaseIndexer().index_directory(path or os.getcwd())
                try:
                    from codereview.retriever import HybridRetriever
                    code_retriever = HybridRetriever()
                    related_chunks = code_retriever.search(rag_query, n_results=top_k)
                    code_context = build_context_block(related_chunks)
                    print(f"[green]Found {len(related_chunks)} related code chunks.[/green]")
                except Exception as retry_error:
                    print(f"[yellow]Warning: Code RAG retry failed: {retry_error}[/yellow]")
    
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
                print("[yellow]No docs found. Rebuilding docs index and retrying...[/yellow]")
                from codereview.docs_indexer import DocsIndexer
                DocsIndexer().index_directory("docs")
                docs_retriever = HybridRetriever(
                    collection=DOCS_DB_COLLECTION,
                    bm25_index_path=DOCS_BM25_INDEX_PATH,
                )
                related_docs = docs_retriever.search(rag_query, n_results=docs_top_k)
                docs_context = build_context_block(related_docs) if related_docs else ""
                print(f"[green]Found {len(related_docs)} relevant best practices.[/green]")
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
                    related_docs = docs_retriever.search(rag_query, n_results=docs_top_k)
                    docs_context = build_context_block(related_docs) if related_docs else ""
                    print(f"[green]Found {len(related_docs)} relevant best practices.[/green]")
                except Exception as retry_error:
                    print(f"[yellow]Warning: Docs RAG retry failed: {retry_error}[/yellow]")
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
                    related_docs = docs_retriever.search(rag_query, n_results=docs_top_k)
                    docs_context = build_context_block(related_docs) if related_docs else ""
                    print(f"[green]Found {len(related_docs)} relevant best practices.[/green]")
                except Exception as retry_error:
                    print(f"[yellow]Warning: Docs RAG retry failed: {retry_error}[/yellow]")
    
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
        json.dump(
            {
                "diff_type": diff_type,
                "diff_text": target_diff,
                "query": query,
                "path": path,
                "use_rag": use_rag,
                "use_docs_rag": use_docs_rag,
                "changed_only": changed_only,
                "base_ref": base_ref,
                "changed_ranges": changed_ranges,
                "code_context": code_context,
                "docs_context": docs_context,
            },
            f,
            indent=2,
        )
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
    from codereview.issue_updater import update_report_for_file
    from codereview.indexer import CodebaseIndexer
    from codereview.path_utils import resolve_repo_path

    try:
        fix_everything = os.getenv("FIX_EVERYTHING", "1") == "1"
        if fix_everything and issue_id != 0:
            print("[yellow]Fix-all mode enabled; skipping per-issue invocation.[/yellow]")
            return

        max_passes = int(os.getenv("MAX_FIX_PASSES", "5"))
        agent = ReActAgent()

        fixed = []
        patch_log = []
        remaining = []
        found_total = 0
        issue_status = {}
        issue_details = {}

        for pass_idx in range(1, max_passes + 1):
            try:
                with open("bug_report_meta.json", "r", encoding="utf-8") as f:
                    meta = json.load(f)
            except FileNotFoundError:
                meta = {}
            agent.context_cache = {
                "code_context": meta.get("code_context", ""),
                "docs_context": meta.get("docs_context", ""),
            }

            analyze(
                staged=False,
                unstaged=False,
                last_commit=False,
                path=meta.get("path"),
                query=meta.get("query"),
                use_rag=meta.get("use_rag", True),
                use_docs_rag=meta.get("use_docs_rag", True),
                changed_only=meta.get("changed_only", False),
                base_ref=meta.get("base_ref", "HEAD~1"),
            )

            with open("bug_report.json", "r") as f:
                report_data = json.load(f)
            issues = report_data.get("consolidated_issues", [])
            if pass_idx == 1:
                found_total = len(issues)
            if not issues:
                remaining = []
                break

            severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
            issues_sorted = sorted(
                issues,
                key=lambda item: (
                    severity_order.get(str(item.get("severity", "")).lower(), 9),
                    (item.get("location") or {}).get("file", ""),
                ),
            )

            diff_text = meta.get("diff_text")
            for issue_data in issues_sorted:
                issue_id = issue_data.get("id")
                if issue_id:
                    issue_details[issue_id] = issue_data
                if issue_id and issue_status.get(issue_id, {}).get("status") == "FIXED":
                    continue
                if meta.get("changed_ranges"):
                    file_path = issue_data.get("location", {}).get("file")
                    if file_path:
                        ranges = meta.get("changed_ranges", {}).get(file_path, [])
                        issue_data["changed_ranges"] = ranges
                issue = BugIssue(**issue_data)
                success = agent.solve_issue(issue, diff_text=diff_text)
                if success and issue.location and issue.location.file:
                    file_path = issue.location.file
                    update_report_for_file("bug_report.json", file_path)
                    try:
                        CodebaseIndexer().index_file(resolve_repo_path(file_path))
                    except Exception as exc:
                        print(
                            f"[yellow]Warning: Could not reindex {file_path}: {exc}[/yellow]"
                        )

                status = agent.last_fix_status or ("FIXED" if success else "FAILED")
                reason = agent.last_fix_reason
                if issue.id:
                    issue_status[issue.id] = {"status": status, "reason": reason}
                if status == "FIXED":
                    fixed.append(
                        {
                            "id": issue.id or "",
                            "severity": issue.severity,
                            "file": (issue.location.file if issue.location else ""),
                            "line": (issue.location.line if issue.location else ""),
                            "function": (issue.location.function if issue.location else ""),
                            "description": issue.description,
                        }
                    )
                    patch_log.append(
                        {
                            "id": issue.id or "",
                            "description": issue.description,
                            "attempts": agent.last_fix_attempts,
                            "verification": agent.last_verification_output,
                            "diff_summary": agent.last_fix_summary,
                        }
                    )
                elif status == "SKIPPED":
                    patch_log.append(
                        {
                            "id": issue.id or "",
                            "description": issue.description,
                            "attempts": agent.last_fix_attempts,
                            "verification": agent.last_verification_output,
                            "diff_summary": agent.last_fix_summary,
                        }
                    )
                else:
                    remaining = issues
                    break
            else:
                remaining = []

        if not remaining:
            try:
                with open("bug_report.json", "r", encoding="utf-8") as f:
                    report_data = json.load(f)
                remaining = report_data.get("consolidated_issues", [])
            except FileNotFoundError:
                remaining = []

        fixed_count = len(fixed)
        failed = [iid for iid, meta in issue_status.items() if meta["status"] == "FAILED"]
        skipped = [iid for iid, meta in issue_status.items() if meta["status"] == "SKIPPED"]
        remaining_count = len(
            [iid for iid, meta in issue_status.items() if meta["status"] not in {"FIXED", "SKIPPED"}]
        )
        summary_lines = [
            "# Fix Summary",
            "",
            f"- Found: {found_total}",
            f"- Fixed: {fixed_count}",
            f"- Failed: {len(failed)}",
            f"- Skipped: {len(skipped)}",
            f"- Remaining actionable: {remaining_count}",
            "",
            "## Fixed Issues",
        ]
        if fixed:
            for item in fixed:
                summary_lines.append(
                    f"- {item['id']} {item['severity']} "
                    f"{item['file']}:{item['line']} {item.get('function','')}: "
                    f"{item['description']}"
                )
        else:
            summary_lines.append("- None")
        summary_lines.append("")
        summary_lines.append("## Failed Issues")
        if failed:
            for issue_id in failed:
                item = issue_details.get(issue_id, {})
                loc = item.get("location") or {}
                reason = issue_status.get(issue_id, {}).get("reason", "")
                summary_lines.append(
                    f"- {issue_id} {item.get('severity','')} "
                    f"{loc.get('file','')}:{loc.get('line','')}: {item.get('description','unknown')}"
                )
                if reason:
                    summary_lines.append(f"  - Last error: {reason}")
        else:
            summary_lines.append("- None")
        summary_lines.append("")
        summary_lines.append("## Skipped Issues")
        if skipped:
            for issue_id in skipped:
                item = issue_details.get(issue_id, {})
                loc = item.get("location") or {}
                reason = issue_status.get(issue_id, {}).get("reason", "")
                summary_lines.append(
                    f"- {issue_id} {item.get('severity','')} "
                    f"{loc.get('file','')}:{loc.get('line','')}: {item.get('description','unknown')}"
                )
                if reason:
                    summary_lines.append(f"  - Reason: {reason}")
        else:
            summary_lines.append("- None")
        summary_lines.append("")
        summary_lines.append("## Remaining Issues")
        if remaining_count:
            for issue_id, meta in issue_status.items():
                if meta["status"] in {"FIXED", "SKIPPED"}:
                    continue
                item = issue_details.get(issue_id, {})
                loc = item.get("location") or {}
                summary_lines.append(
                    f"- {issue_id} {item.get('severity','')} "
                    f"{loc.get('file','')}:{loc.get('line','')}: {item.get('description','unknown')}"
                )
        else:
            summary_lines.append("- None")
        summary_lines.append("")
        summary_lines.append("## Patch Log")
        if patch_log:
            for entry in patch_log:
                summary_lines.append(
                    f"- {entry.get('id','')} {entry['description']} "
                    f"(attempts: {entry['attempts']})"
                )
                if entry.get("verification"):
                    summary_lines.append(f"  - Verification: {entry['verification']}")
                if entry["diff_summary"]:
                    summary_lines.append("```diff")
                    summary_lines.append(entry["diff_summary"])
                    summary_lines.append("```")
        else:
            summary_lines.append("- None")
        with open("bug_report.md", "w", encoding="utf-8") as f:
            f.write("\n".join(summary_lines))

        issues_final = {
            "found": found_total,
            "fixed": fixed_count,
            "failed": len(failed),
            "skipped": len(skipped),
            "remaining_actionable": remaining_count,
            "fixed_issues": fixed,
            "remaining_issues": remaining,
            "failed_issues": failed,
            "skipped_issues": skipped,
            "patch_log": patch_log,
        }
        with open("issues_final.json", "w", encoding="utf-8") as f:
            json.dump(issues_final, f, indent=2)

        _print_consolidated_issues_console(issue_details, issue_status)
    except FileNotFoundError:
        print("[red]No bug report found. Run 'analyze' first.[/red]")


def _print_consolidated_issues_console(issue_details: dict, issue_status: dict) -> None:
    if not issue_details:
        print("\nConsolidated Issues: 0 actionable remaining")
        print("- None")
        return
    grouped = {"security": [], "logic": [], "performance": []}
    for issue_id, issue in issue_details.items():
        issue_type = (issue.get("type") or "").lower()
        status_meta = issue_status.get(issue_id, {"status": "FAILED", "reason": ""})
        entry = {"issue": issue, "status": status_meta}
        if issue_type in grouped:
            grouped[issue_type].append(entry)

    remaining_actionable = sum(
        1
        for meta in issue_status.values()
        if meta.get("status") not in {"FIXED", "SKIPPED"}
    )
    print(
        f"\nConsolidated Issues: {remaining_actionable} actionable remaining"
    )
    for issue_type, entries in grouped.items():
        print(f"- {issue_type.capitalize()}:")
        if not entries:
            print("  - None")
            continue
        for entry in entries:
            issue = entry["issue"]
            status = entry["status"].get("status", "FAILED")
            reason = entry["status"].get("reason", "")
            loc = issue.get("location") or {}
            title = (issue.get("description") or "").split("\n")[0]
            line = loc.get("line") or ""
            func = loc.get("function") or ""
            status_text = status
            if reason:
                status_text = f"{status} ({reason})"
            print(
                f"  - {issue.get('severity','')} {loc.get('file','')}:{line} "
                f"{func} {title} [{status_text}]"
            )

@app.command()
def evaluate(
    dataset_path: str,
    use_rag: bool = typer.Option(True, "--use-rag/--no-use-rag"),
    use_docs_rag: bool = typer.Option(True, "--use-docs-rag/--no-use-docs-rag"),
    top_k: int = typer.Option(6, "--top-k"),
    docs_top_k: int = typer.Option(4, "--docs-top-k"),
    mode: str = typer.Option("both", "--mode", help="Evaluation mode: 'single', 'multi', or 'both'"),
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
            use_rag=use_rag, use_docs_rag=use_docs_rag, top_k=top_k, docs_top_k=docs_top_k, mode="single"
        )
        single_results = single_runner.run(dataset_path)
        with open("evaluation/results_summary_single.json", "w", encoding="utf-8") as f:
            json.dump(single_results, f, indent=2)
        print(f"[cyan]Single mode - F1: {single_results['f1']:.2f}, Precision: {single_results['precision']:.2f}, Recall: {single_results['recall']:.2f}[/cyan]")

    # Run multi mode if requested
    if mode in ("multi", "both"):
        print("[yellow]Running multi-model evaluation...[/yellow]")
        multi_runner = EvaluationRunner(
            use_rag=use_rag, use_docs_rag=use_docs_rag, top_k=top_k, docs_top_k=docs_top_k, mode="multi"
        )
        multi_results = multi_runner.run(dataset_path)
        with open("evaluation/results_summary_multi.json", "w", encoding="utf-8") as f:
            json.dump(multi_results, f, indent=2)
        generate_plots(multi_results, "evaluation/plots")
        print(f"[cyan]Multi mode - F1: {multi_results['f1']:.2f}, Precision: {multi_results['precision']:.2f}, Recall: {multi_results['recall']:.2f}[/cyan]")

    # Compute improvement if both modes were run
    if mode == "both" and single_results and multi_results:
        improvement = compute_multi_llm_improvement(single_results, multi_results)
        with open("evaluation/improvement.json", "w", encoding="utf-8") as f:
            json.dump(improvement, f, indent=2)

        print("\n[bold green]=== Multi-LLM Improvement vs Single Baseline ===[/bold green]")
        print(f"F1 Improvement: {improvement['f1_improvement_pct']:+.1f}% (single: {improvement['single_f1']:.2f} -> multi: {improvement['multi_f1']:.2f})")
        print(f"Precision Improvement: {improvement['precision_improvement_pct']:+.1f}%")
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

    print("\n[bold green]Evaluation complete! Results saved to evaluation/[/bold green]")
    print(f"Final Precision: {results['precision']:.2f}")
    print(f"Final Recall: {results['recall']:.2f}")
    print(f"Final F1: {results['f1']:.2f}")
    print(f"Final Fix rate: {results['fix_rate']:.2f}")

if __name__ == "__main__":
    app()
