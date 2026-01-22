import json
import os
import re
import uuid
from typing import Optional, Tuple, Dict, Set, List

from openai import OpenAI

from .config import (
    OPENAI_API_KEY,
    OPENAI_BASE_URL,
    GEMINI_API_KEY,
    LLM_PROVIDER,
    MODEL_JUDGE,
    GEMINI_MODEL,
    OPENAI_TIMEOUT,
    LLM_MIN_DELAY,
    LLM_MAX_RETRIES,
    DOCS_DB_COLLECTION,
    DOCS_BM25_INDEX_PATH,
    VERIFY_COMMAND,
)
from .retriever import HybridRetriever
from .fixer import CodeFixer
from .models import BugIssue, FixContext, FixFormat
from .diff_utils import parse_changed_lines, parse_unified_diff_files
from .error_classifier import ErrorClassifier
from .fix_context_builder import FixContextBuilder
from .fix_strategy_selector import FixStrategySelector
from .fix_tracker import FixTracker
from .fix_verifier import FixVerifier
from .fix_loop import FixLoopRunner
from .llm_utils import RateLimiter, should_retry, backoff_sleep
from .gemini_client import GeminiClient


def _range_overlaps(start_line: int, end_line: int, changed: Set[int]) -> bool:
    for line in range(start_line, end_line + 1):
        if line in changed:
            return True
    return False


