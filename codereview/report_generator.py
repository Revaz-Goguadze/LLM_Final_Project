import json
import os
import re
from typing import Dict, Set

from .models import FinalReport

class ReportGenerator:
    @staticmethod
    def _parse_changed_lines(diff_text: str) -> Dict[str, Set[int]]:
        changed: Dict[str, Set[int]] = {}
        current_file = None
        current_line = None
        for line in diff_text.splitlines():
            if line.startswith("+++ b/"):
                current_file = line[6:].strip()
                continue
            if line.startswith("@@"):
                match = re.search(r"\+(\d+)(?:,(\d+))?", line)
                if match:
                    current_line = int(match.group(1))
                else:
                    current_line = None
                continue
            if not current_file or current_line is None:
                continue
            if line.startswith("+") and not line.startswith("+++"):
                changed.setdefault(current_file, set()).add(current_line)
                current_line += 1
            elif line.startswith("-") and not line.startswith("---"):
                continue
            else:
                current_line += 1
        return changed

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
                md += f"- **Description**: {issue.description}\n"
                md += f"- **Evidence**: `{issue.evidence}`\n"
                md += f"- **Suggested Fix**: {issue.suggested_fix}\n\n"
        
        return md

    @staticmethod
    def save_report(report, path: str):
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
