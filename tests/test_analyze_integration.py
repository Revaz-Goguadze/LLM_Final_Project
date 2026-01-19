from codereview.models import BugIssue, CodeLocation, FinalReport, GraderReport, GitDiff
import main


class DummyAnalyzer:
    def __init__(self, diff_text: str):
        self._diff_text = diff_text

    def get_diffs(self):
        return GitDiff(
            staged="",
            unstaged=self._diff_text,
            last_commit="",
            changed_files=["sample.py"],
        )


class DummyRetriever:
    def __init__(self, *args, **kwargs):
        pass

    def search(self, *args, **kwargs):
        return []


class DummyGrader:
    def __init__(self, *args, **kwargs):
        pass

    def grade_with_model(self, role, model_id, code):
        return GraderReport(
            grader_id=f"{role}_dummy",
            issues=[],
            best_practices_violations=[],
            overall_score=9.0,
            summary="OK",
        )

    def judge(self, reports):
        issue = BugIssue(
            severity="high",
            type="logic",
            location=CodeLocation(file="sample.py", line=1, function=""),
            description="Example issue",
            evidence="print('b')",
            suggested_fix="",
            confidence=0.95,
        )
        return FinalReport(
            winner_assessment="logic",
            consolidated_issues=[issue],
            overall_health_score=5.0,
            summary="Test",
        )


def test_analyze_writes_report(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "sample.py").write_text("print('b')\n", encoding="utf-8")

    diff_text = (
        "diff --git a/sample.py b/sample.py\n"
        "--- a/sample.py\n"
        "+++ b/sample.py\n"
        "@@ -1 +1 @@\n"
        "-print('a')\n"
        "+print('b')\n"
    )

    monkeypatch.setattr(main, "GitAnalyzer", lambda: DummyAnalyzer(diff_text))
    monkeypatch.setattr(main, "HybridRetriever", DummyRetriever)
    monkeypatch.setattr(main, "MultiLLMGrader", DummyGrader)

    main.analyze(
        unstaged=True,
        use_rag=True,
        use_docs_rag=True,
        top_k=2,
        docs_top_k=2,
        show_context=False,
        context_out=None,
    )

    report_path = tmp_path / "bug_report.json"
    assert report_path.exists()
    data = report_path.read_text(encoding="utf-8")
    assert "consolidated_issues" in data