class ReActAgent:
    def __init__(self):
        self.rate_limiter = RateLimiter(LLM_MIN_DELAY)
        self.model = MODEL_JUDGE
        self.provider = LLM_PROVIDER
        if LLM_PROVIDER == "gemini":
            if not GEMINI_API_KEY:
                raise ValueError("GEMINI_API_KEY is required for fix generation.")
            self.client = GeminiClient(
                api_key=GEMINI_API_KEY,
                model=GEMINI_MODEL,
                min_delay=LLM_MIN_DELAY,
                max_retries=LLM_MAX_RETRIES,
            )
        else:
            if not OPENAI_API_KEY:
                raise ValueError("OPENAI_API_KEY is required for fix generation.")
            client_kwargs = {
                "api_key": OPENAI_API_KEY,
                "timeout": OPENAI_TIMEOUT,
                "max_retries": 2,
            }
            if OPENAI_BASE_URL:
                client_kwargs["base_url"] = OPENAI_BASE_URL
            self.client = OpenAI(**client_kwargs)
        self.retriever = HybridRetriever()
        try:
            self.docs_retriever = HybridRetriever(
                collection=DOCS_DB_COLLECTION,
                bm25_index_path=DOCS_BM25_INDEX_PATH,
            )
        except (ValueError, EOFError):
            self.docs_retriever = None
        self.fixer = CodeFixer()
        self.fix_context_builder = FixContextBuilder(
            self.retriever, self.docs_retriever
        )
        self.fix_strategy_selector = FixStrategySelector()
        self.fix_verifier = FixVerifier(verify_command=VERIFY_COMMAND)
        self.fix_tracker = FixTracker()
        self.error_classifier = ErrorClassifier()

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
            file_content = "".join(lines)

            # Try multiple evidence variants to handle diff formatting
            evidence_variants = [
                evidence,  # Original
                re.sub(r"^[\+\-]\s*", "", evidence),  # Strip leading +/-
                re.sub(
                    r"^[\+\-]\s*", "", evidence, flags=re.MULTILINE
                ),  # Strip from all lines
                " ".join(evidence.split()),  # Normalize whitespace
            ]

            found = any(variant in file_content for variant in evidence_variants)
            if not found:
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
        self,
        issue: BugIssue,
        payload: dict,
        diff_text: Optional[str] = None,
        expected_format: Optional[FixFormat] = None,
    ) -> Tuple[bool, str, dict]:
        if not payload:
            return False, "Empty fix payload", {}

        fix_format = str(payload.get("format", "")).lower().strip()
        if fix_format not in {"patch", "replace"}:
            return False, f"Unsupported fix format: {fix_format}", {}
        if expected_format and fix_format != expected_format.value:
            return (
                False,
                f"Fix format must be '{expected_format.value}' for this attempt",
                {},
            )

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
        # Allow empty replacement for line removal (deletion)
        # But replacement key must be present in payload
        if "replacement" not in payload:
            return False, "Missing replacement content", {}

        start_line = (
            payload.get("start_line") or issue.start_line or issue.location.line
        )
        end_line = payload.get("end_line") or issue.end_line or start_line
        try:
            start_line = int(start_line) if start_line is not None else None
            end_line = int(end_line) if end_line is not None else start_line
        except Exception:
            return False, "Invalid line range in payload", {}

        if not start_line or start_line < 1:
            return False, "Invalid start_line in payload", {}
        if not end_line or end_line < start_line:
            return False, "Invalid end_line in payload", {}

        if issue.start_line and issue.end_line:
            if start_line != issue.start_line or end_line != issue.end_line:
                return (
                    False,
                    "Replacement must match the target line range from the report",
                    {},
                )

        if issue.line_text:
            target_text = issue.line_text.strip()
            replacement_lines = [
                line for line in replacement.splitlines() if line.strip()
            ]
            if start_line == end_line and len(replacement_lines) > 5:
                return False, "Replacement too large for a single-line target", {}
            if target_text and not target_text.startswith(("def ", "class ")):
                if any(
                    line.lstrip().startswith(("def ", "class "))
                    for line in replacement_lines
                ):
                    return (
                        False,
                        "Replacement introduces a new definition outside target scope",
                        {},
                    )

        if diff_text:
            changed_lines = parse_changed_lines(diff_text).get(
                issue.location.file, set()
            )
            if changed_lines and not _range_overlaps(
                start_line, end_line, changed_lines
            ):
                return False, "Replacement does not overlap changed diff lines", {}

        return (
            True,
            "",
            {
                "format": "replace",
                "replacement": replacement,
                "start_line": start_line,
                "end_line": end_line,
            },
        )

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

        for attempt in range(LLM_MAX_RETRIES):
            try:
                self.rate_limiter.wait()
                if self.provider == "gemini":
                    content = self.client.generate(prompt)
                    return prompt, content
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=32768,  # 32K for GLM-4.7 reasoning mode
                    timeout=OPENAI_TIMEOUT,
                )
                if response.choices and response.choices[0].message:
                    content = response.choices[0].message.content or ""
                    return prompt, content
                return prompt, ""
            except Exception as e:
                message = str(e)
                if attempt < LLM_MAX_RETRIES - 1 and should_retry(message):
                    backoff_sleep(attempt)
                    continue
                print(f"Error generating fix: {e}")
                return prompt, ""

    def _format_fix_context(self, fix_context: FixContext) -> str:
        blocks = []
        if fix_context.file_context:
            blocks.append(f"FILE_CONTEXT:\n{fix_context.file_context}")
        if fix_context.diff_context:
            blocks.append(f"DIFF_CONTEXT:\n{fix_context.diff_context}")
        if fix_context.related_files:
            related = "\n".join(f"- {path}" for path in fix_context.related_files)
            blocks.append(f"RELATED_FILES:\n{related}")
        if fix_context.code_rag_results:
            blocks.append(
                self._format_rag_section("CODE_RAG", fix_context.code_rag_results)
            )
        if fix_context.docs_rag_results:
            blocks.append(
                self._format_rag_section("DOCS_RAG", fix_context.docs_rag_results)
            )
        return "\n\n".join(blocks)

    @staticmethod
    def _format_rag_section(label: str, items: List[dict]) -> str:
        lines = [f"{label}:"]
        for item in items:
            meta = item.get("metadata", {}) or {}
            header = meta.get("title") or meta.get("file_path", "context")
            start = meta.get("start_line")
            end = meta.get("end_line")
            if start is not None and end is not None:
                header = f"{header}:{start}-{end}"
            lines.append(f"{header}\n{item.get('content', '')}")
        return "\n".join(lines)

    @staticmethod
    def _issue_key(issue: BugIssue) -> str:
        return f"{issue.location.file}:{issue.location.line}:{issue.type}"

    @staticmethod
    def _extract_verification_method(output: str) -> str:
        for line in output.splitlines():
            if line.startswith("Verification Method:"):
                return line.split(":", 1)[1].strip() or "unknown"
        return "unknown"

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
                query = (
                    f"{issue.description}\n{issue.evidence}\n{last_error or ''}".strip()
                )
                related = self.retriever.search(query, n_results=3)
                for item in related:
                    meta = item.get("metadata", {})
                    header = f"{meta.get('file_path', 'unknown')}:{meta.get('start_line', '?')}-{meta.get('end_line', '?')}"
                    blocks.append(f"{header}\n{item.get('content', '')}")
            except Exception:
                pass

        should_read_docs = (
            "best practice" in issue.description.lower()
            or "security" in issue.type.lower()
        )
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
        return FixLoopRunner(self).run(issue, diff_text=diff_text)


if __name__ == "__main__":
    print("ReActAgent module loaded.")
