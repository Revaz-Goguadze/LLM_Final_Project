import ast
import os
import shutil
import subprocess
from typing import Dict, List, Optional, Tuple


class FixTransaction:
    """
    Explicit transaction object for fix operations.
    Provides atomic multi-file operations with rollback support.
    """

    def __init__(self, transaction_id: str, use_git_fallback: bool = True):
        self.id = transaction_id
        self.touched_files: List[str] = []
        self.backups: Dict[str, str] = {}
        self.use_git_fallback = use_git_fallback
        self.git_ref: Optional[str] = None
        self.operations: List[dict] = []
        self._committed = False

    def snapshot_files(self, file_paths: List[str]) -> None:
        """
        Create snapshots of files before modification.
        Uses in-memory backup with git stash fallback.
        """
        for file_path in file_paths:
            if not os.path.exists(file_path):
                continue

            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    self.backups[file_path] = f.read()
                self.touched_files.append(file_path)
            except (OSError, UnicodeDecodeError):
                pass

        # Git fallback for safety
        if self.use_git_fallback:
            self._git_snapshot()

    def snapshot_file(self, file_path: str) -> None:
        """Snapshot a single file."""
        self.snapshot_files([file_path])

    def _git_snapshot(self) -> None:
        """Create git stash as fallback backup."""
        try:
            result = subprocess.run(
                ["git", "stash", "push", "-m", f"fix-loop-backup-{self.id}"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                # Get the stash ref
                result = subprocess.run(
                    ["git", "stash", "list"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if result.returncode == 0:
                    first_line = result.stdout.split("\n")[0]
                    self.git_ref = first_line.split(":")[0]
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

    def validate_syntax(self, file_path: str) -> Tuple[bool, str]:
        """
        Validate Python syntax for a file.
        Returns (is_valid, error_message).
        """
        if not file_path.endswith(".py"):
            return True, ""

        if not os.path.exists(file_path):
            return False, f"File does not exist: {file_path}"

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                code = f.read()
            ast.parse(code)
            return True, ""
        except SyntaxError as e:
            return (
                False,
                f"Syntax error at line {e.lineno}: {e.msg}",
            )
        except Exception as e:
            return False, f"Validation error: {e}"

    def validate_all_syntax(self) -> Tuple[bool, Dict[str, str]]:
        """
        Validate syntax for all touched files.
        Returns (all_valid, {file_path: error}).
        """
        all_valid = True
        errors: Dict[str, str] = {}

        for file_path in self.touched_files:
            valid, error = self.validate_syntax(file_path)
            if not valid:
                all_valid = False
                errors[file_path] = error

        return all_valid, errors

    def rollback(self) -> bool:
        """
        Rollback all changes from backups.
        Returns success status.
        """
        success = True

        # Restore from memory backups
        for file_path, content in self.backups.items():
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(content)
            except (OSError, UnicodeDecodeError):
                success = False

        # Git stash pop as fallback
        if self.use_git_fallback and self.git_ref:
            try:
                subprocess.run(
                    ["git", "stash", "pop", self.git_ref],
                    capture_output=True,
                    timeout=10,
                )
            except (subprocess.TimeoutExpired, FileNotFoundError):
                pass

        self.touched_files.clear()
        self.backups.clear()
        self._committed = False
        return success

    def commit(self) -> None:
        """
        Mark transaction as committed and clear backups.
        """
        self._committed = True
        # Clear backups to free memory
        self.backups.clear()

    def log_operation(self, operation_type: str, details: dict) -> None:
        """Log an operation for debugging."""
        self.operations.append(
            {"type": operation_type, "details": details, "transaction_id": self.id}
        )

    def get_operations_log(self) -> List[dict]:
        """Get all operations log."""
        return self.operations.copy()

    def is_committed(self) -> bool:
        """Check if transaction was committed."""
        return self._committed

    def get_touched_files(self) -> List[str]:
        """Get list of files touched by this transaction."""
        return self.touched_files.copy()
