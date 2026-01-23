import os
from git import Repo
from .models import GitDiff
from .config import DEMO_EXCLUDE_PREFIXES

class GitAnalyzer:
    def __init__(self, repo_path: str = "."):
        self.repo_path = os.path.abspath(repo_path)
        try:
            self.repo = Repo(self.repo_path)
        except Exception as e:
            # If not a repo, initialize one for testing or raise
            raise Exception(f"Path {repo_path} is not a valid git repository: {e}")
        self._ignore_prefixes = (
            ".bm25/",
            ".vector_store/",
            ".chroma/",
            "__pycache__/",
            "bug_report",
            ".env",
            ".pytest_cache/",
        )
        if DEMO_EXCLUDE_PREFIXES:
            self._ignore_prefixes = self._ignore_prefixes + tuple(DEMO_EXCLUDE_PREFIXES)

    def get_diffs(self) -> GitDiff:
        """Extracts staged, unstaged and last commit diffs."""
        excludes = [
            "--",
            ".",
            ":(exclude,glob).bm25/**",
            ":(exclude,glob).vector_store/**",
            ":(exclude,glob).chroma/**",
            ":(exclude,glob)**/__pycache__/**",
            ":(exclude,glob)bug_report*",
            ":(exclude,glob).env",
            ":(exclude,glob).pytest_cache/**",
        ]
        # Staged changes (index)
        staged_diff = self.repo.git.diff("--cached", *excludes)
        
        # Unstaged changes (working tree)
        unstaged_diff = self.repo.git.diff(*excludes)
        
        # Last commit vs previous (HEAD vs HEAD~1)
        try:
            last_commit_diff = self.repo.git.diff("HEAD~1", "HEAD", *excludes)
        except Exception:
            last_commit_diff = ""  # Initial commit?
            
        # Changed files (union of all)
        changed_files = list(set(
            [item.a_path for item in self.repo.index.diff(None)] +
            [item.a_path for item in self.repo.index.diff("HEAD")] +
            (self._get_files_from_diff(last_commit_diff) if last_commit_diff else [])
        ))
        changed_files = [path for path in changed_files if not self._is_ignored(path)]
        
        return GitDiff(
            staged=staged_diff,
            unstaged=unstaged_diff,
            last_commit=last_commit_diff,
            changed_files=changed_files
        )

    def get_diff_against(self, base_ref: str) -> str:
        excludes = [
            "--",
            ".",
            ":(exclude,glob).bm25/**",
            ":(exclude,glob).vector_store/**",
            ":(exclude,glob).chroma/**",
            ":(exclude,glob)**/__pycache__/**",
            ":(exclude,glob)bug_report*",
            ":(exclude,glob).env",
            ":(exclude,glob).pytest_cache/**",
        ]
        try:
            return self.repo.git.diff(base_ref, "HEAD", *excludes)
        except Exception:
            return ""

    def _get_files_from_diff(self, diff_text: str) -> list:
        files = []
        for line in diff_text.split('\n'):
            if line.startswith('--- a/') or line.startswith('+++ b/'):
                files.append(line[6:].strip())
        return list(set(files))

    def _is_ignored(self, path: str) -> bool:
        return any(path.startswith(prefix) for prefix in self._ignore_prefixes)

if __name__ == "__main__":
    analyzer = GitAnalyzer()
    diffs = analyzer.get_diffs()
    print(f"Files changed: {diffs.changed_files}")
    print(f"Staged diff length: {len(diffs.staged)}")
