import re
from typing import Optional

from .models import BugIssue, FixFormat, RetryStrategy


class FixStrategySelector:
    """
    Selects fix format and retry strategy based on issue characteristics.
    """

    def __init__(self):
        self._multi_file_indicators = ["multiple files", "across files", "imports"]
        self._multi_hunk_indicators = [
            "multiple locations",
            "several places",
            "throughout",
            "various",
        ]
        self._simple_fix_indicators = ["rename", "single line", "add import", "remove"]

    def recommend_format(
        self, issue: BugIssue, diff_text: Optional[str] = None
    ) -> FixFormat:
        """
        Recommend fix format (patch vs replace) based on issue analysis.
        """
        # Check for multi-file changes
        if self._is_multi_file_issue(issue, diff_text):
            return FixFormat.PATCH

        # Check for multi-hunk changes
        if self._is_multi_hunk_issue(issue):
            return FixFormat.PATCH

        # Check for simple single-line fixes
        if self._is_simple_fix(issue):
            return FixFormat.REPLACE

        # Check for indentation-sensitive code
        if self._is_indentation_sensitive(issue):
            return FixFormat.REPLACE

        # Default to patch (safer)
        return FixFormat.PATCH

    def adapt_retry_strategy(
        self, error: str, attempt: int, current_format: FixFormat
    ) -> RetryStrategy:
        """
        Adapt retry strategy based on error type and attempt number.
        """
        error_lower = error.lower()

        # Syntax errors - try different approach
        if any(
            keyword in error_lower
            for keyword in ["syntax", "indentation", "unexpected", "invalid"]
        ):
            return RetryStrategy(
                expand_context=True,
                change_format=current_format == FixFormat.PATCH,
                context_multiplier=2.0,
                additional_instructions="Ensure correct Python syntax and proper indentation.",
            )

        # Import/module errors - expand context
        if any(
            keyword in error_lower
            for keyword in ["import", "module", "name", "not defined"]
        ):
            return RetryStrategy(
                expand_context=True,
                change_format=False,
                context_multiplier=2.0,
                additional_instructions="Ensure all required imports are included.",
            )

        # Test failures - may need logic fix
        if any(
            keyword in error_lower for keyword in ["assert", "test", "failed", "error"]
        ):
            return RetryStrategy(
                expand_context=True,
                change_format=attempt >= 2,
                context_multiplier=1.5,
                additional_instructions="Fix the underlying logic issue.",
            )

        # Context mismatch errors
        if any(
            keyword in error_lower
            for keyword in ["context", "scope", "variable", "undefined"]
        ):
            return RetryStrategy(
                expand_context=True,
                change_format=False,
                context_multiplier=2.0,
                additional_instructions="Ensure all variables and functions are in scope.",
            )

        # Default strategy
        return RetryStrategy(
            expand_context=True,
            change_format=attempt >= 3,
            context_multiplier=1.5,
            additional_instructions="",
        )

    def _is_multi_file_issue(
        self, issue: BugIssue, diff_text: Optional[str]
    ) -> bool:
        """Check if issue requires multi-file changes."""
        desc_lower = issue.description.lower()

        # Check description
        for indicator in self._multi_file_indicators:
            if indicator in desc_lower:
                return True

        # Check diff for multiple files
        if diff_text:
            file_matches = re.findall(r"^\+\+\+ b/(.+)$", diff_text, re.MULTILINE)
            if len(file_matches) > 1:
                return True

        return False

    def _is_multi_hunk_issue(self, issue: BugIssue) -> bool:
        """Check if issue spans multiple hunks/locations."""
        desc_lower = issue.description.lower()

        for indicator in self._multi_hunk_indicators:
            if indicator in desc_lower:
                return True

        # Check evidence for multiple lines
        lines = issue.evidence.count("\n")
        return lines > 3

    def _is_simple_fix(self, issue: BugIssue) -> bool:
        """Check if this is a simple single-line fix."""
        desc_lower = issue.description.lower()

        for indicator in self._simple_fix_indicators:
            if indicator in desc_lower:
                return True

        # Single line evidence
        return "\n" not in issue.evidence and len(issue.evidence) < 100

    def _is_indentation_sensitive(self, issue: BugIssue) -> bool:
        """Check if fix requires precise indentation."""
        evidence_lower = issue.evidence.lower()

        return any(
            keyword in evidence_lower
            for keyword in ["def ", "class ", "if ", "for ", "while ", "try:"]
        )
