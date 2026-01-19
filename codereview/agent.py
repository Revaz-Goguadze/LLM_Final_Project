import json
import os
import re
from typing import Optional, Tuple

from openai import OpenAI

from .config import OPENROUTER_API_KEY, MODEL_JUDGE, MAX_FIX_RETRIES
from .retriever import HybridRetriever
from .fixer import CodeFixer
from .models import BugIssue


class ReActAgent:
    def __init__(self):
        if not OPENROUTER_API_KEY:
            raise ValueError("OPENROUTER_API_KEY is required for fix generation.")
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=OPENROUTER_API_KEY,
        )
        self.model = MODEL_JUDGE
        self.retriever = HybridRetriever()
        self.fixer = CodeFixer()

    def _read_file_lines(self, file_path: str) -> list:
        if not os.path.exists(file_path):
            return []
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return f.readlines()
        except Exception:
            return []

    def _read_file_context(
        self, file_path: str, line: int, context_lines: int = 10
    ) -> str:
        lines = self._read_file_lines(file_path)
        if not lines:
            return ""
        start = max(0, line - context_lines)
        end = min(len(lines), line + context_lines)
        numbered = [
            f"{i + 1}: {l.rstrip()}"
            for i, l in enumerate(lines[start:end], start=start)
        ]
        return "\n".join(numbered)

    def _read_line_range(self, file_path: str, start_line: int, end_line: int) -> str:
        lines = self._read_file_lines(file_path)
        if not lines or start_line < 1:
            return ""
        end_line = max(start_line, end_line)
        start_idx = min(start_line - 1, len(lines))
        end_idx = min(end_line, len(lines))
        return "".join(lines[start_idx:end_idx]).strip()

    def _validate_issue(self, issue: BugIssue) -> Tuple[bool, str]:
        file_path = issue.location.file
        if not file_path or not os.path.exists(file_path):
            return False, f"File not found: {file_path}"

        lines = self._read_file_lines(file_path)
        if not lines:
            return False, f"Unable to read file: {file_path}"

        if issue.location.line:
            if issue.location.line < 1 or issue.location.line > len(lines):
                return (
                    False,
                    f"Line {issue.location.line} out of range for file length {len(lines)}",
                )

        if issue.evidence and issue.evidence.strip():
            evidence = issue.evidence.strip()
            if evidence not in "".join(lines):
                return False, "Evidence string not found in file"

        return True, ""

    def _extract_json_payload(self, content: str) -> Optional[dict]:
        if not content:
            return None
        json_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", content)
        if json_match:
            content = json_match.group(1).strip()
        else:
            json_start = content.find("{")
            json_end = content.rfind("}")
            if json_start != -1 and json_end != -1:
                content = content[json_start : json_end + 1]
        try:
            return json.loads(content)
        except Exception:
            return None

    def _parse_fix_payload(self, content: str) -> dict:
        payload = self._extract_json_payload(content) or {}
        if not isinstance(payload, dict):
            return {}
        return payload

    def _generate_fix(
        self,
        issue: BugIssue,
        file_context: str,
        previous_error: Optional[str] = None,
        extra_context: Optional[str] = None,
    ) -> str:
        error_context = ""
        if previous_error:
            error_context = f"""
The previous fix attempt failed with this error:
{previous_error}

Generate a DIFFERENT fix that addresses this error.
"""

        extra = f"\nADDITIONAL CONTEXT:\n{extra_context}\n" if extra_context else ""

        prompt = f"""You are a code fixing agent. Return a JSON object only.

BUG: {issue.description}
FILE: {issue.location.file}
LINE: {issue.location.line}
{error_context}
CURRENT CODE:
{file_context}
{extra}

INSTRUCTIONS:
1. If a unified diff is safest, return: {{ "format": "patch", "patch": "diff --git ..." }}
2. Otherwise return: {{ "format": "replace", "start_line": int, "end_line": int, "replacement": "..." }}
3. replacement should include only the corrected line(s) and preserve indentation
4. NO markdown, NO code blocks, NO explanations
5. Output JSON only"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=300,
            )
            if response.choices and response.choices[0].message:
                content = response.choices[0].message.content or ""
                return content
            return ""
        except Exception as e:
            print(f"Error generating fix: {e}")
            return ""

    def solve_issue(self, issue: BugIssue) -> bool:
        print(f"\n[Agent] Starting to fix: {issue.description}")
        print(f"[Agent] File: {issue.location.file}, Line: {issue.location.line}")

        is_valid, reason = self._validate_issue(issue)
        if not is_valid:
            print(f"[Agent] Issue is not actionable: {reason}")
            return False

        last_error: Optional[str] = None
        last_fix: Optional[str] = None

        for attempt in range(1, MAX_FIX_RETRIES + 1):
            print(f"\n[Agent] Attempt {attempt}/{MAX_FIX_RETRIES}")
            print("[Agent] Generating fix...")
            file_context = self._read_file_context(
                issue.location.file, issue.location.line, context_lines=15
            )
            extra_context = ""
            if last_error:
                try:
                    query = f"{issue.description}\n{issue.evidence}\n{last_error}"
                    related = self.retriever.search(query, n_results=3)
                    blocks = []
                    for item in related:
                        meta = item.get("metadata", {})
                        header = (
                            f"{meta.get('file_path', 'unknown')}:{meta.get('start_line', '?')}-{meta.get('end_line', '?')}"
                        )
                        blocks.append(f"{header}\n{item.get('content', '')}")
                    extra_context = "\n\n".join(blocks)
                except Exception:
                    extra_context = ""

            raw_fix = self._generate_fix(issue, file_context, last_error, extra_context)
            if not raw_fix:
                print("[Agent] Failed to generate fix")
                continue

            payload = self._parse_fix_payload(raw_fix)
            fix_format = str(payload.get("format", "")).lower()
            is_patch = fix_format == "patch"
            if is_patch:
                current_fix = str(payload.get("patch", "")).strip()
            else:
                current_fix = str(payload.get("replacement", "")).strip() or raw_fix.strip()

            if not current_fix:
                print("[Agent] Empty fix output, retrying")
                last_error = "Empty fix output"
                continue

            if last_fix and current_fix == last_fix:
                print("[Agent] Fix repeated with no changes, stopping early")
                return False

            start_line = payload.get("start_line") or issue.location.line
            end_line = payload.get("end_line") or start_line
            try:
                start_line = int(start_line) if start_line is not None else None
                end_line = int(end_line) if end_line is not None else start_line
            except Exception:
                start_line = issue.location.line
                end_line = start_line

            if not is_patch and start_line:
                existing = self._read_line_range(
                    issue.location.file, start_line, end_line or start_line
                )
                if existing.strip() == current_fix.strip():
                    print("[Agent] Proposed fix is a no-op")
                    last_error = "No-op fix"
                    continue

            pre_content = "".join(self._read_file_lines(issue.location.file))
            success = self.fixer.apply_fix_with_content(
                issue,
                current_fix,
                start_line=start_line,
                end_line=end_line,
                is_patch=is_patch,
            )
            if not success:
                last_error = self.fixer.get_last_error()
                print(f"[Agent] Could not apply fix: {last_error}")
                continue

            post_content = "".join(self._read_file_lines(issue.location.file))
            if pre_content == post_content:
                last_error = "Fix applied but file did not change"
                print(f"[Agent] {last_error}")
                self.fixer.rollback(issue.location.file)
                continue

            verified, output = self.fixer.run_verification_with_output()
            if verified:
                print("[Agent] Fix applied and verified successfully!")
                return True

            last_error = output
            last_fix = current_fix
            self.fixer.rollback(issue.location.file)
            print("[Agent] Fix failed verification, rolling back...")

        print("[Agent] All fix attempts exhausted.")
        return False


if __name__ == "__main__":
    print("ReActAgent module loaded.")
