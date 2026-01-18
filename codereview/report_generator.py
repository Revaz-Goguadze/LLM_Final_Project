import json
from .models import FinalReport

class ReportGenerator:
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
