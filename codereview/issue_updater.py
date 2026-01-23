import json
from typing import List, Optional

from .path_utils import normalize_repo_path, resolve_repo_path


def _find_snippet_line(content: str, snippet: str) -> Optional[int]:
    if not snippet:
        return None
    idx = content.find(snippet)
    if idx == -1:
        return None
    return content[:idx].count("\n") + 1


def _relocate_issue(issue: dict, lines: List[str]) -> None:
    content = "".join(lines)
    candidates = [
        issue.get("evidence_snippet"),
        issue.get("evidence"),
        issue.get("line_text"),
    ]
    candidates = [c for c in candidates if isinstance(c, str) and c.strip()]
    line_no = None
    for candidate in candidates:
        line_no = _find_snippet_line(content, candidate)
        if line_no:
            break

    location = issue.get("location") or {}
    old_line = location.get("line") or issue.get("start_line")
    if line_no:
        location["line"] = line_no
        issue["start_line"] = line_no
        issue["end_line"] = line_no
        issue["line_text"] = lines[line_no - 1].rstrip("\n")
    else:
        if isinstance(old_line, int) and old_line > 0:
            start_line = max(1, old_line - 20)
            end_line = min(len(lines), old_line + 20)
            issue["start_line"] = start_line
            issue["end_line"] = end_line
            if old_line <= len(lines):
                issue["line_text"] = lines[old_line - 1].rstrip("\n")
    issue["location"] = location


def update_report_for_file(report_path: str, file_path: str) -> None:
    abs_path = resolve_repo_path(file_path)
    rel_path = normalize_repo_path(abs_path)
    try:
        with open(report_path, "r", encoding="utf-8") as f:
            report = json.load(f)
    except FileNotFoundError:
        return

    try:
        with open(abs_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except OSError:
        return

    issues = report.get("consolidated_issues", [])
    updated = False
    for issue in issues:
        location = issue.get("location") or {}
        issue_path = normalize_repo_path(str(location.get("file", "")))
        if issue_path != rel_path:
            continue
        location["file"] = rel_path
        issue["location"] = location
        _relocate_issue(issue, lines)
        updated = True

    if updated:
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
