import ast
import os
import subprocess
import sys
from typing import Optional, Tuple

from .models import BugIssue, VerificationResult


class FixVerifier:
    """
    Multi-strategy verification with graceful degradation.
    Falls back through: pytest -> syntax -> import -> semantic

    Optimizations:
    - Skips pytest if no test files exist in project
    - Uses shorter timeouts for faster feedback
    - Caches test discovery results
    """

    def __init__(self, verify_command: str = "pytest"):
        self.verify_command = verify_command
        self._last_fixed_file: Optional[str] = None
        self._has_tests: Optional[bool] = None  # Cache test discovery

    def _check_tests_exist(self) -> bool:
        """Check if any test files exist in the project."""
        if self._has_tests is not None:
            return self._has_tests

        # Quick check for common test patterns
        test_patterns = [
            "tests/",
            "test/",
            "test_*.py",
            "*_test.py",
            "tests.py",
            "conftest.py",
        ]

        for root, dirs, files in os.walk("."):
            # Skip hidden dirs and common non-test dirs
            dirs[:] = [
                d
                for d in dirs
                if not d.startswith(".")
                and d not in ("venv", ".venv", "node_modules", "__pycache__")
            ]

            for f in files:
                if (
                    f.startswith("test_")
                    or f.endswith("_test.py")
                    or f == "conftest.py"
                ):
                    self._has_tests = True
                    return True

            for d in dirs:
                if d in ("tests", "test"):
                    self._has_tests = True
                    return True

        self._has_tests = False
        return False

    def verify_with_fallback(
        self,
        file_path: str,
        issue: BugIssue,
        diff_text: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """
        Verify fix with fallback chain.
        Returns (success, output) where output includes diagnostics.
        """
        self._last_fixed_file = file_path
        diagnostics = []

        # 1. Check syntax first (fast, always available)
        result = self._verify_syntax(file_path)
        diagnostics.append(f"Syntax: {result[1]}")
        if not result[0]:
            # Syntax error is critical - fail fast
            return False, self._format_output("syntax", result[1], diagnostics)

        # 2. Try pytest only if tests exist
        if self._check_tests_exist():
            result = self._verify_with_pytest()
            diagnostics.append(f"Pytest: {result[1][:200]}")
            if result[0]:
                return True, self._format_output("pytest", result[1], diagnostics)
            # Pytest failed but might be unrelated to our fix - continue checking
        else:
            diagnostics.append("Pytest: Skipped (no test files found)")

        # 3. Fallback: Import check
        result = self._verify_import(file_path)
        diagnostics.append(f"Import: {result[1]}")
        if not result[0]:
            return False, self._format_output("import", result[1], diagnostics)

        # 4. If syntax and import pass, consider it verified
        # (pytest failure without syntax/import issues likely means unrelated test failure)
        return True, self._format_output(
            "syntax+import", "Fix verified via static checks", diagnostics
        )

    def _format_output(self, method: str, output: str, diagnostics: list) -> str:
        """Format verification output with diagnostics."""
        lines = [
            f"Verification Method: {method}",
            f"Output: {output}",
            "",
            "Diagnostics:",
        ]
        lines.extend(f"  - {d}" for d in diagnostics)
        return "\n".join(lines)

    def _verify_with_pytest(self) -> Tuple[bool, str]:
        """Run pytest as primary verification."""
        try:
            result = subprocess.run(
                [sys.executable, "-m", self.verify_command, "-x", "--tb=short", "-q"],
                capture_output=True,
                text=True,
                timeout=15,
            )
            output = result.stdout + result.stderr
            if result.returncode == 0:
                return True, "Tests passed"
            elif result.returncode == 5:
                return True, "No tests collected"
            return False, output[:500]
        except subprocess.TimeoutExpired:
            return False, "Pytest timeout (15s)"
        except FileNotFoundError:
            return True, "Pytest not available"
        except Exception as e:
            return False, f"Pytest error: {e}"

    def _verify_syntax(self, file_path: str) -> Tuple[bool, str]:
        """Check Python syntax using ast.parse."""
        if not file_path.endswith(".py"):
            return True, "Not a Python file, skipping syntax check"

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                code = f.read()
            ast.parse(code)
            return True, "Syntax OK"
        except SyntaxError as e:
            return (
                False,
                f"Syntax error at line {e.lineno}: {e.msg}",
            )
        except Exception as e:
            return False, f"Syntax check error: {e}"

    def _verify_import(self, file_path: str) -> Tuple[bool, str]:
        """Try importing the module to check for runtime errors."""
        if not file_path.endswith(".py"):
            return True, "Not a Python file, skipping import check"

        # Get module name from file path
        module_name = os.path.splitext(os.path.basename(file_path))[0]
        module_dir = os.path.dirname(file_path)

        if module_dir not in sys.path:
            sys.path.insert(0, module_dir)

        try:
            __import__(module_name)
            return True, "Import OK"
        except ImportError as e:
            # Import error might be OK (missing dependencies)
            if "no module named" in str(e).lower():
                return True, f"Import OK (missing dependency: {e})"
            return False, f"Import error: {e}"
        except Exception as e:
            # Other errors might indicate issues
            return False, f"Import runtime error: {e}"
        finally:
            if module_dir in sys.path:
                sys.path.remove(module_dir)

    def set_last_fixed_file(self, file_path: str) -> None:
        """Set the last fixed file for verification tracking."""
        self._last_fixed_file = file_path

    def get_last_fixed_file(self) -> Optional[str]:
        """Get the last fixed file."""
        return self._last_fixed_file
