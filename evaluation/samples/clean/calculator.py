from typing import List, Optional
from decimal import Decimal, InvalidOperation


def safe_divide(numerator: float, denominator: float) -> Optional[float]:
    if denominator == 0:
        return None
    return numerator / denominator


def calculate_average(numbers: List[float]) -> Optional[float]:
    if not numbers:
        return None
    return sum(numbers) / len(numbers)


def parse_currency(value: str) -> Optional[Decimal]:
    try:
        cleaned = value.replace("$", "").replace(",", "").strip()
        return Decimal(cleaned)
    except (InvalidOperation, AttributeError):
        return None
