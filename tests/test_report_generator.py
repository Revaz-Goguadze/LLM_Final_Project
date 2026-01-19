from codereview.models import BugIssue, CodeLocation, FinalReport
from codereview.report_generator import ReportGenerator


def test_filter_report_keeps_valid_issue(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    file_path = tmp_path / "sample.py"
    file_path.write_text("print('b')\n", encoding="utf-8")

    diff_text = (
        "diff --git a/sample.py b/sample.py\n"
        "--- a/sample.py\n"
        "+++ b/sample.py\n"
        "@@ -1 +1 @@\n"
        "-print('a')\n"
        "+print('b')\n"
    )

    issue = BugIssue(
        severity="high",
        type="logic",
        location=CodeLocation(file="sample.py", line=1, function=""),
        description="Test issue",
        evidence="print('b')",
        suggested_fix="",
        confidence=0.9,
    )

    report = FinalReport(
        winner_assessment="logic",
        consolidated_issues=[issue],
        overall_health_score=5.0,
        summary="",
    )

    filtered = ReportGenerator.filter_report(report, diff_text)
    assert len(filtered.consolidated_issues) == 1


def test_filter_report_drops_mismatched_line(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    file_path = tmp_path / "sample.py"
    file_path.write_text("print('b')\nprint('c')\n", encoding="utf-8")

    diff_text = (
        "diff --git a/sample.py b/sample.py\n"
        "--- a/sample.py\n"
        "+++ b/sample.py\n"
        "@@ -1 +1 @@\n"
        "-print('a')\n"
        "+print('b')\n"
    )

    issue = BugIssue(
        severity="high",
        type="logic",
        location=CodeLocation(file="sample.py", line=2, function=""),
        description="Line mismatch",
        evidence="print('c')",
        suggested_fix="",
        confidence=0.9,
    )

    report = FinalReport(
        winner_assessment=None,
        consolidated_issues=[issue],
        overall_health_score=5.0,
        summary="",
    )

    filtered = ReportGenerator.filter_report(report, diff_text)
    assert len(filtered.consolidated_issues) == 0
