import json
import re
from typing import Any, List
from openai import OpenAI
from .models import GraderReport, FinalReport
from .config import OPENROUTER_API_KEY, GEMINI_API_KEY, MODEL_JUDGE, OPENROUTER_TIMEOUT

USE_OPENROUTER = bool(OPENROUTER_API_KEY)


class MultiLLMGrader:
    def __init__(self, model_name: str = "google/gemini-2.0-flash-exp:free"):
        if USE_OPENROUTER:
            self.client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=OPENROUTER_API_KEY,
                timeout=OPENROUTER_TIMEOUT,
                max_retries=2,
            )
            self.model_name = model_name
        else:
            if not GEMINI_API_KEY:
                raise ValueError(
                    "GEMINI_API_KEY is required when OPENROUTER_API_KEY is not set."
                )
            import google.generativeai as genai

            genai.configure(api_key=GEMINI_API_KEY)
            self.model = genai.GenerativeModel("gemini-2.0-flash")
            self.model_name = "gemini-2.0-flash"

    def _get_grading_prompt(self, role: str, code: str) -> str:
        base_instruction = """You are a precise code reviewer. You will receive code to analyze.

CRITICAL RULES:
1. Only report REAL bugs that would cause runtime errors, security vulnerabilities, or significant performance problems
2. Do NOT report style preferences, naming conventions, or theoretical edge cases
3. Do NOT report missing docstrings or comments
4. If the code is well-written and follows best practices, return an EMPTY issues array
5. Only report issues with confidence >= 0.85
6. Focus on the CHANGED code (lines with + prefix in diffs), not surrounding context

Each issue must have concrete evidence - a specific line that demonstrates the bug."""

        prompts = {
            "security": f"{base_instruction}\n\nFocus ONLY on critical SECURITY issues: SQL injection, XSS, hardcoded secrets/passwords/API keys, authentication bypasses. Ignore minor security suggestions.",
            "logic": f"{base_instruction}\n\nFocus ONLY on critical LOGIC bugs: null pointer exceptions, off-by-one errors causing crashes, division by zero, infinite loops, incorrect return values. Ignore theoretical edge cases.",
            "performance": f"{base_instruction}\n\nFocus ONLY on severe PERFORMANCE issues: O(n²) or worse in hot paths, N+1 database queries, unbounded memory growth, blocking I/O in async contexts. Ignore micro-optimizations.",
        }

        system_prompt = prompts.get(
            role, f"{base_instruction}\n\nAnalyze the code for critical bugs only."
        )

        return f"""{system_prompt}

Return your assessment strictly as a JSON object matching this schema:
{{ "issues": [ {{ "severity": "critical/high/medium/low", "type": "security/logic/performance/style", "location": {{"file": "string", "line": int, "function": "string"}}, "description": "string", "evidence": "string", "suggested_fix": "string", "confidence": float }} ], "best_practices_violations": [ {{ "rule": "string", "description": "string", "count": int }} ], "overall_score": float (0-10, where 10 is perfect code), "summary": "string" }}

REMEMBER: If the code is clean and well-written, return {{"issues": [], "best_practices_violations": [], "overall_score": 9.0, "summary": "Code is well-written with no significant issues."}}

Code to analyze:

{code}"""

    def _json_candidates(self, content: str) -> List[str]:
        if not content:
            return []
        candidates: List[str] = [content]
        for match in re.finditer(r"```(?:json)?\s*([\s\S]*?)```", content):
            candidates.append(match.group(1).strip())
        json_start = content.find("{")
        json_end = content.rfind("}")
        if json_start != -1 and json_end != -1 and json_end > json_start:
            candidates.append(content[json_start : json_end + 1])
        deduped = []
        seen = set()
        for candidate in candidates:
            cleaned = candidate.strip()
            if cleaned and cleaned not in seen:
                deduped.append(cleaned)
                seen.add(cleaned)
        return deduped

    def _safe_json_loads(self, content: str) -> Any:
        last_error = None
        for candidate in self._json_candidates(content):
            try:
                return json.loads(candidate)
            except Exception as e:
                last_error = e
            try:
                cleaned = re.sub(r",\s*([}\]])", r"\1", candidate)
                return json.loads(cleaned)
            except Exception as e:
                last_error = e
        raise ValueError(f"Failed to parse JSON output: {last_error}")

    def _coerce_grader_payload(self, payload: Any) -> dict:
        if isinstance(payload, list) and payload:
            payload = payload[0]
        if not isinstance(payload, dict):
            payload = {}
        issues = payload.get("issues")
        if not isinstance(issues, list):
            issues = []
        violations = payload.get("best_practices_violations")
        if not isinstance(violations, list):
            violations = []
        overall = payload.get("overall_score")
        summary = payload.get("summary") or "No summary provided."
        return {
            "issues": issues,
            "best_practices_violations": violations,
            "overall_score": overall if isinstance(overall, (int, float)) else 0,
            "summary": summary,
        }

    def _coerce_final_payload(self, payload: Any) -> dict:
        if isinstance(payload, list) and payload:
            payload = payload[0]
        if not isinstance(payload, dict):
            payload = {}
        consolidated = payload.get("consolidated_issues")
        if not isinstance(consolidated, list):
            consolidated = []
        score = payload.get("overall_health_score")
        summary = payload.get("summary") or "No summary provided."
        return {
            "winner_assessment": payload.get("winner_assessment"),
            "consolidated_issues": consolidated,
            "overall_health_score": score if isinstance(score, (int, float)) else 0,
            "summary": summary,
        }

    def grade_with_model(self, role: str, model_id: str, code: str) -> GraderReport:
        prompt = self._get_grading_prompt(role, code)

        try:
            content = ""
            data = None
            for attempt in range(2):
                if USE_OPENROUTER:
                    response = self.client.chat.completions.create(
                        model=model_id,
                        messages=[{"role": "user", "content": prompt}],
                        timeout=OPENROUTER_TIMEOUT,
                    )
                    if not response.choices or not response.choices[0].message:
                        raise ValueError("No response choices returned")
                    content = response.choices[0].message.content
                else:
                    response = self.model.generate_content(prompt)
                    content = response.text

                print(
                    f"[DEBUG] Raw response for {role}: {content[:200] if content else 'EMPTY'}..."
                )

                if not content:
                    raise ValueError("Empty response from model")

                try:
                    data = self._safe_json_loads(content)
                    break
                except ValueError:
                    if attempt == 0 and USE_OPENROUTER:
                        continue
                    raise

            if data is None:
                raise ValueError("Empty response from model")

            data = self._coerce_grader_payload(data)
            data["grader_id"] = (
                f"{role}_{model_id.split('/')[-1].split(':')[0] if '/' in model_id else model_id}"
            )
            return GraderReport(**data)
        except Exception as e:
            print(f"Error grading for {role}: {e}")
            return GraderReport(
                grader_id=f"{role}_error",
                issues=[],
                best_practices_violations=[],
                overall_score=0,
                summary=f"Error: {e}",
            )

    def judge(self, reports: List[GraderReport]) -> FinalReport:
        all_reports_text = json.dumps([r.model_dump() for r in reports], indent=2)

        prompt = (
            f"You are the Final Judge LLM. Review these {len(reports)} code analysis reports and produce a consolidated report.\n\n"
            "FILTERING RULES:\n"
            "1. ONLY include issues with severity 'critical' or 'high'\n"
            "2. ONLY include issues with confidence >= 0.8\n"
            "3. Remove duplicates - keep the best-explained version\n"
            "4. Remove style/documentation issues entirely\n"
            "5. If all graders found no significant issues, return an empty consolidated_issues array\n\n"
            "Return strictly as JSON matching this schema:\n"
            '{ "winner_assessment": "string naming the most helpful grader", "consolidated_issues": [...list of BugIssue objects with severity critical/high only], "overall_health_score": float, "summary": "string" }\n\n'
            f"Reports:\n{all_reports_text}"
        )

        try:
            if USE_OPENROUTER:
                response = self.client.chat.completions.create(
                    model=MODEL_JUDGE,
                    messages=[{"role": "user", "content": prompt}],
                    timeout=OPENROUTER_TIMEOUT,
                )
                if not response.choices or not response.choices[0].message:
                    raise ValueError("No response choices returned")
                content = response.choices[0].message.content
            else:
                response = self.model.generate_content(prompt)
                content = response.text

            if not content:
                raise ValueError("Empty response from model")

            data = self._safe_json_loads(content)
            data = self._coerce_final_payload(data)
            return FinalReport(**data)
        except Exception as e:
            print(f"Error during final judgment: {e}")
            return FinalReport(
                consolidated_issues=[],
                overall_health_score=0,
                summary=f"Judgment failed: {e}",
            )
