import json
import os
import re
from typing import Dict, Optional, Set

from .models import FinalReport
from .chunker import ASTChunker
from .diff_utils import parse_changed_lines


class ReportGenerator:
    @staticmethod
    def _find_evidence_line(lines: list[str], evidence: str) -> Optional[int]:
        """Search for evidence text in file lines, return 1-based line number."""
        if not evidence or not lines:
            return None

        evidence_clean = evidence.strip().lstrip("+-").strip()
        if not evidence_clean:
            return None

        for i, line in enumerate(lines):
            if evidence_clean in line:
                return i + 1

        first_part = evidence_clean.split("\n")[0].strip()
        if first_part and len(first_part) > 10:
            for i, line in enumerate(lines):
                if first_part in line:
                    return i + 1

        return None

    @staticmethod
    def _validate_and_correct_line(issue, lines: list[str]) -> int:
        """Validate LLM line number against evidence, correct if mismatched."""
        line_no = issue.location.line if issue.location else None
        evidence = issue.evidence or ""

        if not lines:
            return line_no or 1

        if line_no and 0 < line_no <= len(lines):
            current_line = lines[line_no - 1]
            evidence_clean = evidence.strip().lstrip("+-").strip()
            if evidence_clean and evidence_clean in current_line:
                return line_no

        found_line = ReportGenerator._find_evidence_line(lines, evidence)
        if found_line:
            print(f"[LINE FIX] Corrected line {line_no} -> {found_line}")
            return found_line

        return line_no or 1

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

            file_path = issue.location.file
            if not os.path.exists(file_path):
                continue

            if file_path not in file_cache:
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        file_cache[file_path] = f.readlines()
                except Exception:
                    file_cache[file_path] = []

            lines = file_cache.get(file_path, [])

            corrected_line = ReportGenerator._validate_and_correct_line(issue, lines)
            if issue.location.line != corrected_line:
                issue.location.line = corrected_line

            line_no = corrected_line
            if line_no and line_no > 0:
                if issue.start_line is None:
                    issue.start_line = line_no
                if issue.end_line is None:
                    issue.end_line = issue.start_line
                if issue.line_text is None:
                    if line_no <= len(lines):
                        issue.line_text = lines[line_no - 1].rstrip("\n")
                if (
                    issue.chunk_start_line is None
                    or issue.chunk_end_line is None
                    or issue.chunk_name is None
                ):
                    if file_path not in chunk_cache:
                        chunk_cache[file_path] = chunker.chunk_file(file_path)
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

        filtered = []
        for issue in report.consolidated_issues:
            severity = (issue.severity or "").lower()
            if severity not in {"critical", "high"}:
                continue
            if issue.confidence is not None and issue.confidence < 0.8:
                continue

            file_path = issue.location.file if issue.location else None
            if not file_path or not os.path.exists(file_path):
                continue

            if diff_files and file_path not in diff_files:
                continue

            if issue.location and issue.location.line and file_path in changed_lines:
                if issue.location.line not in changed_lines[file_path]:
                    continue

            if file_path not in file_cache:
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        file_cache[file_path] = f.read()
                except Exception:
                    file_cache[file_path] = ""

            evidence = (issue.evidence or "").strip()
            if evidence:
                evidence_variants = {evidence, evidence.lstrip("+-").strip()}
                file_content = file_cache.get(file_path, "")
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
            summary = (
                f"Filtered report after validation. {len(filtered)} issues retained."
            )

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
                severity_emoji = {
                    "critical": "🔴",
                    "high": "🟠",
                    "medium": "🟡",
                    "low": "🟢",
                }.get(issue.severity.lower(), "⚪")
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
