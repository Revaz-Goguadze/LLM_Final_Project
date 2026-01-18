import json
from typing import List
from openai import OpenAI
from .models import GraderReport, BugIssue, BestPracticeViolation, FinalReport
from .config import (
    OPENAI_API_KEY,
    OPENROUTER_API_KEY,
    MODEL_GRADER_SECURITY,
    MODEL_GRADER_LOGIC,
    MODEL_GRADER_PERF,
    MODEL_JUDGE,
)

class MultiLLMGrader:
    def __init__(self):
        if OPENROUTER_API_KEY:
            self.client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=OPENROUTER_API_KEY,
            )
        else:
            self.client = OpenAI(
                api_key=OPENAI_API_KEY,
            )

    def _get_grading_prompt(self, role: str, code: str) -> str:
        prompts = {
            "security": "You are a senior security engineer. Analyze the following code for security vulnerabilities (SQLi, XSS, hardcoded secrets, etc.).",
            "logic": "You are a senior lead developer. Analyze the following code for logic bugs, edge cases, and algorithmic correctness.",
            "performance": "You are a performance optimization expert. Analyze the following code for bottlenecks, memory leaks, and inefficient operations."
        }
        
        system_prompt = prompts.get(role, "Analyze the code for bugs.")
        
        return f"{system_prompt}\n\nReturn your assessment strictly as a JSON object matching this schema:\n" \
               "{ \"issues\": [ { \"severity\": \"critical/high/medium/low\", \"type\": \"security/logic/performance/style\", \"location\": {\"file\": \"string\", \"line\": int, \"function\": \"string\"}, \"description\": \"string\", \"evidence\": \"string\", \"suggested_fix\": \"string\", \"confidence\": float } ], " \
               "\"best_practices_violations\": [ { \"rule\": \"string\", \"description\": \"string\", \"count\": int } ], " \
               "\"overall_score\": float (0-10, where 10 is perfect code), \"summary\": \"string\" }\n\nCode to analyze:\n\n{code}"

    def grade_with_model(self, role: str, model_id: str, code: str) -> GraderReport:
        prompt = self._get_grading_prompt(role, code)
        
        try:
            response = self.client.chat.completions.create(
                model=model_id,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
            )
            data = json.loads(response.choices[0].message.content)
            data["grader_id"] = f"{role}_{model_id}"
            return GraderReport(**data)
        except Exception as e:
            print(f"Error grading with {model_id} for {role}: {e}")
            # Return empty report on error
            return GraderReport(
                grader_id=f"{role}_{model_id}_error",
                issues=[],
                best_practices_violations=[],
                overall_score=0,
                summary=f"Error: {e}"
            )

    def judge(self, reports: List[GraderReport]) -> FinalReport:
        """Judge handles the consolidation of reports (Stage 4 in original assignment)."""
        # For simplicity in this CLI version, we'll use an LLM call to consolidate
        all_reports_text = json.dumps([r.model_dump() for r in reports], indent=2)
        
        prompt = f"You are the Final Judge LLM. Review these {len(reports)} code analysis reports and produce a single consolidated final report.\n\n" \
                 "Filter out duplicates, resolve disagreements by prioritizing the most severe or well-reasoned issues, and provide a master summary.\n\n" \
                 "Return strictly as JSON matching this schema:\n" \
                 "{ \"winner_assessment\": \"string naming the most helpful grader\", \"consolidated_issues\": [...list of BugIssue objects], \"overall_health_score\": float, \"summary\": \"string\" }\n\n" \
                 f"Reports:\n{all_reports_text}"
        
        try:
            response = self.client.chat.completions.create(
                model=MODEL_JUDGE,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
            )
            data = json.loads(response.choices[0].message.content)
            return FinalReport(**data)
        except Exception as e:
            print(f"Error during final judgment: {e}")
            return FinalReport(
                consolidated_issues=[],
                overall_health_score=0,
                summary=f"Judgment failed: {e}"
            )

if __name__ == "__main__":
    # Test with dummy code
    grader = MultiLLMGrader()
    sample_code = """
def login(user, password):
    # SECURITY BUG: Hardcoded secret (placeholder for test)
    SECRET = "123456"
    if password == SECRET:
        return True
    return False
"""
    # Note: This will only work if OPENROUTER_API_KEY is set in .env
    print("Testing grader (requires API key)...")
    # report = grader.grade_with_model("security", MODEL_GRADER_SECURITY, sample_code)
    # print(report.model_dump_json(indent=2))
