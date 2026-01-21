from typing import Optional

from .models import ErrorCategory, Remedy


class ErrorClassifier:
    """
    Classifies fix failures into categories and suggests remedies.
    Enables adaptive retry strategies based on error patterns.
    """

    # Error patterns for classification
    SYNTAX_PATTERNS = [
        "syntax",
        "indentation",
        "unexpected",
        "invalid",
        "syntaxerror",
        "indentationerror",
        "tab",
    ]

    TEST_FAILURE_PATTERNS = [
        "assert",
        "test",
        "failed",
        "failure",
        "assertion",
        "unittest",
        "pytest",
    ]

    CONTEXT_PATTERNS = [
        "context",
        "scope",
        "undefined",
        "not defined",
        "nameerror",
        "variable",
        "out of scope",
    ]

    IMPORT_PATTERNS = [
        "import",
        "module",
        "no module named",
        "modulenotfounderror",
        "importerror",
    ]

    LOGIC_PATTERNS = [
        "logic",
        "zero",
        "division",
        "index",
        "key",
        "type",
        "value",
        "attribute",
    ]

    VERIFICATION_PATTERNS = [
        "verification",
        "verify",
        "check",
        "validation",
    ]

    def classify_error(
        self, error_output: str, error_type: str = ""
    ) -> ErrorCategory:
        """
        Classify error based on output patterns.
        Returns ErrorCategory enum value.
        """
        error_lower = error_output.lower()

        # Check syntax errors
        if any(
            pattern in error_lower for pattern in self.SYNTAX_PATTERNS
        ) or "syntax" in error_type.lower():
            return ErrorCategory.SYNTAX_ERROR

        # Check test failures
        if any(pattern in error_lower for pattern in self.TEST_FAILURE_PATTERNS):
            return ErrorCategory.TEST_FAILURE

        # Check context/scope errors
        if any(pattern in error_lower for pattern in self.CONTEXT_PATTERNS):
            return ErrorCategory.CONTEXT_MISMATCH

        # Check import errors
        if any(pattern in error_lower for pattern in self.IMPORT_PATTERNS):
            return ErrorCategory.CONTEXT_MISMATCH

        # Check verification errors
        if any(
            pattern in error_lower for pattern in self.VERIFICATION_PATTERNS
        ) or "verification" in error_type.lower():
            return ErrorCategory.VERIFICATION_ERROR

        # Check logic errors
        if any(pattern in error_lower for pattern in self.LOGIC_PATTERNS):
            return ErrorCategory.LOGIC_ERROR

        return ErrorCategory.UNKNOWN

    def suggest_remedy(self, category: ErrorCategory) -> Remedy:
        """
        Suggest remedy based on error category.
        Returns Remedy with action and description.
        """
        remedies = {
            ErrorCategory.SYNTAX_ERROR: Remedy(
                action="expand_context_and_fix_format",
                description="Syntax error detected. Expand context and consider using patch format instead of replace.",
                params={"context_multiplier": 2.0, "prefer_patch": True},
            ),
            ErrorCategory.TEST_FAILURE: Remedy(
                action="expand_context",
                description="Test failure. Expand context to understand the expected behavior better.",
                params={"context_multiplier": 1.5},
            ),
            ErrorCategory.CONTEXT_MISMATCH: Remedy(
                action="expand_context_and_add_imports",
                description="Context or scope issue. Expand context and ensure imports are included.",
                params={"context_multiplier": 2.0, "include_imports": True},
            ),
            ErrorCategory.LOGIC_ERROR: Remedy(
                action="expand_context",
                description="Logic error. Expand context to understand the full flow.",
                params={"context_multiplier": 1.5},
            ),
            ErrorCategory.VERIFICATION_ERROR: Remedy(
                action="retry_with_different_format",
                description="Verification failed. Try different fix format.",
                params={"change_format": True},
            ),
            ErrorCategory.UNKNOWN: Remedy(
                action="expand_context",
                description="Unknown error. Expand context and try again.",
                params={"context_multiplier": 1.5},
            ),
        }

        return remedies.get(category, remedies[ErrorCategory.UNKNOWN])

    def get_retry_instructions(self, remedy: Remedy) -> str:
        """
        Get retry instructions based on remedy.
        Returns formatted instructions for the LLM.
        """
        instructions = []

        if remedy.params.get("expand_context", True):
            instructions.append("- Expand the context to include more surrounding code")

        if remedy.params.get("prefer_patch", False):
            instructions.append("- Use patch format (git diff) instead of replace")

        if remedy.params.get("include_imports", False):
            instructions.append("- Ensure all necessary imports are included")

        if remedy.params.get("change_format", False):
            instructions.append("- Try a different fix format")

        if remedy.description:
            instructions.append(f"- Note: {remedy.description}")

        return "\n".join(instructions) if instructions else "- Review the error and adjust the fix"

    def analyze_error_pattern(
        self, error_history: list[str]
    ) -> tuple[ErrorCategory, int]:
        """
        Analyze error patterns across multiple attempts.
        Returns (dominant_category, pattern_count).
        """
        if not error_history:
            return ErrorCategory.UNKNOWN, 0

        category_counts = {}
        for error in error_history:
            category = self.classify_error(error)
            category_counts[category] = category_counts.get(category, 0) + 1

        if not category_counts:
            return ErrorCategory.UNKNOWN, 0

        dominant_category = max(category_counts, key=category_counts.get)
        return dominant_category, category_counts[dominant_category]
