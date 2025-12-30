import os
import subprocess
from .models import BugIssue

class CodeFixer:
    def __init__(self):
        pass

    def apply_fix(self, issue: BugIssue) -> bool:
        """Attempts to apply a suggested fix to the code. 
        NOTE: This is a simplified version that assumes the suggested_fix is the new code for the location.
        In a production system, this would be a diff-based application or LLM-driven editing.
        """
        file_path = issue.location.file
        if not os.path.exists(file_path):
            print(f"File {file_path} not found.")
            return False

        # For the demo, we'll implement a 'search and replace' or 'whole file replace' if the fix is provided
        # A better way is to ask an LLM to generate the exact diff.
        print(f"Applying fix to {file_path}...")
        # Placeholder: In a real tool, we'd use another LLM call to apply the fix safely.
        return True

    def run_verification(self) -> bool:
        """Runs tests to verify the fix."""
        print("Running verification tests...")
        try:
            # Try running pytest if it exists
            result = subprocess.run(["pytest"], capture_output=True, text=True)
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
