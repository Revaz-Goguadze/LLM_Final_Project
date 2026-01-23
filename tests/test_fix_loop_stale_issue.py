from pathlib import Path

from codereview.fix_loop import FixLoopRunner
from codereview.models import BugIssue, CodeLocation
from codereview.agent import ReActAgent


def _make_agent() -> ReActAgent:
    return ReActAgent.__new__(ReActAgent)


def test_missing_evidence_marks_resolved(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    file_path = Path("sample.py")
    file_path.write_text(
        "def read_file(path):\n"
        "    with open(path, 'r') as f:\n"
        "        return f.read()\n",
        encoding="utf-8",
    )

    issue = BugIssue(
        severity="high",
        type="security",
        location=CodeLocation(file=str(file_path), line=2, function="read_file"),
        description="Use context manager for file reads",
        evidence="f = open(",
        suggested_fix="with open(",
        confidence=0.9,
    )

    runner = FixLoopRunner(_make_agent())
    status = runner._classify_missing_evidence(issue)
    assert status == "resolved"
