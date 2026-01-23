import json
import os
import re
from typing import Dict, Set

from .models import FinalReport
from .chunker import ASTChunker
from .diff_utils import parse_changed_lines
from .path_utils import normalize_repo_path, resolve_repo_path

class ReportGenerator:
    @staticmethod
    def enrich_report(report: FinalReport) -> FinalReport:
        if not report.consolidated_issues:
            return report

        file_cache: Dict[str, list[str]] = {}
        chunker = ASTChunker()
        chunk_cache: Dict[str, list] = {}
        for issue in report.consolidated_issues:
            if not issue.location or not issue.location.file:
                continue

            file_path = normalize_repo_path(issue.location.file)
            issue.location.file = file_path
            abs_path = resolve_repo_path(file_path)
            if not os.path.exists(abs_path):
                continue

            if file_path not in file_cache:
                try:
                    with open(abs_path, "r", encoding="utf-8") as f:
                        file_cache[file_path] = f.readlines()
                except Exception:
                    file_cache[file_path] = []

            line_no = issue.location.line
            if line_no and line_no > 0:
                if issue.start_line is None:
                    issue.start_line = line_no
                if issue.end_line is None:
                    issue.end_line = issue.start_line
                if issue.line_text is None:
                    lines = file_cache.get(file_path, [])
                    if line_no <= len(lines):
                        issue.line_text = lines[line_no - 1].rstrip("\n")
                if (
                    issue.chunk_start_line is None
                    or issue.chunk_end_line is None
                    or issue.chunk_name is None
                ):
                    if file_path not in chunk_cache:
                        chunk_cache[file_path] = chunker.chunk_file(abs_path)
                    for chunk in chunk_cache[file_path]:
                        if chunk.start_line <= line_no <= chunk.end_line:
                            issue.chunk_start_line = chunk.start_line
                            issue.chunk_end_line = chunk.end_line
                            issue.chunk_name = chunk.name
                            issue.chunk_type = chunk.type
                            break

        return report

    @staticmethod
    def _parse_changed_lines(diff_text: str) -> Dict[str, Set[int]]:
        return parse_changed_lines(diff_text)

    @staticmethod
    def filter_report(report: FinalReport, diff_text: str) -> FinalReport:
        if not report.consolidated_issues:
            return report

        changed_lines = ReportGenerator._parse_changed_lines(diff_text)
        diff_files = set(changed_lines.keys())
        file_cache: Dict[str, str] = {}
        cwd = os.getcwd()

        filtered = []
        for issue in report.consolidated_issues:
            severity = (issue.severity or "").lower()
            if severity not in {"critical", "high"}:
                continue
            if issue.confidence is not None and issue.confidence < 0.8:
                continue

            file_path = normalize_repo_path(issue.location.file) if issue.location else None
            if not file_path:
                continue
            if issue.location:
                issue.location.file = file_path

            abs_path = resolve_repo_path(file_path)
            if not os.path.exists(abs_path):
                continue

            rel_path = normalize_repo_path(abs_path, cwd)
            if diff_files and rel_path not in diff_files and file_path not in diff_files:
                continue

            if issue.location and issue.location.line:
                changed = changed_lines.get(rel_path) or changed_lines.get(file_path)
                if changed and issue.location.line not in changed:
                    continue

            if abs_path not in file_cache:
                try:
                    with open(abs_path, "r", encoding="utf-8") as f:
                        file_cache[abs_path] = f.read()
                except Exception:
                    file_cache[abs_path] = ""

            evidence = (issue.evidence or "").strip()
            if evidence:
                evidence_variants = {
                    evidence,
                    evidence.lstrip("+-").strip(),
                    re.sub(r"^[Ll]?\d+:\s*", "", evidence).strip(),
                }
                file_content = file_cache.get(abs_path, "")
                if not any(ev and ev in file_content for ev in evidence_variants):
                    if not any(ev and ev in diff_text for ev in evidence_variants):
                        continue

            filtered.append(issue)

        if len(filtered) == len(report.consolidated_issues):
            return report

        summary = report.summary
        if not filtered:
            summary = "No high-confidence issues remained after validation."
        else:
            summary = f"Filtered report after validation. {len(filtered)} issues retained."

        return FinalReport(
            winner_assessment=report.winner_assessment,
            consolidated_issues=filtered,
            overall_health_score=report.overall_health_score,
            summary=summary,
        )

    @staticmethod
    def to_markdown(report: FinalReport) -> str:
        md = f"# Code Review Report\n\n"
        md += f"**Overall Health Score**: {report.overall_health_score}/10\n\n"
        md += f"## Summary\n{report.summary}\n\n"
        
        if report.winner_assessment:
            md += f"> **Judge's Note**: Most helpful assessment provided by {report.winner_assessment}\n\n"
        
        md += "## Identified Issues\n\n"
        if not report.consolidated_issues:
            md += "No major issues found. Great job!\n"
        else:
            for issue in report.consolidated_issues:
                severity_emoji = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(issue.severity.lower(), "⚪")
                md += f"### {severity_emoji} {issue.type.upper()}: {issue.severity}\n"
                md += f"- **Location**: `{issue.location.file}` (Function: `{issue.location.function}`, Line: {issue.location.line})\n"
                if issue.start_line and issue.end_line:
                    md += f"- **Line Range**: {issue.start_line}-{issue.end_line}\n"
                if issue.line_text:
                    md += f"- **Line Text**: `{issue.line_text}`\n"
                if issue.chunk_start_line and issue.chunk_end_line:
                    md += f"- **Chunk Range**: {issue.chunk_start_line}-{issue.chunk_end_line}\n"
                if issue.chunk_name:
                    md += f"- **Chunk Name**: {issue.chunk_name} ({issue.chunk_type})\n"
                md += f"- **Description**: {issue.description}\n"
                md += f"- **Evidence**: `{issue.evidence}`\n"
                md += f"- **Suggested Fix**: {issue.suggested_fix}\n\n"
        
        return md

    @staticmethod
    def save_report(report, path: str):
        if isinstance(report, FinalReport):
            report = ReportGenerator.enrich_report(report)

        if hasattr(report, "model_dump"):
            payload = report.model_dump()
        else:
            payload = report
        with open(path, "w") as f:
            json.dump(payload, f, indent=2)

        if isinstance(report, FinalReport):
            md_path = path.replace(".json", ".md")
            with open(md_path, "w") as f:
                f.write(ReportGenerator.to_markdown(report))
