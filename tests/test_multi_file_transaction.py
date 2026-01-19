import subprocess
from pathlib import Path

from codereview.fixer import CodeFixer
from codereview.models import BugIssue, CodeLocation


def test_apply_patch_and_rollback_multi_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    subprocess.run(["git", "init"], check=True, capture_output=True)

    file_a = Path("a.py")
    file_b = Path("b.py")
    file_a.write_text("print('a')\n", encoding="utf-8")
    file_b.write_text("print('b')\n", encoding="utf-8")
    subprocess.run(["git", "add", "a.py", "b.py"], check=True, capture_output=True)

    file_a.write_text("print('a1')\n", encoding="utf-8")
    file_b.write_text("print('b1')\n", encoding="utf-8")
    diff = subprocess.run(["git", "diff"], check=True, capture_output=True, text=True)
    patch = diff.stdout

    file_a.write_text("print('a')\n", encoding="utf-8")
    file_b.write_text("print('b')\n", encoding="utf-8")

    issue = BugIssue(
        severity="high",
        type="logic",
        location=CodeLocation(file="a.py", line=1, function=""),
        description="Update files",
        evidence="",
        suggested_fix="",
        confidence=0.9,
    )

    fixer = CodeFixer()
    success, touched = fixer.apply_fix_with_transaction(issue, patch, is_patch=True)
    assert success is True
    assert set(touched) == {"a.py", "b.py"}
    assert file_a.read_text(encoding="utf-8") == "print('a1')\n"
    assert file_b.read_text(encoding="utf-8") == "print('b1')\n"

    fixer.rollback_files(touched)
    assert file_a.read_text(encoding="utf-8") == "print('a')\n"
    assert file_b.read_text(encoding="utf-8") == "print('b')\n"
