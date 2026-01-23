import json
from pathlib import Path

from codereview.fix_loop import FixLoopRunner
from codereview.models import BugIssue, CodeLocation, FixContext, FixFormat, RetryStrategy, Remedy


class DummyFixStrategySelector:
    def recommend_format(self, issue, diff_text):
        return FixFormat.REPLACE

    def adapt_retry_strategy(self, last_error, attempt, preferred_format):
        return RetryStrategy(change_format=False, context_multiplier=1.0)


class DummyErrorClassifier:
    def classify_error(self, _error):
        return "unknown"

    def suggest_remedy(self, _category):
        return Remedy(action="none", description="", params={})

    def get_retry_instructions(self, _remedy):
        return ""


class DummyFixContextBuilder:
    def build_context(
        self,
        issue,
        diff_text=None,
        attempt=1,
        previous_error=None,
        context_multiplier=1.0,
    ):
        return FixContext(file_context=f"{issue.location.line}: pass")


class DummyFixVerifier:
    def __init__(self):
        self.calls = 0

    def verify_with_fallback(self, _file_path, _issue, diff_text=None):
        self.calls += 1
        if self.calls == 1:
            return False, "Verification failed"
        return True, "Verification Method: dummy"


class DummyFixer:
    def __init__(self):
        self.backups = {}
        self.last_error = ""

    def apply_fix_with_transaction(self, issue, fix_content, start_line=None, end_line=None, is_patch=False):
        file_path = issue.location.file
        path = Path(file_path)
        self.backups[file_path] = path.read_text(encoding="utf-8")
        lines = self.backups[file_path].splitlines()
        if start_line is None or end_line is None:
            return False, []
        replacement_lines = fix_content.splitlines()
        start_idx = start_line - 1
        end_idx = end_line
        new_lines = lines[:start_idx] + replacement_lines + lines[end_idx:]
        path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
        return True, [file_path]

    def rollback_files(self, file_paths):
        for file_path in file_paths:
            if file_path in self.backups:
                Path(file_path).write_text(self.backups[file_path], encoding="utf-8")

    def get_last_error(self):
        return self.last_error


class DummyAgent:
    def __init__(self, run_dir, prompts):
        self._run_dir = run_dir
        self._prompts = prompts
        self.fix_strategy_selector = DummyFixStrategySelector()
        self.error_classifier = DummyErrorClassifier()
        self.fix_context_builder = DummyFixContextBuilder()
        self.fix_verifier = DummyFixVerifier()
        self.fixer = DummyFixer()
        self.fix_tracker = type("Tracker", (), {"record_attempt": lambda *args, **kwargs: None})()
        self._attempt = 0

    def _init_run_dir(self):
        self._run_dir.mkdir(parents=True, exist_ok=True)
        return str(self._run_dir)

    def _write_run_file(self, *_args, **_kwargs):
        return None

    def _validate_issue(self, _issue):
        return True, ""

    def _format_fix_context(self, fix_context):
        return fix_context.file_context

    def _generate_fix(self, issue, file_context, previous_error, extra_context):
        self._attempt += 1
        prompt = f"{previous_error or ''}\n{extra_context or ''}"
        self._prompts.append(prompt)
        if self._attempt == 1:
            payload = {
                "format": "replace",
                "start_line": issue.location.line,
                "end_line": issue.location.line,
                "replacement": "b = 2",
            }
        else:
            payload = {
                "format": "replace",
                "start_line": issue.location.line,
                "end_line": issue.location.line,
                "replacement": "b = 3",
            }
        return prompt, json.dumps(payload)

    def _parse_fix_payload(self, content):
        return json.loads(content)

    def _validate_fix_payload(self, issue, payload, diff_text=None, expected_format=None):
        return True, "", payload

    def _read_file_lines(self, file_path):
        return Path(file_path).read_text(encoding="utf-8").splitlines(keepends=True)

    def _read_line_range(self, file_path, start_line, end_line):
        lines = self._read_file_lines(file_path)
        return "".join(lines[start_line - 1:end_line]).strip()

    def _extract_verification_method(self, output):
        return "dummy"

    def _issue_key(self, issue):
        return f"{issue.location.file}:{issue.location.line}"


def test_verification_failure_adds_diff_summary(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    file_path = tmp_path / "sample.py"
    file_path.write_text("a = 1\nb = 1\n", encoding="utf-8")

    issue = BugIssue(
        severity="high",
        type="logic",
        location=CodeLocation(file=str(file_path), line=2, function=""),
        description="Update line",
        evidence="b = 1",
        suggested_fix="",
        confidence=0.9,
        start_line=2,
        end_line=2,
        line_text="b = 1",
    )

    prompts = []
    agent = DummyAgent(tmp_path / "runs", prompts)
    runner = FixLoopRunner(agent)

    assert runner.run(issue, diff_text=None) is True
    assert len(prompts) >= 2
    assert "Verification failed" in prompts[1]
    assert "DIFF_SUMMARY" in prompts[1]
