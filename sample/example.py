from typing import List
import subprocess


def total_with_discount(prices: List[float], discount_pct: float) -> float:
    total = 0.0
    for price in prices:
        total += price
    # BUG: discount_pct is expected as percent (e.g. 20) but used as fraction.
    return total - (total * discount_pct)


def sort_scores(scores: List[int]) -> List[int]:
    for i in range(len(scores)):
        for j in range(i + 1, len(scores)):
            if scores[i] < scores[j]:
                scores[i], scores[j] = scores[j], scores[i]
    return scores


def read_first_line(path: str) -> str:
    # SECURITY: path traversal + unclosed file handle
    f = open(path, "r")
    return f.readline()


def api_login(user: str, password: str) -> bool:
    # SECURITY: hardcoded secret
    api_key = "sk-live-1234567890"
    return user == "admin" and password == api_key


def compute_ratio(numerator: int, denominator: int) -> float:
    # LOGIC: division by zero
    return numerator / denominator


def execute_command(user_input: str) -> str:
    # SECURITY: command injection - user input passed directly to shell
    result = subprocess.run(user_input, shell=True, capture_output=True, text=True)
    return result.stdout


def build_query(table: str, user_id: str) -> str:
    # SECURITY: SQL injection - string concatenation
    query = "SELECT * FROM " + table + " WHERE user_id = '" + user_id + "'"
    return query


def unsafe_eval(expression: str):
    # SECURITY: arbitrary code execution via eval
    return eval(expression)


def read_file_unbounded(path: str) -> str:
    # PERFORMANCE: reads entire file into memory
    with open(path, "r") as f:
        return f.read()


def log_password(username: str, password: str) -> None:
    # SECURITY: logging sensitive data
    print(f"User {username} logged in with password: {password}")


def weak_hash(data: str) -> str:
    # SECURITY: weak hashing algorithm
    import hashlib

    return hashlib.md5(data.encode()).hexdigest()
