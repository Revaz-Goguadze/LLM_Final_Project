from codereview.grader import MultiLLMGrader


def _make_grader() -> MultiLLMGrader:
    return MultiLLMGrader.__new__(MultiLLMGrader)


def test_normalize_issue_list_maps_invalid_fields(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    grader = _make_grader()
    issues = [
        {
            "severity": "performance",
            "type": "invalid-type",
            "location": {"file": str(tmp_path / "sample.py"), "line": "2"},
        }
    ]

    normalized = grader._normalize_issue_list(issues, "security")
    assert normalized[0]["severity"] == "high"
    assert normalized[0]["type"] == "security"
    assert normalized[0]["location"]["file"] == "sample.py"
    assert normalized[0]["location"]["line"] == 2
