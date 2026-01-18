import os
import subprocess
import tempfile
from typing import Optional
from .models import BugIssue
from .config import VERIFY_COMMAND

class CodeFixer:
    def __init__(self):
        pass

    @staticmethod
    def _is_unified_diff(text: str) -> bool:
        return "diff --git" in text or text.startswith("--- ")

    def _apply_patch(self, patch_text: str) -> bool:
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".patch") as f:
            f.write(patch_text)
            patch_path = f.name
        try:
            check = subprocess.run(["git", "apply", "--check", patch_path], capture_output=True, text=True)
            if check.returncode != 0:
                print(f"Patch check failed:\n{check.stderr}")
                return False
            apply = subprocess.run(["git", "apply", patch_path], capture_output=True, text=True)
            if apply.returncode != 0:
                print(f"Patch apply failed:\n{apply.stderr}")
                return False
            return True
        finally:
            try:
                os.remove(patch_path)
            except OSError:
                pass

    def _apply_simple_replace(self, file_path: str, evidence: str, replacement: str) -> bool:
        if not evidence.strip():
            return False
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        if evidence not in content:
            return False
        new_content = content.replace(evidence, replacement, 1)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        return True

    def apply_fix(self, issue: BugIssue) -> bool:
        """Attempts to apply a suggested fix to the code."""
        file_path = issue.location.file
        if not os.path.exists(file_path):
            print(f"File {file_path} not found.")
            return False

        print(f"Applying fix to {file_path}...")
        suggested = issue.suggested_fix or ""
        if self._is_unified_diff(suggested):
            return self._apply_patch(suggested)
        return self._apply_simple_replace(file_path, issue.evidence or "", suggested)

    def run_verification(self) -> bool:
        """Runs tests to verify the fix."""
        print("Running verification tests...")
        try:
            cmd = VERIFY_COMMAND.split()
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                print("Tests passed!")
                return True
            else:
                print(f"Tests failed:\n{result.stdout}\n{result.stderr}")
                return False
        except FileNotFoundError:
            print("Pytest not found. Skipping verification.")
            return True # Fallback

    def rollback(self, file_path: str):
        """Reverts changes using git."""
        print(f"Rolling back changes to {file_path}...")
        subprocess.run(["git", "checkout", file_path])
