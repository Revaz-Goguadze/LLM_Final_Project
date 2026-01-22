from __future__ import annotations

import re
from typing import Dict, List, Set


def parse_unified_diff_files(diff_text: str) -> List[str]:
    """Parse unified diff to extract affected file paths.

    Handles both:
    - diff --git a/path b/path format (git diffs)
    - +++ b/path format (unified diffs without git headers)
    """
    files: List[str] = []
    seen = set()

    for line in diff_text.splitlines():
        # Try diff --git format first
        if line.startswith("diff --git "):
            parts = line.split()
            if len(parts) >= 4:
                b_path = parts[3]
                if b_path.startswith("b/"):
                    b_path = b_path[2:]
                if b_path and b_path not in seen:
                    seen.add(b_path)
                    files.append(b_path)
        # Also handle +++ b/path format (for diffs without git headers)
        elif line.startswith("+++ b/"):
            b_path = line[6:].strip()
            if b_path and b_path not in seen:
                seen.add(b_path)
                files.append(b_path)
        # Also handle --- a/path format as fallback
        elif line.startswith("--- a/"):
            a_path = line[6:].strip()
            # Convert to b path equivalent
            if a_path and a_path != "/dev/null":
                if a_path not in seen:
                    seen.add(a_path)
                    files.append(a_path)

    return files


def parse_changed_lines(diff_text: str) -> Dict[str, Set[int]]:
    changed: Dict[str, Set[int]] = {}
    current_file = None
    current_line = None
    for line in diff_text.splitlines():
        if line.startswith("+++ b/"):
            current_file = line[6:].strip()
            continue
        if line.startswith("@@"):
            match = re.search(r"\+(\d+)(?:,(\d+))?", line)
            if match:
                current_line = int(match.group(1))
            else:
                current_line = None
            continue
        if not current_file or current_line is None:
            continue
        if line.startswith("+") and not line.startswith("+++"):
            changed.setdefault(current_file, set()).add(current_line)
            current_line += 1
        elif line.startswith("-") and not line.startswith("---"):
            continue
        else:
            current_line += 1
    return changed
