import os
from git import Repo
from .models import GitDiff

class GitAnalyzer:
    def __init__(self, repo_path: str = "."):
        self.repo_path = os.path.abspath(repo_path)
        try:
            self.repo = Repo(self.repo_path)
        except Exception as e:
            # If not a repo, initialize one for testing or raise
            raise Exception(f"Path {repo_path} is not a valid git repository: {e}")

    def get_diffs(self) -> GitDiff:
        """Extracts staged, unstaged and last commit diffs."""
        # Staged changes (index)
        staged_diff = self.repo.git.diff("--cached")
        
        # Unstaged changes (working tree)
        unstaged_diff = self.repo.git.diff()
        
        # Last commit vs previous (HEAD vs HEAD~1)
        try:
            last_commit_diff = self.repo.git.diff("HEAD~1", "HEAD")
        except Exception:
            last_commit_diff = ""  # Initial commit?
            
        # Changed files (union of all)
        changed_files = list(set(
            [item.a_path for item in self.repo.index.diff(None)] +
            [item.a_path for item in self.repo.index.diff("HEAD")] +
            (self._get_files_from_diff(last_commit_diff) if last_commit_diff else [])
        ))
        
        return GitDiff(
            staged=staged_diff,
            unstaged=unstaged_diff,
            last_commit=last_commit_diff,
            changed_files=changed_files
        )

    def _get_files_from_diff(self, diff_text: str) -> list:
        files = []
        for line in diff_text.split('\n'):
            if line.startswith('--- a/') or line.startswith('+++ b/'):
                files.append(line[6:].strip())
        return list(set(files))

if __name__ == "__main__":
    analyzer = GitAnalyzer()
    diffs = analyzer.get_diffs()
    print(f"Files changed: {diffs.changed_files}")
    print(f"Staged diff length: {len(diffs.staged)}")
