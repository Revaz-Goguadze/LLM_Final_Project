import os
from typing import Optional


def normalize_repo_path(path: str, repo_root: Optional[str] = None) -> str:
    if not path:
        return ""
    repo_root = repo_root or os.getcwd()
    abs_path = os.path.abspath(path)
    rel_path = os.path.relpath(abs_path, repo_root)
    rel_path = rel_path.replace("\\", "/")
    if rel_path.startswith("./"):
        rel_path = rel_path[2:]
    return rel_path


def resolve_repo_path(path: str, repo_root: Optional[str] = None) -> str:
    if not path:
        return ""
    repo_root = repo_root or os.getcwd()
    if os.path.isabs(path):
        return os.path.abspath(path)
    return os.path.abspath(os.path.join(repo_root, path))
