import json
from typing import List, Dict, Any
from openai import OpenAI
from .config import OPENROUTER_API_KEY, MODEL_JUDGE, MAX_FIX_RETRIES
from .retriever import HybridRetriever
from .fixer import CodeFixer
from .models import BugIssue

class ReActAgent:
    def __init__(self):
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=OPENROUTER_API_KEY,
        )
        self.retriever = HybridRetriever()
        self.fixer = CodeFixer()

    def solve_issue(self, issue: BugIssue):
        """Agentic loop to solve a specific bug."""
        print(f"\n[bold green]Agent starting to fix issue: {issue.description}[/bold green]")
        
        for attempt in range(1, MAX_FIX_RETRIES + 1):
            print(f"Attempt {attempt}/{MAX_FIX_RETRIES}")
            success = self.fixer.apply_fix(issue)
            if not success:
                print("Could not apply fix.")
                continue
            verified = self.fixer.run_verification()
            if verified:
                print("Fix applied and verified successfully!")
                return
            self.fixer.rollback(issue.location.file)
            print("Fix failed verification and was rolled back.")
        print("All fix attempts failed.")

if __name__ == "__main__":
    print("ReActAgent module loaded.")
