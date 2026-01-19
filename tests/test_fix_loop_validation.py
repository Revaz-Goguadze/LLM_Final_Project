import subprocess
from pathlib import Path

from codereview.agent import ReActAgent
from codereview.fixer import CodeFixer
from codereview.models import BugIssue, CodeLocation


def _make_agent() -> ReActAgent:
    agent = ReActAgent.__new__(ReActAgent)
    agent.fixer = CodeFixer()
    return agent


def test_validate_fix_payload_replace_ok(tmp_path):
    issue = BugIssue(
        severity="high",
        type="logic",
        location=CodeLocation(file=str(tmp_path / "sample.py"), line=1, function=""),
        description="Replace line",
        evidence="",
        suggested_fix="",
        confidence=0.9,
    )

    agent = _make_agent()
    payload = {
        "format": "replace",
        "replacement": "print('ok')",
        "start_line": 1,
        "end_line": 1,
    }

    is_valid, reason, normalized = agent._validate_fix_payload(issue, payload)
    assert is_valid is True
    assert reason == ""
    assert normalized["format"] == "replace"


def test_validate_fix_payload_replace_rejects_outside_diff(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    file_path = tmp_path / "sample.py"
    file_path.write_text("a = 1\nb = 2\n", encoding="utf-8")

    diff_text = (
        "diff --git a/sample.py b/sample.py\n"
        "--- a/sample.py\n"
        "+++ b/sample.py\n"
        "@@ -1 +1 @@\n"
        "-a = 0\n"
        "+a = 1\n"
    )

    issue = BugIssue(
        severity="high",
        type="logic",
        location=CodeLocation(file="sample.py", line=2, function=""),
        description="Replace line",
        evidence="b = 2",
        suggested_fix="",
        confidence=0.9,
    )

    agent = _make_agent()
    payload = {
        "format": "replace",
        "replacement": "b = 3",
        "start_line": 2,
        "end_line": 2,
    }

    is_valid, reason, _ = agent._validate_fix_payload(
        issue, payload, diff_text=diff_text
    )
    assert is_valid is False
    assert "changed diff lines" in reason


def test_validate_fix_payload_patch_invalid(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    subprocess.run(["git", "init"], check=True, capture_output=True)
    (tmp_path / "sample.py").write_text("print('a')\n", encoding="utf-8")

    issue = BugIssue(
        severity="high",
        type="logic",
        location=CodeLocation(file="sample.py", line=1, function=""),
        description="Bad patch",
        evidence="",
        suggested_fix="",
        confidence=0.9,
    )

    agent = _make_agent()
    payload = {"format": "patch", "patch": "not a real patch"}

    is_valid, reason, _ = agent._validate_fix_payload(issue, payload)
    assert is_valid is False
    assert "Patch check failed" in reason or reason


def test_validate_fix_payload_patch_valid(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    subprocess.run(["git", "init"], check=True, capture_output=True)
    file_path = Path("sample.py")
    file_path.write_text("print('a')\n", encoding="utf-8")
    subprocess.run(["git", "add", "sample.py"], check=True, capture_output=True)

    file_path.write_text("print('b')\n", encoding="utf-8")
    diff = subprocess.run(
        [
            "git",
            "-c",
            "diff.noprefix=false",
            "-c",
            "core.autocrlf=false",
            "diff",
            "--no-color",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    patch = diff.stdout
    assert "diff --git" in patch
    if not patch.endswith("\n"):
        patch += "\n"
    file_path.write_text("print('a')\n", encoding="utf-8")
    patch_file = tmp_path / "valid.patch"
    patch_file.write_text(patch, encoding="utf-8")
    check = subprocess.run(
        ["git", "apply", "--check", str(patch_file)],
        capture_output=True,
        text=True,
    )
    assert check.returncode == 0, check.stderr

    issue = BugIssue(
        severity="high",
        type="logic",
        location=CodeLocation(file="sample.py", line=1, function=""),
        description="Good patch",
        evidence="",
        suggested_fix="",
        confidence=0.9,
    )

    agent = _make_agent()
    assert agent.fixer.check_patch_text(patch) is True
    payload = {"format": "patch", "patch": patch}

    is_valid, reason, normalized = agent._validate_fix_payload(issue, payload)
    assert is_valid is True
    assert reason == ""
    assert normalized["format"] == "patch"
