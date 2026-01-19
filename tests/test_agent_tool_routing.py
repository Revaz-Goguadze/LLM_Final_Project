from codereview.agent import ReActAgent
from codereview.models import BugIssue, CodeLocation


class DummyRetriever:
    def __init__(self, *args, **kwargs):
        self.calls = []

    def search(self, query, n_results=3):
        self.calls.append((query, n_results))
        return []


def _make_agent(tmp_path):
    agent = ReActAgent.__new__(ReActAgent)
    agent.fixer = None
    agent.retriever = DummyRetriever()
    agent.docs_retriever = DummyRetriever()
    return agent


def test_build_tool_context_reads_docs_on_security(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    file_path = tmp_path / "sample.py"
    file_path.write_text("print('a')\n", encoding="utf-8")

    issue = BugIssue(
        severity="high",
        type="security",
        location=CodeLocation(file="sample.py", line=1, function=""),
        description="Security issue",
        evidence="print('a')",
        suggested_fix="",
        confidence=0.9,
    )

    agent = _make_agent(tmp_path)
    context, steps = agent._build_tool_context(issue, last_error=None)

    assert "READ_FILE" in steps
    assert "READ_DOCS" in steps
    assert agent.docs_retriever.calls
    assert "FILE_CONTEXT" in context


def test_build_tool_context_searches_on_error(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    file_path = tmp_path / "sample.py"
    file_path.write_text("print('a')\n", encoding="utf-8")

    issue = BugIssue(
        severity="high",
        type="logic",
        location=CodeLocation(file="sample.py", line=1, function=""),
        description="Logic issue",
        evidence="missing",
        suggested_fix="",
        confidence=0.9,
    )

    agent = _make_agent(tmp_path)
    context, steps = agent._build_tool_context(issue, last_error="failed")

    assert "SEARCH_CODE" in steps
    assert agent.retriever.calls
    assert "FILE_CONTEXT" in context
