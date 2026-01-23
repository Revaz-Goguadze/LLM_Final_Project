import os
import ast
from typing import Optional, List, Dict, Any

from .models import BugIssue, FixContext
from .path_utils import resolve_repo_path
from .retriever import HybridRetriever


class FixContextBuilder:
    """
    Builds comprehensive context for fix generation using dual-RAG.
    Always builds full context proactively, not reactively.
    """

    def __init__(
        self,
        code_retriever: HybridRetriever,
        docs_retriever: HybridRetriever,
        base_context_radius: int = 15,
    ):
        self.code_retriever = code_retriever
        self.docs_retriever = docs_retriever
        self.base_context_radius = base_context_radius
        self._context_cache: Dict[str, FixContext] = {}

    def build_context(
        self,
        issue: BugIssue,
        diff_text: Optional[str] = None,
        attempt: int = 1,
        previous_error: Optional[str] = None,
        context_multiplier: float = 1.0,
        context_cache: Optional[dict] = None,
    ) -> FixContext:
        """
        Build comprehensive fix context using dual-RAG and file analysis.
        Context expands with each attempt.
        """
        # Expand context radius on retries
        context_radius = int(
            self.base_context_radius * context_multiplier * (1.5 ** (attempt - 1))
        )

        # 1. Read file context (expanded on retries)
        file_context = self._read_file_context(
            issue.location.file, issue.location.line or 1, context_radius
        )

        # 2. Always search code RAG unless cached
        code_rag = []
        if context_cache and context_cache.get("code_context"):
            code_rag = [
                {
                    "content": context_cache.get("code_context", ""),
                    "metadata": {"title": "cached_code_context"},
                }
            ]
        else:
            code_rag = self._search_code_rag(issue, attempt, previous_error)

        # 3. Search docs RAG if security or best practice issue
        docs_rag = []
        if self._should_read_docs(issue):
            if context_cache and context_cache.get("docs_context"):
                docs_rag = [
                    {
                        "content": context_cache.get("docs_context", ""),
                        "metadata": {"title": "cached_docs_context"},
                    }
                ]
            else:
                docs_rag = self._search_docs_rag(issue)

        # 4. Add diff context if available
        diff_context = self._extract_diff_context(diff_text, issue.location.file)

        # 5. Find related files (imports, dependencies)
        related_files = self._find_related_files(issue.location.file)

        return FixContext(
            file_context=file_context,
            code_rag_results=code_rag,
            docs_rag_results=docs_rag,
            diff_context=diff_context,
            related_files=related_files,
            attempt=attempt,
            previous_error=previous_error,
        )

    def _read_file_context(
        self, file_path: str, line: int, context_radius: int
    ) -> str:
        """Read file context with line numbers."""
        abs_path = resolve_repo_path(file_path)
        if not os.path.exists(abs_path):
            return ""

        try:
            with open(abs_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except (OSError, UnicodeDecodeError):
            return ""

        start = max(0, line - context_radius - 1)
        end = min(len(lines), line + context_radius)
        numbered = [
            f"{i + 1}: {l.rstrip()}"
            for i, l in enumerate(lines[start:end], start=start)
        ]
        return "\n".join(numbered)

    def _search_code_rag(
        self, issue: BugIssue, attempt: int, previous_error: Optional[str]
    ) -> List[Dict[str, Any]]:
        """Search code RAG with query built from issue."""
        query_parts = [issue.description, issue.evidence]
        if previous_error:
            query_parts.append(f"Previous error: {previous_error}")

        query = "\n".join(query_parts)
        n_results = min(3 + attempt, 8)  # More results on later attempts

        try:
            return self.code_retriever.search(query, n_results=n_results)
        except (OSError, ValueError, RuntimeError):
            return []

    def _should_read_docs(self, issue: BugIssue) -> bool:
        """Determine if docs RAG should be searched."""
        return (
            "security" in issue.type.lower()
            or "best practice" in issue.description.lower()
            or "authentication" in issue.description.lower()
            or "authorization" in issue.description.lower()
        )

    def _search_docs_rag(self, issue: BugIssue) -> List[Dict[str, Any]]:
        """Search documentation RAG."""
        query = f"{issue.description}\n{issue.evidence}"
        try:
            return self.docs_retriever.search(query, n_results=3)
        except (OSError, ValueError, RuntimeError):
            return []

    def _extract_diff_context(
        self, diff_text: Optional[str], file_path: str
    ) -> Optional[str]:
        """Extract relevant diff context for the file."""
        if not diff_text:
            return None

        lines = diff_text.split("\n")
        relevant_lines = []
        in_target_file = False

        for line in lines:
            if line.startswith(f"--- a/{file_path}") or line.startswith(
                f"+++ b/{file_path}"
            ):
                in_target_file = True
                relevant_lines.append(line)
            elif in_target_file:
                if line.startswith("@@") or line.startswith("+") or line.startswith("-"):
                    relevant_lines.append(line)
                elif line.startswith("diff ") or line.startswith("index "):
                    break

        return "\n".join(relevant_lines) if relevant_lines else None

    def _find_related_files(self, file_path: str) -> List[str]:
        """Find related files based on imports."""
        abs_path = resolve_repo_path(file_path)
        if not os.path.exists(abs_path):
            return []

        try:
            with open(abs_path, "r", encoding="utf-8") as f:
                source = f.read()
        except (OSError, UnicodeDecodeError):
            return []

        related = []
        try:
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        related.append(alias.name.split(".")[0] + ".py")
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        related.append(node.module.split(".")[0] + ".py")
        except (SyntaxError, ValueError):
            pass

        # Filter to existing files
        base_dir = os.path.dirname(abs_path)
        return [
            f
            for f in related
            if os.path.exists(os.path.join(base_dir, f))
            or os.path.exists(f)
        ]
