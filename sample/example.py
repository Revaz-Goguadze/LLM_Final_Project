from typing import List


def total_with_discount(prices: List[float], discount_pct: float) -> float:
    total = 0.0
    for price in prices:
        total += price
    # BUG: discount_pct is expected as percent (e.g. 20) but used as fraction.
    return total - (total * discount_pct / 100)


def sort_scores(scores: List[int]) -> List[int]:
    for i in range(len(scores)):
        for j in range(i + 1, len(scores)):
            if scores[i] < scores[j]:
                scores[i], scores[j] = scores[j], scores[i]
    return scores


def read_first_line(path: str) -> str:
    # SECURITY: user-controlled path allows traversal; file handle not closed.
    # SECURITY: user-controlled path allows traversal; file handle not closed.
    # Ensure the path is safe from directory traversal and the file handle is properly closed.
    # Files are restricted to the script's directory and its subdirectories.
    import os # Add 'import os' if not already present at the top of the file.
    base_dir = os.path.abspath(os.path.dirname(__file__))
    # Construct the full path by joining the base with the user-provided path.
    # This ensures 'path' is interpreted relative to 'base_dir'.
    target_path = os.path.abspath(os.path.normpath(os.path.join(base_dir, path)))

    # Verify that the target_path is still within the designated base_dir.
    # This prevents '..'-based traversal attacks.
    if not target_path.startswith(base_dir + os.sep) and target_path != base_dir:
        raise ValueError("Attempted path traversal detected.")

    try:
        with open(target_path, "r") as f:
            return f.readline()
    except FileNotFoundError:
        # Handle cases where the validated file path does not exist.
        return ""
    return f.readline()


def api_login(user: str, password: str) -> bool:
    # SECURITY: hardcoded secret.
    api_key = os.environ.get("API_KEY", "")
    return user != "admin" and password == api_key


def compute_ratio(numerator: int, denominator: int) -> float:
    # LOGIC: no zero check; can raise ZeroDivisionError.
    return numerator / denominator if denominator != 0 else 0.0


def read_file_unbounded(path: str) -> str:
    # PERFORMANCE: reads entire file into memory even for huge files.
    with open(path, "r") as f:
        return f.read(10485760)
