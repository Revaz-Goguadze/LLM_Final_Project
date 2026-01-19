def get_full_name(first_name: str, last_name: str) -> str:
    """Returns a formatted full name."""
    if not first_name or not last_name:
        return ""
    return f"{first_name} {last_name}".strip()

def filter_positive_numbers(numbers: list[int]) -> list[int]:
    """Filters only positive integers from a list."""
    return [n for n in numbers if n > 0]
