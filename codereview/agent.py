import json
from typing import List, Dict, Any
from openai import OpenAI
from .config import OPENROUTER_API_KEY, MODEL_JUDGE
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
        
        # Simple 1-step logic for now:
        # 1. Search for context
        # 2. Refine fix
        # 3. Apply
        # 4. Verify
        
        # TODO: Full ReAct loop with multi-step reasoning
        
        success = self.fixer.apply_fix(issue)
        if success:
            verified = self.fixer.run_verification()
            if not verified:
                self.fixer.rollback(issue.location.file)
                print("Fix failed verification and was rolled back.")
            else:
                print("Fix applied and verified successfully!")
        else:
            print("Could not apply fix.")

if __name__ == "__main__":
    print("ReActAgent module loaded.")
