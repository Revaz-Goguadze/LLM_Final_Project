import re
from typing import List, Dict, Any


def extract_diff_file_paths(diff_text: str) -> List[str]:
    paths = []
    for line in diff_text.splitlines():
        if line.startswith("+++ b/"):
            paths.append(line.replace("+++ b/", "").strip())
        elif line.startswith("--- a/"):
            paths.append(line.replace("--- a/", "").strip())
    unique = []
    seen = set()
    for p in paths:
        if p and p not in seen:
            seen.add(p)
            unique.append(p)
    return unique


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3] + "..."


def truncate_text(text: str, max_chars: int = 1200) -> str:
    return _truncate(text, max_chars)


def build_rag_query(user_query: str | None, diff_text: str, max_diff_chars: int = 2000) -> str:
    diff_lines = []
    for line in diff_text.splitlines():
        if line.startswith("+++") or line.startswith("---") or line.startswith("@@"):
            continue
        if line.startswith("+") or line.startswith("-"):
            diff_lines.append(line)
    diff_snippet = _truncate("\n".join(diff_lines), max_diff_chars)
    file_paths = extract_diff_file_paths(diff_text)
    parts = []
    if user_query:
        parts.append(user_query.strip())
    if file_paths:
        parts.append("Files: " + ", ".join(file_paths))
    if diff_snippet:
        parts.append("Diff snippet:\n" + diff_snippet)
    return "\n\n".join(parts).strip()


def build_context_block(results: List[Dict[str, Any]], max_chars: int = 5000) -> str:
    blocks = []
    for item in results:
        meta = item.get("metadata", {})
        header = f"{meta.get('file_path', 'unknown')}:{meta.get('start_line', '?')}-{meta.get('end_line', '?')} ({meta.get('name', 'chunk')})"
        content = item.get("content", "")
        blocks.append(f"### {header}\n{content}")
    context = "\n\n".join(blocks)
    return _truncate(context, max_chars)


def build_analysis_input(user_query: str | None, diff_text: str, rag_context: str | None) -> str:
    parts = []
    if user_query:
        parts.append(f"User query:\n{user_query.strip()}")
    if rag_context:
        parts.append(f"Relevant code context:\n{rag_context}")
    parts.append(f"Git diff:\n{diff_text}")
    return "\n\n".join(parts)
