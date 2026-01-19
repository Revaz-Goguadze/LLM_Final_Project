from codereview.agent import ReActAgent


def test_run_dir_and_logging(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    agent = ReActAgent.__new__(ReActAgent)

    run_dir = agent._init_run_dir()
    assert run_dir.startswith("runs/")

    agent._write_run_file(run_dir, "issue.json", "{}")
    issue_path = tmp_path / run_dir / "issue.json"
    assert issue_path.exists()
    assert issue_path.read_text(encoding="utf-8") == "{}"
