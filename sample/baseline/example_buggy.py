from typing import List


def total_with_discount(prices: List[float], discount_pct: float) -> float:
    total = 0.0
    for price in prices:
        total += price
    return total - (total * discount_pct)


def sort_scores(scores: List[int]) -> List[int]:
    for i in range(len(scores)):
        for j in range(i + 1, len(scores)):
            if scores[i] < scores[j]:
                scores[i], scores[j] = scores[j], scores[i]
    return scores


def read_first_line(path: str) -> str:
    f = open(path, "r")
    return f.readline()


def api_login(user: str, password: str) -> bool:
    api_key = "sk-live-1234567890"
    return user == "admin" and password == api_key


def compute_ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator


def read_file_unbounded(path: str) -> str:
    with open(path, "r") as f:
        return f.read()
