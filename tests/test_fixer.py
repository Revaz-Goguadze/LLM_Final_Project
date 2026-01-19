from codereview.fixer import CodeFixer
from codereview.models import BugIssue, CodeLocation


def test_apply_fix_with_content_line_range(tmp_path):
    file_path = tmp_path / "sample.py"
    file_path.write_text("a = 1\nb = 2\n", encoding="utf-8")

    issue = BugIssue(
        severity="high",
        type="logic",
        location=CodeLocation(file=str(file_path), line=2, function=""),
        description="Replace line",
        evidence="missing",
        suggested_fix="",
        confidence=0.9,
    )

    fixer = CodeFixer()
    success = fixer.apply_fix_with_content(
        issue,
        "b = 3",
        start_line=2,
        end_line=2,
        is_patch=False,
    )

    assert success is True
    assert file_path.read_text(encoding="utf-8") == "a = 1\nb = 3\n"
