import os
import subprocess
import tempfile
from typing import Iterable, Optional, Tuple, List
from .models import BugIssue
from .config import VERIFY_COMMAND, ALLOW_FIX_PATCH
from .diff_utils import parse_unified_diff_files


class CodeFixer:
    def __init__(self):
        self.last_error = ""
        self._backups = {}
        self._allow_patch = ALLOW_FIX_PATCH

    def _snapshot_file(self, file_path: str) -> None:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                self._backups[file_path] = f.read()
        except Exception:
            self._backups[file_path] = ""

    def _snapshot_files(self, file_paths: Iterable[str]) -> List[str]:
        touched: List[str] = []
        for file_path in file_paths:
            if not file_path or file_path in touched:
                continue
            touched.append(file_path)
            self._snapshot_file(file_path)
        return touched

    @staticmethod
    def _is_unified_diff(text: str) -> bool:
        return "diff --git" in text or text.startswith("--- ")

    def _apply_patch(self, patch_text: str) -> bool:
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".patch") as f:
            f.write(patch_text)
            patch_path = f.name
        try:
            if not self.check_patch(patch_path):
                return False
            apply = subprocess.run(
                ["git", "apply", patch_path], capture_output=True, text=True
            )
            if apply.returncode != 0:
                self.last_error = f"Patch apply failed: {apply.stderr}"
                print(self.last_error)
                return False
            return True
        finally:
            try:
                os.remove(patch_path)
            except OSError:
                pass

    def _apply_simple_replace(
        self, file_path: str, evidence: str, replacement: str
    ) -> bool:
        if not evidence.strip():
            self.last_error = "Empty evidence string"
            return False
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            self.last_error = f"Failed to read file: {e}"
            return False

        if evidence not in content:
            self.last_error = f"Evidence not found in {file_path}"
            return False

        new_content = content.replace(evidence, replacement, 1)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        return True

    def _apply_line_range_fix(
        self, file_path: str, start_line: int, end_line: int, replacement: str
    ) -> bool:
        import textwrap

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except Exception as e:
            self.last_error = f"Failed to read file: {e}"
            return False

        if start_line < 1:
            self.last_error = f"Invalid start line: {start_line}"
            return False

        if end_line < start_line:
            end_line = start_line

        effective_start = min(start_line, len(lines))
        effective_end = min(end_line, len(lines))
        if effective_start != start_line or effective_end != end_line:
            print(
                f"Line range {start_line}-{end_line} exceeds file length, using {effective_start}-{effective_end}"
            )

        original_line = lines[effective_start - 1] if lines else ""
        original_indent = len(original_line) - len(original_line.lstrip())
        indent_str = original_line[:original_indent]

        normalized_replacement = textwrap.dedent(replacement).strip("\n")
        replacement_lines = normalized_replacement.splitlines()
        if not replacement_lines:
            self.last_error = "Empty replacement"
            return False

        positive_indents = [
            len(line) - len(line.lstrip())
            for line in replacement_lines
            if line.strip()
        ]
        min_indent = min(positive_indents) if positive_indents else 0

        indented_lines = []
        for line in replacement_lines:
            if not line.strip():
                indented_lines.append("\n")
                continue
            line_indent = len(line) - len(line.lstrip())
            normalized_indent = max(0, line_indent - min_indent)
            indented_lines.append(
                indent_str + " " * normalized_indent + line.lstrip() + "\n"
            )

        new_lines = (
            lines[: effective_start - 1]
            + indented_lines
            + lines[effective_end:]
        )

        with open(file_path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
        return True

    def apply_fix(self, issue: BugIssue) -> bool:
        file_path = issue.location.file
        if not os.path.exists(file_path):
            self.last_error = f"File {file_path} not found"
            print(self.last_error)
            return False

        print(f"Applying fix to {file_path}...")
        self._snapshot_file(file_path)
        suggested = issue.suggested_fix or ""
        if self._allow_patch and self._is_unified_diff(suggested):
            return self._apply_patch(suggested)
        if self._apply_simple_replace(file_path, issue.evidence or "", suggested):
            return True
        if issue.location.line and issue.location.line > 0:
            print(
                f"Evidence mismatch, falling back to line-based fix at line {issue.location.line}"
            )
            return self._apply_line_range_fix(
                file_path, issue.location.line, issue.location.line, suggested
            )
        return False

    def apply_fix_with_content(
        self,
        issue: BugIssue,
        fix_content: str,
        start_line: Optional[int] = None,
        end_line: Optional[int] = None,
        is_patch: bool = False,
    ) -> bool:
        file_path = issue.location.file
        if not os.path.exists(file_path):
            self.last_error = f"File {file_path} not found"
            return False

        print(f"Applying fix to {file_path}...")
        self._snapshot_file(file_path)

        if self._allow_patch and (is_patch or self._is_unified_diff(fix_content)):
            return self._apply_patch(fix_content)

        if self._apply_simple_replace(file_path, issue.evidence or "", fix_content):
            return True

        if start_line is None:
            start_line = issue.location.line
        if end_line is None:
            end_line = start_line

        if start_line and start_line > 0:
            print(
                f"Evidence mismatch, falling back to line-based fix at line range {start_line}-{end_line}"
            )
            return self._apply_line_range_fix(file_path, start_line, end_line, fix_content)

        return False

    def apply_fix_with_transaction(
        self,
        issue: BugIssue,
        fix_content: str,
        start_line: Optional[int] = None,
        end_line: Optional[int] = None,
        is_patch: bool = False,
    ) -> Tuple[bool, List[str]]:
        file_path = issue.location.file
        if not os.path.exists(file_path):
            self.last_error = f"File {file_path} not found"
            return False, []

        # Determine which files will be touched by parsing patch content
        # Explicit is_patch=True overrides ALLOW_FIX_PATCH config
        is_explicit_patch = is_patch or self._is_unified_diff(fix_content)

        if is_explicit_patch:
            touched_files = parse_unified_diff_files(fix_content) or [file_path]
            # Snapshot all affected files before applying
            self._snapshot_files(touched_files)

            # Apply patch if explicitly requested OR if allowed by config
            # is_patch=True means caller explicitly wants patch application
            should_apply = is_patch or self._allow_patch
            if should_apply:
                applied = self._apply_patch(fix_content)
                if not applied:
                    self.rollback_files(touched_files)
                return applied, touched_files
            else:
                # Patch detected but not explicitly requested and not allowed by config
                return False, touched_files

        # Non-patch path
        touched_files = self._snapshot_files([file_path])
        if self._apply_simple_replace(file_path, issue.evidence or "", fix_content):
            return True, touched_files

        if start_line is None:
            start_line = issue.location.line
        if end_line is None:
            end_line = start_line

        if start_line and start_line > 0:
            print(
                f"Evidence mismatch, falling back to line-based fix at line range {start_line}-{end_line}"
            )
            applied = self._apply_line_range_fix(
                file_path, start_line, end_line, fix_content
            )
            if not applied:
                self.rollback_files(touched_files)
            return applied, touched_files

        self.rollback_files(touched_files)
        return False, touched_files

    def check_patch_text(self, patch_text: str) -> bool:
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".patch") as f:
            f.write(patch_text)
            patch_path = f.name
        try:
            return self.check_patch(patch_path)
        finally:
            try:
                os.remove(patch_path)
            except OSError:
                pass

    def check_patch(self, patch_path: str) -> bool:
        check = subprocess.run(
            ["git", "apply", "--check", patch_path], capture_output=True, text=True
        )
        if check.returncode != 0:
            self.last_error = f"Patch check failed: {check.stderr}"
            print(self.last_error)
            return False
        return True

    def run_verification(self) -> bool:
        success, _ = self.run_verification_with_output()
        return success

    def run_verification_with_output(self) -> Tuple[bool, str]:
        print("Running verification tests...")
        try:
            cmd = VERIFY_COMMAND.split()
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            output = f"{result.stdout}\n{result.stderr}".strip()
            if result.returncode == 0:
                print("Tests passed!")
                return True, output
            elif result.returncode == 5 and "no tests ran" in output.lower():
                print("No tests found. Assuming fix is valid.")
                return True, output
            else:
                print(f"Tests failed:\n{output}")
                self.last_error = output
                return False, output
        except subprocess.TimeoutExpired:
            self.last_error = "Tests timed out after 60 seconds"
            return False, self.last_error
        except FileNotFoundError:
            print("Test command not found. Assuming fix is valid.")
            return True, "No test runner available"

    def rollback(self, file_path: str):
        print(f"Rolling back changes to {file_path}...")
        if file_path in self._backups:
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(self._backups[file_path])
                return
            except Exception:
                pass
        subprocess.run(["git", "restore", "--", file_path], capture_output=True)
        subprocess.run(["git", "checkout", "--", file_path], capture_output=True)

    def rollback_files(self, file_paths: Iterable[str]) -> None:
        for file_path in file_paths:
            self.rollback(file_path)

    def get_last_error(self) -> str:
        return self.last_error
