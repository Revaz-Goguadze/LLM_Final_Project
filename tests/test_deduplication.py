import pytest
from codereview.models import BugIssue, CodeLocation
from codereview.grader import MultiLLMGrader


def test_deduplicate_same_location():
    grader = MultiLLMGrader()

    issues = [
        BugIssue(
            severity="critical",
            type="security",
            location=CodeLocation(file="test.py", line=10),
            description="Path traversal",
            evidence="open(path)",
            suggested_fix="validate path",
            confidence=0.9,
        ),
        BugIssue(
            severity="high",
            type="security",
            location=CodeLocation(file="test.py", line=12),
            description="Path traversal vulnerability",
            evidence="open(user_path)",
            suggested_fix="sanitize input",
            confidence=0.85,
        ),
    ]

    result = grader._deduplicate_issues(issues)
    assert len(result) == 1
    assert result[0].confidence == 0.9


def test_deduplicate_different_types():
    grader = MultiLLMGrader()

    issues = [
        BugIssue(
            severity="critical",
            type="security",
            location=CodeLocation(file="test.py", line=10),
            description="Path traversal",
            evidence="open(path)",
            suggested_fix="validate path",
            confidence=0.9,
        ),
        BugIssue(
            severity="high",
            type="logic",
            location=CodeLocation(file="test.py", line=11),
            description="Off by one",
            evidence="range(len-1)",
            suggested_fix="use range(len)",
            confidence=0.85,
        ),
    ]

    result = grader._deduplicate_issues(issues)
    assert len(result) == 2


def test_deduplicate_different_files():
    grader = MultiLLMGrader()

    issues = [
        BugIssue(
            severity="critical",
            type="security",
            location=CodeLocation(file="file1.py", line=10),
            description="Path traversal",
            evidence="open(path)",
            suggested_fix="validate path",
            confidence=0.9,
        ),
        BugIssue(
            severity="critical",
            type="security",
            location=CodeLocation(file="file2.py", line=10),
            description="Path traversal",
            evidence="open(path)",
            suggested_fix="validate path",
            confidence=0.85,
        ),
    ]

    result = grader._deduplicate_issues(issues)
    assert len(result) == 2


def test_deduplicate_empty_list():
    grader = MultiLLMGrader()
    result = grader._deduplicate_issues([])
    assert len(result) == 0


def test_deduplicate_outside_threshold():
    grader = MultiLLMGrader()

    issues = [
        BugIssue(
            severity="critical",
            type="security",
            location=CodeLocation(file="test.py", line=10),
            description="Path traversal",
            evidence="open(path)",
            suggested_fix="validate path",
            confidence=0.9,
        ),
        BugIssue(
            severity="high",
            type="security",
            location=CodeLocation(file="test.py", line=50),
            description="Path traversal",
            evidence="open(path)",
            suggested_fix="validate path",
            confidence=0.85,
        ),
    ]

    result = grader._deduplicate_issues(issues)
    assert len(result) == 2


def test_deduplicate_with_dict_input():
    grader = MultiLLMGrader()

    issues = [
        {
            "severity": "critical",
            "type": "security",
            "location": {"file": "test.py", "line": 10},
            "description": "Path traversal",
            "evidence": "open(path)",
            "suggested_fix": "validate path",
            "confidence": 0.9,
        },
        {
            "severity": "high",
            "type": "security",
            "location": {"file": "test.py", "line": 12},
            "description": "Path traversal",
            "evidence": "open(path)",
            "suggested_fix": "sanitize input",
            "confidence": 0.85,
        },
    ]

    result = grader._deduplicate_issues(issues)
    assert len(result) == 1
