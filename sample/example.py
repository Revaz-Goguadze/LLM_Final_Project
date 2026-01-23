from pathlib import Path
from typing import List
import os


def total_with_discount(prices: List[float], discount_pct: float) -> float:
    """Return total after applying a percent discount (20.0 == 20%)."""
    total = sum(prices)
    return total - (total * (discount_pct / 100.0))


def sort_scores(scores: List[int]) -> List[int]:
    """Sort scores descending in place and return the list."""
    scores.sort(reverse=True)
    return scores


def read_first_line(path: str) -> str:
    """Read the first line from a file under the sample directory."""
    base_dir = Path(__file__).resolve().parent
    target = Path(path)
    if not target.is_absolute():
        target = base_dir / target
    resolved = target.resolve()
    if base_dir not in resolved.parents and resolved != base_dir:
        raise PermissionError("Access denied: Attempted to access file outside sample directory.")
    with open(resolved, "r", encoding="utf-8") as f:
        return f.readline()


def api_login(user: str, password: str) -> bool:
    import hmac

    secret = os.environ.get("API_KEY")
    admin_user = os.environ.get("ADMIN_USER")
    if not secret or not admin_user:
        return False
    if user != admin_user:
        return False
    return hmac.compare_digest(password, secret)


def compute_ratio(numerator: int, denominator: int) -> float:
    if denominator == 0:
        raise ValueError("Denominator cannot be zero.")
    return numerator / denominator


def read_file_unbounded(path: str) -> str:
    base_dir = Path(__file__).resolve().parent
    resolved = (base_dir / path).resolve()
    if base_dir not in resolved.parents and resolved != base_dir:
        raise ValueError("Attempted path traversal detected.")
    max_bytes = 10 * 1024 * 1024
    chunks = []
    read_bytes = 0
    with open(resolved, "r", encoding="utf-8") as f:
        while True:
            data = f.read(1024 * 64)
            if not data:
                break
            read_bytes += len(data.encode("utf-8"))
            if read_bytes > max_bytes:
                break
            chunks.append(data)
    return "".join(chunks)
