from dataclasses import dataclass, field
from datetime import datetime
import json
import os
from typing import Dict, Any, List


@dataclass
class FixAttempt:
    """Record a single fix attempt."""
    timestamp: str
    issue_id: str
    mode: str
    success: bool
    attempts: int
    verification_method: str
    error_message: str = ""


@dataclass
class FixStats:
    """Aggregate fix statistics."""
    total_attempts: int = 0
    successful_fixes: int = 0
    failed_fixes: int = 0
    avg_attempts_per_fix: float = 0.0
    per_mode_stats: Dict[str, Dict[str, Any]] = field(default_factory=dict)


class FixTracker:
    """Track fix success rates across evaluation runs."""

    def __init__(self, storage_path: str = "evaluation/fix_history.json"):
        self.storage_path = storage_path
        self.history: List[FixAttempt] = []
        self._load_history()

    def _load_history(self):
        """Load existing fix history."""
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, "r") as f:
                    data = json.load(f)
                    self.history = [FixAttempt(**item) for item in data]
            except (json.JSONDecodeError, TypeError, KeyError):
                self.history = []

    def _save_history(self):
        """Persist fix history."""
        os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
        data = [item.__dict__ for item in self.history]
        with open(self.storage_path, "w") as f:
            json.dump(data, f, indent=2)

    def record_attempt(
        self,
        issue_id: str,
        mode: str,
        success: bool,
        attempts: int,
        verification_method: str,
        error_message: str = "",
    ):
        """Record a fix attempt."""
        attempt = FixAttempt(
            timestamp=datetime.now().isoformat(),
            issue_id=issue_id,
            mode=mode,
            success=success,
            attempts=attempts,
            verification_method=verification_method,
            error_message=error_message,
        )
        self.history.append(attempt)
        self._save_history()

    def get_stats(self) -> FixStats:
        """Calculate aggregate statistics."""
        if not self.history:
            return FixStats()

        stats = FixStats()
        stats.total_attempts = len(self.history)
        stats.successful_fixes = sum(1 for a in self.history if a.success)
        stats.failed_fixes = stats.total_attempts - stats.successful_fixes

        total_attempts = sum(a.attempts for a in self.history)
        stats.avg_attempts_per_fix = total_attempts / len(self.history) if self.history else 0

        # Per-mode breakdown
        modes = set(a.mode for a in self.history)
        for mode in modes:
            mode_attempts = [a for a in self.history if a.mode == mode]
            mode_success = sum(1 for a in mode_attempts if a.success)
            mode_total = sum(a.attempts for a in mode_attempts)

            stats.per_mode_stats[mode] = {
                "total_fixes": len(mode_attempts),
                "successful": mode_success,
                "success_rate": mode_success / len(mode_attempts) if mode_attempts else 0,
                "avg_attempts": mode_total / len(mode_attempts) if mode_attempts else 0,
            }

        return stats

    def clear_history(self):
        """Clear all fix history."""
        self.history.clear()
        self._save_history()
