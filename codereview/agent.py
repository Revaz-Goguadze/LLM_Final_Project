import json
import os
import re
import uuid
from typing import Optional, Tuple, Dict, Set

from openai import OpenAI

from .config import (
    OPENROUTER_API_KEY,
    MODEL_JUDGE,
    MAX_FIX_RETRIES,
    DOCS_DB_COLLECTION,
    DOCS_BM25_INDEX_PATH,
)
from .retriever import HybridRetriever
from .fixer import CodeFixer
from .models import BugIssue
from .diff_utils import parse_changed_lines, parse_unified_diff_files
from .agent_state import AgentState


def _range_overlaps(start_line: int, end_line: int, changed: Set[int]) -> bool:
    for line in range(start_line, end_line + 1):
        if line in changed:
            return True
    return False


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
        self.docs_retriever = HybridRetriever(
            collection=DOCS_DB_COLLECTION,
            bm25_index_path=DOCS_BM25_INDEX_PATH,
        )
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

    def _validate_fix_payload(
        self, issue: BugIssue, payload: dict, diff_text: Optional[str] = None
    ) -> Tuple[bool, str, dict]:
        if not payload:
            return False, "Empty fix payload", {}

        fix_format = str(payload.get("format", "")).lower().strip()
        if fix_format not in {"patch", "replace"}:
            return False, f"Unsupported fix format: {fix_format}", {}

        if fix_format == "patch":
            patch_text = str(payload.get("patch", ""))
            if not patch_text:
                return False, "Missing patch content", {}
            if not patch_text.endswith("\n"):
                patch_text += "\n"
            if diff_text:
                diff_files = set(parse_changed_lines(diff_text).keys())
                touched = parse_unified_diff_files(patch_text)
                if diff_files and any(f not in diff_files for f in touched):
                    return False, "Patch touches files outside the analyzed diff", {}
            if not self.fixer.check_patch_text(patch_text):
                return False, self.fixer.get_last_error() or "Patch check failed", {}
            return True, "", {"format": "patch", "patch": patch_text}

        replacement = str(payload.get("replacement", "")).strip()
        if not replacement:
            return False, "Missing replacement content", {}

        start_line = payload.get("start_line") or issue.location.line
        end_line = payload.get("end_line") or start_line
        try:
            start_line = int(start_line) if start_line is not None else None
            end_line = int(end_line) if end_line is not None else start_line
        except Exception:
            return False, "Invalid line range in payload", {}

        if not start_line or start_line < 1:
            return False, "Invalid start_line in payload", {}
        if not end_line or end_line < start_line:
            return False, "Invalid end_line in payload", {}

        if diff_text:
            changed_lines = parse_changed_lines(diff_text).get(issue.location.file, set())
            if changed_lines and not _range_overlaps(start_line, end_line, changed_lines):
                return False, "Replacement does not overlap changed diff lines", {}

        return True, "", {
            "format": "replace",
            "replacement": replacement,
            "start_line": start_line,
            "end_line": end_line,
        }

    def _generate_fix(
        self,
        issue: BugIssue,
        file_context: str,
        previous_error: Optional[str] = None,
        extra_context: Optional[str] = None,
    ) -> Tuple[str, str]:
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
                return prompt, content
            return prompt, ""
        except Exception as e:
            print(f"Error generating fix: {e}")
            return prompt, ""

    def _init_run_dir(self) -> str:
        run_id = uuid.uuid4().hex
        run_dir = os.path.join("runs", run_id)
        os.makedirs(run_dir, exist_ok=True)
        return run_dir

    def _write_run_file(self, run_dir: str, rel_path: str, content: str) -> None:
        path = os.path.join(run_dir, rel_path)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

    def _build_tool_context(
        self, issue: BugIssue, last_error: Optional[str]
    ) -> Tuple[str, list]:
        steps = []
        blocks = []

        file_context = self._read_file_context(
            issue.location.file, issue.location.line, context_lines=20
        )
        if file_context:
            steps.append("READ_FILE")
            blocks.append(f"FILE_CONTEXT:\n{file_context}")

        evidence_missing = False
        if issue.evidence and issue.evidence.strip():
            content = "".join(self._read_file_lines(issue.location.file))
            evidence_missing = issue.evidence.strip() not in content

        if evidence_missing or last_error:
            steps.append("SEARCH_CODE")
            try:
                query = f"{issue.description}\n{issue.evidence}\n{last_error or ''}".strip()
                related = self.retriever.search(query, n_results=3)
                for item in related:
                    meta = item.get("metadata", {})
                    header = (
                        f"{meta.get('file_path', 'unknown')}:{meta.get('start_line', '?')}-{meta.get('end_line', '?')}"
                    )
                    blocks.append(f"{header}\n{item.get('content', '')}")
            except Exception:
                pass

        should_read_docs = "best practice" in issue.description.lower() or "security" in issue.type.lower()
        if should_read_docs:
            steps.append("READ_DOCS")
            try:
                query = f"{issue.description}\n{issue.evidence}"
                related_docs = self.docs_retriever.search(query, n_results=3)
                for item in related_docs:
                    meta = item.get("metadata", {})
                    header = meta.get("title") or meta.get("file_path", "doc")
                    blocks.append(f"{header}\n{item.get('content', '')}")
            except Exception:
                pass

        return "\n\n".join(blocks), steps

    def solve_issue(self, issue: BugIssue, diff_text: Optional[str] = None) -> bool:
        print(f"\n[Agent] Starting to fix: {issue.description}")
        print(f"[Agent] File: {issue.location.file}, Line: {issue.location.line}")

        state = AgentState.VALIDATE_ISSUE
        run_dir = self._init_run_dir()
        self._write_run_file(
            run_dir, "issue.json", json.dumps(issue.model_dump(), indent=2)
        )

        is_valid, reason = self._validate_issue(issue)
        if not is_valid:
            print(f"[Agent] Issue is not actionable: {reason}")
            self._write_run_file(run_dir, "final_state.txt", state.value)
            return False

        last_error: Optional[str] = None
        last_fix: Optional[str] = None

        for attempt in range(1, MAX_FIX_RETRIES + 1):
            state = AgentState.BUILD_CONTEXT
            print(f"\n[Agent] Attempt {attempt}/{MAX_FIX_RETRIES}")
            print("[Agent] Generating fix...")
            file_context = self._read_file_context(
                issue.location.file, issue.location.line, context_lines=15
            )
            extra_context, steps = self._build_tool_context(issue, last_error)
            if steps:
                print(f"[Agent] Tool steps: {', '.join(steps)}")
            context_text = "\n\n".join(
                part
                for part in [
                    f"STEPS: {', '.join(steps)}" if steps else "",
                    f"FILE_CONTEXT:\n{file_context}" if file_context else "",
                    extra_context,
                ]
                if part
            )
            if attempt == 1:
                self._write_run_file(run_dir, "context.txt", context_text)
            self._write_run_file(run_dir, f"attempt_{attempt}_context.txt", context_text)

            state = AgentState.GENERATE_FIX
            prompt, raw_fix = self._generate_fix(
                issue, file_context, last_error, extra_context
            )
            self._write_run_file(run_dir, f"attempt_{attempt}_prompt.txt", prompt)
            self._write_run_file(run_dir, f"attempt_{attempt}_raw_llm.txt", raw_fix)
            if not raw_fix:
                print("[Agent] Failed to generate fix")
                self._write_run_file(
                    run_dir,
                    f"attempt_{attempt}_payload.json",
                    json.dumps({"error": "Empty LLM response"}, indent=2),
                )
                continue

            payload = self._parse_fix_payload(raw_fix)
            state = AgentState.VALIDATE_FIX
            is_valid, reason, normalized = self._validate_fix_payload(
                issue, payload, diff_text=diff_text
            )
            if not is_valid:
                last_error = reason
                print(f"[Agent] Invalid fix payload: {reason}")
                self._write_run_file(
                    run_dir,
                    f"attempt_{attempt}_payload.json",
                    json.dumps({"error": reason, "raw": payload}, indent=2),
                )
                continue

            self._write_run_file(
                run_dir,
                f"attempt_{attempt}_payload.json",
                json.dumps(normalized, indent=2),
            )

            fix_format = normalized.get("format")
            is_patch = fix_format == "patch"
            if is_patch:
                current_fix = normalized.get("patch", "")
            else:
                current_fix = normalized.get("replacement", "")

            if not current_fix:
                print("[Agent] Empty fix output, retrying")
                last_error = "Empty fix output"
                continue

            if last_fix and current_fix == last_fix:
                print("[Agent] Fix repeated with no changes, stopping early")
                return False

            start_line = normalized.get("start_line") if not is_patch else None
            end_line = normalized.get("end_line") if not is_patch else None

            if not is_patch and start_line:
                existing = self._read_line_range(
                    issue.location.file, start_line, end_line or start_line
                )
                if existing.strip() == current_fix.strip():
                    print("[Agent] Proposed fix is a no-op")
                    last_error = "No-op fix"
                    continue

            pre_content = "".join(self._read_file_lines(issue.location.file))
            state = AgentState.APPLY_FIX
            success, touched_files = self.fixer.apply_fix_with_transaction(
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
                state = AgentState.ROLLBACK
                self.fixer.rollback_files(touched_files)
                continue

            state = AgentState.VERIFY
            verified, output = self.fixer.run_verification_with_output()
            self._write_run_file(
                run_dir, f"attempt_{attempt}_verification.txt", output
            )
            if verified:
                print("[Agent] Fix applied and verified successfully!")
                state = AgentState.SUCCESS
                self._write_run_file(run_dir, "final_state.txt", state.value)
                return True

            last_error = output
            last_fix = current_fix
            state = AgentState.ROLLBACK
            self.fixer.rollback_files(touched_files)
            print("[Agent] Fix failed verification, rolling back...")

        print("[Agent] All fix attempts exhausted.")
        state = AgentState.FAIL
        self._write_run_file(run_dir, "final_state.txt", state.value)
        return False


if __name__ == "__main__":
    print("ReActAgent module loaded.")
